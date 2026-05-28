"""Flow router lookups — every routing decision the orchestrator makes goes
through this surface."""
from __future__ import annotations

import pytest

from e2e_orchestrator.application.flow_router import FlowNotFoundError, FlowRouter


def test_resolve_handoff_flow(ontology_service):
    router = FlowRouter(ontology_service)
    flow = router.resolve("raise_demand_anomaly")
    assert flow.source_role == "demand_sensing"
    assert flow.target_role == "demand_planning"
    assert flow.quantum == "DemandAnomaly"
    assert flow.returns is None


def test_resolve_query_flow_carries_returns(ontology_service):
    router = FlowRouter(ontology_service)
    flow = router.resolve("check_otif_exposure")
    assert flow.returns == "OTIFExposure"


def test_unknown_flow_raises(ontology_service):
    router = FlowRouter(ontology_service)
    with pytest.raises(FlowNotFoundError):
        router.resolve("nonexistent_flow")
