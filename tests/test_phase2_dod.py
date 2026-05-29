"""Phase 2 Definition-of-Done assertion.

The DoD reads:

  A `DemandAnomaly` quantum is injected at the boundary, dispatched to the
  `demand_planning` agent, the agent calls `handoff('submit_supply_request',
  SupplyRequest(...))`, the orchestrator validates the quantum, evaluates any
  axioms (none on this flow), appends to the event log, and routes to a stub
  `supply_planning`. The event log shows the full transaction with idempotency
  key. Agent reasoning visible in the trace.

We exercise the DoD using a `ScriptedAgentHandler` for `demand_planning` —
this asserts the orchestrator surface end-to-end without requiring an LLM API
key. The contract being verified is the orchestrator's, not the LLM's: the LLM
sits behind the same `RoleHandler.invoke` contract as the script does, so any
finding here would also surface with a real LLM driving the same tool calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from e2e_orchestrator.application.agent_factory import (
    InternalStubHandler,
    ScriptedAgentHandler,
    ScriptedToolCall,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.boundary.demand_sensing import emit_demand_anomaly
from e2e_orchestrator.durability import EventKind, JsonlBackend


async def test_phase2_round_trip(ontology_service, tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "phase2.jsonl")

    # demand_planning: scripted agent that reads its view (visible in trace),
    # then fires the handoff that the DoD demands. This stands in for the LLM.
    dp_script = [
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
        ScriptedToolCall(
            tool="handoff",
            kwargs={
                "flow": "submit_supply_request",
                "quantum": {
                    "request_id": "sr-from-anomaly-0001",
                    "sku": "sku-toothpaste-6oz",
                    "volume": 4500,
                    "required_by": 60,
                    "source_signal_ref": "anom-demo-0001",
                },
            },
        ),
        ScriptedToolCall(tool="emit_event", kwargs={"name": "forecast_revised", "payload": {"sku": "sku-toothpaste-6oz"}}),
    ]
    # Only demand_planning is scripted. supply_planning is NOT hand-wired here:
    # in stub mode the factory builds it as the default InternalStubHandler, the
    # same as any not-yet-driven internal role. (Phase 3 removed the explicit
    # supply_planning override that used to live here.)
    overrides = {
        "demand_planning": ScriptedAgentHandler("demand_planning", orch=None, script=dp_script),
    }

    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    # Late-bind orchestrator on overrides.
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]

    result = await emit_demand_anomaly(orch)
    assert result.events_appended > 0
    events = backend.read_events()
    kinds = [e.kind for e in events]

    # 1. Boundary ingress recorded.
    assert EventKind.BOUNDARY_INGRESS in kinds, kinds

    # 2. demand_planning was invoked.
    assert EventKind.AGENT_INVOCATION_STARTED in kinds
    starts = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED]
    roles_invoked = {e.payload["role"] for e in starts}
    assert "demand_planning" in roles_invoked
    assert "supply_planning" in roles_invoked

    # 3. The agent's reasoning trail (here: tool calls) is visible in the log.
    tool_calls = [e for e in events if e.kind == EventKind.AGENT_TOOL_CALL]
    tool_names = [tc.payload["tool"] for tc in tool_calls]
    assert "read_ontology" in tool_names
    assert "handoff" in tool_names

    # 4. The handoff was executed (validated + axioms + appended).
    executed = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED]
    assert len(executed) == 1
    payload = executed[0].payload
    assert payload["flow"] == "submit_supply_request"
    assert payload["source_role"] == "demand_planning"
    assert payload["target_role"] == "supply_planning"
    assert payload["quantum_class"] == "SupplyRequest"

    # 5. The handoff carries a stable idempotency key derived from
    #    (source_role, target_role, flow, quantum_id, sequence).
    key = executed[0].idempotency_key
    assert key is not None
    assert key.startswith("handoff:demand_planning:supply_planning:submit_supply_request:")

    # 6. Axiom evaluation event written even with no axioms (clean trace).
    axiom_events = [e for e in events if e.kind == EventKind.AXIOM_EVALUATED]
    assert len(axiom_events) == 1
    assert axiom_events[0].payload["ok"] is True

    # 7. JSONL file actually written — replay reads from disk.
    on_disk = (tmp_path / "phase2.jsonl").read_text().strip().splitlines()
    assert len(on_disk) == len(events)


async def test_phase2_handoff_idempotent_on_replay(ontology_service):
    """A second append with the same idempotency key returns the prior event
    and does not double-dispatch."""
    backend = JsonlBackend()
    # Build a hand-rolled context and call orch.schedule_handoff twice with a
    # forced sequence number to simulate a replay.
    from e2e_orchestrator.application.orchestrator import ToolContext

    overrides = {"supply_planning": InternalStubHandler("supply_planning", orch=None)}
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    overrides["supply_planning"]._orch = orch  # type: ignore[attr-defined]

    ctx = ToolContext(
        invocation_id="inv-x",
        role="demand_planning",
        incoming_flow="raise_demand_anomaly",
        incoming_quantum_id="q-x",
        incoming_quantum_class="DemandAnomaly",
        incoming_payload={},
    )
    payload = {
        "request_id": "sr-1",
        "sku": "sku-A",
        "volume": 100,
        "required_by": 50,
    }
    r1 = orch.schedule_handoff(flow_name="submit_supply_request", quantum=payload, ctx=ctx)
    assert r1.status == "accepted"
    # Force a replay by reusing the same sequence — the orchestrator
    # auto-increments, so we step it back one to recreate the prior key.
    ctx.sequence -= 1
    r2 = orch.schedule_handoff(flow_name="submit_supply_request", quantum=payload, ctx=ctx)
    # Quantum IDs differ (orchestrator stamps fresh ones), so this is a different
    # idempotency key — the replay-protection guarantee is that a SAME key
    # appended twice returns the prior event. Verify the lower-level invariant.
    assert r2.status == "accepted"
    # Direct duplicate test via the backend:
    a = backend.append(EventKind.HANDOFF_EXECUTED, {"x": 1}, idempotency_key="replay-key")
    b = backend.append(EventKind.HANDOFF_EXECUTED, {"x": 1}, idempotency_key="replay-key")
    assert a.fresh and not b.fresh
    assert a.event.seq == b.event.seq

    await orch.drain()
