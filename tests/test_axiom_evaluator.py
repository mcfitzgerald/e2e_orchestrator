"""Axiom evaluator tests — the deterministic safety floor.

Covers each dispatch path (tool_ref, expr, nl-only), the grounding check
(hallucinated entity → unknown_entity), and the Phase 4 DoD's "same code path
handles `respect_lead_time` and `line_capacity_not_exceeded`": both blocking
world-state axioms are evaluated through the identical `evaluate_axiom` →
tool-registry path, producing the same outcome + recovery surface. The named
stop condition is also pinned: an `expr` needing a function call or entity
traversal is reported non-enforcing (a tool_ref-migration candidate), never
interpreted."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from e2e_orchestrator.application.axiom_evaluator import AxiomEvaluator
from e2e_orchestrator.application.axiom_tools import default_registry


@pytest.fixture
def evaluator(ontology_service, world_state):
    return AxiomEvaluator(ontology_service, world_state)


def _production_request(volume, *, line="NJ-L1", plant="PLANT-NJ", sku="TP-FLAG-6OZ"):
    return {
        "request_id": "pr-test",
        "sku": sku,
        "volume": volume,
        "window_start_day": 140,
        "window_end_day": 146,
        "assigned_plant": plant,
        "assigned_line": line,
        "status": "requested",
    }


# ---- tool_ref path (the real ontology axiom) -------------------------------


def test_tool_ref_capacity_blocks_on_conflict(evaluator):
    result = evaluator.evaluate("request_production", _production_request(3000))
    assert result.ok is False
    assert result.recovery_flow == "escalate_capacity_conflict"
    assert result.recovery_quantum is not None
    assert result.recovery_quantum["shortfall_units"] == 1500
    assert result.recovery_quantum["line_ref"] == "NJ-L1"
    outcome = result.results[0]
    assert outcome.name == "line_capacity_not_exceeded"
    assert outcome.severity == "blocking"
    assert outcome.passed is False


def test_tool_ref_capacity_passes_within_capacity(evaluator):
    result = evaluator.evaluate("request_production", _production_request(1200))
    assert result.ok is True
    assert result.recovery_flow is None
    assert result.results[0].passed is True


def test_grounding_unknown_entity_rejected(evaluator):
    # Hallucinated line/plant → caught by the evaluator, not waved through.
    result = evaluator.evaluate("request_production", _production_request(1200, line="line-oh1-a", plant="PLANT-OH1"))
    assert result.ok is False
    assert "unknown_entity" in result.results[0].evidence
    # No recovery quantum can be built for a phantom line → no auto-recovery.
    assert result.recovery_quantum is None


def test_no_axioms_clean_pass(evaluator):
    result = evaluator.evaluate("submit_supply_request", {"request_id": "x", "sku": "TP-FLAG-6OZ", "volume": 1, "required_by": 140})
    assert result.ok is True
    assert result.results == ()


# ---- expr path (slot subset; no function calls / traversal) ----------------


def test_expr_pure_slot_pass_and_fail(evaluator):
    ax = SimpleNamespace(name="vol_le_cap", severity="blocking", tool_ref=None,
                         expr="{quantum.volume} <= {quantum.cap}", on_failure_route_to=None)
    assert evaluator.evaluate_axiom(ax, {"volume": 10, "cap": 20}).passed is True
    assert evaluator.evaluate_axiom(ax, {"volume": 30, "cap": 20}).passed is False


def test_expr_missing_slot_not_enforced(evaluator):
    ax = SimpleNamespace(name="vol_le_cap", severity="blocking", tool_ref=None,
                         expr="{quantum.volume} <= {quantum.cap}", on_failure_route_to=None)
    out = evaluator.evaluate_axiom(ax, {"volume": 10})  # cap unset
    assert out.passed is True
    assert "unset slot" in out.evidence


def test_expr_function_call_is_stop_condition(evaluator):
    """The named stop condition: a function call in expr is NOT interpreted —
    it is flagged as a tool_ref-migration candidate, non-enforcing."""
    ax = SimpleNamespace(name="lead", severity="blocking", tool_ref=None,
                         expr="{quantum.required_by} >= today() + 5", on_failure_route_to=None)
    out = evaluator.evaluate_axiom(ax, {"required_by": 10})
    assert out.passed is True
    assert "tool_ref" in out.evidence


def test_expr_entity_traversal_is_stop_condition(evaluator):
    ax = SimpleNamespace(name="cap", severity="blocking", tool_ref=None,
                         expr="{quantum.assigned_line.capacity_total} >= {quantum.volume}",
                         on_failure_route_to=None)
    out = evaluator.evaluate_axiom(ax, {"volume": 10})
    assert out.passed is True
    assert "tool_ref" in out.evidence


# ---- nl-only path ----------------------------------------------------------


def test_nl_only_is_advisory_pass(evaluator):
    ax = SimpleNamespace(name="soft", severity="advisory", tool_ref=None, expr=None, on_failure_route_to=None)
    out = evaluator.evaluate_axiom(ax, {})
    assert out.passed is True
    assert "deterministic eval not applicable" in out.evidence


# ---- "same code path handles both blocking axioms" (DoD) -------------------


def test_same_code_path_handles_both_world_state_axioms(evaluator):
    """Both `line_capacity_not_exceeded` and `respect_lead_time` are world-state
    axioms; both resolve through the identical tool_ref dispatch and yield the
    same AxiomOutcome shape + recovery routing. (The registry already binds
    `evaluate_respect_lead_time`; once the ontology declares its tool_ref it
    routes here at runtime too — see the upstream briefing.)"""
    cap_ax = SimpleNamespace(
        name="line_capacity_not_exceeded", severity="blocking",
        tool_ref="evaluate_line_capacity_not_exceeded", expr=None,
        on_failure_route_to="escalate_capacity_conflict",
    )
    lead_ax = SimpleNamespace(
        name="respect_lead_time", severity="blocking",
        tool_ref="evaluate_respect_lead_time", expr=None,
        on_failure_route_to="replan_on_infeasible_request",
    )
    assert "evaluate_respect_lead_time" in default_registry()

    cap_fail = evaluator.evaluate_axiom(cap_ax, _production_request(3000))
    lead_fail = evaluator.evaluate_axiom(lead_ax, {"required_by": 110, "supplier": "SUP-MENTHOL-002"})
    lead_pass = evaluator.evaluate_axiom(lead_ax, {"required_by": 200, "supplier": "SUP-MENTHOL-002"})

    # Identical outcome surface for both axioms.
    for out in (cap_fail, lead_fail, lead_pass):
        assert hasattr(out, "passed") and hasattr(out, "evidence") and hasattr(out, "severity")

    assert cap_fail.passed is False and cap_fail.recovery_flow == "escalate_capacity_conflict"
    assert lead_fail.passed is False and lead_fail.recovery_flow == "replan_on_infeasible_request"
    assert lead_pass.passed is True and lead_pass.recovery_flow is None


def test_respect_lead_time_unknown_supplier_grounding(evaluator):
    lead_ax = SimpleNamespace(
        name="respect_lead_time", severity="blocking",
        tool_ref="evaluate_respect_lead_time", expr=None,
        on_failure_route_to="replan_on_infeasible_request",
    )
    out = evaluator.evaluate_axiom(lead_ax, {"required_by": 200, "supplier": "SUP-NOPE"})
    assert out.passed is False
    assert "unknown_entity" in out.evidence
