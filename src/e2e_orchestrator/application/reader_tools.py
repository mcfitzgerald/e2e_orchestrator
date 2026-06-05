"""Deterministic reader tools — world-state reads for grounded agent reasoning.

The Phase 5 counterpart to `axiom_tools.py`. Where axiom tools back `tool_ref`
axioms, reader tools back the `scont:Tool` declarations an agent invokes via
`call_tool`. Same registry shape (name → callable, bound at boot), same
discipline: domain knowledge lives **here**, the orchestrator only dispatches
and validates I/O against the tool's declared input/output classes.

These are the deterministic fix for the hallucinated-grounding pattern Phase 3
surfaced: instead of inventing a `(plant, line)` the agent calls
`query_plants_for_sku` / `query_line_load` and grounds on real world-state
entities. The reach already worked once pre-wiring (`runs/phase4-post-1.8-live`
seq 8); this module is what the reach now hits.

Each tool has the uniform signature `(input: dict, world_state: WorldState) ->
ReaderToolResult`. A grounding miss — the queried entity isn't in world state —
returns `output=None` with an `unknown_entity`-style `evidence` string (the same
floor `axiom_tools` uses). The orchestrator surfaces that honestly rather than
fabricating a typed shell; a *valid but empty* result (the entity exists, no
matching rows) returns an empty typed `output`, which is a different signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .axiom_tools import UNKNOWN_ENTITY, _entity_id

if TYPE_CHECKING:  # world_state imports the application layer; avoid a cycle.
    from ..world_state.loader import WorldState


@dataclass(frozen=True)
class ReaderToolResult:
    """Outcome of a reader-tool call.

    `output` is a dict shaped for the tool's declared `output_class` (validated
    by the orchestrator before it reaches the agent), or `None` on a grounding
    miss — the queried entity is absent from world state, so there is nothing
    real to return and `evidence` explains why."""

    output: dict[str, Any] | None
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)


ReaderTool = Callable[..., ReaderToolResult]   # (input: dict, world_state: WorldState)


# ---------------------------------------------------------------------------
# query_plants_for_sku  ->  PlantQueryResult{lines: [ProductionLine]}
# ---------------------------------------------------------------------------


def query_plants_for_sku(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Which production lines can make this SKU? World state has no SKU→line
    capability table, so the grounded signal is the production schedule: a line
    that currently runs the SKU can make it. Returns the real ProductionLine
    entities — the agent grounds on `NJ-L1` instead of inventing `line-A`."""
    sku = _entity_id(input.get("sku"), "sku_code")
    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None, evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")

    lines: list[dict[str, Any]] = []
    for line in world_state.instances_of("ProductionLine"):
        load = world_state.query_line_load(line.get("plant_code"), line.get("line_code"), 1, 365)
        if sku in load.scheduled_skus:
            lines.append(line.as_dict())

    codes = [l["line_code"] for l in lines]
    return ReaderToolResult(
        output={"lines": lines},
        evidence=f"{len(lines)} line(s) currently scheduling {sku}: {codes}",
        details={"sku": sku, "line_codes": codes},
    )


# ---------------------------------------------------------------------------
# query_line_load  ->  LineLoad
# ---------------------------------------------------------------------------


