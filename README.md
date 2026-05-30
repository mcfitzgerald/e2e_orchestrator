# e2e_orchestrator

Orchestrator + generic agent runtime for the supply chain ontology developed in
[`e2e_ontology`](../e2e_ontology). Phase 2 proved the thesis end-to-end for a
single agent; Phase 3 generalized it to three roles with no per-role code; and
**Phase 4 puts the deterministic backbone under the agent layer** — real
world-state-backed axiom evaluation, FSM guards, and automatic recovery routing
on a blocking constraint, all without an LLM in the routing path.

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
  runtime/        wires everything; `e2e-orchestrator` CLI entrypoint
tests/            unit tests + Phase 2/3/4 DoD assertions
```

The sibling `e2e_ontology` repo is surfaced on `sys.path` by
`src/e2e_orchestrator/_bootstrap.py`. Override via `E2E_ONTOLOGY_PATH`.

## Quick start

```sh
uv sync --extra dev
uv run pytest                          # all tests, including the Phase 2 + 3 DoD tests (stub mode)
uv run e2e-orchestrator --mode stub    # promo whiplash happy path (default scenario), no LLM
uv run e2e-orchestrator                # same, with a real LLM (needs ADK credentials)

uv run e2e-orchestrator --scenario capacity-conflict --mode stub  # Phase 4 Scene 4 (blocking axiom + recovery)
uv run e2e-orchestrator --scenario demand-anomaly --mode stub     # original Phase 2 round trip
```

`--scenario` selects the run: `promo` (default — the Phase 3 three-role happy
path), `capacity-conflict` (Phase 4 Scene 4 — a blocking axiom fires and the
orchestrator auto-routes the recovery flow), or `demand-anomaly` (the original
Phase 2 single-role round trip). Each run produces `runs/<scenario>-<ts>.jsonl`
— the append-only event log. Replay and trace UIs (Phase 8) consume this format.

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

The Walmart 3x promo enters; `supply_planning` assigns the full uplift (3000
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
