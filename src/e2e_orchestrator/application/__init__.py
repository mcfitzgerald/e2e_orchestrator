"""Application layer — the interesting code: agent factory, prompt rendering,
flow router, quantum validation, axiom evaluation, FSM tracking, decision
surface assembly. Domain-aware via the ontology; never domain-coded."""
from .orchestrator import (
    DispatchResult,
    HandoffResult,
    Orchestrator,
    QueryResult,
)

__all__ = ["DispatchResult", "HandoffResult", "Orchestrator", "QueryResult"]