def query_line_load(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Scheduled production load on a (plant, line) across a window, against the
    line's rated weekly capacity. Wraps `WorldState.query_line_load` and shapes
    the result for the declared `LineLoad` output class."""
    plant = input.get("plant_code")
    line = input.get("line_code")
    start = input.get("window_start_day")
    end = input.get("window_end_day")

    if line is None or world_state.get_production_line(plant, line) is None:
        return ReaderToolResult(
            output=None,
            evidence=f"{UNKNOWN_ENTITY}: line_code={line!r} plant_code={plant!r} not found in world state",
        )

    load = world_state.query_line_load(plant, line, int(start), int(end))
    output = {
        "plant_code": load.plant_code,
        "line_code": load.line_code,
        "window_start_day": load.window_start_day,
        "window_end_day": load.window_end_day,
        "scheduled_units": load.scheduled_units,
    }
    return ReaderToolResult(
        output=output,
        evidence=(
            f"{load.plant_code}/{load.line_code} window [{start},{end}]: "
            f"scheduled {load.scheduled_units:g}"
            + (f", available {load.available:g} of {load.rated_weekly_capacity}" if load.available is not None else "")
        ),
        details={"rated_weekly_capacity": load.rated_weekly_capacity, "available": load.available,
                 "scheduled_skus": list(load.scheduled_skus)},
    )


# ---------------------------------------------------------------------------
# query_commitments_in_window  ->  CommitmentQueryResult{commitments: [RetailerCommitment]}
# ---------------------------------------------------------------------------


def query_commitments_in_window(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Retailer commitments touching a (sku, retailer?, window). The window
    filter is on `mabd_day` (must-arrive-by). `retailer` is optional — omit to
    match all. Returns real RetailerCommitment entities for OTIF reasoning."""
    sku = _entity_id(input.get("sku"), "sku_code")
    retailer = input.get("retailer")
    start = input.get("window_start_day")
    end = input.get("window_end_day")

    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None, evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")

    lo, hi = int(start), int(end)
    matches: list[dict[str, Any]] = []
    for c in world_state.instances_of("RetailerCommitment"):
        if c.get("sku") != sku:
            continue
        if retailer is not None and c.get("retailer") != retailer:
            continue
        mabd = c.get("mabd_day")
        if mabd is None or not (lo <= int(mabd) <= hi):
            continue
        matches.append(c.as_dict())

    ids = [c["commitment_id"] for c in matches]
    return ReaderToolResult(
        output={"commitments": matches},
        evidence=f"{len(matches)} commitment(s) for {sku}"
        + (f"/{retailer}" if retailer else "")
        + f" with mabd in [{lo},{hi}]: {ids}",
        details={"sku": sku, "retailer": retailer, "commitment_ids": ids},
    )


# ---------------------------------------------------------------------------
# query_supplier_for_sku  ->  Supplier
# ---------------------------------------------------------------------------


def query_supplier_for_sku(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Which supplier provides raw materials for this SKU? The demo world models
    raw-material suppliers but declares no SKU→supplier bill-of-materials link,
    so for a finished good the honest grounded answer is a miss. The lookup is
    generic (a future fixture that adds a `sku` slot to Supplier resolves here);
    it never fabricates a supplier — that would re-introduce the hallucination
    this tool exists to prevent."""
    sku = _entity_id(input.get("sku"), "sku_code")
    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None, evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")

    supplier = world_state.find("Supplier", sku=sku)
    if supplier is None:
        return ReaderToolResult(
            output=None,
            evidence=f"{UNKNOWN_ENTITY}: no raw-material supplier mapped to sku={sku!r} in world state",
        )
    return ReaderToolResult(
        output=supplier.as_dict(),
        evidence=f"supplier {supplier.get('supplier_code')} supplies {sku}",
        details={"sku": sku},
    )


# ---------------------------------------------------------------------------
# query_baseline_demand  ->  BaselineDemand
# ---------------------------------------------------------------------------


def query_baseline_demand(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Baseline (pre-promo) demand run-rate for a SKU. A promo's
    `volume_uplift_factor` multiplies this baseline — grounding the base so
    `demand_planning` multiplies a *real* number instead of inventing one (the
    report §5 ungrounded-quantity gap: a live run sized a promo SupplyRequest at
    45,000 off a guessed base). The `BaselineDemand` rows are an outbound-edge
    shim for a real demand/forecast system behind the same `scont:Tool`
    contract; the lookup is generic and never fabricates a run-rate.

    A SKU with no baseline row is a *valid-but-empty* miss (typed output, no
    units) — distinct from an unknown SKU, which is the `unknown_entity` floor."""
    sku = _entity_id(input.get("sku"), "sku_code")
    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None, evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")

    start = input.get("window_start_day")
    end = input.get("window_end_day")
    row = world_state.find("BaselineDemand", sku=sku)
    if row is None:
        return ReaderToolResult(
            output={"sku": sku},
            evidence=f"no baseline demand on record for sku={sku!r} in world state",
            details={"sku": sku, "empty": True},
        )

    output: dict[str, Any] = {"sku": sku, "units_per_week": row.get("units_per_week")}
    if start is not None:
        output["window_start_day"] = int(start)
    if end is not None:
        output["window_end_day"] = int(end)
    return ReaderToolResult(
        output=output,
        evidence=(
            f"baseline demand for {sku}: {output['units_per_week']:g} units/week"
            + (f" over window [{start},{end}]" if start is not None or end is not None else " (standing run-rate)")
        ),
        details={"sku": sku, "units_per_week": output["units_per_week"]},
    )


# ---------------------------------------------------------------------------
# query_coman_availability  ->  ComanAvailability
# ---------------------------------------------------------------------------


def query_coman_availability(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Co-manufacturer gate FACTS for a SKU in the requested window:
    `qualified_for_sku`, `open_window` (units of uncommitted co-man capacity),
    `moq`, plus the `premium_cost_per_unit` and `lead_time_days` the agent
    weighs. The deterministic counterpart to the `check_coman_availability`
    query flow — both surface the *same* facts so the agent reaches the same
    grounded conclusion whether it reads or asks (Session-1 contract).

    The agent reads these and concludes whether `shift_to_coman` is viable
    (`viable_coman_shift`); this tool never returns a pre-baked yes/no, and the
    co-man rows are an outbound-edge shim for a real co-man capacity system
    behind the same `scont:Tool` contract. An unknown SKU is the
    `unknown_entity` floor; a known SKU with no co-man on record is an honest
    grounding miss (no fabricated co-man), mirroring `query_supplier_for_sku`."""
    sku = _entity_id(input.get("sku"), "sku_code")
    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None, evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")

    row = world_state.find("ComanAvailability", sku=sku)
    if row is None:
        return ReaderToolResult(
            output=None,
            evidence=f"{UNKNOWN_ENTITY}: no co-manufacturer on record for sku={sku!r} in world state",
        )

    output: dict[str, Any] = {
        "sku": sku,
        "qualified_for_sku": row.get("qualified_for_sku"),
        "open_window": row.get("open_window"),
        "moq": row.get("moq"),
    }
    # Premium / lead time are optional inputs the agent weighs — include when present.
    if row.get("premium_cost_per_unit") is not None:
        output["premium_cost_per_unit"] = row.get("premium_cost_per_unit")
    if row.get("lead_time_days") is not None:
        output["lead_time_days"] = row.get("lead_time_days")

    needed = input.get("volume")
    return ReaderToolResult(
        output=output,
        evidence=(
            f"co-man for {sku}: qualified={output['qualified_for_sku']}, "
            f"open_window={output['open_window']:g}, moq={output['moq']:g}"
            + (f" (need {float(needed):g})" if needed is not None else "")
        ),
        details={"sku": sku, "needed": needed},
    )


# ---------------------------------------------------------------------------
# Registry. Keys are the `implementation` contract names on the scont:Tool
# declarations; the orchestrator binds them to these callables at boot.
# ---------------------------------------------------------------------------

DEFAULT_READER_TOOLS: dict[str, ReaderTool] = {
    "query_plants_for_sku": query_plants_for_sku,
    "query_line_load": query_line_load,
    "query_commitments_in_window": query_commitments_in_window,
    "query_supplier_for_sku": query_supplier_for_sku,
    "query_baseline_demand": query_baseline_demand,
    "query_coman_availability": query_coman_availability,
}


def default_registry() -> dict[str, ReaderTool]:
    """Fresh copy of the default reader-tool registry (callers may extend it)."""
    return dict(DEFAULT_READER_TOOLS)
