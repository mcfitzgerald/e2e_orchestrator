# e2e_orchestrator

Orchestrator + generic agent runtime for the supply chain ontology developed in
[`e2e_ontology`](../e2e_ontology). Phase 2 proved the thesis end-to-end for a
single agent; Phase 3 generalized it to three roles with no per-role code; Phase
4 put the deterministic backbone (world-state axioms, FSM guards, auto-recovery)
under the agent layer; Phase 5 added Playbook execution + reader tools (Scene 5
cross-domain context assembly); **Phase 6 completes the demo** — the three
resolution paths, the full promo-whiplash narrative from one seed through
conflict → resolution → re-convergence, and a trace renderer + replay so the log
tells the Scene 1→6 story; and **Phase 7 opens the front door** — the whole system
is reachable through MCP as a generic `ingress + read` adapter, realizing the
inbound boundary edge the ontology already declares (`is_boundary`). The demand
side is also grounded now (Seed A): `demand_planning` reads a real baseline via
`query_baseline_demand` instead of inventing one.

## What this repo contains

- **Generic Agent** — one ADK `LlmAgent` template, instantiated per role.
  Identity comes from `OntologyService.render_role_view(role).as_agent_prompt()`;
  the seven-tool kit (`read_ontology`, `emit_event`, `handoff`, `query`,
  `advance_fsm`, `call_tool`, `surface_decision`, plus `respond_to_query` for
  query targets) is bound at invocation time as closures over the orchestrator.
- **Orchestrator** — deterministic backbone. Validates quanta against the LinkML
  schema, evaluates axioms against world state, enforces FSM guards, routes
  flows by ontology lookup (and auto-follows `on_failure_route_to` on a blocking
  axiom), persists every meaningful event to a JSONL log with stable idempotency
  keys. Split into application + durability layers behind a small contract so the
  durability backend (JSONL today, Temporal later) is swappable.
- **World state** — a YAML fixture (`e2e_ontology/world_state.yaml`) loaded and
  validated against the schema at boot; the axiom evaluator reads it for
  tool-backed axioms (line schedules, lead times) and an injectable `today()`
  clock. Swappable for an enterprise system-of-record reader behind the same
  query surface.
- **Boundary** — scripted seeders for `demand_sensing` / `customer_development`
  and stub responders for other boundary roles. No LLM inside a boundary role.

## What's locked in (durable design rules — see `CONTRIBUTING.md`)

1. **World vs. policy.** The ontology models the world and the action
   vocabulary. It never models the decision policy. The orchestrator refuses to
   consume policy fields from the ontology (no `prefer:`, no `fallback_chain:`).
2. **No LLM in the routing path.** Routing is a deterministic ontology lookup.
   ADK's `transfer_to_agent` / `sub_agents`-as-routing is unused.
3. **No per-role code in the agent template.** A second or third role lands as
   a YAML edit upstream, not a code change here.
4. **Three borrowed disciplines.** Idempotency keys on every flow firing,
   commands→events (CQRS), signals as the primitive for waits.

## Layout

```
src/e2e_orchestrator/
  application/    flow router, quantum validator, axiom evaluator + tools,
                  FSM tracker, orchestrator
    tools/        the seven-tool kit, bound per-invocation
  world_state/    fixture loader + generic typed queries (schedule, clock)
  durability/     JSONL event log + in-memory views + asyncio signals
  boundary/       ingress simulators + stub responders
  mcp/            Phase 7 front door: OrchestratorFrontDoor (core) + FastMCP
                  server (e2e-mcp). ingress_quantum=command, trace/narrative/
                  decisions/roleview resources=events. A dumb transport adapter.
  runtime/        wires everything; CLIs: e2e-orchestrator, e2e-narrate, e2e-replay
tests/            unit tests + Phase 2/3/4/5/6/7 DoD assertions
```

The sibling `e2e_ontology` repo is a declared dependency, installed from a local
editable checkout (`../e2e_ontology`) via `[tool.uv.sources]` in
`pyproject.toml`; pin it to a git rev there for a reproducible/CI build.

