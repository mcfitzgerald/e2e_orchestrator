# Changelog

All notable changes to the orchestrator + generic agent runtime are documented
in this file. Format and voice follow the `e2e_ontology` sibling repo —
date-stamped session entries, no tagged releases yet, everything under
[Unreleased] until we cut a first version.

## [Unreleased]

### 2026-05-29 — Phase 3: multi-role happy path (Scenes 1-3)

- **Three roles, zero template edits.** `supply_planning` and
  `production_planning` are now real `LlmAgentHandler`s in `llm` mode — built by
  the existing factory from their rendered ontology role views, with **no
  changes to the agent template (`agent_factory.py`) or the seven tools
  (`tools/agent_toolkit.py`)**. The Phase 3 stop condition ("Phase 3 requires
  per-role code in the generic agent template") did not trip: the diff touches
  only boundary simulation, runtime wiring, and tests. This is the load-bearing
  proof that the generic-agent thesis generalizes past one role.
- **Second boundary seeder.** `boundary/customer_development.py`
  (`emit_promo_plan_aligned`) — symmetric to `demand_sensing`. Constructs an
  aligned `TradePromotion` (BOGO on Product A at Walmart, 3x lift, 2-week window
  ~6 weeks out, `commitment_status: aligned`) and dispatches the
  `submit_promo_plan` ingress flow into `demand_planning`. No LLM inside the
  boundary role.
- **Scenario registry + single-command happy path.** `runtime/main.py`
  generalized from a single hard-coded Phase 2 path to a `SCENARIOS` registry.
  `e2e-orchestrator` now runs the **promo whiplash happy path by default**:
  `submit_promo_plan → demand_planning → submit_supply_request → supply_planning
  → request_production → production_planning`. The original Phase 2 round trip is
  preserved behind `--scenario demand-anomaly`. Stub-mode scripts for the three
  roles let the full chain run without an LLM key (`--mode stub`); the
  orchestrator can't tell a script from an LLM, so the structural DoD holds for
  the live run.
- **Override removed.** The hand-wired `supply_planning` `InternalStubHandler`
  override is gone from both `runtime/main.py` and `tests/test_phase2_dod.py`.
  In stub mode the factory builds the same `InternalStubHandler` as a default
  (no special-casing); in llm mode it builds a real agent. The Phase 2 DoD test
  still passes unchanged in substance.
- **Phase 3 DoD test.** `tests/test_phase3_dod.py` asserts the three-role chain
  via scripted handlers: TradePromotion ingress at the `customer_development`
  boundary, exactly three agents invoked in order, both handoffs routed by
  deterministic ontology lookup (`submit_supply_request` → supply_planning,
  `request_production` → production_planning), stable idempotency keys, an
  axiom-evaluation event per handoff, and `read_ontology` lookups by every role
  on the path (routing traceable to the ontology). Imports the canonical scripts
  and seeder from `runtime.main` so the CLI stub path and the test can't drift.
  21 tests pass.
- **Verified live.** Three-agent run on Vertex (`gemini-2.5-flash`):
  `TradePromotion` injected at `customer_development` → `demand_planning` →
  `supply_planning` → `production_planning`. All three LLM agents acted; both
  handoffs routed deterministically; **zero `quantum_rejected`** — every agent
  built a schema-valid quantum on the first try. The agency is real, not
  replayed: `supply_planning` made its own network call (provisional
  `plant-A`/`line-1`, a day 30-36 window chosen to hit `required_by` 42, volume
  4500) — all different from the stub script's values — and its reasoning
  explicitly cited the `line_capacity_not_exceeded` axiom and its automatic
  reroute. `production_planning` advanced `ProductionRequestLifecycle` on
  `assign`. 19 events; local artifact at `runs/phase3-live.jsonl`. (Note: the
  LLMs acted directly from their rendered role-view system prompts and largely
  skipped the optional `read_ontology` calls the stub scripts make — routing is
  still 100% deterministic in the orchestrator, so the DoD holds.)

### 2026-05-29 — Phase 2 verified live + pairing with ontology Phase 1.5

- **Verified live.** First end-to-end live run with `gemini-2.5-flash` on
  Vertex AI: `DemandAnomaly` injected at the `demand_sensing` boundary →
  `demand_planning` LLM agent → `submit_supply_request` → `supply_planning`
  stub. The agent's first `handoff` payload was correct on the first try —
  no `quantum_rejected`, no retry, single `handoff_executed`. Reasoning
  chunks show identity grounded in the rendered role view ("As
  `demand_planning`, my role is to revise the forecast and then request
  supply"). 13 events in the trace; local artifact at
  `runs/phase2-live.jsonl`.
- **Surfaced upstream.** The first live attempt failed in a renderer-side
  way: the agent guessed `SupplyRequest` field names (`required_by_day`,
  `quantity`) because the role view declared only the quantum *class*, not
  its slot *schema*. Quantum slot structure is world model per §2, so the
  fix belonged upstream. Documented the gap, handed off to the ontology
  session, which landed it as Phase 1.5 (`e2e_ontology` commit `c18d372`).
  Schemas now render with name, range, required-ness, and description.
- **Paired with Phase 1.5.** `_to_flow_summary` upstream now requires a
  `SchemaView`; `FlowRouter.resolve` forwards it. One-line orchestrator-side
  change.
- **Live-run scaffolding.** Three small fixes the live verification
  surfaced:
  - `LlmAgentHandler.app_name` switched from `e2e_orchestrator:<role>` to
    `e2e_orchestrator_<role>` — ADK's `App.name` validator rejects `:`.
  - Default model switched from `gemini-flash-latest` (AI Studio shorthand;
    404s on Vertex regional endpoints like `us-east4`) to
    `gemini-2.5-flash` (ADK's own documented default per
    `LlmAgent.set_default_model` docs).
  - Minimal dotenv loader (`src/e2e_orchestrator/_env.py`, ~25 lines, no
    `python-dotenv` dependency) + `.env.example` so per-checkout Vertex
    credentials don't leak into the shell.
- **Phase 2 stop condition cleared.** `plan_of_attack.md` Phase 2: *"If the
  DoD doesn't hold within two working sessions, the contract between the
  Ontology Service and the Generic Agent is wrong — fix the contract before
  pressing forward."* Contract held in one session post-1.5 fix; Phase 3
  unblocked. 20 tests pass; live run reproduces the scripted DoD.

### 2026-05-28 — Phase 2: orchestrator scaffold + generic agent + first round trip

- **Added.** Two-layer split per `agent_system_design.md` §4.5. Application
  layer (`src/e2e_orchestrator/application/`): `orchestrator.py` (the
  deterministic backbone — boundary ingress, validate, axiom eval, idem,
  log, dispatch), `flow_router.py` (pure ontology lookup), `axiom_evaluator.py`
  (Phase 2 stub — no axioms on this path; Phase 4 fills in `expr:` and
  tool-backed eval), `quantum_validator.py` (LinkML SchemaView-driven slot
  validation; rejects unknown_slot, missing_required, type_mismatch,
  enum_unknown), `agent_factory.py` (`LlmAgentHandler` for non-boundary
  roles, `BoundaryStubHandler` for `is_boundary: true`, `InternalStubHandler`
  as the Phase-2 stand-in for not-yet-built internal roles,
  `ScriptedAgentHandler` test double).
- **Added.** Fixed seven-tool kit
  (`application/tools/agent_toolkit.py`): `read_ontology`, `emit_event`,
  `handoff`, `query`, `advance_fsm`, `call_tool`, `surface_decision` —
  plus `respond_to_query` for query-targeted invocations. Per-invocation
  closures over `(orchestrator, ToolContext)`. ADK auto-generates JSON
  schemas from signatures + docstrings. Every mutating tool routes through
  the orchestrator with a stable idempotency key.
- **Added.** Durability layer (`src/e2e_orchestrator/durability/`):
  `interface.py` (the `DurabilityBackend` Protocol — `append`,
  `check_idempotency`, `read_events`, `await_signal`, `notify_signal`,
  `read_view`, `put_view`), `jsonl_backend.py` (POC implementation —
  append-only JSONL log + in-memory views + `asyncio.Future`-based
  signals). Production swap-in (Temporal/Restate) is a different class
  behind the same Protocol; application layer doesn't move.
- **Added.** Boundary simulator
  (`src/e2e_orchestrator/boundary/demand_sensing.py`) — scripted, never an
  LLM. Constructs a `DemandAnomaly` payload and calls
  `orch.dispatch_boundary_ingress("raise_demand_anomaly", payload)`. Phase
  3 will add a symmetric `customer_development` seeder for the promo
  pathway.
- **Added.** Runtime entrypoint (`runtime/main.py`) wired to the
  `e2e-orchestrator` console script via `pyproject.toml`. `--mode stub`
  forces `ScriptedAgentHandler` for `demand_planning` and runs without
  needing LLM credentials.
- **Added.** Tests (20 pass): `test_event_log.py` (append, idempotency,
  signals, views), `test_quantum_validator.py` (required/type/unknown_slot
  paths), `test_flow_router.py` (handoff vs query resolution),
  `test_agent_factory.py` (boundary/internal/llm handler dispatch),
  `test_phase2_dod.py` (full round trip via `ScriptedAgentHandler` plus an
  idempotency-on-replay assertion).
- **Added.** `pyproject.toml` (`uv`-managed; deps: `google-adk`,
  `linkml-runtime`, `pydantic`, `pyyaml`, `pytest`, `pytest-asyncio`).
  `_bootstrap.py` surfaces the sibling `e2e_ontology` repo on `sys.path`
  via `E2E_ONTOLOGY_PATH` or by convention (`../e2e_ontology`). Temporary
  until the ontology repo gets a `pyproject.toml`.
- **Added.** Project docs: `CLAUDE.md` (durable design rules, stop
  conditions, common pitfalls), `CONTRIBUTING.md` (§2 world-vs-policy,
  three borrowed disciplines, what-lives-where), `README.md` (Phase 2 DoD
  + layout + quickstart).
- **Phase 2 (scaffold) DoD met.** Scripted-form: `tests/test_phase2_dod.py`
  asserts boundary_ingress → invocation_started → tool_call(read_ontology)
  → tool_call(handoff) → axiom_evaluated → handoff_executed with the right
  idempotency key shape and JSONL-on-disk matching in-memory events. Live
  verification deferred to the 2026-05-29 session (see above).
