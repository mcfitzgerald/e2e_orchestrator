# Seed B — Phase 7: the MCP front door

**Type:** orchestrator-repo coding-session seed. Self-contained — assume zero
context from any other session.
**Track:** B (platform breadth — proves the architecture generalizes *outward*).
Independent of Seed A (which touches the ontology + the reader-tool surface); this
touches the orchestrator's *external interface*. The only shared files are
`pyproject.toml` and `CLAUDE.md` — trivial to keep apart.
**Depends on:** the Ontology Service + the existing orchestrator only. Startable
now; gated on nothing.

---

## Frame: this is the *first realized edge*, and an experiment

Read `briefings/design-memo-ontology-exposes-handshakes.md` first. Short version:
the system has two edges to the outside world — **inbound** (boundary roles, where
signals enter) and **outbound** (`scont:Tool` reader tools, where the agent reaches
data). Today both are **shims** (seeded boundary responders; `world_state.yaml`
fixture). Phase 7 is the **first time we realize a standard handshake end-to-end**
— the *inbound* edge, as MCP — so it is the **reference pattern for every edge** and
the **experiment** that informs an open design question: should the ontology
*expose the handshake transport* (REST/MCP/A2A, endpoint, discovery), or does that
stay a connector/binding layer outside the ontology? (Leaning: *contract in, wire
out*.) **A2A is the outbound/agent dual** of this — out of scope to build, but the
same edge concept. You don't resolve the question; you **produce the evidence** (see
"What this experiment should teach us" at the end). Build the front door cleanly and
report what the realized edge reveals.

---

## TL;DR