## Quick start

```sh
uv sync --extra dev
uv run pytest                          # all tests, including the Phase 2 + 3 DoD tests (stub mode)
uv run e2e-orchestrator --mode stub    # promo whiplash happy path (default scenario), no LLM
uv run e2e-orchestrator                # same, with a real LLM (needs ADK credentials)

uv run e2e-orchestrator --scenario capacity-conflict --mode stub  # Phase 4 Scene 4 (blocking axiom + recovery)
uv run e2e-orchestrator --scenario capacity-resolution --mode stub  # Phase 5 Scene 5 (playbook + context assembly)
uv run e2e-orchestrator --scenario full-demo --mode stub --narrate  # Phase 6 — full Scene 1→6 narrative, rendered
uv run e2e-orchestrator --scenario demand-anomaly --mode stub     # original Phase 2 round trip

# Render any existing trace into the Scene 1→6 story, or compare two for replay:
uv run e2e-narrate runs/<scenario>-<ts>.jsonl
uv run e2e-replay runs/<a>.jsonl runs/<b>.jsonl   # deterministic-orchestration equivalence
```

`--scenario` selects the run:
- `promo` (default — the Phase 3 three-role happy path),
- `capacity-conflict` (Phase 4 Scene 4 — a blocking axiom fires and the
  orchestrator auto-routes the recovery flow),
- `capacity-resolution` (Phase 5 Scene 5 — the `resolve_capacity_conflict`
  playbook runs, three context-assembly queries fan out, a decision is surfaced,
  `shift_to_coman` is chosen; this is the live `--mode llm` vehicle),
- `resolution-internal` / `resolution-promo` (Phase 6 — the other two resolution
  paths: `re_request_production` with a revised quantum that passes the capacity
  guard, and `request_promo_revision` across the commercial boundary),
- `full-demo` (Phase 6 — the whole promo-whiplash narrative from ONE promo seed:
  Scenes 1→6, conflict derived honestly in stub, ending in re-convergence),
- `demand-anomaly` (the original Phase 2 single-role round trip).

Each run produces `runs/<scenario>-<ts>.jsonl` — the append-only event log.
`--narrate` prints the readable Scene 1→6 story after the run; `e2e-narrate`
renders any saved trace; `e2e-replay` confirms two traces share the same
deterministic orchestration structure. The rich trace UI is Phase 8.

## Phase 2 definition of done

A `DemandAnomaly` enters at the `demand_sensing` boundary; the
`demand_planning` agent (LLM or scripted, depending on `--mode`) calls
`handoff('submit_supply_request', SupplyRequest(...))`; the orchestrator
validates the quantum, evaluates flow axioms (none on this path), appends
`handoff_executed` with a stable idempotency key, and dispatches to a stub
`supply_planning`. The trace shows the full transaction with agent reasoning.

See `tests/test_phase2_dod.py` for the executable assertion. Verified live
2026-05-29 (`gemini-2.5-flash` on Vertex); see CHANGELOG.

## Phase 3 definition of done

A single command runs the full promo whiplash happy path (Scenes 1-3):

```
submit_promo_plan → demand_planning → submit_supply_request → supply_planning
  → request_production → production_planning
```

A `TradePromotion` enters at the `customer_development` boundary; three internal
role agents act in turn (`demand_planning`, `supply_planning`,
`production_planning`); every handoff is routed by deterministic ontology lookup
(no LLM chooses a target); the trace shows each role grounding itself in its
rendered role view (`read_ontology`). Crucially, **adding the second and third
roles required no edit to the agent template or the seven tools** — the new
agents are the same `LlmAgentHandler` parameterized by role, with identity from
the ontology. See `tests/test_phase3_dod.py`.

Verified live 2026-05-29: three real LLM agents acted on Vertex, zero
quantum rejections, and `supply_planning` produced the first concrete
agency moment — invented its own plant/line/window plan, sized volume to
hit `required_by`, cited the capacity axiom as a constraint. Trace details
in CHANGELOG. Future phases should watch for this signal as the
"is the agency surface still healthy" landmark (see `CLAUDE.md`).

