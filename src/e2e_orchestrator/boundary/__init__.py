"""Boundary roles — scripted, never LLM-backed.

Boundary roles (`is_boundary: true` in the ontology) sit outside the supply
chain proper. They originate signals (demand_sensing, customer_development) or
accept handoffs that exit the system (co_manufacturing). The orchestrator's
boundary module supplies:

  - Ingress simulators that construct a typed quantum and call
    `orchestrator.dispatch_boundary_ingress`.
  - Stub responders for boundary roles that receive handoffs/queries (this
    role-handler shape lives in `application.agent_factory.BoundaryStubHandler`).
"""
from .customer_development import emit_promo_plan_aligned
from .demand_sensing import emit_demand_anomaly

__all__ = ["emit_demand_anomaly", "emit_promo_plan_aligned"]
