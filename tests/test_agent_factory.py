"""Agent factory: confirms boundary roles get BoundaryStubHandler, non-boundary
roles get LlmAgentHandler in 'llm' mode, and stub mode forces InternalStubHandler.

These assertions enforce the design rule that LLM-vs-stub-vs-boundary dispatch
is purely a function of (ontology declaration, mode flag) — never per-role code."""
from __future__ import annotations

from e2e_orchestrator.application.agent_factory import (
    BoundaryStubHandler,
    InternalStubHandler,
    LlmAgentHandler,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.durability import JsonlBackend


def _make_orch(service, mode: str = "llm", overrides=None) -> Orchestrator:
    factory = build_default_handler_factory(service, mode=mode, overrides=overrides)
    return Orchestrator(service=service, backend=JsonlBackend(), handler_factory=factory)


def test_boundary_role_gets_boundary_stub(ontology_service):
    orch = _make_orch(ontology_service, mode="llm")
    handler = orch._get_handler("demand_sensing")
    assert isinstance(handler, BoundaryStubHandler)


def test_non_boundary_in_llm_mode_gets_llm_handler(ontology_service):
    orch = _make_orch(ontology_service, mode="llm")
    handler = orch._get_handler("demand_planning")
    assert isinstance(handler, LlmAgentHandler)


def test_non_boundary_in_stub_mode_gets_internal_stub(ontology_service):
    orch = _make_orch(ontology_service, mode="stub")
    handler = orch._get_handler("demand_planning")
    assert isinstance(handler, InternalStubHandler)


def test_override_wins_over_mode(ontology_service):
    overrides = {"demand_planning": InternalStubHandler("demand_planning", orch=None)}
    orch = _make_orch(ontology_service, mode="llm", overrides=overrides)
    handler = orch._get_handler("demand_planning")
    assert handler is overrides["demand_planning"]
