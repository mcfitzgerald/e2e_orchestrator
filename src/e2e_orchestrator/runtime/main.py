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

from .. import _bootstrap
from .._env import load_dotenv_if_present

# Load .env at import time so ADK env vars are visible before the agent factory
# is built. Idempotent; no-op if no .env exists.
load_dotenv_if_present()

from ontology_service import OntologyService

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
                "source_signal_ref": "PROMO-WMT-FLAG-2026Q2",
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

# Phase 4 — capacity conflict (Scene 4). Same Walmart 3x promo ingress; this
# time supply_planning sizes the ProductionRequest to the full uplift (3000
# incremental units on NJ-L1 for week 140). NJ-L1 already carries 3500/5000 in
# that window, so scheduled 3500 + requested 3000 = 6500 > 5000 — the blocking
# line_capacity_not_exceeded axiom fires and the orchestrator follows
# on_failure_route_to: escalate_capacity_conflict back to supply_planning. No
# LLM is in the routing. supply_planning's recovery handler just acknowledges
# (cross-domain resolution is Scene 5 / Phase 5).
_CONFLICT_DEMAND_PLANNING = [
    ScriptedToolCall(tool="read_ontology", kwargs={"query": "my_view"}),
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
                "source_signal_ref": "PROMO-WMT-FLAG-2026Q2",
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


async def run_scenario(
    scenario: str = DEFAULT_SCENARIO,
    *,
    log_path: Path | None = None,
    mode: str = "llm",
    ontology_yaml: Path | None = None,
) -> dict:
    """Execute a scenario end-to-end. Returns a summary dict for human reading."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {sorted(SCENARIOS)}")
    spec = SCENARIOS[scenario]

    yaml_path = ontology_yaml or _bootstrap.ONTOLOGY_YAML_PATH
    service = OntologyService.load(yaml_path)
    backend = JsonlBackend(log_path=log_path)

    # No per-role overrides in llm mode: identity + action come from the
    # ontology role view. In stub mode, drive each role on the path with its
    # canonical script so the trace is visible without an LLM key. Any role not
    # scripted falls back to the factory default (InternalStubHandler in stub
    # mode), which simply acknowledges.
    overrides: dict = {}
    if mode == "stub":
        for role, script in spec["scripts"].items():
            overrides[role] = ScriptedAgentHandler(role, orch=None, script=script)

    factory = build_default_handler_factory(service, overrides=overrides, mode=mode)
    orch = Orchestrator(service=service, backend=backend, handler_factory=factory)
    # Late-bind the orchestrator on every override that holds an internal ref.
    for h in overrides.values():
        if hasattr(h, "_orch"):
            h._orch = orch  # type: ignore[attr-defined]

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
    args = parser.parse_args(argv)

    log_path = args.log or _default_log_path(args.scenario)
    mode = args.mode or "llm"
    summary = asyncio.run(
        run_scenario(args.scenario, log_path=log_path, mode=mode, ontology_yaml=args.ontology)
    )
    print(json.dumps(summary, indent=2))
    if args.print_events and log_path.exists():
        print("---")
        with log_path.open() as fh:
            for line in fh:
                print(line.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
