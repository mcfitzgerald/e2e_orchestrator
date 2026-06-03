"""Reader-tool unit tests (Phase 5; +query_baseline_demand per Seed A).

The `scont:Tool` implementations read world state and return real entities,
shaped for their declared output class. A grounding miss (entity absent from
world state) returns `output=None` with an `unknown_entity` evidence string — the
deterministic counter to the hallucinated-grounding pattern, the same floor the
axiom tools use. These tests pin both behaviours and confirm every typed output
validates against its declared output class via the SchemaView-driven validator.
"""
from __future__ import annotations

import pytest

from e2e_orchestrator.application import reader_tools
from e2e_orchestrator.application.quantum_validator import QuantumValidator


@pytest.fixture()
def validator(ontology_service) -> QuantumValidator:
    return QuantumValidator(ontology_service.ontology.schema_view)


def test_query_plants_for_sku_returns_real_lines(world_state, validator):
    res = reader_tools.query_plants_for_sku({"sku": "TP-FLAG-6OZ"}, world_state)
    assert res.output is not None
    codes = [l["line_code"] for l in res.output["lines"]]
    # NJ-L1 is the only line scheduling TP-FLAG-6OZ in the fixture — grounded,
    # not invented.
    assert codes == ["NJ-L1"]
    assert validator.validate("PlantQueryResult", res.output).ok


def test_query_plants_for_sku_unknown_sku_is_grounding_floor(world_state):
    res = reader_tools.query_plants_for_sku({"sku": "NOPE-SKU"}, world_state)
    assert res.output is None
    assert res.evidence.startswith("unknown_entity")


def test_query_line_load_matches_conflict_math(world_state, validator):
    res = reader_tools.query_line_load(
        {"plant_code": "PLANT-NJ", "line_code": "NJ-L1", "window_start_day": 140, "window_end_day": 146},
        world_state,
    )
    assert res.output is not None
    # Baseline NJ-L1 load in the promo window is 3500 (1500 + 2000) of 5000.
    assert res.output["scheduled_units"] == 3500
    assert res.details["available"] == 1500
    assert validator.validate("LineLoad", res.output).ok


def test_query_line_load_unknown_line_is_grounding_floor(world_state):
    res = reader_tools.query_line_load(
        {"plant_code": "PLANT-NJ", "line_code": "GHOST-L9", "window_start_day": 140, "window_end_day": 146},
        world_state,
    )
    assert res.output is None
    assert res.evidence.startswith("unknown_entity")


def test_query_commitments_in_window_filters_by_sku_and_window(world_state, validator):
    res = reader_tools.query_commitments_in_window(
        {"sku": "TP-SEC-6OZ", "window_start_day": 125, "window_end_day": 145}, world_state
    )
    assert res.output is not None
    ids = {c["commitment_id"] for c in res.output["commitments"]}
    # The at-risk Bullseye commitment (mabd 130) and the Greenfield one (mabd 132)
    # fall in-window; nothing for other SKUs leaks in.
    assert ids == {"COM-BUL-SEC-Q2", "COM-GRN-SEC-Q2"}
    assert validator.validate("CommitmentQueryResult", res.output).ok


def test_query_commitments_retailer_filter(world_state):
    res = reader_tools.query_commitments_in_window(
        {"sku": "TP-SEC-6OZ", "retailer": "BULLSEYE", "window_start_day": 125, "window_end_day": 145},
        world_state,
    )
    ids = {c["commitment_id"] for c in res.output["commitments"]}
    assert ids == {"COM-BUL-SEC-Q2"}


def test_query_supplier_for_sku_is_honest_grounding_miss(world_state):
    # The demo world declares no SKU→supplier bill-of-materials link, so a
    # finished-good lookup must miss rather than fabricate a supplier.
    res = reader_tools.query_supplier_for_sku({"sku": "TP-FLAG-6OZ"}, world_state)
    assert res.output is None
    assert res.evidence.startswith("unknown_entity")


def test_query_baseline_demand_grounds_promo_base(world_state, validator):
    # Seed A: demand_planning reads a REAL baseline instead of inventing one.
    res = reader_tools.query_baseline_demand({"sku": "TP-FLAG-6OZ"}, world_state)
    assert res.output is not None
    # 1500/week tracks the production baseline; ×3.0 promo uplift → 4500, the
    # 3000 incremental SupplyRequest volume traces to this readable number.
    assert res.output["units_per_week"] == 1500
    assert validator.validate("BaselineDemand", res.output).ok


def test_query_baseline_demand_window_passthrough(world_state, validator):
    res = reader_tools.query_baseline_demand(
        {"sku": "TP-FLAG-6OZ", "window_start_day": 142, "window_end_day": 156}, world_state
    )
    assert res.output["window_start_day"] == 142
    assert res.output["window_end_day"] == 156
    assert validator.validate("BaselineDemand", res.output).ok


def test_query_baseline_demand_unknown_sku_is_grounding_floor(world_state):
    res = reader_tools.query_baseline_demand({"sku": "NOPE-SKU"}, world_state)
    assert res.output is None
    assert res.evidence.startswith("unknown_entity")


def test_query_baseline_demand_known_sku_no_baseline_is_valid_empty(world_state, validator):
    # A real SKU with no baseline row is valid-but-empty (typed output, no
    # units), distinct from the unknown-entity floor. No demo SKU is missing a
    # baseline, so synthesise the case with a throwaway world state.
    from e2e_orchestrator.world_state.loader import Entity, WorldState

    ws = WorldState(
        instances={
            "SKU": [Entity("SKU", {"sku_code": "BARE-SKU", "name": "x", "active": True})],
            "BaselineDemand": [],
        },
        production_schedule=[],
        clock={"today_day_of_year": 100},
    )
    res = reader_tools.query_baseline_demand({"sku": "BARE-SKU"}, ws)
    assert res.output is not None
    assert "units_per_week" not in res.output
    assert res.details.get("empty") is True


def test_registry_keys_match_implementation_names(ontology_service):
    # Every reader tool the role view exposes must bind to a registered callable.
    declared = {
        t.body.implementation
        for role in ("supply_planning", "demand_planning")
        for t in ontology_service.tools_available_to(role)
    }
    registry = reader_tools.default_registry()
    assert "query_baseline_demand" in declared
    assert declared <= set(registry)
