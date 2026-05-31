"""Runaway-loop trips — deterministic, in-code safety limits.

Billing data lags ~a day, so these are the real protection against a runaway
agent/flow. Three layers (see CHANGELOG 2026-05-31):
  - Layer 1 (per-invocation LLM-call cap) lives in agent_factory via ADK's
    RunConfig(max_llm_calls=...); it only fires against a live model, so it's
    not exercised here (stub mode makes no LLM calls).
  - Layer 3 (max agent invocations per run) and Layer 2 (max cumulative tokens
    per run) live in the orchestrator and are exercised below without an LLM.

Both orchestrator guards emit a RUNAWAY_GUARD_TRIPPED event and raise
RunawayGuardError, halting the run with the reason visible in the trace.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from e2e_orchestrator.application.agent_factory import (
    ScriptedAgentHandler,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator, RunawayGuardError
from e2e_orchestrator.boundary.customer_development import emit_promo_plan_aligned
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS


def _build_promo_orch(ontology_service, backend):
    """Promo 3-role happy path in stub mode (same wiring as test_phase3_dod)."""
    scripts = SCENARIOS["promo"]["scripts"]
    overrides = {
        role: ScriptedAgentHandler(role, orch=None, script=script)
        for role, script in scripts.items()
    }
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    return orch


async def test_max_invocations_guard_trips(ontology_service, tmp_path: Path, monkeypatch):
    # The promo path invokes three agents. Cap at 2 → the third dispatch trips.
    monkeypatch.setenv("E2E_MAX_INVOCATIONS", "2")
    backend = JsonlBackend(log_path=tmp_path / "runaway-inv.jsonl")
    orch = _build_promo_orch(ontology_service, backend)  # reads env in __init__

    with pytest.raises(RunawayGuardError):
        await emit_promo_plan_aligned(orch)

    events = backend.read_events()
    trips = [e for e in events if e.kind == EventKind.RUNAWAY_GUARD_TRIPPED]
    assert len(trips) == 1
    assert trips[0].payload["guard"] == "max_invocations"
    assert trips[0].payload["limit"] == 2
    # Halted on the 3rd dispatch → exactly two invocations actually started.
    starts = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED]
    assert len(starts) == 2


class _BigUsageHandler:
    """Minimal handler whose invoke reports more tokens than the run ceiling."""

    def __init__(self, role: str):
        self.role = role

    async def invoke(self, ctx, message):
        return {"kind": "llm", "role": self.role, "usage": {"total_tokens": 10_000_000}}


async def test_max_run_tokens_guard_trips(ontology_service, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("E2E_MAX_RUN_TOKENS", "1000")  # any real usage blows past this
    backend = JsonlBackend(log_path=tmp_path / "runaway-tok.jsonl")
    overrides = {"demand_planning": _BigUsageHandler("demand_planning")}
    factory = build_default_handler_factory(ontology_service, overrides=overrides, mode="stub")
    orch = Orchestrator(service=ontology_service, backend=backend, handler_factory=factory)

    with pytest.raises(RunawayGuardError):
        await emit_promo_plan_aligned(orch)

    trips = [e for e in backend.read_events() if e.kind == EventKind.RUNAWAY_GUARD_TRIPPED]
    assert len(trips) == 1
    assert trips[0].payload["guard"] == "max_run_tokens"
    assert trips[0].payload["run_tokens"] >= 10_000_000
