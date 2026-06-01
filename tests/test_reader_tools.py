"""Reader-tool unit tests (Phase 5).

The four `scont:Tool` implementations read world state and return real entities,
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
    # The at-risk Bullseye commitment (mabd 130) and the Kroger one (mabd 132)
    # fall in-window; nothing for other SKUs leaks in.
    assert ids == {"COM-BUL-SEC-Q2", "COM-KRG-SEC-Q2"}
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


def test_registry_keys_match_implementation_names(ontology_service):
    # Every reader tool the role view exposes must bind to a registered callable.
    declared = {t.body.implementation for t in ontology_service.tools_available_to("supply_planning")}
    registry = reader_tools.default_registry()
    assert declared <= set(registry)