Expose the orchestrator system through **MCP (Model Context Protocol)** so an
external client can **drop a signal into the supply chain** and **read back what
happened** — without an LLM in the routing path, without per-role code, and
without bypassing the commands→events backbone. This is the *breadth* proof: the
boundary-role pattern (`initial_design_draft.md §3.1` — "signals enter from
outside the orchestration envelope") generalized into a standard protocol the
outside world already speaks.

**The surface, decided:**

- **MCP Tools (write side = commands):** one generic primitive,
  `ingress_quantum(flow, payload, idempotency_key?)`, that routes through the
  existing `Orchestrator.dispatch_boundary_ingress(...)`. Optionally a thin
  `run_demo_scenario(scenario, mode)` convenience wrapper over `run_scenario` for
  the demo. **Not** the seven-tool kit (see "What NOT to expose").
- **MCP Resources (read side = events/state, read-only):** the run's event-log
  trace, the rendered narrative (`runtime/narrative.py`), the decision surfaces
  emitted during the run, and the ontology-rendered role views
  (`render_role_view(role).as_agent_prompt()`).

The mapping is exact and load-bearing: **MCP tools ↔ commands, MCP resources ↔
events.** The front door is a *dumb adapter* — it validates I/O and forwards;
all routing, validation, axioms, and FSM stay in the deterministic backbone.

> **Before writing code: re-pull current MCP + ADK-MCP guidance via `context7`.**
> Both move fast and training cutoffs lie about them. The API notes below were
> pulled fresh for this seed (see "Library grounding"), but re-verify the exact
> `FastMCP` / transport symbols at implementation time.

---

## Why now

Phases 1–6 are done and verified live: the full promo-whiplash narrative runs
end-to-end from one seed, with a deterministic floor, real agency, and grounded
references. The architecture's *internal* claims are demonstrated. What is **not**
yet demonstrated is that the same system presents cleanly through a *standard
external interface* — that "a generic agent + deterministic orchestrator" is not
just a closed demo but a platform other systems can call. MCP is the lingua franca
for exactly that, and exposing the front door is the cheapest credible breadth
proof. It also sets up a future where an external ADK (or any) agent consumes our
orchestrator as one MCP tool among many.

---

## The surface — in detail

### Write side — `ingress_quantum` (MCP tool, a command)

```
ingress_quantum(flow: str, payload: dict, idempotency_key: str | None = None) -> dict
```

- Forwards to `Orchestrator.dispatch_boundary_ingress(...)` — the existing,
  validated entry seam used by the boundary simulators
  (`boundary/customer_development.py`, `boundary/demand_sensing.py`) and by
  `inject_capacity_conflict`. The MCP tool is *another caller of the same seam*,
  not a new path.
- `flow` names a boundary-ingress flow (e.g. `submit_promo_plan`); `payload` is the
  typed quantum body. The **quantum validator** validates `payload` against the
  flow's declared quantum class before anything routes — a malformed ingress is
  rejected with the same `quantum_rejected` shape the rest of the system uses, not
  a bespoke MCP error.
- **Idempotency:** MCP clients retry. Accept an optional `idempotency_key` and
  thread it into the orchestrator's existing idempotency discipline so a retried
  ingress does not double-fire. If omitted, derive a stable one. This is the third
  borrowed discipline showing up at the boundary — do not skip it.
- Returns a small dict: the run/quantum id + a pointer (resource URI) to the trace
  the caller can then read. **It does not return downstream effects synchronously
  by reaching into in-memory state** — effects are read from the event log via
  resources (commands→events).

The signature is **generic** — `(flow, payload)`. It does **not** enumerate roles
or branch on domain. Adding role N+1 upstream must not touch this server.

### Read side — resources (read-only, sourced from events)

Expose as MCP resources (or read-only tools if a resource URI scheme is awkward —
pick per current SDK ergonomics):

- **`trace://<run_id>`** — the JSONL event log for a run (the same artifact
  `runs/*.jsonl` holds). Read-only projection of what happened.
- **`narrative://<run_id>`** — the human-readable Scene 1→6 story via
  `runtime/narrative.py` (which already renders it; reuse, don't re-implement).
- **`decisions://<run_id>`** — the decision surface(s) surfaced during the run
  (the `decision_surfaced` events / their payloads).
- **`roleview://<role>`** — `OntologyService.render_role_view(role).as_agent_prompt()`,
  read-only. Lets a client inspect the ontology-derived identity of any role
  without running anything. (This is pure Ontology Service read — the cleanest
  possible MCP resource and a good first slice.)

Resources are **derived from the event log / Ontology Service**, never from peeking
at live in-memory orchestrator state mid-flight. That keeps replayability and the
commands→events invariant intact.

---

## Constraints that still hold at the boundary (do not regress)

1. **No LLM in routing.** The MCP server is a protocol adapter; it must never call
   an LLM to decide where a quantum goes. Routing stays in
   `application/flow_router.py`, the single source of truth. (An MCP *client* may
   be an LLM agent — that's fine; the routing inside our system stays
   deterministic.)
2. **Commands → events.** Every external action goes *through the orchestrator*.
   The MCP tool calls `dispatch_boundary_ingress` / `run_scenario`; it never
   dispatches downstream directly, never writes events itself, never mutates state
   behind the orchestrator's back. Reads come from the event log.
3. **No per-role code.** `ingress_quantum(flow, payload)` is generic. No `if role
   == ...`, no per-role tool registration, no enumeration of the demo's roles in
   the server. The standing stop condition applies: **if exposing the front door
   requires per-role branching in the MCP layer, the abstraction is leaking — stop
   and surface it.**
4. **§2 world-vs-policy.** The MCP layer consumes the Ontology Service / orchestrator;
   it models **no** policy and adds **no** new ontology fields. It introduces no
   `prefer`/`priority`/`fallback`-shaped surface. It's transport, not world model.
5. **Idempotency** on ingress (above) — the one discipline that's easy to drop at a
   network boundary and must not be.

---

## Library grounding (pulled fresh via context7 — re-verify at implementation)

- **Use the Python `mcp` SDK's `FastMCP`** for a clean, low-ceremony server:
  `from mcp.server.fastmcp import FastMCP`; `mcp = FastMCP("e2e-orchestrator")`;
  decorate handlers (`@mcp.tool()` / `@mcp.resource(...)`) — schemas are
  auto-generated from type hints + docstrings (same ergonomics ADK gives the seven
  tools, which the team already relies on). Drop to `mcp.server.lowlevel.Server`
  only if you need handler-level control FastMCP doesn't give.
- **Transports:** start on **stdio** (`mcp.run(transport="stdio")`) — simplest,
  trivially testable, and directly consumable by an ADK `McpToolset` client via
  `StdioConnectionParams`. Target **streamable HTTP** for the "real front door"
  deployment shape (external systems over the network). Make transport config, not
  code.
- **ADK angle (informational):** ADK can *consume* MCP (`McpToolset`) and can
  *expose* ADK tools via a low-level server (`adk_to_mcp_tool_type`). We are doing
  **neither** of those directly — we expose the *orchestrator system*, so we use
  the plain `mcp` SDK, not the ADK-tool-exposing path. The ADK-MCP path matters
  only as the **stretch DoD** below: an external ADK agent consuming our front door
  as a client.
- **New entry point:** add `e2e-mcp = "e2e_orchestrator.mcp.server:main"` (or
  similar) to `[project.scripts]` in `pyproject.toml`, alongside `e2e-orchestrator`
  / `e2e-narrate` / `e2e-replay`. New module under `src/e2e_orchestrator/mcp/`.

---

## What NOT to expose / NOT to do

- **Do not expose the seven-tool kit over MCP.** Those tools are the *agent's*
  hands — Python closures over `(orchestrator, ToolContext)`, built fresh per
  invocation, several of which (`surface_decision`, `schedule_handoff`,
  `respond_to_query`) only make sense mid-invocation with a live `ToolContext`.
  Surfacing them externally is a category error: it would invite per-role coupling
  and bypass commands→events. The external surface is **ingress + reads**, full
  stop.
- **Do not let the MCP server route or decide.** No LLM, no flow logic, no axiom
  evaluation in the server. It forwards to the orchestrator and reads the log.
- **Do not return downstream effects by reading live in-memory state.** Return a
  pointer; let the client read the trace resource. Preserves replay + CQRS.
- **Do not add ontology fields or policy.** Transport only.
- **Do not skip idempotency** because "it's just a demo." The retry boundary is
  exactly where it earns its keep.

---

## Phase 7 DoD

1. An MCP server (`e2e-mcp`) exposing `ingress_quantum` (write) + the read-only
   resources (`trace`, `narrative`, `decisions`, `roleview`).
2. **A standard MCP client drives the promo-whiplash demo end-to-end through MCP**
   — ingress the `submit_promo_plan` quantum via `ingress_quantum`, then read the
   resulting `narrative://<run_id>` — reproducing the CLI demo through the protocol
   instead of `e2e-orchestrator --scenario`. (Use the MCP Inspector or a scripted
   `mcp` client; an ADK `McpToolset` agent consuming it is the **stretch** form.)
3. **Disciplines held, demonstrably:** no LLM in routing (routing still entirely in
   `flow_router`); commands→events (every external action goes through
   `dispatch_boundary_ingress` / the orchestrator; reads come from the event log);
   idempotency key on ingress (a retried `ingress_quantum` does not double-fire —
   add a test); no per-role code in the server; §2 untouched.
4. Structural tests exercise the server's tool/resource handlers against the **real**
   orchestrator seams (not mocks of them). Existing suite stays green.
5. `roleview://<role>` returns the same bytes as
   `render_role_view(role).as_agent_prompt()` — proving the front door is a faithful
   read of the Ontology Service.
6. CLAUDE.md gets a short Phase 7 note (the MCP boundary + the four constraints it
   must preserve), so a future session doesn't re-introduce routing or per-role
   code at the boundary.

**Stop condition (per the project's standing rule):** if the front door cannot be
expressed as a generic `ingress + read` adapter — if it needs to know about
specific roles, or wants to make a routing decision, or wants to expose an
agent-facing tool — pause and send a briefing back to the dev-manager session
before coding around it. That shape would mean the boundary is leaking the
abstraction the whole project is built to keep clean.

---

## Open questions to resolve while building (surface, don't guess)

- **Resource vs read-tool ergonomics.** If the current SDK's resource URI scheme is
  awkward for parameterized reads (`trace://<run_id>`), exposing the reads as
  read-only *tools* is acceptable — pick per current SDK ergonomics and note the
  choice. The *semantics* (read-only, sourced from events) matter; the MCP
  primitive used to carry them is secondary.
- **Run lifecycle / addressability.** The CLI runs one scenario per process and
  writes one trace file. The MCP server is long-lived and may field multiple
  ingresses — decide how `run_id` is minted and how traces are addressed
  (in-memory map of run_id → trace path is fine for the POC; note it as the
  reference-impl shape, like the rest of the durability layer per
  `docs/limitations.md`).
- **Transport for the demo.** stdio is enough for DoD #2; note streamable-HTTP as
  the production target without building auth (the MCP security/OAuth path is real
  but out of POC scope — flag it, defer it).

---

## What this experiment should teach us (capture in the Phase 7 live report)

Phase 7 is the evidence-gatherer for `agent_system_design.md` §12.8 (whether the
ontology should expose handshake transport). While building, observe and record:

- **Contract coverage.** When `ingress_quantum` becomes a real MCP tool, how much
  of its declaration is *already* covered by the existing boundary-role /
  `scont:Tool` contract, vs. what had to be added at the orchestrator/transport
  layer? (High coverage → the ontology already declares the edge; only the wire is
  extra.)
- **Did anything transport-shaped want to be *declared*** rather than wired —
  endpoint, session, auth, idempotency-at-the-wire? Each such thing is evidence for
  (or against) a future `scont:Connector` construct.
- **One abstraction for both directions?** Could the inbound MCP surface and an
  outbound reader tool be described by the *same* edge/handshake abstraction? If
  yes, that's the unification; if they diverge, note why.

These three observations are the deliverable that feeds the design question — as
important as the working front door itself. Do **not** try to answer §12.8 in code;
just surface what the realized edge reveals.
