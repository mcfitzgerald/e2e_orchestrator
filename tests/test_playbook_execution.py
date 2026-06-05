"""Playbook execution + decision-surface tests (Phase 5).

Drives the `capacity-resolution` scenario end-to-end with scripted handlers and
asserts the wiring: the `resolve_capacity_conflict` Playbook surfaces at
supply_planning's `escalate_capacity_conflict` re-entry, the three declared
context-assembly query flows fan out and return typed responses (wait_all join),
the decision is surfaced and validated, exactly one resolution flow is fired, and
the playbook's always_fires effects (capacity_resolved + plan_fulfillment) follow.

Also pins the deterministic floors `call_tool` and `surface_decision` add: a
reader-tool call grounds on a real entity, and a `surface_decision` citing a
playbook not anchored to the role is rejected as `unknown_playbook`.
"""
from __future__ import annotations

from pathlib import Path

from e2e_orchestrator.application.agent_factory import (
    ScriptedAgentHandler,
    ScriptedToolCall,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator, ToolContext
from e2e_orchestrator.application.tools import make_toolkit
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS

_SEED = SCENARIOS["capacity-resolution"]["seeder"]

CONTEXT_QUERIES = {"check_otif_exposure", "check_promo_flexibility", "check_coman_availability"}
RESOLUTION_FLOWS = {"shift_to_coman", "re_request_production", "request_promo_revision",
                    "allocate_partial_fill"}


def _build_orch(ontology_service, backend) -> Orchestrator:
    spec = SCENARIOS["capacity-resolution"]
    scripts = {**spec.get("responders", {}), **spec["scripts"]}
    overrides = {
        role: ScriptedAgentHandler(role, orch=None, script=script)
        for role, script in scripts.items()
    }
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    return orch


async def test_playbook_context_assembly_and_resolution(ontology_service, tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "capres.jsonl")
    orch = _build_orch(ontology_service, backend)
    await _SEED(orch)
    events = backend.read_events()

    # 1. The conflict re-entered supply_planning via escalate_capacity_conflict.
    starts = [e.payload for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED]
    assert "escalate_capacity_conflict" in {s["incoming_flow"] for s in starts}

    # 2. All THREE declared context-assembly query flows fired (deterministic
    #    context assembly), each returning its typed response (wait_all join).
    queries = [e.payload for e in events if e.kind == EventKind.QUERY_REQUESTED]
    assert {q["flow"] for q in queries} == CONTEXT_QUERIES
    answered = [e.payload for e in events if e.kind == EventKind.QUERY_ANSWERED]
    response_classes = {a["response_class"] for a in answered}
    assert response_classes == {"OTIFExposure", "PromoFlexibility", "ComanAvailability"}

    # 3. The decision was surfaced against the real, anchored playbook.
    surfaced = [e.payload for e in events if e.kind == EventKind.DECISION_SURFACED]
    assert len(surfaced) == 1
    assert surfaced[0]["playbook"] == "resolve_capacity_conflict"
    assert surfaced[0]["validated"] is True

    # 4. Exactly ONE resolution flow fired (the agency moment), and the
    #    playbook's always_fires effects followed it.
    executed = [e.payload["flow"] for e in events if e.kind == EventKind.HANDOFF_EXECUTED]
    chosen = [f for f in executed if f in RESOLUTION_FLOWS]
    assert len(chosen) == 1
    assert "capacity_resolved" in {
        e.payload["name"] for e in events if e.kind == EventKind.EVENT_EMITTED
    }
    assert "plan_fulfillment" in executed


async def test_reader_tool_grounds_before_decision(ontology_service):
    """The grounded happy path: a call_tool read returns a real line, in the
    trace, before the resolution — the hallucinated-grounding fix."""
    backend = JsonlBackend()
    orch = _build_orch(ontology_service, backend)
    await _SEED(orch)
    tool_calls = [
        e.payload for e in backend.read_events() if e.kind == EventKind.AGENT_TOOL_CALL
    ]
    plant_reads = [
        c for c in tool_calls
        if c["tool"] == "call_tool" and c["args"].get("name") == "query_plants_for_sku"
    ]
    assert plant_reads, "supply_planning never grounded via query_plants_for_sku"
    result = plant_reads[0]["result"]
    assert result["status"] == "ok"
    codes = [l["line_code"] for l in result["output"]["lines"]]
    assert "NJ-L1" in codes  # a real world-state line, not invented


async def test_surface_decision_rejects_unknown_playbook(ontology_service):
    """A playbook not anchored to the acting role is rejected deterministically —
    a §2-safe floor (rejects non-existent names; ranks nothing)."""
    backend = JsonlBackend()
    orch = _build_orch(ontology_service, backend)
    ctx = ToolContext(
        invocation_id="inv-x", role="supply_planning", incoming_flow="escalate_capacity_conflict",
        incoming_quantum_id="q", incoming_quantum_class="CapacityConflict", incoming_payload={},
    )
    tk = make_toolkit(orch, ctx)

    bad = tk.surface_decision(playbook="totally_made_up", options=["shift_to_coman"])
    assert bad["status"] == "unknown_playbook"
    assert "resolve_capacity_conflict" in bad["anchored_playbooks"]

    # A real playbook passes the ref floor — it is NOT rejected as unknown. (No
    # queries were fired in this bare invocation, so it then meets the wait_all
    # gate; the two floors compose, ref-check first.)
    good = tk.surface_decision(playbook="resolve_capacity_conflict", options=["shift_to_coman"])
    assert good["status"] != "unknown_playbook"
    assert good["status"] == "wait_all_unsatisfied"


# ---------------------------------------------------------------------------
# wait_all synchronization gate (Phase 5 follow-up)
# ---------------------------------------------------------------------------

_ALL_OPTIONS = ["shift_to_coman", "re_request_production", "request_promo_revision"]


def _build_orch_with_supply(ontology_service, backend, supply_script) -> Orchestrator:
    spec = SCENARIOS["capacity-resolution"]
    scripts = {**spec.get("responders", {}), "supply_planning": supply_script}
    overrides = {
        role: ScriptedAgentHandler(role, orch=None, script=script)
        for role, script in scripts.items()
    }
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    return orch


async def test_wait_all_gate_blocks_then_recovers(ontology_service):
    """Firing 2 of 3 required queries and calling surface_decision is rejected
    with wait_all_unsatisfied naming the missing flow; firing the third then
    surfaces. The 2-of-3 short-circuit is structurally impossible, not just
    discouraged."""
    q = lambda flow, qq: ScriptedToolCall(tool="query", kwargs={"flow": flow, "query_quantum": qq})
    decide = ScriptedToolCall(tool="surface_decision", kwargs={"playbook": "resolve_capacity_conflict", "options": _ALL_OPTIONS})
    script = {
        "escalate_capacity_conflict": [
            q("check_coman_availability", {"sku": "TP-FLAG-6OZ", "volume": 1500, "window_start_day": 140, "window_end_day": 146}),
            q("check_otif_exposure", {"sku": "TP-SEC-6OZ", "retailer": "BULLSEYE", "proposed_delay_days": 3}),
            decide,  # only 2 of 3 fired → gated
            q("check_promo_flexibility", {"promo_id": "PROMO-MGM-FLAG-2026Q2", "proposed_change_kind": "shift_timing"}),
            decide,  # now all three → surfaces
        ],
    }
    backend = JsonlBackend()
    orch = _build_orch_with_supply(ontology_service, backend, script)
    await _SEED(orch)
    events = backend.read_events()

    # The gate fired once, named the one missing required flow, and is in the trace.
    gated = [e.payload for e in events if e.kind == EventKind.WAIT_ALL_UNSATISFIED]
    assert len(gated) == 1
    assert gated[0]["missing"] == ["check_promo_flexibility"]

    # After the third query, the decision surfaced exactly once.
    surfaced = [e.payload for e in events if e.kind == EventKind.DECISION_SURFACED]
    assert len(surfaced) == 1
    assert surfaced[0]["validated"] is True

    # The gated attempt is ordered before the surfaced decision.
    kinds = [e.kind for e in events]
    assert kinds.index(EventKind.WAIT_ALL_UNSATISFIED) < kinds.index(EventKind.DECISION_SURFACED)


async def test_wait_all_gate_is_inert_without_matching_wait_all_playbook(ontology_service):
    """Scope guard: the gate does nothing when there is no matching anchored
    playbook (it never blocks decisions outside a wait_all Playbook)."""
    backend = JsonlBackend()
    orch = _build_orch(ontology_service, backend)
    # Unknown playbook name → inert.
    assert orch.wait_all_missing(playbook="does_not_exist", role="supply_planning", invocation_id="x") == []
    # Playbook not anchored to this role → inert.
    assert orch.wait_all_missing(playbook="resolve_capacity_conflict", role="demand_planning", invocation_id="x") == []
    # Active case (real wait_all playbook, no queries fired) → every required flow missing.
    missing = orch.wait_all_missing(playbook="resolve_capacity_conflict", role="supply_planning", invocation_id="never")
    assert set(missing) == CONTEXT_QUERIES
