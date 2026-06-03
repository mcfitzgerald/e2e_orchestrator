"""FastMCP wiring for the orchestrator front door + the `e2e-mcp` entry point.

This module is deliberately thin: it binds `OrchestratorFrontDoor` (in `core.py`)
to MCP tools (write side = commands) and resources (read side = events). The
mapping is exact and load-bearing — **MCP tools ↔ commands, MCP resources ↔
events** — and every handler just forwards to the front door. No routing, no
LLM, no axiom evaluation, no per-role code lives here.

Transport is config, not code: stdio by default (trivially testable; directly
consumable by an ADK `McpToolset` client over `StdioConnectionParams`),
streamable-HTTP for the "real front door" network deployment. The MCP
security/OAuth path is real but out of POC scope — flagged, deferred.

The front door's `mode` ("llm" / "stub") and `world` (which simulated supply
chain sits behind the door) are read from the environment at startup so the same
server binary runs the live LLM demo or a no-API-key stub run without code
changes:

    E2E_MCP_MODE   = llm | stub        (default: llm)
    E2E_MCP_WORLD  = <scenario name>   (default: full-demo)
"""
from __future__ import annotations

import argparse
import os
import sys

from .._env import load_dotenv_if_present

load_dotenv_if_present()

from mcp.server.fastmcp import FastMCP

from .core import OrchestratorFrontDoor, UnknownRunError

# ---------------------------------------------------------------------------
# Front door + server. The front door is built lazily on first use so importing
# this module (e.g. for the entry point or tests) does not parse the ontology.
# ---------------------------------------------------------------------------

_front_door: OrchestratorFrontDoor | None = None


def front_door() -> OrchestratorFrontDoor:
    global _front_door
    if _front_door is None:
        _front_door = OrchestratorFrontDoor(
            mode=os.environ.get("E2E_MCP_MODE", "llm"),
            world=os.environ.get("E2E_MCP_WORLD", "full-demo"),
        )
    return _front_door


def build_server(door: OrchestratorFrontDoor | None = None) -> FastMCP:
    """Construct a FastMCP server bound to `door` (or the process front door).
    Factored out so a test can bind a stub-mode front door and drive the server
    through an in-memory client session against the real orchestrator seams."""
    if door is not None:
        global _front_door
        _front_door = door

    mcp = FastMCP("e2e-orchestrator")

    # ---- write side (commands) ------------------------------------------

    @mcp.tool()
    async def ingress_quantum(
        flow: str,
        payload: dict,
        idempotency_key: str | None = None,
    ) -> dict:
        """Drop a signal into the supply chain at a boundary flow (a command).

        Generic over `(flow, payload)` — it does not enumerate roles or branch on
        domain. Forwards to the orchestrator's `dispatch_boundary_ingress` seam
        (the same entry the boundary simulators use); the quantum validator
        checks `payload` against the flow's declared quantum class before
        anything routes. Routing, axioms and FSM stay in the deterministic
        backbone — no LLM decides where the quantum goes.

        `idempotency_key` is optional but recommended: a retried ingress with the
        same key returns the same run without re-dispatching. Returns the
        run/quantum id and resource pointers (`trace://`, `narrative://`,
        `decisions://`) — read downstream effects off the trace, not from a
        synchronous return value.
        """
        result = await front_door().ingress(flow, payload, idempotency_key=idempotency_key)
        return result.as_dict()

    @mcp.tool()
    async def run_demo_scenario(scenario: str = "full-demo", mode: str | None = None) -> dict:
        """Run a canned scenario end-to-end through its *own* boundary seeder and
        register the run (convenience wrapper over the CLI's `run_scenario`).
        Use this to reproduce the full promo-whiplash demo through the protocol;
        `ingress_quantum` is the generic boundary edge. Returns the same
        run/quantum id + resource pointers."""
        result = await front_door().run_demo(scenario, mode=mode)
        return result.as_dict()

    # ---- read side (resources, read-only, sourced from events) ----------

    @mcp.resource("trace://{run_id}")
    def trace(run_id: str) -> str:
        """The JSONL event log for a run — a read-only projection of what
        happened (the same artifact `runs/*.jsonl` holds)."""
        return front_door().read_trace(run_id)

    @mcp.resource("narrative://{run_id}")
    def narrative(run_id: str) -> str:
        """The human-readable Scene 1→6 story for a run, rendered from the event
        log by `runtime.narrative`."""
        return front_door().read_narrative(run_id)

    @mcp.resource("decisions://{run_id}")
    def decisions(run_id: str) -> str:
        """The decision surface(s) surfaced during a run (the `decision_surfaced`
        event payloads), as JSON."""
        return front_door().read_decisions(run_id)

    @mcp.resource("roleview://{role}")
    def roleview(role: str) -> str:
        """`render_role_view(role).as_agent_prompt()` — the ontology-derived
        identity of any role, read-only, no run required. Byte-identical to what
        the orchestrator binds as an LlmAgent's instruction."""
        return front_door().read_roleview(role)

    return mcp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="e2e-mcp",
        description="Expose the orchestrator system through MCP (Phase 7 front door).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default=os.environ.get("E2E_MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio). streamable-http is the production front-door shape "
        "(no auth wired — out of POC scope).",
    )
    parser.add_argument("--mode", choices=("llm", "stub"), default=None, help="Override E2E_MCP_MODE.")
    parser.add_argument("--world", default=None, help="Override E2E_MCP_WORLD (which scenario world sits behind the door).")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.mode:
        os.environ["E2E_MCP_MODE"] = args.mode
    if args.world:
        os.environ["E2E_MCP_WORLD"] = args.world

    server = build_server()
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
