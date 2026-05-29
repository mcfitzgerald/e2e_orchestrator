# e2e_orchestrator

Orchestrator + generic agent runtime for the supply chain ontology developed in
[`e2e_ontology`](../e2e_ontology). Phase 2 proved the thesis end-to-end for a
single agent; **Phase 3 proves it generalizes to three roles** — the promo
whiplash happy path (Scenes 1-3) runs through `demand_planning`,
`supply_planning`, and `production_planning` with no per-role code.

## What this repo contains

- **Generic Agent** — one ADK `LlmAgent` template, instantiated per role.
  Identity comes from `OntologyService.render_role_view(role).as_agent_prompt()`;
  the seven-tool kit (`read_ontology`, `emit_event`, `handoff`, `query`,
  `advance_fsm`, `call_tool`, `surface_decision`, plus `respond_to_query` for
  query targets) is bound at invocation time as closures over the orchestrator.
- **Orchestrator** — deterministic backbone. Validates quanta against the LinkML
  schema, evaluates axioms (Phase 4 fills in real evaluation), routes flows by
  ontology lookup, persists every meaningful event to a JSONL log with stable
  idempotency keys. Split into application + durability layers behind a small
  contract so the durability backend (JSONL today, Temporal later) is
  swappable.
- **Boundary** — scripted seeders for `demand_sensing` and stub responders for
  other boundary roles. No LLM inside a boundary role.

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
  application/    flow router, quantum validator, axiom evaluator, orchestrator
    tools/        the seven-tool kit, bound per-invocation
  durability/     JSONL event log + in-memory views + asyncio signals
  boundary/       ingress simulators + stub responders
  runtime/        wires everything; `e2e-orchestrator` CLI entrypoint
tests/            unit tests + Phase 2 DoD assertion
```

The sibling `e2e_ontology` repo is surfaced on `sys.path` by
`src/e2e_orchestrator/_bootstrap.py`. Override via `E2E_ONTOLOGY_PATH`.

## Quick start

```sh
uv sync --extra dev
uv run pytest                          # all tests, including the Phase 2 + 3 DoD tests (stub mode)
uv run e2e-orchestrator --mode stub    # promo whiplash happy path (default scenario), no LLM
uv run e2e-orchestrator                # same, with a real LLM (needs ADK credentials)

uv run e2e-orchestrator --scenario demand-anomaly --mode stub   # original Phase 2 round trip
```

`--scenario` selects the run: `promo` (default — the Phase 3 three-role happy
path) or `demand-anomaly` (the original Phase 2 single-role round trip). Each
run produces `runs/<scenario>-<ts>.jsonl` — the append-only event log. Replay
and trace UIs (Phase 8) consume this format.

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
