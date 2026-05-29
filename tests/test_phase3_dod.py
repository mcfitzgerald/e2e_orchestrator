"""Phase 3 Definition-of-Done assertion.

The DoD (from the ontology repo's `plan_of_attack.md` §3) reads:

  A single command runs the full happy path. The trace shows three role agents
  acting, no domain-specific code per role, and routing decisions traceable to
  ontology lookups visible in the tool-call traces.

The path (Scenes 1-3 of the promo whiplash narrative):

  promo_plan_aligned → submit_promo_plan → demand_planning
    → forecast_revised → submit_supply_request → supply_planning
    → production_assigned → request_production → production_planning

We exercise it with `ScriptedAgentHandler`s for the three internal roles — same
as Phase 2, this asserts the orchestrator surface end-to-end without an LLM key.
The contract being verified is the orchestrator's: an LLM sits behind the same
`RoleHandler.invoke` surface as the script, so the structural guarantees here
(deterministic routing, idempotency keys, three agents acting, lookups in the
trace) hold identically for the live run.

The scripts and the boundary seeder are imported from `runtime.main` so the
stub CLI path and this test exercise exactly the same wiring — no drift.
"""
from __future__ import annotations

from pathlib import Path

from e2e_orchestrator.application.agent_factory import (
    ScriptedAgentHandler,
    build_default_handler_factory,
)
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.boundary.customer_development import emit_promo_plan_aligned
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS


def _build_orch(ontology_service, backend):
    """Wire the promo scenario in stub mode exactly as the runtime does:
    scripted handlers for the three roles on the path, factory defaults for
    everything else, no hand-special-cased supply_planning override."""
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


async def test_phase3_three_role_happy_path(ontology_service, tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "phase3.jsonl")
    orch = _build_orch(ontology_service, backend)

    result = await emit_promo_plan_aligned(orch)
    assert result.events_appended > 0
    events = backend.read_events()
    kinds = [e.kind for e in events]

    # 1. The promo entered at the customer_development boundary as a TradePromotion.
    ingress = [e for e in events if e.kind == EventKind.BOUNDARY_INGRESS]
    assert len(ingress) == 1
    assert ingress[0].payload["flow"] == "submit_promo_plan"
    assert ingress[0].payload["quantum_class"] == "TradePromotion"
    assert ingress[0].payload["source_role"] == "customer_development"
    assert ingress[0].payload["target_role"] == "demand_planning"
    assert ingress[0].payload["trigger_event"] == "promo_plan_aligned"

    # 2. THREE role agents acted — the core Phase 3 claim.
    starts = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED]
    roles_invoked = [e.payload["role"] for e in starts]
    assert roles_invoked == ["demand_planning", "supply_planning", "production_planning"], roles_invoked

    # 3. Routing decisions are traceable to ontology lookups: every role on the
    #    path read its view (or a flow's axioms) before acting.
    lookups = [
        tc.payload for tc in events
        if tc.kind == EventKind.AGENT_TOOL_CALL and tc.payload["tool"] == "read_ontology"
    ]
    roles_that_looked_up = {l["role"] for l in lookups}
    assert {"demand_planning", "supply_planning", "production_planning"} <= roles_that_looked_up

    # 4. Two handoffs executed, in order, with the deterministic routing the
    #    ontology declares — no LLM chose these targets.
    executed = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED]
    routes = [(e.payload["flow"], e.payload["source_role"], e.payload["target_role"]) for e in executed]
    assert routes == [
        ("submit_supply_request", "demand_planning", "supply_planning"),
        ("request_production", "supply_planning", "production_planning"),
    ], routes
    assert [e.payload["quantum_class"] for e in executed] == ["SupplyRequest", "ProductionRequest"]

    # 5. Stable idempotency keys on every handoff firing (replay-safe).
    keys = [e.idempotency_key for e in executed]
    assert keys[0].startswith("handoff:demand_planning:supply_planning:submit_supply_request:")
    assert keys[1].startswith("handoff:supply_planning:production_planning:request_production:")

    # 6. An axiom-evaluation event is written for each handoff (clean trace even
    #    though no axiom blocks on the happy path — Phase 4 exercises blocking).
    axiom_events = [e for e in events if e.kind == EventKind.AXIOM_EVALUATED]
    assert len(axiom_events) == 2
    assert all(e.payload["ok"] is True for e in axiom_events)

    # 7. JSONL on disk matches the in-memory log — replay reads from disk.
    on_disk = (tmp_path / "phase3.jsonl").read_text().strip().splitlines()
    assert len(on_disk) == len(events)
