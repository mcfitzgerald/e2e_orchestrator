"""Deterministic compute tools for tool-backed axioms.

Some axioms exceed the `equals_expression` slot subset — they need world-state
access (schedules, lead times, calendars). The ontology declares these with a
`tool_ref` naming a deterministic Python callable; the orchestrator binds the
name to a function here at boot (`AxiomEvaluator` dispatches to it instead of
parsing `expr`). This is the named Phase 4 design point: world-state axioms go
through `tool_ref`, not a growing expression interpreter.

Each tool has the uniform signature `(quantum: dict, world_state: WorldState)
-> AxiomToolResult`. Domain knowledge lives **here** (the deterministic compute
layer), never in the orchestrator: a failing blocking axiom may attach a
`recovery_quantum` already shaped for the recovery flow's class, so the
orchestrator only has to validate + route it.

Grounding (the Phase 4 addition to the spirit of the DoD): a tool whose quantum
references an entity the world state does not contain returns `passed=False`
with `evidence="unknown_entity"`. A hallucinated `assigned_line` / `assigned_plant`
is caught by code, not waved through. Phase 5's reader tools are the real fix
for the hallucination itself; Phase 4 exposes the gap honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # avoid a runtime import cycle: world_state imports the
    # application layer's quantum_validator, which loads this module.
    from ..world_state.loader import WorldState

UNKNOWN_ENTITY = "unknown_entity"


@dataclass(frozen=True)
class AxiomToolResult:
    passed: bool
    evidence: str
    # When a blocking axiom fails, a tool may pre-build the recovery quantum
    # (shaped for the `on_failure_route_to` flow's class). The orchestrator
    # validates + dispatches it; absent it (e.g. a grounding failure where no
    # real conflict exists), the orchestrator records the block without
    # dispatching a recovery flow.
    recovery_quantum: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)


AxiomTool = Callable[..., AxiomToolResult]   # (quantum: dict, world_state: WorldState)


def _entity_id(value: Any, *candidate_keys: str) -> str | None:
    """A class-ranged slot may arrive as a bare id string or an inlined dict.
    Pull the identifier either way."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for k in candidate_keys:
            if value.get(k):
                return str(value[k])
        # Fall back to the first string-ish value.
        for v in value.values():
            if isinstance(v, str) and v:
                return v
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


# ---------------------------------------------------------------------------
# line_capacity_not_exceeded  (request_production → escalate_capacity_conflict)
# ---------------------------------------------------------------------------


def evaluate_line_capacity_not_exceeded(quantum: dict, world_state: WorldState) -> AxiomToolResult:
    """Total scheduled production on the assigned line for the requested window,
    plus the requested volume, must not exceed the line's rated weekly capacity.

    Mirrors the axiom's `expr` (`sum_scheduled_units(line, window) + volume <=
    line.rated_weekly_capacity`) but resolves the line and schedule from world
    state — the part `equals_expression` cannot express."""
    plant = quantum.get("assigned_plant")
    line_code = _entity_id(quantum.get("assigned_line"), "line_code", "line")
    sku = _entity_id(quantum.get("sku"), "sku_code")
    volume = _num(quantum.get("volume")) or 0.0
    ws_start = quantum.get("window_start_day")
    ws_end = quantum.get("window_end_day")

    # --- grounding check ---------------------------------------------------
    line = world_state.get_production_line(plant, line_code) if line_code else None
    if line is None:
        return AxiomToolResult(
            passed=False,
            evidence=f"{UNKNOWN_ENTITY}: assigned_line={line_code!r} assigned_plant={plant!r} "
            "not found in world state",
        )
    if sku is not None and world_state.get_sku(sku) is None:
        return AxiomToolResult(
            passed=False,
            evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state",
        )

    load = world_state.query_line_load(plant, line_code, int(ws_start), int(ws_end))
    capacity = int(line.rated_weekly_capacity)
    total = load.scheduled_units + volume
    passed = total <= capacity

    if passed:
        return AxiomToolResult(
            passed=True,
            evidence=(
                f"{plant}/{line_code} window [{ws_start},{ws_end}]: scheduled "
                f"{load.scheduled_units:g} + requested {volume:g} = {total:g} "
                f"<= rated weekly capacity {capacity}"
            ),
            details={"scheduled_units": load.scheduled_units, "capacity": capacity, "total": total},
        )

    shortfall = total - capacity
    competing = list(load.scheduled_skus)
    if sku is not None and sku not in competing:
        competing.append(sku)
    at_risk = [c.commitment_id for c in world_state.commitments_for_skus(competing)]

    recovery_quantum = {
        "conflict_id": f"conf-{quantum.get('request_id', line_code)}",
        "line_ref": line_code,
        "competing_skus": competing,
        "shortfall_units": shortfall,
        "at_risk_commitments": at_risk,
        "window_start_day": int(ws_start),
        "window_end_day": int(ws_end),
    }
    return AxiomToolResult(
        passed=False,
        evidence=(
            f"{plant}/{line_code} window [{ws_start},{ws_end}]: scheduled "
            f"{load.scheduled_units:g} + requested {volume:g} = {total:g} "
            f"> rated weekly capacity {capacity}; shortfall {shortfall:g}"
        ),
        recovery_quantum=recovery_quantum,
        details={
            "scheduled_units": load.scheduled_units,
            "capacity": capacity,
            "total": total,
            "shortfall_units": shortfall,
            "competing_skus": competing,
        },
    )


# ---------------------------------------------------------------------------
# respect_lead_time  (submit_procurement_request → replan_on_infeasible_request)
# ---------------------------------------------------------------------------


def evaluate_respect_lead_time(quantum: dict, world_state: WorldState) -> AxiomToolResult:
    """A request's required-by day must not fall inside its supplier's lead
    time. Mirrors the axiom's `expr` (`required_by >= today() + supplier.
    lead_time_days`) but resolves the supplier and the injectable clock from
    world state — both `today()` (a function) and the supplier traversal are
    outside the slot-expression subset, so this is `tool_ref` territory."""
    required_by = _num(quantum.get("required_by"))
    supplier_code = _entity_id(quantum.get("supplier"), "supplier_code")

    supplier = world_state.get_supplier(supplier_code) if supplier_code else None
    if supplier is None:
        return AxiomToolResult(
            passed=False,
            evidence=f"{UNKNOWN_ENTITY}: supplier={supplier_code!r} not found in world state",
        )
    if required_by is None:
        return AxiomToolResult(passed=False, evidence="required_by is missing or non-numeric")

    today = world_state.today()
    lead = int(supplier.lead_time_days)
    earliest = today + lead
    passed = required_by >= earliest
    rel = ">=" if passed else "<"
    return AxiomToolResult(
        passed=passed,
        evidence=(
            f"required_by {int(required_by)} {rel} today({today}) + lead_time "
            f"{lead} = {earliest} for supplier {supplier_code}"
        ),
        details={"today": today, "lead_time_days": lead, "earliest_feasible_day": earliest},
    )


# ---------------------------------------------------------------------------
# Registry. The orchestrator binds tool_ref names to these at boot.
# ---------------------------------------------------------------------------

DEFAULT_AXIOM_TOOLS: dict[str, AxiomTool] = {
    "evaluate_line_capacity_not_exceeded": evaluate_line_capacity_not_exceeded,
    "evaluate_respect_lead_time": evaluate_respect_lead_time,
}


def default_registry() -> dict[str, AxiomTool]:
    """Fresh copy of the default tool registry (callers may extend it)."""
    return dict(DEFAULT_AXIOM_TOOLS)
