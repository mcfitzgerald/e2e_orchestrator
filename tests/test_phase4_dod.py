"""Phase 4 Definition-of-Done assertion.

The DoD (ontology repo `plan_of_attack.md` §4):

  Blocking axiom triggers the recovery flow without LLM involvement in the
  routing. The same code path handles `respect_lead_time` and
  `line_capacity_not_exceeded`. The trace shows the deterministic evaluation
  outcome as a non-LLM event.

Scene 4, end-to-end: a Megalomart 3x promo enters; demand_planning revises and
hands a SupplyRequest to supply_planning; supply_planning assigns the full
uplift (3000 units) to NJ-L1 — a loaded line whose residual available is 5000
(50000 total − 45000 committed), of which the toothpaste SKUs already use 3500.
The blocking `line_capacity_not_exceeded` axiom fires deterministically and the
orchestrator follows `on_failure_route_to: escalate_capacity_conflict` back to
supply_planning — no LLM chooses the route, and production_planning never gets
the option to wave capacity through.

Exercised with scripted handlers (same as Phase 2/3) wired from the canonical
`SCENARIOS` registry, so the CLI path and the test can't drift; the orchestrator
can't tell a script from an LLM, so the structural guarantees hold for the live
run too."""
from __future__ import annotations

from pathlib import Path

import pytest

from e2e_orchestrator.application.agent_factory import (
    ScriptedAgentHandler,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.boundary.customer_development import emit_promo_plan_aligned
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS


def _build_orch(ontology_service, backend):
    scripts = SCENARIOS["capacity-conflict"]["scripts"]
    overrides = {
        role: ScriptedAgentHandler(role, orch=None, script=script)
        for role, script in scripts.items()
    }
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    return orch


async def test_phase4_capacity_conflict_recovery(ontology_service, tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "phase4.jsonl")
    orch = _build_orch(ontology_service, backend)

    await emit_promo_plan_aligned(orch)
    events = backend.read_events()

    # 1. The promo entered at the boundary as a TradePromotion.
    ingress = [e for e in events if e.kind == EventKind.BOUNDARY_INGRESS]
    assert len(ingress) == 1 and ingress[0].payload["quantum_class"] == "TradePromotion"

    # 2. The blocking axiom fired deterministically — a non-LLM event in the
    #    trace — on the request_production handoff, with the real conflict math.
    axiom_events = [e for e in events if e.kind == EventKind.AXIOM_EVALUATED]
    rp_axiom = [e for e in axiom_events if e.payload["flow"] == "request_production"]
    assert len(rp_axiom) == 1
    assert rp_axiom[0].payload["ok"] is False
    outcome = rp_axiom[0].payload["outcomes"][0]
    assert outcome["name"] == "line_capacity_not_exceeded"
    assert outcome["severity"] == "blocking"
    assert outcome["passed"] is False
    assert "6500" in outcome["evidence"] and "5000" in outcome["evidence"]

    # 3. The original handoff was BLOCKED — the floor is in code. request_production
    #    never executed; the agent had no option to override.
    blocked = [e for e in events if e.kind == EventKind.HANDOFF_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].payload["flow"] == "request_production"
    assert blocked[0].payload["rerouted_to"] == "escalate_capacity_conflict"

    executed = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED]
    flows_executed = [e.payload["flow"] for e in executed]
    assert "request_production" not in flows_executed   # blocked, not executed

    # 4. The recovery flow was taken automatically by the orchestrator:
    #    escalate_capacity_conflict (production_planning → supply_planning),
    #    carrying a CapacityConflict with the computed shortfall.
    recovery = [e for e in executed if e.payload["flow"] == "escalate_capacity_conflict"]
    assert len(recovery) == 1
    rp = recovery[0].payload
    assert rp["source_role"] == "production_planning"
    assert rp["target_role"] == "supply_planning"
    assert rp["quantum_class"] == "CapacityConflict"
    assert rp["recovery_for"] == "request_production"
    assert rp["payload"]["shortfall_units"] == 1500

    # 5. supply_planning was re-invoked with the recovery flow; production_planning
    #    was never invoked (the gate caught the conflict before dispatch).
    starts = [e.payload for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED]
    roles_invoked = [s["role"] for s in starts]
    assert roles_invoked == ["demand_planning", "supply_planning", "supply_planning"]
    assert "production_planning" not in roles_invoked
    incoming_flows = {s["incoming_flow"] for s in starts}
    assert "escalate_capacity_conflict" in incoming_flows

    # 6. No quantum was rejected — every quantum (incl. the auto-built recovery
    #    CapacityConflict) was schema-valid.
    assert not [e for e in events if e.kind == EventKind.QUANTUM_REJECTED]

    # 7. Stable idempotency keys on the recovery dispatch (replay-safe).
    assert recovery[0].idempotency_key is not None
    assert recovery[0].idempotency_key.startswith("recovery:")


async def test_phase4_conflict_is_deterministic(ontology_service):
    """No LLM in the routing → the recovery path is identical every run."""
    def run():
        backend = JsonlBackend()
        orch = _build_orch(ontology_service, backend)
        return backend, orch

    async def execute(orch, backend):
        await emit_promo_plan_aligned(orch)
        return [
            (e.kind, e.payload.get("flow"))
            for e in backend.read_events()
            if e.kind in (EventKind.HANDOFF_BLOCKED, EventKind.HANDOFF_EXECUTED)
        ]

    b1, o1 = run()
    b2, o2 = run()
    trace1 = await execute(o1, b1)
    trace2 = await execute(o2, b2)
    assert trace1 == trace2
    assert (EventKind.HANDOFF_BLOCKED, "request_production") in trace1
    assert (EventKind.HANDOFF_EXECUTED, "escalate_capacity_conflict") in trace1
