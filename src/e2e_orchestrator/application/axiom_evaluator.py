"""Deterministic axiom evaluation.

Phase 2 scope: structural pass-through. The flows exercised in the Phase 2 DoD
(`raise_demand_anomaly`, `submit_supply_request`) declare no axioms, so the
evaluator's job is to return a clean "no axioms attached → pass" result and
write a single `axiom_evaluated` event for the trace. The evaluator's shape is
set up so Phase 4 fills in `expr:` interpretation and tool-backed evaluation
without changing the surface the orchestrator depends on.

Contract:
  evaluate(flow_name, quantum) -> AxiomEvalResult
    .ok               — every blocking axiom passed
    .results          — per-axiom outcomes (incl. advisory)
    .recovery_flow    — name of the on_failure_route_to recovery flow (if a
                        blocking axiom failed; else None)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ontology_service import OntologyService


@dataclass(frozen=True)
class AxiomOutcome:
    name: str
    severity: str | None
    passed: bool
    evidence: str                 # human-readable reason, kept terse


@dataclass(frozen=True)
class AxiomEvalResult:
    ok: bool
    results: tuple[AxiomOutcome, ...]
    recovery_flow: str | None = None


class AxiomEvaluator:
    """Phase 2 stub: returns 'no axioms' or marks every axiom as a Phase-4-TODO.

    Replaced in Phase 4 with the real evaluator (slot-level `expr:` interpreter
    + tool-backed evaluation for world-state axioms). The orchestrator's call
    site doesn't change — that's the design point."""

    def __init__(self, service: OntologyService):
        self._svc = service

    def evaluate(self, flow_name: str, quantum: dict[str, Any]) -> AxiomEvalResult:
        axioms = self._svc.axioms_on_flow(flow_name)
        if not axioms:
            return AxiomEvalResult(ok=True, results=())

        # Phase 4 lands real evaluation; until then, mark each axiom as
        # advisory-passed with a clear evidence string so it's visible in the
        # trace that this code path was reached but not enforced.
        outcomes = tuple(
            AxiomOutcome(
                name=ax.name,
                severity=_enum_value(ax.severity),
                passed=True,
                evidence="phase 4 placeholder — evaluator not yet implemented",
            )
            for ax in axioms
        )
        return AxiomEvalResult(ok=True, results=outcomes)


def _enum_value(v: Any) -> str | None:
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)
