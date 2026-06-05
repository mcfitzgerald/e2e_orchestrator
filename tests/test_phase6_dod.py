"""Phase 6 Definition-of-Done (ontology repo `plan_of_attack.md` §6).

  DoD: A single command runs the full promo-whiplash narrative end-to-end. The
  trace tells the story. The narrative document and the trace agree.

This pins, deterministically (scripted, no LLM):

  • the FULL narrative from ONE seed — Scene 1 (promo ingress) → Scene 4
    (deterministic floor blocks the over-capacity request and auto-reroutes) →
    Scene 5 (context assembly: three queries + surfaced decision) → Scene 6
    (a resolution + plan_fulfillment re-convergence) → clean terminal;
  • the demonstrated resolution paths, including allocate_partial_fill (the
    holding-move self-flow that terminates cleanly without re-entering the
    playbook), re_request_production's revised quantum PASSING the same capacity
    floor that blocked the original (the floor accepts the corrected plan, not just
    rejects the bad one) via plant_scheduler, and request_promo_revision routing
    through trade and on to the customer_development boundary;
  • deterministic orchestration replay (same seed → identical structural trace);
  • the trace renderer producing the Scene 1→6 narrative, agreeing with the run.

The live two-seed agency half (different resolutions across LLM seeds) is the
Phase 5 DoD + the captured live runs under `runs/`; here we pin the structural
frame the narrative rests on.
"""
from __future__ import annotations

from e2e_orchestrator.application.agent_factory import ScriptedAgentHandler, build_default_handler_factory
from e2e_orchestrator.application.orchestrator import Orchestrator
from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.runtime.main import SCENARIOS
from e2e_orchestrator.runtime.narrative import render_narrative
from e2e_orchestrator.runtime.replay import signatures_match, structural_signature

RESOLUTION_FLOWS = {"shift_to_coman", "re_request_production", "request_promo_revision",
                    "allocate_partial_fill"}
CONTEXT_QUERIES = {"check_otif_exposure", "check_promo_flexibility", "check_coman_availability"}


async def _run(service, scenario: str) -> list:
    """Run a registry scenario end-to-end in stub mode against the shared
    service, returning the event log. Mirrors how the CLI wires overrides so the
    test and the single command can't drift."""
    spec = SCENARIOS[scenario]
    scripts = {**spec.get("responders", {}), **spec["scripts"]}
    overrides = {role: ScriptedAgentHandler(role, orch=None, script=s) for role, s in scripts.items()}
    factory = build_default_handler_factory(service, overrides=overrides, mode="stub")
    backend = JsonlBackend()
    orch = Orchestrator(service=service, backend=backend, handler_factory=factory)
    for h in overrides.values():
        h._orch = orch  # type: ignore[attr-defined]
    await spec["seeder"](orch)
    return backend.read_events()


def _kinds(events) -> list[str]:
    return [e.kind for e in events]


def _flows(events, kind) -> list[str]:
    return [e.payload["flow"] for e in events if e.kind == kind]


# ---------------------------------------------------------------------------
# The full single-seed narrative (the headline DoD).
# ---------------------------------------------------------------------------


