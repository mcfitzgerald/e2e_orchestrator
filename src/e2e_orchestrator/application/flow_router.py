"""Flow router — pure ontology lookup, no LLM.

Given a flow name, resolves the FlowSummary (source/target roles, quantum class,
trigger event, returns class, lifecycle ref, axioms). Single source of truth for
routing decisions; the orchestrator depends on this for every dispatch.
"""
from __future__ import annotations

from ontology_service import FlowSummary, OntologyService
from ontology_service.service import _to_flow_summary  # type: ignore[attr-defined]


class FlowNotFoundError(KeyError):
    """The named flow does not exist in the ontology."""


class FlowRouter:
    def __init__(self, service: OntologyService):
        self._svc = service

    def resolve(self, flow_name: str) -> FlowSummary:
        flow = self._svc.ontology.get_flow(flow_name) if hasattr(self._svc.ontology, "get_flow") else None
        if flow is None:
            flow = self._svc.ontology.flows.get(flow_name)
        if flow is None:
            raise FlowNotFoundError(flow_name)
        # Phase 1.5 of the ontology service added quantum + returns schema
        # rendering on FlowSummary; the adapter now needs the SchemaView.
        return _to_flow_summary(flow, self._svc.ontology.schema_view)
