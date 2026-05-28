"""Phase 2 runtime entrypoint.

Wires the durability backend (JSONL), the Ontology Service (loaded from the
sibling `e2e_ontology` repo), the agent factory (LLM by default; `--stub` for
no-API-key runs), and the boundary simulator. Fires a `DemandAnomaly` at
`demand_sensing` and drives the round trip:

  raise_demand_anomaly → demand_planning → submit_supply_request → supply_planning

`supply_planning` is an `InternalStubHandler` in Phase 2 (real agent lands in
Phase 3). The trace is written to `runs/<timestamp>.jsonl` by default.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import _bootstrap

from ontology_service import OntologyService

from ..application.agent_factory import (
    InternalStubHandler,
    ScriptedAgentHandler,
    ScriptedToolCall,
    build_default_handler_factory,
)
from ..application.orchestrator import Orchestrator
from ..boundary.demand_sensing import emit_demand_anomaly
from ..durability import JsonlBackend


# Canonical scripted demand_planning for the Phase 2 DoD path. Mirrors what an
# LLM agent driven by the rendered role view *should* do when a DemandAnomaly
# arrives: introspect, then hand off a SupplyRequest. Used in --mode stub so the
# DoD trace is visible without an LLM API key.
_PHASE2_DEMAND_PLANNING_SCRIPT = [
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


def _default_log_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / f"phase2-{ts}.jsonl"


async def run_phase2(
    *,
    log_path: Path | None = None,
    mode: str = "llm",
    ontology_yaml: Path | None = None,
) -> dict:
    """Execute the Phase 2 DoD path. Returns a summary dict for human reading."""
    yaml_path = ontology_yaml or _bootstrap.ONTOLOGY_YAML_PATH
    service = OntologyService.load(yaml_path)
    backend = JsonlBackend(log_path=log_path)

    # Phase 2: supply_planning isn't built yet; force an internal stub so the
    # handoff has somewhere to land. Boundary stubs are auto-wired by the
    # factory based on `is_boundary` in the ontology.
    overrides: dict = {
        "supply_planning": InternalStubHandler("supply_planning", orch=None),  # orch wired below
    }
    # In stub mode, drive demand_planning with the canonical Phase 2 script so
    # the DoD trace is visible without an LLM API key. In llm mode, the agent
    # factory builds a real LlmAgentHandler.
    if mode == "stub":
        overrides["demand_planning"] = ScriptedAgentHandler(
            "demand_planning", orch=None, script=_PHASE2_DEMAND_PLANNING_SCRIPT
        )
    factory = build_default_handler_factory(service, overrides=overrides, mode=mode)

    orch = Orchestrator(service=service, backend=backend, handler_factory=factory)
    # Late-bind the orchestrator on every override that holds an internal ref.
    for h in overrides.values():
        if hasattr(h, "_orch"):
            h._orch = orch  # type: ignore[attr-defined]

    dispatch = await emit_demand_anomaly(orch)
    events = backend.read_events()
    summary = {
        "log_path": str(log_path) if log_path else None,
        "events_appended": dispatch.events_appended,
        "seed_event_seq": dispatch.seed_event_seq,
        "event_kinds": [e.kind for e in events],
    }
    return summary


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e2e-orchestrator", description="Run the Phase 2 demand→supply round trip.")
    parser.add_argument("--log", type=Path, default=None, help="Path to write the JSONL event log (default: runs/phase2-<ts>.jsonl)")
    parser.add_argument("--mode", choices=("llm", "stub"), default=None, help="'llm' uses ADK (default); 'stub' runs without an LLM.")
    parser.add_argument("--ontology", type=Path, default=None, help="Override the supply_chain_demo.yaml path.")
    parser.add_argument("--print-events", action="store_true", help="Print every event to stdout after the run.")
    args = parser.parse_args(argv)

    log_path = args.log or _default_log_path()
    mode = args.mode or "llm"
    summary = asyncio.run(run_phase2(log_path=log_path, mode=mode, ontology_yaml=args.ontology))
    print(json.dumps(summary, indent=2))
    if args.print_events and log_path.exists():
        print("---")
        with log_path.open() as fh:
            for line in fh:
                print(line.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