async def test_full_demo_runs_scenes_1_through_6_from_one_seed(ontology_service):
    events = await _run(ontology_service, "full-demo")
    kinds = _kinds(events)

    # Scene 1 — a single boundary ingress seeds the whole run.
    ingress = [e for e in events if e.kind == EventKind.BOUNDARY_INGRESS]
    assert len(ingress) == 1
    assert ingress[0].payload["flow"] == "submit_promo_plan"
    assert ingress[0].payload["quantum_class"] == "TradePromotion"

    # Scene 4 — the conflict is DERIVED honestly (no injection): the over-capacity
    # request_production is blocked by the line_capacity floor and auto-rerouted.
    blocked = [e for e in events if e.kind == EventKind.HANDOFF_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].payload["flow"] == "request_production"
    assert blocked[0].payload["rerouted_to"] == "escalate_capacity_conflict"
    assert any(a["name"] == "line_capacity_not_exceeded" and not a["passed"]
               for a in blocked[0].payload["failed_axioms"])
    # ...and the orchestrator (not the LLM) executed the recovery flow.
    recovery = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED
                and e.payload.get("recovery_for") == "request_production"]
    assert len(recovery) == 1
    assert recovery[0].payload["flow"] == "escalate_capacity_conflict"

    # Scene 5 — context assembly: exactly the three declared query flows, and a
    # validated surfaced decision.
    assert set(_flows(events, EventKind.QUERY_REQUESTED)) == CONTEXT_QUERIES
    decisions = [e for e in events if e.kind == EventKind.DECISION_SURFACED]
    assert len(decisions) == 1 and decisions[0].payload["validated"] is True
    # The decision never short-circuited the wait_all gate.
    assert EventKind.WAIT_ALL_UNSATISFIED not in kinds

    # Scene 6 — exactly one resolution chosen, then re-convergence via the
    # always_fires effects (capacity_resolved + plan_fulfillment). The headline
    # pick is allocate_partial_fill — the reflexive holding move, coherent with the
    # flagship co-man being gated out on facts (open_window 1000 < 1500, moq 2000).
    chosen = [f for f in _flows(events, EventKind.HANDOFF_EXECUTED) if f in RESOLUTION_FLOWS]
    assert chosen == ["allocate_partial_fill"]
    emitted = {e.payload["name"] for e in events if e.kind == EventKind.EVENT_EMITTED}
    assert "capacity_resolved" in emitted
    assert "plan_fulfillment" in _flows(events, EventKind.HANDOFF_EXECUTED)

    # Verification (a): allocate_partial_fill is a self-flow (supply_planning →
    # supply_planning) that terminates cleanly. It must NOT re-enter the
    # resolve_capacity_conflict playbook — escalate_capacity_conflict is invoked
    # exactly once and the decision surfaces exactly once (no self-handoff loop).
    alloc = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED
             and e.payload["flow"] == "allocate_partial_fill"]
    assert len(alloc) == 1
    assert alloc[0].payload["source_role"] == "supply_planning"
    assert alloc[0].payload["target_role"] == "supply_planning"
    assert alloc[0].payload["quantum_class"] == "SupplyRequest"
    escalations = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED
                   and e.payload["incoming_flow"] == "escalate_capacity_conflict"]
    assert len(escalations) == 1
    assert len(decisions) == 1  # the playbook surfaced once, not re-run on re-entry

    # Clean terminal: nothing rejected, no guard trip.
    assert EventKind.QUANTUM_REJECTED not in kinds
    assert EventKind.RUNAWAY_GUARD_TRIPPED not in kinds


# ---------------------------------------------------------------------------
# 6.1 — the two remaining resolution paths.
# ---------------------------------------------------------------------------


async def test_re_request_production_revised_quantum_passes_the_capacity_floor(ontology_service):
    """The internal-resolution path: plant_scheduler (the lever-owner per
    Session-1 D1) advances the revised ProductionRequest through
    requested→assigned, and the SAME blocking axiom that fired in Scene 4 now
    PASSES as the FSM guard — the deterministic floor accepting the corrected
    plan."""
    events = await _run(ontology_service, "resolution-internal")

    # The chosen resolution is re_request_production, routed to plant_scheduler
    # (no longer production_planning) — the role that owns the internal re-plan.
    rr = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED
          and e.payload["flow"] == "re_request_production"]
    assert len(rr) == 1
    assert rr[0].payload["target_role"] == "plant_scheduler"
    assert rr[0].payload["quantum_class"] == "ProductionRequest"
    # plant_scheduler was actually invoked to receive and re-plan it.
    received = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED
                and e.payload["role"] == "plant_scheduler"
                and e.payload["incoming_flow"] == "re_request_production"]
    assert len(received) == 1

    # The FSM guard (line_capacity_not_exceeded) is re-evaluated on the corrected
    # quantum and PASSES → requested → assigned. This is "axiom now passes".
    trans = [e for e in events if e.kind == EventKind.FSM_TRANSITIONED
             and e.payload["fsm"] == "ProductionRequestLifecycle"]
    assert len(trans) == 1
    t = trans[0].payload
    assert (t["from_state"], t["to_state"], t["trigger"]) == ("requested", "assigned", "assign")
    assert t["guard"] == "line_capacity_not_exceeded"
    assert t["guard_passed"] is True
    # The floor was NOT bypassed: no block on this path.
    assert EventKind.FSM_BLOCKED not in _kinds(events)
    assert EventKind.HANDOFF_BLOCKED not in _kinds(events)
    # Re-convergence still fires regardless of which resolution was chosen.
    assert "plan_fulfillment" in _flows(events, EventKind.HANDOFF_EXECUTED)


