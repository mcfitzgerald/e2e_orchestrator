"""FSM tracker tests — lifecycle state + guard enforcement.

The tracker advances a quantum through its declared StateMachine, evaluating
each transition's guard via the same deterministic evaluator as flow axioms.
On a blocking guard failure it does not advance and surfaces the recovery
route. Generic over `StateMachineBody` — these tests drive
`ProductionRequestLifecycle` (whose `requested → assigned` guard is the
tool-backed `line_capacity_not_exceeded`)."""
from __future__ import annotations

import pytest

from e2e_orchestrator.application.axiom_evaluator import AxiomEvaluator
from e2e_orchestrator.application.fsm_tracker import FsmTracker
from e2e_orchestrator.durability import EventKind, JsonlBackend

FSM = "ProductionRequestLifecycle"


@pytest.fixture
def tracker(ontology_service, world_state):
    backend = JsonlBackend()
    evaluator = AxiomEvaluator(ontology_service, world_state)
    return FsmTracker(ontology_service, evaluator, backend), backend


def _pr(volume, *, line="NJ-L1", plant="PLANT-NJ"):
    return {
        "request_id": "pr-fsm",
        "sku": "TP-FLAG-6OZ",
        "volume": volume,
        "window_start_day": 140,
        "window_end_day": 146,
        "assigned_plant": plant,
        "assigned_line": line,
        "status": "requested",
    }


def test_initial_state_is_fsm_initial(tracker):
    trk, _ = tracker
    assert trk.current_state(FSM, "q-1") == "requested"


def test_guard_passes_advances(tracker):
    trk, backend = tracker
    result = trk.advance(quantum_id="q-ok", fsm=FSM, trigger="assign", quantum=_pr(1200))
    assert result.status == "transitioned"
    assert result.from_state == "requested"
    assert result.to_state == "assigned"
    assert trk.current_state(FSM, "q-ok") == "assigned"
    assert any(e.kind == EventKind.FSM_TRANSITIONED for e in backend.read_events())


def test_state_persists_across_advances(tracker):
    trk, _ = tracker
    trk.advance(quantum_id="q-seq", fsm=FSM, trigger="assign", quantum=_pr(1200))
    # 'schedule' has no guard; should advance from assigned → scheduled.
    result = trk.advance(quantum_id="q-seq", fsm=FSM, trigger="schedule", quantum=_pr(1200))
    assert result.status == "transitioned"
    assert result.from_state == "assigned"
    assert result.to_state == "scheduled"


def test_blocking_guard_blocks_and_routes(tracker):
    trk, backend = tracker
    result = trk.advance(quantum_id="q-bad", fsm=FSM, trigger="assign", quantum=_pr(3000))
    assert result.status == "blocked"
    assert result.from_state == "requested"
    assert result.recovery_flow == "escalate_capacity_conflict"
    assert result.recovery_quantum is not None
    # State did not advance.
    assert trk.current_state(FSM, "q-bad") == "requested"
    assert any(e.kind == EventKind.FSM_BLOCKED for e in backend.read_events())


def test_unknown_trigger_rejected(tracker):
    trk, _ = tracker
    result = trk.advance(quantum_id="q-x", fsm=FSM, trigger="finish", quantum=_pr(1200))
    assert result.status == "rejected"
    assert "no transition" in result.reason


def test_unknown_fsm_rejected(tracker):
    trk, _ = tracker
    result = trk.advance(quantum_id="q-x", fsm="NoSuchFSM", trigger="assign", quantum=_pr(1200))
    assert result.status == "rejected"
    assert "unknown state machine" in result.reason
