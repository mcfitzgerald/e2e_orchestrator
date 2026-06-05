"""Phase A3 — balanced scenario variants (structural, no LLM).

Closes the open Phase-A live item: the canonical capacity conflict is determinate
(only NJ-L1 makes the flagship, and it's maxed), so every live run correctly
converges to request_promo_revision. The balanced variants add a grounded second
lever so that, LIVE, (a) the resolution can vary by seed and (b) plant_scheduler
fires. Those are LIVE properties — here we pin only the structural frame:

  • the two scenarios are registered and load the BALANCED world fixture;
  • on that fixture query_plants_for_sku surfaces CA-L1 (with residual headroom)
    as a flagship alternative — the mechanism that makes internal re-plan viable —
    while the CANONICAL scenario still sees only the maxed NJ-L1 (no leak);
  • the locked variant wires the contractually-locked promo responder (K2);
  • both variants run end-to-end in stub mode, and the locked stub resolves
    through plant_scheduler (true to the forced lever).

We deliberately do NOT assert a particular LIVE lever — the live choice is agency.
"""
from __future__ import annotations

import pytest

from e2e_orchestrator.application.reader_tools import query_plants_for_sku
from e2e_orchestrator.runtime.main import (
    SCENARIOS,
    build_scenario_orchestrator,
    run_scenario,
)

SHORTFALL = 1500
BALANCED = "capacity-resolution-balanced"
LOCKED = "capacity-resolution-locked"


def test_variants_registered():
    assert BALANCED in SCENARIOS
    assert LOCKED in SCENARIOS
    # Both pin the balanced world fixture via the generic spec key.
    assert SCENARIOS[BALANCED]["world_state"].name == "world_state_balanced.yaml"
    assert SCENARIOS[LOCKED]["world_state"].name == "world_state_balanced.yaml"


@pytest.mark.parametrize("scenario", [BALANCED, LOCKED])
def test_variant_loads_balanced_fixture(scenario):
    """The threaded world_state_path reaches the orchestrator: CA-L1 reads as a
    flagship line with free residual >= the shortfall."""
    orch, *_ = build_scenario_orchestrator(scenario, mode="stub")
    load = orch.world_state.query_line_load("PLANT-CA", "CA-L1", 140, 146)
    assert "TP-FLAG-6OZ" in load.scheduled_skus
    free = load.available - load.scheduled_units
    assert free >= SHORTFALL, f"CA-L1 free residual {free} < shortfall {SHORTFALL}"


def test_balanced_surfaces_alt_line_canonical_does_not():
    """The load-bearing distinction: query_plants_for_sku (the reader the live
    agent uses to find alternatives) returns CA-L1 on the balanced fixture but
    only the maxed NJ-L1 on the canonical one — so the variant, not a prompt
    nudge, is what opens the internal-re-plan lever."""
    orch_canon, *_ = build_scenario_orchestrator("capacity-resolution", mode="stub")
    orch_bal, *_ = build_scenario_orchestrator(BALANCED, mode="stub")

    canon = query_plants_for_sku({"sku": "TP-FLAG-6OZ"}, orch_canon.world_state)
    bal = query_plants_for_sku({"sku": "TP-FLAG-6OZ"}, orch_bal.world_state)

    assert canon.details["line_codes"] == ["NJ-L1"]
    assert set(bal.details["line_codes"]) == {"NJ-L1", "CA-L1"}


def test_nj_l1_conflict_invariant_survives_on_variant():
    """The variant adds an alternative; it does not rescale the conflict. NJ-L1
    still reads 5000 residual / 3500 scheduled / 1500 shortfall on the balanced
    fixture."""
    orch, *_ = build_scenario_orchestrator(BALANCED, mode="stub")
    nj = orch.world_state.query_line_load("PLANT-NJ", "NJ-L1", 140, 146)
    assert nj.available == 5000
    assert nj.scheduled_units == 3500
    # promo (3x on the 1500 flag baseline) -> 6500 -> shortfall 1500
    assert 6500 - nj.available == SHORTFALL


def test_locked_responder_closes_the_promo_lever():
    """K2 is a responder, not a fixture flip: the locked scenario wires a
    check_promo_flexibility responder reporting contractually_locked + no
    timing/volume movement, so viable_promo_renegotiation fails for the agent."""
    spec = SCENARIOS[LOCKED]
    resp = spec["responders"]["customer_development"]["check_promo_flexibility"]
    payload = resp[0].kwargs["response"]
    assert payload["commitment_status"] == "contractually_locked"
    assert payload["can_shift_timing"] is False
    assert payload["can_reduce_volume"] is False
    # The balanced (open) scenario keeps the aligned responder for contrast.
    open_resp = SCENARIOS[BALANCED]["responders"]["customer_development"]["check_promo_flexibility"]
    assert open_resp[0].kwargs["response"]["commitment_status"] == "aligned"


@pytest.mark.asyncio
async def test_both_variants_run_end_to_end_stub():
    """Both scenarios build + seed + run cleanly in stub mode; the locked variant
    routes through plant_scheduler (true to the forced internal lever)."""
    bal = await run_scenario(BALANCED, mode="stub")
    locked = await run_scenario(LOCKED, mode="stub")

    assert bal["events_appended"] > 0
    assert locked["events_appended"] > 0
    # Locked stub forces re_request_production -> plant_scheduler.
    assert "plant_scheduler" in locked["roles_invoked"]
