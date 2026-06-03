"""MCP front door (Phase 7) — the first realized external edge.

Exposes the orchestrator system through the Model Context Protocol so an
external client can drop a signal into the supply chain (write side = a command)
and read back what happened (read side = events/state, read-only). The mapping is
exact and load-bearing: **MCP tools ↔ commands, MCP resources ↔ events.**

The front door is a *dumb adapter*. It validates I/O and forwards; all routing,
validation, axioms, and FSM evaluation stay in the deterministic backbone
(`application/`). It must never:

  1. call an LLM to decide routing (routing stays in `flow_router`),
  2. dispatch downstream itself or write events behind the orchestrator's back
     (every external action goes through `dispatch_boundary_ingress`; reads come
     from the event log),
  3. carry per-role code (`ingress_quantum(flow, payload)` is generic — no
     `if role == ...`, no per-role tool registration),
  4. model policy or add ontology fields (transport only — §2 untouched).

`core.OrchestratorFrontDoor` holds the transport-agnostic logic (and is what the
tests exercise against the real orchestrator seams); `server.py` is the thin
FastMCP wiring + the `e2e-mcp` entry point.
"""
from __future__ import annotations

from .core import IngressResult, OrchestratorFrontDoor, RunRecord

__all__ = ["OrchestratorFrontDoor", "IngressResult", "RunRecord"]
