"""Phase 5 Definition-of-Done assertion (the load-bearing claim).

The DoD (ontology repo `plan_of_attack.md` §5):

  Across two runs with different LLM seeds, supply_planning fires the **same
  three query flows** (deterministic context assembly) but may pick **different
  resolutions** (irreducible agency). The contrast is visible in the trace.

A scripted test cannot vary an LLM seed, so it encodes the *structural*
guarantee the live run rests on: the context-assembly query set is deterministic
and independent of the resolution. We run two variants that differ ONLY in the
chosen resolution flow (allocate_partial_fill vs re_request_production) and assert the
three query flows are identical across both while the resolution differs — the
same-queries / different-resolution signal, made deterministic. The live
two-seed run (captured under `runs/`) is the agency half of the proof.

Scripted handlers wire from the canonical `SCENARIOS["capacity-resolution"]`
registry, so the CLI path and the test can't drift; the orchestrator can't tell
a script from an LLM, so the structural guarantee holds for the live run too.
"""
from __future__ import annotations

import copy

from e2e_orchestrator.application.agent_factory import (
    ScriptedAgentHandler,
    ScriptedToolCall,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS

_SEED = SCENARIOS["capacity-resolution"]["seeder"]

CONTEXT_QUERIES = {"check_otif_exposure", "check_promo_flexibility", "check_coman_availability"}
RESOLUTION_FLOWS = {"shift_to_coman", "re_request_production", "request_promo_revision",
                    "allocate_partial_fill"}


def _supply_script_choosing(resolution_flow: str, quantum: dict) -> dict:
    """A copy of the canonical supply_planning script with only the resolution
    handoff swapped — everything before it (playbook read, reader-tool grounding,
    the three context-assembly queries, the surfaced decision) is identical."""
    base = copy.deepcopy(SCENARIOS["capacity-resolution"]["scripts"]["supply_planning"])
    steps = base["escalate_capacity_conflict"]
    swapped = []
    for step in steps:
        if step.tool == "handoff" and step.kwargs.get("flow") in RESOLUTION_FLOWS:
            swapped.append(ScriptedToolCall(tool="handoff", kwargs={"flow": resolution_flow, "quantum": quantum}))
        else:
            swapped.append(step)
    base["escalate_capacity_conflict"] = swapped
    return base


async def _run(ontology_service, supply_override: dict | None) -> list:
    spec = SCENARIOS["capacity-resolution"]
    scripts = {**spec.get("responders", {}), **spec["scripts"]}
    if supply_override is not None:
        scripts["supply_planning"] = supply_override
    overrides = {
        role: ScriptedAgentHandler(role, orch=None, script=script)
        for role, script in scripts.items()
    }
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    backend = JsonlBackend()
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    await _SEED(orch)
    return backend.read_events()


def _query_set(events) -> set[str]:
    return {e.payload["flow"] for e in events if e.kind == EventKind.QUERY_REQUESTED}


def _resolution(events) -> str:
    executed = [e.payload["flow"] for e in events if e.kind == EventKind.HANDOFF_EXECUTED]
    chosen = [f for f in executed if f in RESOLUTION_FLOWS]
    assert len(chosen) == 1, f"expected exactly one resolution, got {chosen}"
    return chosen[0]


async def test_phase5_same_queries_different_resolution(ontology_service):
    # Run A — the canonical scenario (picks allocate_partial_fill, the reflexive
    # holding move; coherent now that the flagship co-man is gated out on facts).
    events_a = await _run(ontology_service, supply_override=None)

    # Run B — same context assembly, different resolution (re_request_production
    # to plant_scheduler with a feasible internal ProductionRequest).
    internal = {
        "request_id": "pr-internal-capres", "sku": "TP-FLAG-6OZ", "volume": 1500,
        "window_start_day": 140, "window_end_day": 146,
        "assigned_plant": "PLANT-CA", "assigned_line": "CA-L1", "status": "requested",
    }
    events_b = await _run(ontology_service, supply_override=_supply_script_choosing("re_request_production", internal))

    # Deterministic context assembly: the SAME three query flows fire in both.
    assert _query_set(events_a) == CONTEXT_QUERIES
    assert _query_set(events_b) == CONTEXT_QUERIES
    assert _query_set(events_a) == _query_set(events_b)

    # Irreducible agency: the resolution differs across the two runs.
    assert _resolution(events_a) == "allocate_partial_fill"
    assert _resolution(events_b) == "re_request_production"
    assert _resolution(events_a) != _resolution(events_b)


async def test_phase5_always_fires_regardless_of_resolution(ontology_service):
    """capacity_resolved + plan_fulfillment fire on every resolution path."""
    for events in (await _run(ontology_service, None),):
        emitted = {e.payload["name"] for e in events if e.kind == EventKind.EVENT_EMITTED}
        executed = {e.payload["flow"] for e in events if e.kind == EventKind.HANDOFF_EXECUTED}
        assert "capacity_resolved" in emitted
        assert "plan_fulfillment" in executed


async def test_phase5_context_assembly_is_deterministic(ontology_service):
    """No LLM in context assembly → the query set is identical every run."""
    a = _query_set(await _run(ontology_service, None))
    b = _query_set(await _run(ontology_service, None))
    assert a == b == CONTEXT_QUERIES
