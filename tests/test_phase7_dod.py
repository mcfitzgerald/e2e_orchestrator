"""Phase 7 Definition-of-Done (orchestrator Seed B — the MCP front door).

  DoD: the orchestrator system is reachable through MCP as a generic
  `ingress + read` adapter — an external client drops a signal in and reads back
  what happened — with the four boundary constraints intact (no LLM in routing;
  commands→events; no per-role code; §2 untouched), idempotency held at the wire.

This pins, deterministically (stub mode, no LLM):

  • DoD #2 — a standard MCP client drives the promo-whiplash demo end-to-end
    *through MCP*: `ingress_quantum(submit_promo_plan, …)` then read
    `narrative://<run_id>` reproduces the full Scene 1→6 story. Exercised both at
    the front-door core and through a real `ClientSession` over the SDK's
    in-memory transport (DoD #4 — handlers tested against the real orchestrator
    seams, not mocks).
  • DoD #3 — disciplines held: routing stays in `flow_router` (the server holds
    no router/LLM); commands→events (the run is reconstructed purely from the
    event log); a retried `ingress_quantum` with the same idempotency key does
    not double-fire; the server tool signature is generic `(flow, payload)` with
    no per-role branching; no policy/ontology fields are introduced.
  • DoD #5 — `roleview://<role>` returns the same bytes as
    `render_role_view(role).as_agent_prompt()`.

The live `--mode llm` reproduction (the same `ingress_quantum` driving real
LlmAgents through the protocol) is gated on explicit permission; the structural
frame it rests on is pinned here.
"""
from __future__ import annotations

import inspect
import json
from datetime import timedelta

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect
from mcp.types import AnyUrl

from e2e_orchestrator.mcp.core import OrchestratorFrontDoor, UnknownRunError
from e2e_orchestrator.mcp.server import build_server

# The demo Scene-1 TradePromotion the customer_development boundary simulator
# emits; an external MCP client supplies it directly via ingress_quantum.
_PROMO_PAYLOAD = {
    "promo_id": "PROMO-MGM-FLAG-2026Q2",
    "sku": "TP-FLAG-6OZ",
    "retailer": "MEGALOMART",
    "volume_uplift_factor": 3.0,
    "promo_start_day": 142,
    "promo_end_day": 156,
    "commitment_status": "aligned",
}

RESOLUTION_FLOWS = {"shift_to_coman", "re_request_production", "request_promo_revision",
                    "allocate_partial_fill"}
CONTEXT_QUERIES = {"check_otif_exposure", "check_promo_flexibility", "check_coman_availability"}


@pytest.fixture
def door(ontology_yaml_path) -> OrchestratorFrontDoor:
    """A stub-mode front door over the full-demo world. No trace files written
    (runs_dir=None) — runs live in the in-memory registry."""
    return OrchestratorFrontDoor(
        mode="stub", world="full-demo", ontology_yaml=ontology_yaml_path, runs_dir=None
    )


# ---------------------------------------------------------------------------
# DoD #2 — the demo runs end-to-end through the generic boundary edge.
# ---------------------------------------------------------------------------


async def test_ingress_quantum_drives_full_narrative(door):
    """ingress_quantum(submit_promo_plan, payload) → the full promo-whiplash
    narrative plays out behind the door, and the run is addressable."""
    result = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD, idempotency_key="demo-1")
    assert result.status == "accepted"
    assert result.run_id and result.quantum_id
    assert result.trace == f"trace://{result.run_id}"
    assert result.narrative == f"narrative://{result.run_id}"

    rec = door.get_run(result.run_id)
    kinds = [e["kind"] for e in rec.events]
    # Scene 1 ingress, Scene 4 floor blocks + auto-reroutes, Scene 5 context
    # assembly (three queries + a surfaced decision), Scene 6 a resolution.
    assert kinds[0] == "boundary_ingress" or "boundary_ingress" in kinds
    assert "handoff_blocked" in kinds
    assert "decision_surfaced" in kinds
    queried = {e["payload"]["flow"] for e in rec.events if e["kind"] == "query_requested"}
    assert CONTEXT_QUERIES <= queried
    resolved = {e["payload"]["flow"] for e in rec.events if e["kind"] == "handoff_executed"} & RESOLUTION_FLOWS
    assert resolved, "a resolution flow should have fired"