async def test_request_promo_revision_routes_through_trade_to_the_retailer_boundary(ontology_service):
    """The commercial path, Session-1 D1: request_promo_revision now hands to the
    internal `trade` role-owner, which confirms the promo is negotiable and then
    crosses the boundary to customer_development via negotiate_promo_with_retailer.
    This is Session-2 verification (b) — the new trade→retailer handoff routes and
    responds correctly."""
    events = await _run(ontology_service, "resolution-promo")

    # 1. The lever hands to trade (the role-owner), not straight to the boundary.
    pr = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED
          and e.payload["flow"] == "request_promo_revision"]
    assert len(pr) == 1
    assert pr[0].payload["source_role"] == "supply_planning"
    assert pr[0].payload["target_role"] == "trade"
    assert pr[0].payload["quantum_class"] == "TradePromotion"
    # trade was actually invoked to receive it.
    trade_inv = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED
                 and e.payload["role"] == "trade"
                 and e.payload["incoming_flow"] == "request_promo_revision"]
    assert len(trade_inv) == 1

    # 2. trade crosses the boundary to customer_development.
    nego = [e for e in events if e.kind == EventKind.HANDOFF_EXECUTED
            and e.payload["flow"] == "negotiate_promo_with_retailer"]
    assert len(nego) == 1
    assert nego[0].payload["source_role"] == "trade"
    assert nego[0].payload["target_role"] == "customer_development"
    assert nego[0].payload["quantum_class"] == "TradePromotion"
    # customer_development was actually invoked to receive the negotiation.
    received = [e for e in events if e.kind == EventKind.AGENT_INVOCATION_STARTED
                and e.payload["role"] == "customer_development"
                and e.payload["incoming_flow"] == "negotiate_promo_with_retailer"]
    assert len(received) == 1
    assert "plan_fulfillment" in _flows(events, EventKind.HANDOFF_EXECUTED)


async def test_paths_share_identical_context_assembly(ontology_service):
    """Same-queries / different-resolution, across the demonstrated resolution
    paths: the context-assembly query set is identical and independent of the
    choice (§2 — the playbook scaffolds judgment, it doesn't make the decision).

    The playbook offers FOUR levers; three are coherently choosable for the
    flagship conflict and demonstrated here. The fourth, shift_to_coman, is the
    gated-out lever for this conflict (open_window 1000 < 1500 needed, moq 2000) —
    correctly NOT chosen in stub; its rejection is the live-verification claim
    (Phase A §4 live half), not a structural one."""
    chosen = {}
    for scenario, expect in (("full-demo", "allocate_partial_fill"),
                             ("resolution-internal", "re_request_production"),
                             ("resolution-promo", "request_promo_revision")):
        events = await _run(ontology_service, scenario)
        assert set(_flows(events, EventKind.QUERY_REQUESTED)) == CONTEXT_QUERIES
        res = [f for f in _flows(events, EventKind.HANDOFF_EXECUTED) if f in RESOLUTION_FLOWS]
        assert res == [expect]
        chosen[scenario] = res[0]
    # Three scenarios, three distinct resolutions — identical context assembly
    # under each, the resolution choice the only thing that varies.
    assert set(chosen.values()) == {"allocate_partial_fill", "re_request_production",
                                    "request_promo_revision"}


# ---------------------------------------------------------------------------
# 6.3 — replay + trace narrative.
# ---------------------------------------------------------------------------


async def test_deterministic_orchestration_replay(ontology_service):
    """Same seed → identical structural trace (routing + axiom verdicts + FSM),
    modulo random ids. The deterministic-backbone replay guarantee."""
    a = await _run(ontology_service, "full-demo")
    b = await _run(ontology_service, "full-demo")
    assert signatures_match(a, b)
    # Sanity: the signature actually captured the load-bearing landmarks.
    sig = structural_signature(a)
    assert any(s[0] == "handoff_blocked" for s in sig)
    assert any(s[0] == "decision_surfaced" for s in sig)


async def test_trace_narrative_renders_and_agrees_with_the_run(ontology_service):
    """The renderer turns the log into the Scene 1→6 story, and the story agrees
    with the trace (DoD: 'the narrative document and the trace agree')."""
    events = await _run(ontology_service, "full-demo")
    text = render_narrative(events)

    # Every scene landmark surfaces in the narrative.
    assert "SCENE 1" in text and "boundary ingress" in text
    assert "SCENE 4" in text and "DETERMINISTIC FLOOR" in text and "line_capacity" in text
    assert "auto-reroute to escalate_capacity_conflict" in text
    assert "decision surfaced" in text and "resolve_capacity_conflict" in text
    assert "check_otif_exposure" in text and "check_coman_availability" in text
    # The narrative's stated resolution agrees with the event that recorded it.
    resolved = next(e for e in events if e.kind == EventKind.EVENT_EMITTED
                    and e.payload["name"] == "capacity_resolved")
    assert resolved.payload["payload"]["resolution"] == "allocate_partial_fill"
    assert "resolved via 'allocate_partial_fill'" in text
    assert "re-converged on the happy path" in text
