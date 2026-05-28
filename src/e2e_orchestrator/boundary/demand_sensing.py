"""Boundary ingress simulator for `demand_sensing`.

`demand_sensing` is a boundary role declared in the ontology. In production it
stands in for an anomaly-detection pipeline (POS streams, EDI feeds, social
listening). In the POC it is externally simulated — we construct a
`DemandAnomaly` payload and dispatch the `raise_demand_anomaly` ingress flow.
"""
from __future__ import annotations

from typing import Any

from ..application.orchestrator import DispatchResult, Orchestrator


async def emit_demand_anomaly(
    orch: Orchestrator,
    *,
    anomaly_id: str = "anom-demo-0001",
    sku: str = "sku-toothpaste-6oz",
    detected_day: int = 42,
    departure_units: float = 1500.0,
    severity_score: float = 0.85,
    source_system: str = "pos_stream_simulated",
) -> DispatchResult:
    """Build a `DemandAnomaly` quantum and dispatch the `raise_demand_anomaly`
    ingress flow. Returns the dispatch result so the caller can inspect the
    event log size after the run."""
    payload: dict[str, Any] = {
        "anomaly_id": anomaly_id,
        "sku": sku,
        "detected_day": detected_day,
        "departure_units": departure_units,
        "severity_score": severity_score,
        "source_system": source_system,
    }
    return await orch.dispatch_boundary_ingress("raise_demand_anomaly", payload)