async def test_narrative_resource_tells_the_story(door):
    """narrative://<run_id> reproduces the Scene 1→6 story from the event log."""
    result = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD)
    narrative = door.read_narrative(result.run_id)
    assert "SCENE 1" in narrative
    assert "DETERMINISTIC FLOOR" in narrative  # Scene 4
    assert "decision surfaced" in narrative      # Scene 5/6
    assert "OUTCOME: capacity conflict resolved" in narrative


async def test_decisions_resource_returns_surfaced_decisions(door):
    result = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD)
    decisions = json.loads(door.read_decisions(result.run_id))
    assert len(decisions) == 1
    surfaced = decisions[0]
    assert surfaced["playbook"] == "resolve_capacity_conflict"
    # The options carry no ranking — §2: a surfaced decision is choices, not a
    # preference order.
    assert set(surfaced["options"]) == RESOLUTION_FLOWS


async def test_trace_resource_is_the_event_log(door):
    """trace://<run_id> is the JSONL event log — reads come from events, and the
    run is fully reconstructable from it (commands→events / CQRS)."""
    result = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD)
    trace = door.read_trace(result.run_id)
    lines = [json.loads(ln) for ln in trace.splitlines() if ln.strip()]
    assert lines, "trace should be non-empty JSONL"
    assert all({"seq", "kind", "payload"} <= set(ev) for ev in lines)
    assert lines[0]["kind"] == "boundary_ingress"


# ---------------------------------------------------------------------------
# DoD #3 — disciplines held at the boundary.
# ---------------------------------------------------------------------------


async def test_idempotent_ingress_does_not_double_fire(door):
    """A retried ingress with the same idempotency key returns the SAME run and
    does not dispatch a second time (no new run, no second boundary_ingress)."""
    first = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD, idempotency_key="retry-key")
    runs_after_first = set(door.list_runs())
    second = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD, idempotency_key="retry-key")

    assert second.replayed is True
    assert second.run_id == first.run_id
    assert second.quantum_id == first.quantum_id
    assert set(door.list_runs()) == runs_after_first, "retry must not mint a new run"
    # Exactly one boundary_ingress across the (single) run — the downstream did
    # not re-fire.
    rec = door.get_run(first.run_id)
    ingresses = [e for e in rec.events if e["kind"] == "boundary_ingress"]
    assert len(ingresses) == 1


async def test_idempotency_key_yields_stable_quantum_id(door):
    """The wire idempotency key is folded into a stable quantum_id so the
    orchestrator's own `boundary:<flow>:<qid>` discipline is deterministic across
    retries (the in-run half of the discipline)."""
    a = await door.ingress("submit_promo_plan", _PROMO_PAYLOAD, idempotency_key="same")
    door2 = OrchestratorFrontDoor(mode="stub", world="full-demo", runs_dir=None)
    b = await door2.ingress("submit_promo_plan", _PROMO_PAYLOAD, idempotency_key="same")
    # Different front-door instances (fresh registries) → different runs, but the
    # derived quantum_id is identical because it's a pure function of the key.
    assert a.quantum_id == b.quantum_id


async def test_front_door_holds_no_router_or_llm():
    """No LLM in routing, no per-role code: the front-door surface is generic.
    The MCP tool signature is `(flow, payload, idempotency_key)` and the core
    forwards — it owns no FlowRouter-as-decider and no role enumeration."""
    # The public write surface is exactly (flow, payload, idempotency_key).
    sig = inspect.signature(OrchestratorFrontDoor.ingress)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["flow", "payload", "idempotency_key"]

    # No per-role branching / role names baked into the front door modules.
    import e2e_orchestrator.mcp.core as core_mod
    import e2e_orchestrator.mcp.server as server_mod

    for mod in (core_mod, server_mod):
        src = inspect.getsource(mod)
        for role in ("demand_planning", "supply_planning", "production_planning"):
            assert role not in src, f"per-role name {role!r} leaked into {mod.__name__}"