## Phase 4 definition of done

A blocking axiom triggers the recovery flow **without an LLM in the routing**.
Run Scene 4:

```
uv run e2e-orchestrator --scenario capacity-conflict --mode stub
```

The Megalomart 3x promo enters; `supply_planning` assigns the full uplift (3000
units) to NJ-L1, which already carries 3500/5000 in the window. The orchestrator
evaluates `line_capacity_not_exceeded` against world state
(`sum_scheduled_units + volume <= rated_weekly_capacity`), the blocking axiom
fires (`6500 > 5000`, shortfall 1500), `request_production` is **blocked, not
executed**, and the orchestrator automatically follows
`on_failure_route_to: escalate_capacity_conflict` back to `supply_planning`
carrying a `CapacityConflict`. `production_planning` never gets the option to
wave capacity through — the floor is in code. The same evaluator backs FSM
guards (`advance_fsm`) and `respect_lead_time`; the trace shows the
deterministic outcome as a non-LLM event. See `tests/test_phase4_dod.py`,
`tests/test_axiom_evaluator.py`, `tests/test_fsm_tracker.py`.

A second guarantee added to the DoD's spirit: hallucinated entity references
(`assigned_line` / `assigned_plant` absent from world state) are caught by the
evaluator (`unknown_entity`) and rejected. Verified live 2026-05-30 — the
deterministic floor caught the LLM hallucinating a line where Phase 3 silently
passed it; agency surface stayed healthy, grounding remains the Phase 5
reader-tool gap. Details in CHANGELOG.

## Phase 5 definition of done

The generic agent reads its anchored Playbook, fans out the **same** three
context-assembly queries every run (deterministic), and surfaces a validated
decision — but the resolution it picks is the LLM's judgment and may differ
across seeds. Run Scene 5:

```
uv run e2e-orchestrator --scenario capacity-resolution --mode stub
```

Reader tools (`application/reader_tools.py`) let the agent ground real
plants/lines/commitments instead of inventing them; `call_tool` validates
input/output against the declared classes; `surface_decision` rejects an unknown
playbook ref (`unknown_playbook` floor); and a `wait_all` gate holds the decision
until every required query has a response. See `tests/test_phase5_dod.py`,
`tests/test_reader_tools.py`, `tests/test_playbook_execution.py`.

## Phase 6 definition of done

**A single command runs the full promo-whiplash narrative end-to-end; the trace
tells the Scene 1→6 story; the narrative document and the trace agree.**

```
uv run e2e-orchestrator --scenario full-demo --mode stub --narrate
```

From ONE promo seed: the promo enters (Scene 1), the forecast is revised and a
SupplyRequest flows to supply_planning (Scenes 2–3), the full uplift overflows
NJ-L1 so the `line_capacity_not_exceeded` floor **blocks** `request_production`
and the orchestrator auto-reroutes `escalate_capacity_conflict` (Scene 4),
supply_planning runs the playbook and assembles cross-domain context (Scene 5),
picks a resolution and fires `plan_fulfillment` so the chain **re-converges**
(Scene 6). In stub mode the conflict is derived honestly (deterministic scripts). Live
`--mode llm` can *also* derive it (a verification run did — see below), but
`--scenario capacity-resolution` *injects* it for a reliable Scenes 4–6 run,
because a reader-tool-grounded agent sometimes sizes the request to fit and
dodges a derived conflict (the Phase 5 finding — see CHANGELOG).

All **three** resolution paths are exercised: `shift_to_coman` (external
boundary), `re_request_production` (internal re-entry — the revised quantum
**passes** the same capacity guard that blocked the original, via the
`requested→assigned` FSM transition: the floor *accepting* the corrected plan),
and `request_promo_revision` (across the commercial boundary). The context-
assembly query set is identical across all three; only the resolution differs.

