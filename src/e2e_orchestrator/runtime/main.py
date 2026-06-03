"""Runtime entrypoint.

Wires the durability backend (JSONL), the Ontology Service (loaded from the
sibling `e2e_ontology` repo), the agent factory (LLM by default; `--mode stub`
for no-API-key runs), and the boundary simulators. Two scenarios are wired:

  promo (Phase 3 DoD — the default; Scenes 1-3 of the promo whiplash narrative):
    submit_promo_plan → demand_planning → submit_supply_request → supply_planning
    → request_production → production_planning
    Three internal role agents act; deterministic routing throughout.

  demand-anomaly (the original Phase 2 round trip):
    raise_demand_anomaly → demand_planning → submit_supply_request → supply_planning

There are **no per-role handler overrides** in `llm` mode: every internal role
is built by the factory as an `LlmAgentHandler` whose identity comes entirely
from the rendered ontology role view. In `stub` mode each role on the path is
driven by a `ScriptedAgentHandler` so the trace is visible without an LLM API
key — the orchestrator cannot tell a script from an LLM (same `RoleHandler`
surface), so the structural DoD it exercises holds for the live run too.

The trace is written to `runs/<scenario>-<timestamp>.jsonl` by default.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from .._env import load_dotenv_if_present

# Load .env at import time so ADK env vars are visible before the agent factory
# is built. Idempotent; no-op if no .env exists.
load_dotenv_if_present()

from ontology_service import SUPPLY_CHAIN_DEMO_YAML, OntologyService

from ..application.agent_factory import (
    ScriptedAgentHandler,
    ScriptedToolCall,
    build_default_handler_factory,
)
from ..application.orchestrator import DispatchResult, Orchestrator
from ..boundary.customer_development import emit_promo_plan_aligned
from ..boundary.demand_sensing import emit_demand_anomaly
from ..durability import JsonlBackend


# ---------------------------------------------------------------------------
# Stub-mode scripts. Each list mirrors what an LLM agent driven by the rendered
# role view *should* do when the named quantum arrives: introspect its view,
# emit the triggering event, then fire the single declared outgoing handoff.
# Used only in `--mode stub` so the DoD trace is visible without an LLM key. In
# `--mode llm` these roles are LlmAgentHandlers with no script — identity and
# action come from the ontology. Payload field names/enums match the rendered
# quantum schemas (post ontology Phase 1.5).
# ---------------------------------------------------------------------------

# Promo whiplash happy path (Phase 3, Scenes 1-3). Grounded in world_state:
# TP-FLAG-6OZ produced on NJ-L1 in the conflict window, but sized to the line's
# remaining headroom (NJ-L1 baseline week 140 = 3500/5000) so the deterministic
# Phase 4 capacity axiom PASSES. The full 3x promo uplift — which overflows the
# line — is exactly what `--scenario capacity-conflict` exercises; here the
# happy slice keeps the request within capacity.
_PROMO_DEMAND_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
    ScriptedToolCall(tool="emit_event", kwargs={"name": "forecast_revised", "payload": {"sku": "TP-FLAG-6OZ"}}),
    ScriptedToolCall(
        tool="handoff",
        kwargs={
            "flow": "submit_supply_request",
            "quantum": {
                "request_id": "sr-from-promo-0001",
                "sku": "TP-FLAG-6OZ",
                "volume": 1200,
                "required_by": 146,
                "source_signal_ref": "PROMO-MGM-FLAG-2026Q2",
            },
        },
    ),
]

_PROMO_SUPPLY_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
    ScriptedToolCall(tool="emit_event", kwargs={"name": "production_assigned", "payload": {"sku": "TP-FLAG-6OZ", "plant": "PLANT-NJ"}}),
    ScriptedToolCall(
        tool="handoff",
        kwargs={
            "flow": "request_production",
            "quantum": {
                "request_id": "pr-from-promo-0001",
                "sku": "TP-FLAG-6OZ",
                "volume": 1200,
                "window_start_day": 140,
                "window_end_day": 146,
                "assigned_plant": "PLANT-NJ",
                "assigned_line": "NJ-L1",
                "status": "requested",
            },
        },
    ),
]

# Happy-path terminal: production_planning has no outgoing handoff on the happy
# path (its only outgoing flow, escalate_capacity_conflict, is the conflict
# path). It grounds itself in its role view and inspects the capacity axiom it
# is guarded by — both visible as ontology lookups in the trace.
_PROMO_PRODUCTION_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "axioms_on_flow:request_production"}),
]

# Phase 4 — capacity conflict (Scene 4). Same Megalomart 3x promo ingress; this
# time supply_planning sizes the ProductionRequest to the full uplift (3000
# incremental units on NJ-L1 for week 140). NJ-L1 already carries 3500/5000 in
# that window, so scheduled 3500 + requested 3000 = 6500 > 5000 — the blocking
# line_capacity_not_exceeded axiom fires and the orchestrator follows
# on_failure_route_to: escalate_capacity_conflict back to supply_planning. No
# LLM is in the routing. supply_planning's recovery handler just acknowledges
# (cross-domain resolution is Scene 5 / Phase 5).
_CONFLICT_DEMAND_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
    # Ground the promo base before applying the uplift (Seed A): read the real
    # baseline demand (1500/wk) instead of inventing one, then size the request
    # to baseline × 3.0 − baseline = 3000 incremental. Mirrors what a grounded
    # LLM demand_planning does now that it has a reader tool — the no-API-key
    # counterpart to the live query_baseline_demand call. The volume is derived
    # from a number it read, not a guess (the report §5 ungrounded-quantity gap).
    ScriptedToolCall(tool="call_tool", kwargs={"name": "query_baseline_demand", "input": {"sku": "TP-FLAG-6OZ"}}),
    ScriptedToolCall(tool="emit_event", kwargs={"name": "forecast_revised", "payload": {"sku": "TP-FLAG-6OZ"}}),
    ScriptedToolCall(
        tool="handoff",
        kwargs={
            "flow": "submit_supply_request",
            "quantum": {
                "request_id": "sr-from-promo-conflict",
                "sku": "TP-FLAG-6OZ",
                "volume": 3000,
                "required_by": 146,
                "source_signal_ref": "PROMO-MGM-FLAG-2026Q2",
            },
        },
    ),
]

_CONFLICT_SUPPLY_PLANNING = {
    # Scene 4 ingress: assign the full uplift to NJ-L1 → overflows capacity.
    "submit_supply_request": [
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
        ScriptedToolCall(tool="emit_event", kwargs={"name": "production_assigned", "payload": {"sku": "TP-FLAG-6OZ", "plant": "PLANT-NJ"}}),
        ScriptedToolCall(
            tool="handoff",
            kwargs={
                "flow": "request_production",
                "quantum": {
                    "request_id": "pr-from-promo-conflict",
                    "sku": "TP-FLAG-6OZ",
                    "volume": 3000,
                    "window_start_day": 140,
                    "window_end_day": 146,
                    "assigned_plant": "PLANT-NJ",
                    "assigned_line": "NJ-L1",
                    "status": "requested",
                },
            },
        ),
    ],
    # Recovery re-entry: the orchestrator routed the CapacityConflict back here.
    # Phase 4 just acknowledges + inspects the conflict; Scene 5 (Phase 5) adds
    # the cross-domain context assembly that resolves it.
    "escalate_capacity_conflict": [
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "flow:escalate_capacity_conflict"}),
    ],
}

# Phase 5/6 — Scene 5 context assembly + Scene 6 resolution. Same 3000-unit
# conflict as `capacity-conflict`; supply_planning's `escalate_capacity_conflict`
# re-entry runs the `resolve_capacity_conflict` Playbook: read the playbook,
# ground a real (plant, line) via reader tools, fan out the three context-assembly
# queries (wait_all join), surface the decision, pick ONE resolution, then fire
# the playbook's always_fires effects (capacity_resolved + plan_fulfillment).
#
# The choice among the three resolution paths is the agent's judgment. In
# `--mode llm` it's the LLM's to make and may differ per seed (the Phase 5 DoD);
# in stub it's scripted. The context-assembly prefix (steps 1-4) is IDENTICAL
# across all three resolutions — only the resolution handoff (step 5) differs —
# so the same-queries / different-resolution contrast is structural, not
# per-path code. `_capres_escalate_script` builds the script for any resolution.


def _capres_escalate_script(
    resolution_flow: str,
    resolution_quantum: dict,
) -> list[ScriptedToolCall]:
    """Build supply_planning's `escalate_capacity_conflict` script for a chosen
    resolution. Steps 1-4 (playbook read, reader-tool grounding, the three
    context-assembly queries, the surfaced decision) are the same for every
    resolution; only the resolution handoff (step 5) varies. always_fires
    (capacity_resolved + plan_fulfillment, step 6) is invariant — it fires on
    every path, which is what drives re-convergence to the happy path."""
    return [
        # 1. First action on screen — read the playbook anchored to me (§10 proof).
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "playbook:resolve_capacity_conflict"}),
        # 2. Ground a real (plant, line, window) instead of inventing one.
        ScriptedToolCall(tool="call_tool", kwargs={"name": "query_plants_for_sku", "input": {"sku": "TP-FLAG-6OZ"}}),
        ScriptedToolCall(
            tool="call_tool",
            kwargs={
                "name": "query_line_load",
                "input": {"plant_code": "PLANT-NJ", "line_code": "NJ-L1", "window_start_day": 140, "window_end_day": 146},
            },
        ),
        # 3. Context assembly — the three declared query flows (wait_all join).
        ScriptedToolCall(
            tool="query",
            kwargs={"flow": "check_otif_exposure", "query_quantum": {"sku": "TP-SEC-6OZ", "retailer": "BULLSEYE", "proposed_delay_days": 3}},
        ),
        ScriptedToolCall(
            tool="query",
            kwargs={"flow": "check_promo_flexibility", "query_quantum": {"promo_id": "PROMO-MGM-FLAG-2026Q2", "proposed_change_kind": "shift_timing"}},
        ),
        ScriptedToolCall(
            tool="query",
            kwargs={"flow": "check_coman_availability", "query_quantum": {"sku": "TP-FLAG-6OZ", "volume": 1500, "window_start_day": 140, "window_end_day": 146}},
        ),
        # 4. Surface the decision (validates the playbook ref; never picks for us).
        ScriptedToolCall(
            tool="surface_decision",
            kwargs={
                "playbook": "resolve_capacity_conflict",
                "context": {"shortfall_units": 1500, "at_risk_commitment": "COM-BUL-SEC-Q2"},
                "options": ["re_request_production", "request_promo_revision", "shift_to_coman"],
            },
        ),
        # 5. Pick ONE resolution path (judgment — scripted here per scenario).
        ScriptedToolCall(tool="handoff", kwargs={"flow": resolution_flow, "quantum": resolution_quantum}),
        # 6. always_fires — agent-driven (the orchestrator has no event→flow
        #    trigger; firing these is the agent following the playbook, §2-safe).
        #    Fires on EVERY resolution path → drives re-convergence to happy path.
        ScriptedToolCall(tool="emit_event", kwargs={"name": "capacity_resolved", "payload": {"sku": "TP-FLAG-6OZ", "resolution": resolution_flow}}),
        ScriptedToolCall(
            tool="handoff",
            kwargs={
                "flow": "plan_fulfillment",
                "quantum": {
                    "request_id": "sr-fulfillment-capres",
                    "sku": "TP-FLAG-6OZ",
                    "volume": 3000,
                    "required_by": 146,
                    "source_signal_ref": "PROMO-MGM-FLAG-2026Q2",
                },
            },
        ),
    ]


# Scene 6 resolution quanta — one per path.
#   shift_to_coman: external co-man absorbs the volume (demo_narrative Scene 6).
_COMAN_QUANTUM = {
    "request_id": "pr-coman-capres", "sku": "TP-FLAG-6OZ", "volume": 1500,
    "window_start_day": 140, "window_end_day": 146,
    "assigned_plant": "COMAN-1", "assigned_line": "COMAN-1-L1", "status": "assigned",
}
#   re_request_production: internal re-entry with a REVISED ProductionRequest.
#   Same line (NJ-L1), volume reduced to the headroom (3500 scheduled + 1500 =
#   5000 = rated capacity) so the line_capacity_not_exceeded guard now PASSES at
#   production_planning's requested→assigned transition. This is the narrative's
#   "request_production re-evaluated, axiom now passes" — the deterministic floor
#   ACCEPTING the corrected plan, the mirror image of Scene 4 blocking the bad one.
_REREQUEST_QUANTUM = {
    "request_id": "pr-rerequest-capres", "sku": "TP-FLAG-6OZ", "volume": 1500,
    "window_start_day": 140, "window_end_day": 146,
    "assigned_plant": "PLANT-NJ", "assigned_line": "NJ-L1", "status": "requested",
}
#   request_promo_revision: hand a revised TradePromotion (2x not 3x) back across
#   the boundary to customer_development for renegotiation. Skeletal/boundary path.
_PROMO_REVISION_QUANTUM = {
    "promo_id": "PROMO-MGM-FLAG-2026Q2", "sku": "TP-FLAG-6OZ", "retailer": "MEGALOMART",
    "volume_uplift_factor": 2.0, "promo_start_day": 142, "promo_end_day": 156,
    "commitment_status": "aligned",
}

_CAPRES_SUPPLY_PLANNING = {
    # Scene 4 ingress (unchanged): assign full uplift to NJ-L1 → overflows → the
    # capacity axiom blocks and the orchestrator reroutes escalate_capacity_conflict.
    "submit_supply_request": _CONFLICT_SUPPLY_PLANNING["submit_supply_request"],
    # Scene 5+6: the Playbook executes here, picking shift_to_coman.
    "escalate_capacity_conflict": _capres_escalate_script("shift_to_coman", _COMAN_QUANTUM),
}

# Production_planning, resolution variant. On the internal-resolution path
# (re_request_production) it receives a REVISED ProductionRequest and advances
# ProductionRequestLifecycle requested→assigned. The `assign` transition's guard
# is the same blocking `line_capacity_not_exceeded` axiom that fired in Scene 4 —
# here it is re-evaluated against the corrected quantum and PASSES, so the FSM
# advances (FSM_TRANSITIONED, guard_passed=True). The deterministic floor accepts
# the corrected plan. (quantum_id is the runtime handle the orchestrator stamps;
# advance_fsm defaults it to the quantum in hand, so the script doesn't name it.)
_RESOLUTION_PRODUCTION_PLANNING = {
    "re_request_production": [
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
        ScriptedToolCall(tool="read_ontology", kwargs={"query": "axioms_on_flow:request_production"}),
        ScriptedToolCall(tool="advance_fsm", kwargs={"fsm": "ProductionRequestLifecycle", "trigger": "assign"}),
    ],
}

# Scripted query responders for the three cross-domain roles supply_planning
# fans out to during context assembly. Each is keyed on its query flow and
# returns a typed response via respond_to_query. (In --mode llm these are real
# agents; the scripts only drive the stub DoD trace.)
_CAPRES_LOGISTICS = {
    "check_otif_exposure": [
        ScriptedToolCall(
            tool="respond_to_query",
            kwargs={"response": {
                "retailer": "BULLSEYE", "sku": "TP-SEC-6OZ", "delay_days": 3,
                "affected_shipment_value": 240000, "calculated_penalty": 7200,
            }},
        ),
    ],
}
_CAPRES_CUSTOMER_DEV = {
    "check_promo_flexibility": [
        ScriptedToolCall(
            tool="respond_to_query",
            kwargs={"response": {
                "promo_id": "PROMO-MGM-FLAG-2026Q2", "commitment_status": "aligned",
                "can_shift_timing": True, "can_reduce_volume": True,
                "notes": "Megalomart promo still aligned (not committed); timing shift negotiable.",
            }},
        ),
    ],
}
_CAPRES_COMAN = {
    "check_coman_availability": [
        ScriptedToolCall(
            tool="respond_to_query",
            kwargs={"response": {
                "sku": "TP-FLAG-6OZ", "is_qualified": True, "has_capacity": True,
                "premium_cost_per_unit": 0.85, "lead_time_days": 10,
            }},
        ),
    ],
}

# Original Phase 2 demand-anomaly round trip.
_ANOMALY_DEMAND_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
    ScriptedToolCall(
        tool="handoff",
        kwargs={
            "flow": "submit_supply_request",
            "quantum": {
                "request_id": "sr-from-anomaly-0001",
                "sku": "sku-toothpaste-6oz",
                "volume": 4500,
                "required_by": 60,
                "source_signal_ref": "anom-demo-0001",
            },
        },
    ),
    ScriptedToolCall(tool="emit_event", kwargs={"name": "forecast_revised", "payload": {"sku": "sku-toothpaste-6oz"}}),
]


# ---------------------------------------------------------------------------
# Scene 5 seeder — inject a detected capacity conflict straight into
# supply_planning. plan_of_attack §5 says Scene 5 *begins* with the conflict
# already detected: the orchestrator routes a CapacityConflict to supply_planning
# via escalate_capacity_conflict and the resolve_capacity_conflict Playbook is
# the agent's first action. Deriving the conflict from an upstream production
# assignment is unreliable live — a reader-tool-grounded supply_planning sizes
# the request to fit (or shifts the window) and avoids the conflict entirely
# (exactly the grounding win Phase 5 delivers). Injection makes the playbook
# path deterministic without scripting the agent's judgment.
# ---------------------------------------------------------------------------


async def inject_capacity_conflict(orch: Orchestrator) -> DispatchResult:
    """Seed Scene 5: route a CapacityConflict to supply_planning. The payload
    mirrors what the Phase 4 capacity axiom tool builds (NJ-L1 over capacity in
    the promo window, Bullseye's TP-SEC-6OZ commitment at risk)."""
    return await orch.dispatch_boundary_ingress(
        "escalate_capacity_conflict",
        {
            "conflict_id": "conf-scene5",
            "line_ref": "NJ-L1",
            "competing_skus": ["TP-FLAG-6OZ", "TP-SEC-6OZ"],
            "shortfall_units": 1500,
            "at_risk_commitments": ["COM-BUL-SEC-Q2"],
            "window_start_day": 140,
            "window_end_day": 146,
        },
    )


# ---------------------------------------------------------------------------
# Scenario registry. A scenario is (boundary seeder, stub-mode scripts). The
# scripts are consulted only in `--mode stub`; in `--mode llm` the factory
# builds real LlmAgentHandlers for every role with no override.
# ---------------------------------------------------------------------------

Seeder = Callable[[Orchestrator], Awaitable[DispatchResult]]

SCENARIOS: dict[str, dict] = {
    "promo": {
        "seeder": emit_promo_plan_aligned,
        "scripts": {
            "demand_planning": _PROMO_DEMAND_PLANNING,
            "supply_planning": _PROMO_SUPPLY_PLANNING,
            "production_planning": _PROMO_PRODUCTION_PLANNING,
        },
    },
    "capacity-conflict": {
        "seeder": emit_promo_plan_aligned,
        "scripts": {
            "demand_planning": _CONFLICT_DEMAND_PLANNING,
            "supply_planning": _CONFLICT_SUPPLY_PLANNING,
            "production_planning": _PROMO_PRODUCTION_PLANNING,
        },
    },
    "capacity-resolution": {
        "seeder": inject_capacity_conflict,
        "scripts": {
            "supply_planning": _CAPRES_SUPPLY_PLANNING,
        },
        # Cross-domain query responders. These stand in for external/boundary
        # domains (logistics, commercial, co-man) and are wired in BOTH modes so
        # the live supply_planning agent weighs *real typed evidence* (§3 case 1:
        # heterogeneous trade-off) rather than empty boundary stubs. The role
        # under test — supply_planning — stays a real LLM in `--mode llm`.
        "responders": {
            "logistics_planning": _CAPRES_LOGISTICS,
            "customer_development": _CAPRES_CUSTOMER_DEV,
            "co_manufacturing": _CAPRES_COMAN,
        },
    },
    # Phase 6 — the other two resolution paths, same injected conflict + identical
    # context assembly as `capacity-resolution`, only the chosen resolution differs.
    # CLI access to each path so a human can run all three; the structural proof
    # (same queries, different resolution) lives in test_phase6_dod.py.
    "resolution-internal": {
        "seeder": inject_capacity_conflict,
        "scripts": {
            "supply_planning": {
                "submit_supply_request": _CONFLICT_SUPPLY_PLANNING["submit_supply_request"],
                "escalate_capacity_conflict": _capres_escalate_script("re_request_production", _REREQUEST_QUANTUM),
            },
            "production_planning": _RESOLUTION_PRODUCTION_PLANNING,
        },
        "responders": {
            "logistics_planning": _CAPRES_LOGISTICS,
            "customer_development": _CAPRES_CUSTOMER_DEV,
            "co_manufacturing": _CAPRES_COMAN,
        },
    },
    "resolution-promo": {
        "seeder": inject_capacity_conflict,
        "scripts": {
            "supply_planning": {
                "submit_supply_request": _CONFLICT_SUPPLY_PLANNING["submit_supply_request"],
                "escalate_capacity_conflict": _capres_escalate_script("request_promo_revision", _PROMO_REVISION_QUANTUM),
            },
        },
        "responders": {
            "logistics_planning": _CAPRES_LOGISTICS,
            "customer_development": _CAPRES_CUSTOMER_DEV,
            "co_manufacturing": _CAPRES_COMAN,
        },
    },
    # Phase 6 — the full promo-whiplash narrative from ONE seed: Scenes 1-6.
    # In stub mode the conflict is DERIVED honestly: demand_planning hands a
    # full-uplift SupplyRequest to supply_planning, which assigns 3000 to NJ-L1;
    # the line_capacity_not_exceeded axiom fires (Scene 4) and the orchestrator
    # auto-reroutes escalate_capacity_conflict; supply_planning then runs the
    # playbook (Scene 5) and picks shift_to_coman (Scene 6); plan_fulfillment
    # re-converges on the happy path. No injection needed in stub — the scripts
    # are deterministic. (Live `--mode llm` uses --scenario capacity-resolution,
    # which INJECTS the conflict, because a reader-tool-grounded LLM sizes the
    # request to fit and dodges a derived conflict — the documented Phase 5
    # finding. See CHANGELOG.)
    "full-demo": {
        "seeder": emit_promo_plan_aligned,
        "scripts": {
            "demand_planning": _CONFLICT_DEMAND_PLANNING,
            "supply_planning": _CAPRES_SUPPLY_PLANNING,
            "production_planning": _PROMO_PRODUCTION_PLANNING,
        },
        "responders": {
            "logistics_planning": _CAPRES_LOGISTICS,
            "customer_development": _CAPRES_CUSTOMER_DEV,
            "co_manufacturing": _CAPRES_COMAN,
        },
    },
    "demand-anomaly": {
        "seeder": emit_demand_anomaly,
        "scripts": {
            "demand_planning": _ANOMALY_DEMAND_PLANNING,
        },
    },
}

DEFAULT_SCENARIO = "promo"


def _default_log_path(scenario: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / f"{scenario}-{ts}.jsonl"


def build_scenario_orchestrator(
    scenario: str = DEFAULT_SCENARIO,
    *,
    log_path: Path | None = None,
    mode: str = "llm",
    ontology_yaml: Path | None = None,
    service: OntologyService | None = None,
) -> tuple[Orchestrator, JsonlBackend, OntologyService, dict]:
    """Wire a scenario's orchestrator + backend WITHOUT firing its seeder.

    This is the shared construction path: `run_scenario` adds the seeder on top;
    the MCP front door (`mcp/core.py`) reuses the identical wiring but supplies
    its *own* boundary ingress in place of the seeder — so the simulated world
    behind the front door (stub scripts in `--mode stub`, real LlmAgents in
    `--mode llm`, plus the cross-domain responders) is exactly the CLI's. The
    front door changes who knocks, not what's behind the door.

    Returns `(orch, backend, service, spec)`. The caller drives ingress.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {sorted(SCENARIOS)}")
    spec = SCENARIOS[scenario]

    if service is None:
        yaml_path = ontology_yaml or SUPPLY_CHAIN_DEMO_YAML
        service = OntologyService.load(yaml_path)
    backend = JsonlBackend(log_path=log_path)

    # No per-role overrides in llm mode: identity + action come from the
    # ontology role view. In stub mode, drive each role on the path with its
    # canonical script so the trace is visible without an LLM key. Any role not
    # scripted falls back to the factory default (InternalStubHandler in stub
    # mode), which simply acknowledges.
    overrides: dict = {}
    # Cross-domain responders (if any) are simulated in every mode — they model
    # external domains, not the role under test.
    for role, script in spec.get("responders", {}).items():
        overrides[role] = ScriptedAgentHandler(role, orch=None, script=script)
    # The role under test + the rest of the path are scripted only in stub mode;
    # in llm mode they come from the ontology role view (a real LlmAgentHandler).
    if mode == "stub":
        for role, script in spec["scripts"].items():
            overrides[role] = ScriptedAgentHandler(role, orch=None, script=script)

    factory = build_default_handler_factory(service, overrides=overrides, mode=mode)
    orch = Orchestrator(service=service, backend=backend, handler_factory=factory)
    # Late-bind the orchestrator on every override that holds an internal ref.
    for h in overrides.values():
        if hasattr(h, "_orch"):
            h._orch = orch  # type: ignore[attr-defined]
    return orch, backend, service, spec


async def run_scenario(
    scenario: str = DEFAULT_SCENARIO,
    *,
    log_path: Path | None = None,
    mode: str = "llm",
    ontology_yaml: Path | None = None,
) -> dict:
    """Execute a scenario end-to-end. Returns a summary dict for human reading."""
    orch, backend, service, spec = build_scenario_orchestrator(
        scenario, log_path=log_path, mode=mode, ontology_yaml=ontology_yaml
    )

    seeder: Seeder = spec["seeder"]
    dispatch = await seeder(orch)
    events = backend.read_events()
    summary = {
        "scenario": scenario,
        "mode": mode,
        "log_path": str(log_path) if log_path else None,
        "events_appended": dispatch.events_appended,
        "seed_event_seq": dispatch.seed_event_seq,
        "roles_invoked": sorted(
            {e.payload["role"] for e in events if e.kind == "agent_invocation_started"}
        ),
        "event_kinds": [e.kind for e in events],
    }
    return summary


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="e2e-orchestrator",
        description="Run a supply chain orchestrator scenario end-to-end.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default=DEFAULT_SCENARIO,
        help=f"Which scenario to run (default: {DEFAULT_SCENARIO}, the Phase 3 promo happy path).",
    )
    parser.add_argument("--log", type=Path, default=None, help="Path to write the JSONL event log (default: runs/<scenario>-<ts>.jsonl)")
    parser.add_argument("--mode", choices=("llm", "stub"), default=None, help="'llm' uses ADK (default); 'stub' runs without an LLM.")
    parser.add_argument("--ontology", type=Path, default=None, help="Override the supply_chain_demo.yaml path.")
    parser.add_argument("--print-events", action="store_true", help="Print every event to stdout after the run.")
    parser.add_argument("--narrate", action="store_true", help="Print the readable Scene 1→6 trace narrative after the run.")
    args = parser.parse_args(argv)

    log_path = args.log or _default_log_path(args.scenario)
    mode = args.mode or "llm"
    summary = asyncio.run(
        run_scenario(args.scenario, log_path=log_path, mode=mode, ontology_yaml=args.ontology)
    )
    if args.narrate and log_path.exists():
        from .narrative import render_trace_file
        print(render_trace_file(log_path))
    else:
        print(json.dumps(summary, indent=2))
    if args.print_events and log_path.exists():
        print("---")
        with log_path.open() as fh:
            for line in fh:
                print(line.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
