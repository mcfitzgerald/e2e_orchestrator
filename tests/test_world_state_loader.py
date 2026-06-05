"""World-state loader tests.

The loader reads `world_state.yaml`, validates every instance against its
declared class via the same SchemaView-driven validator the orchestrator uses,
and exposes generic typed queries. These tests pin the conflict math (the
deterministic Phase 4 target in the fixture header) and the grounding signal
(a missing entity resolves to None, which the axiom tools turn into
`unknown_entity`)."""
from __future__ import annotations

import pytest

from e2e_orchestrator.world_state import WorldState, WorldStateValidationError


def test_instances_validate_and_load(world_state: WorldState):
    assert len(world_state.instances_of("SKU")) == 5
    assert len(world_state.instances_of("ProductionLine")) == 4
    assert len(world_state.instances_of("Supplier")) == 6
    assert len(world_state.instances_of("RetailerCommitment")) == 8
    assert len(world_state.instances_of("TradePromotion")) == 2


def test_typed_accessors(world_state: WorldState):
    line = world_state.get_production_line("PLANT-NJ", "NJ-L1")
    assert line is not None
    # Residual-capacity model: a real, loaded line — 50k total, 90% committed.
    assert line.capacity_total == 50000
    assert line.committed_load == 45000
    assert line.plant_code == "PLANT-NJ"

    sku = world_state.get_sku("TP-FLAG-6OZ")
    assert sku is not None and sku.category == "oral_care"

    supplier = world_state.get_supplier("SUP-MENTHOL-002")
    assert supplier is not None and supplier.lead_time_days == 28


def test_clock(world_state: WorldState):
    assert world_state.today() == 100


def test_grounding_missing_entity_returns_none(world_state: WorldState):
    # The hallucinated entities from the old Phase 3 stub — absent here.
    assert world_state.get_production_line("PLANT-OH1", "line-oh1-a") is None
    # Real line code but wrong plant → still None (plant must match).
    assert world_state.get_production_line("PLANT-OH1", "NJ-L1") is None
    assert world_state.get_sku("sku-toothpaste-6oz") is None
    assert world_state.get_supplier("SUP-NOPE") is None


def test_line_load_conflict_math(world_state: WorldState):
    """The fixture header's Scene 4 math, RESIDUAL-CAPACITY model: NJ-L1 runs
    45000/50000 committed (90% utilized) → 5000 residual available; the two
    toothpaste SKUs use 3500 of that residual at week 140. Reframe, not rescale:
    `available` (5000) reproduces the old toy "rated capacity 5000" exactly."""
    load = world_state.query_line_load("PLANT-NJ", "NJ-L1", 140, 146)
    assert load.scheduled_units == 3500
    assert load.capacity_total == 50000
    assert load.committed_load == 45000
    assert load.available == 5000           # residual = 50000 − 45000
    assert load.utilization == 0.90
    assert set(load.scheduled_skus) == {"TP-FLAG-6OZ", "TP-SEC-6OZ"}

    # Full 3x uplift (3000 incremental) overflows the residual: 3500 + 3000 = 6500 > 5000.
    assert load.scheduled_units + 3000 > load.available
    # The happy-path slice (1200) fits the residual: 3500 + 1200 = 4700 <= 5000.
    assert load.scheduled_units + 1200 <= load.available


def test_line_load_is_weekly_grained(world_state: WorldState):
    # A two-week window sums both scheduled weeks (140 + 147); the weekly
    # capacity comparison is meant for a single-week window.
    two_week = world_state.query_line_load("PLANT-NJ", "NJ-L1", 140, 153)
    assert two_week.scheduled_units == 7000


def test_commitments_for_skus_generic_filter(world_state: WorldState):
    ids = {c.commitment_id for c in world_state.commitments_for_skus(["TP-SEC-6OZ"])}
    assert ids == {"COM-BUL-SEC-Q2", "COM-GRN-SEC-Q2"}


def test_strict_validation_rejects_bad_instance(ontology_service, tmp_path):
    bad = tmp_path / "bad_world.yaml"
    # ProductionLine.capacity_total / committed_load are required + integer; omit them.
    bad.write_text(
        "production_lines:\n"
        "  - line_code: X-1\n"
        "    plant_code: PLANT-X\n"
        "    active: true\n",
        encoding="utf-8",
    )
    sv = ontology_service.ontology.schema_view
    with pytest.raises(WorldStateValidationError):
        WorldState.load(bad, sv, strict=True)