async def test_internal_flow_rejected_at_boundary(door):
    """The inbound edge only accepts flows entering from a declared boundary
    role; an internal flow is rejected with the system's normal vocabulary, not a
    bespoke MCP error. (Generic — derived from `is_boundary`, no role names.)"""
    result = await door.ingress(
        "submit_supply_request",
        {"request_id": "x", "sku": "y", "volume": 1, "required_by": 1, "source_signal_ref": "z"},
    )
    assert result.status == "rejected"
    assert "not_a_boundary_ingress" in result.reason


async def test_unknown_flow_rejected(door):
    result = await door.ingress("no_such_flow", {})
    assert result.status == "rejected"
    assert "unknown_flow" in result.reason


async def test_malformed_payload_rejected_with_quantum_rejected(door):
    """A malformed ingress is rejected through the *quantum validator* — the same
    `quantum_rejected` event the rest of the system uses — not a bespoke error."""
    result = await door.ingress("submit_promo_plan", {"promo_id": "only-this"}, idempotency_key="bad")
    assert result.status == "rejected"
    rec = door.get_run(result.run_id)
    assert any(e["kind"] == "quantum_rejected" for e in rec.events)


# ---------------------------------------------------------------------------
# DoD #5 — roleview is a faithful read of the Ontology Service.
# ---------------------------------------------------------------------------


async def test_roleview_is_byte_faithful(door):
    for role in ("demand_planning", "supply_planning", "production_planning", "customer_development"):
        got = door.read_roleview(role)
        expected = door.service.render_role_view(role).as_agent_prompt()
        assert got == expected, f"roleview://{role} drifted from render_role_view"


async def test_roleview_unknown_role_raises(door):
    with pytest.raises(UnknownRunError):
        door.read_roleview("not_a_role")


# ---------------------------------------------------------------------------
# DoD #4 — through a real MCP ClientSession (in-memory transport), real seams.
# ---------------------------------------------------------------------------


async def test_end_to_end_through_mcp_client(door):
    """A standard MCP client (over the SDK's in-memory transport) lists the
    tools/resources, calls ingress_quantum, and reads narrative://<run_id> —
    reproducing the CLI demo through the protocol instead of `e2e-orchestrator
    --scenario`."""
    server = build_server(door)
    async with connect(server, read_timeout_seconds=timedelta(seconds=60)) as session:
        await session.initialize()

        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"ingress_quantum", "run_demo_scenario"} <= tools

        templates = {t.uriTemplate for t in (await session.list_resource_templates()).resourceTemplates}
        assert {"trace://{run_id}", "narrative://{run_id}", "decisions://{run_id}", "roleview://{role}"} <= templates

        call = await session.call_tool(
            "ingress_quantum",
            {"flow": "submit_promo_plan", "payload": _PROMO_PAYLOAD, "idempotency_key": "mcp-e2e"},
        )
        out = json.loads(call.content[0].text)
        assert out["status"] == "accepted"

        narrative_res = await session.read_resource(AnyUrl(out["narrative"]))
        narrative = narrative_res.contents[0].text
        assert "SCENE 1" in narrative
        assert "OUTCOME: capacity conflict resolved" in narrative

        # roleview resource is byte-faithful through the protocol too (DoD #5).
        rv = await session.read_resource(AnyUrl("roleview://supply_planning"))
        assert rv.contents[0].text == door.service.render_role_view("supply_planning").as_agent_prompt()


async def test_run_demo_scenario_tool(door):
    """The convenience wrapper reproduces a canned scenario through its own
    seeder and registers the run."""
    result = await door.run_demo("full-demo", mode="stub")
    assert result.status == "accepted"
    narrative = door.read_narrative(result.run_id)
    assert "OUTCOME: capacity conflict resolved" in narrative