`e2e-narrate` renders any trace into the readable story; `e2e-replay` confirms
deterministic orchestration replay (same seed → identical structural trace,
modulo random ids — the LLM step itself is not bit-reproducible, by design). See
`tests/test_phase6_dod.py`.

Verified live 2026-05-31 on `gemini-3.5-flash`, **two runs that picked different
resolutions** (irreducible agency, live):
- `capacity-resolution` (Scenes 4–6, injection): 9 invocations, 323,871 tokens
  (204,504 ≈ 63% cached), `shift_to_coman` — co-man premium $1,275 < OTIF $7,200.
  Trace `runs/phase6-live-capres-A.jsonl`.
- `full-demo` (the **whole Scene 1→6 narrative from one seed**, conflict derived
  honestly live): 12 invocations, 594,290 tokens (303,843 ≈ 51% cached),
  `request_promo_revision` — chose to renegotiate the still-`aligned` promo over a
  $36,975 co-man premium. Trace `runs/phase6-live-fulldemo.jsonl`.

Both runs: no guard tripped, zero rejections, `wait_all` satisfied, agency
**healthy + grounded** (real entities only; large numbers all traceable through
the deterministic floor). First re-verification of the resolution arc — and of
Scenes 1–3 — on a Gemini 3.x model, and the §10 "path materially differs across
runs" criterion met live. Guards survive the full narrative with margin (12/25
invocations, 0.59M/2M tokens).

## Phase 7 definition of done

**The orchestrator system is reachable through MCP as a generic `ingress + read`
adapter — an external client drops a signal in and reads back what happened — with
the four boundary constraints intact.**

```
uv run e2e-mcp --transport stdio --mode stub --world full-demo
```

`ingress_quantum(flow, payload, idempotency_key?)` is the single write surface
(tool = command); it forwards to `Orchestrator.dispatch_boundary_ingress` and
returns a *pointer* (resource URIs), not synchronous downstream effects. Read-only
`trace://`, `narrative://`, `decisions://`, `roleview://` resources project the
event log / Ontology Service (resources = events). The server is a dumb adapter:
**no LLM in routing** (routing stays in `flow_router`), **commands→events** (reads
come only from the log), **no per-role code** (`ingress(flow, payload)` is generic
— a standing stop condition if it ever needs per-role branching), **§2 untouched**
(transport only). The seven-tool kit is deliberately **not** exposed — those are the
agent's hands, and surfacing them would invite per-role coupling. `mcp/core.py`
holds the transport-agnostic logic (tested against the real seams); `mcp/server.py`
is the thin FastMCP wiring. See `tests/test_phase7_dod.py` (incl. a real
`ClientSession` over the SDK in-memory transport).

Verified live 2026-06-01/02 on `gemini-3.5-flash`, driving real `LlmAgent`s through
the protocol: a single `ingress_quantum(submit_promo_plan, …)` ran the full
promo-whiplash narrative end-to-end (`runs/mcp-run-cd439092752c.jsonl` — 0.49M
tokens, ~$0.42, no guard trip), resolving via `request_promo_revision`. With Seed A
in place, `demand_planning`'s first action is `query_baseline_demand` → reads the
real baseline (1500/wk) → sizes the request from that read — **no free-floating
quantity** (closes the sixth agency-surface pattern; see `CLAUDE.md`).

## Phase 7 §12.8 — the ontology exposes the handshakes (open)

The world fixture and the seeded boundary responders are **shims behind edges the
ontology already declares**: boundary roles (inbound) and `scont:Tool` readers
(outbound). In production these bind to real integrations (REST/MCP/A2A) behind the
*same* typed contracts; the agent and the routing don't change. Phase 7 realizes the
first such edge (inbound, as MCP) and is the **experiment** informing whether the
transport itself becomes declarative (a `scont:Connector` in the ontology) or stays a
binding layer — leaning **contract in, wire out**. See `docs/limitations.md` and the
design memo `briefings/design-memo-ontology-exposes-handshakes.md`; the open question
is `e2e_ontology/agent_system_design.md` §12.8.
