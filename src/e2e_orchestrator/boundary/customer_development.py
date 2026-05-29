"""Boundary ingress simulator for `customer_development`.

`customer_development` is a boundary role declared in the ontology. In
production it stands in for the commercial side of S&OP — the function that
negotiates trade promotions with retailers. In the POC it is externally
simulated: once a promotion has been aligned through S&OP, we construct a
`TradePromotion` quantum and dispatch the `submit_promo_plan` ingress flow,
which carries the aligned commitment across the supply chain boundary into
`demand_planning`.

Symmetric to `demand_sensing.emit_demand_anomaly` — same shape, different
boundary role, different quantum. This is the Scene 1 entry point of the promo
whiplash narrative.
"""
from __future__ import annotations

from typing import Any

from ..application.orchestrator import DispatchResult, Orchestrator


async def emit_promo_plan_aligned(
    orch: Orchestrator,
    *,
    promo_id: str = "promo-walmart-bogo-0001",
    sku: str = "sku-toothpaste-6oz",
    retailer: str = "Walmart",
    volume_uplift_factor: float = 3.0,
    promo_start_day: int = 42,
    promo_end_day: int = 56,
    commitment_status: str = "aligned",
) -> DispatchResult:
    """Build a `TradePromotion` quantum and dispatch the `submit_promo_plan`
    ingress flow. Defaults encode the demo narrative's Scene 1: a BOGO on
    Product A at Walmart, 3x baseline lift for the 2-week promo window starting
    in ~6 weeks, aligned through S&OP. Returns the dispatch result so the caller
    can inspect the event log size after the run."""
    payload: dict[str, Any] = {
        "promo_id": promo_id,
        "sku": sku,
        "retailer": retailer,
        "volume_uplift_factor": volume_uplift_factor,
        "promo_start_day": promo_start_day,
        "promo_end_day": promo_end_day,
        "commitment_status": commitment_status,
    }
    return await orch.dispatch_boundary_ingress("submit_promo_plan", payload)
