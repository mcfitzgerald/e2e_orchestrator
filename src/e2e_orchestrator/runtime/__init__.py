"""Runtime — wires the orchestrator, the durability backend, the agent factory,
and the boundary simulator together. The Phase 2 entrypoint runs the
DemandAnomaly → demand_planning → SupplyRequest → supply_planning round trip."""
