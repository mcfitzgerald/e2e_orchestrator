# Changelog

All notable changes to the orchestrator + generic agent runtime are documented
in this file. Format and voice follow the `e2e_ontology` sibling repo —
date-stamped session entries, no tagged releases yet, everything under
[Unreleased] until we cut a first version.

## [Unreleased]

### 2026-05-30 — Model migration to `gemini-3-flash-preview` + Phase 1.7b pairing + dev-manager seed

- **Model migration.** Default agent model moved from `gemini-2.5-flash` to
  `gemini-3-flash-preview` (Vertex preview). Three reasons: (1) 2.5-flash is on
  a retirement path, no earlier than 2026-10-16, so migration is required
  before Phase 8 demo polish either way; (2) ~3× faster, +15% accuracy
  reportedly, with the accuracy bump directly relevant to Phase 5's Scene 5
  trade-off reasoning; (3) cost premium ($0.50/$3.00 vs $0.30/$2.50 per 1M
  input/output tokens) is negligible at our usage volume (single-digit dollars
  across the whole project at projected demo iteration counts). The preview
  works on `us-east4` without needing the `global` endpoint.
- **Removed the hard-coded model fallback** in `LlmAgentHandler.__init__`. The
  model identifier is now config, not code — when `E2E_AGENT_MODEL` isn't set
  and no explicit `model=` is passed, the constructor raises a clear error
  pointing at `.env.example`. Rationale: the right model depends on what's
  supported on the user's Vertex project + region at any given time
  (preview/GA, regional/global), and a hard-coded default that quietly works
  on one machine while 404-ing on another is a footgun we already hit twice.
  Explicit > implicit. `.env.example` documents the current recommendation
  plus alternatives (2.5-flash for the stable path, 3-pro-preview for heavier
  reasoning, 3.5-flash for newest/heaviest).
- **Live re-verification.** `--scenario demand-anomaly` on
  `gemini-3-flash-preview`: clean end-to-end. The four-pattern agency-surface
  heuristic still holds (operational stance reasoning, no identity-discovery
  framing), confirming the orientation preface isn't model-specific. Same run
  surfaced a fresh hallucinated-grounding case — `assigned_line='line-A'
  assigned_plant='plant-001'` — which the `tool_ref` evaluator caught as
  `unknown_entity` and auto-rerouted via `escalate_capacity_conflict`. Same
  pattern as Phase 4's earlier traces, different invented names — confirms
  the floor catches arbitrary hallucinations, not just the specific ones
  Phase 4 tested against. Trace at `runs/phase4-respect-lt-live.jsonl`.
- **Phase 1.7b paired (ontology side).** `respect_lead_time` on
  `submit_procurement_request` now declares `tool_ref: evaluate_respect_lead_time`
  (e2e_ontology commit on 2026-05-30). The orchestrator-side callable was
  already registered in Phase 4's `application/axiom_tools.py`. Unit-level
  acceptance verified: the ontology-declared axiom now routes via `tool_ref`
  and blocks an infeasible procurement payload (`required_by 120 < today(100)
  + lead_time 28 = 128 for SUP-MENTHOL-002`) → `replan_on_infeasible_request`.
  Live trace of this path is owed when a scenario naturally traverses
  procurement (probably Phase 5 or later).
- **Dev-manager session seed** (`briefings/dev-manager-session-seed.md`). The
  conversation that ran the project through Phases 2/3/4 was doing double
  duty as a coding session and as a project-tracker session. This brief
  cleanly extracts the tracker role into its own seed: project intent, design
  rules, two-repo coordination patterns, current state, four-pattern agency
  heuristic, reading order. Paste-ready as the seed prompt for a new
  development-manager session whose job is briefings and decision tracking,
  not code edits.

### 2026-05-30 — Phase 4: deterministic backbone (axioms + FSM + world state)

- **World-state loader (`world_state/loader.py`).** Loads
  `e2e_ontology/world_state.yaml`, validates every instance against its declared
  class via the same SchemaView-driven `QuantumValidator` the orchestrator uses
  for quanta ("the fixture is real data shaped by the real schema", §9). Exposes
  **generic, parameterized** queries — `find(class, **slots)`, `get_sku`,
  `get_supplier`, `get_production_line(plant, line)`, `query_line_load(line,
  window)`, and an injectable `today()` clock. No per-instance/domain accessor
  (the Phase 4 loader stop condition). The orchestrator instantiates one at boot
  and exposes it to the axiom evaluator.
- **Real axiom evaluator (`application/axiom_evaluator.py`).** Replaces the
  Phase 2 stub. Dispatch is by what the axiom declares, uniformly: `tool_ref` →
  registry callable `(quantum, world_state)`; else `expr` → **slot-level**
  subset (`{quantum.<slot>}` resolved against the payload; comparisons /
  boolean / arithmetic via a restricted AST walk); else `nl`-only → advisory
  pass. The named stop condition is enforced in code: an `expr` containing a
  **function call** (`today()`) or **entity traversal**
  (`{quantum.assigned_line.rated_weekly_capacity}`) is reported *non-enforcing*
  ("candidate for tool_ref"), never interpreted — the interpreter does not grow
  function support. `evaluate_axiom` is shared by flow-axiom and FSM-guard
  checks, so the deterministic floor is identical on both.
- **Axiom tool registry (`application/axiom_tools.py`).** Deterministic compute
  tools for world-state axioms: `evaluate_line_capacity_not_exceeded` and
  `evaluate_respect_lead_time`. Domain knowledge lives here (the legitimate
  home), not in the orchestrator — a failing blocking axiom returns a
  `recovery_quantum` already shaped for the `on_failure_route_to` flow's class,
  so the orchestrator only validates + routes it. **Grounding check** (Phase 4's
  addition to the DoD spirit): a quantum referencing an entity absent from world
  state returns `passed=False, evidence="unknown_entity"`. A hallucinated
  `assigned_line` / `assigned_plant` is caught by code, not waved through.
- **FSM tracker (`application/fsm_tracker.py`).** Per-quantum lifecycle state in
  the durability backend's materialized views (§9). `advance_fsm` (Phase-2 stub
  in the toolkit) becomes real: look up the declared `StateMachineBody`, find the
  transition from the current state, evaluate the guard via the shared
  evaluator, advance or follow `on_failure_route_to`. Generic over
  `StateMachineBody` — guard axioms are resolved by scanning declared flow
  axioms; no per-FSM logic (the tracker stop condition).
- **Orchestrator auto-recovery.** A blocking axiom failure no longer just logs:
  the original handoff is **not** executed (the floor is in code), and when the
  failing axiom supplies both a recovery flow and a constructable recovery
  quantum, the orchestrator **automatically dispatches** `on_failure_route_to` —
  no LLM in the routing. A grounding failure (`unknown_entity`) yields no
  recovery quantum, so the run halts at the gate and the gap is visible in the
  trace rather than hidden.
- **`capacity-conflict` scenario (Scene 4).** `--scenario capacity-conflict`:
  the Walmart 3x promo, with supply_planning assigning the full uplift (3000
  units) to NJ-L1 — which already carries 3500/5000 in the window. `3500 + 3000
  = 6500 > 5000` → the blocking `line_capacity_not_exceeded` axiom fires and the
  orchestrator routes `escalate_capacity_conflict` (production_planning →
  supply_planning) carrying a `CapacityConflict` with the computed 1500-unit
  shortfall. The promo happy path was **grounded** to real world-state entities
  (TP-FLAG-6OZ on NJ-L1, sized to headroom) so it still passes the deterministic
  evaluator.
- **Validator: multivalued slots.** `QuantumValidator` now validates each
  element of a multivalued slot against its range (CapacityConflict's
  `competing_skus`, `at_risk_commitments`). Generic; no regression for the flat
  Phase 2/3 quanta.
- **Tests (48 pass, +27).** `test_world_state_loader.py` (validation + conflict
  math + grounding), `test_axiom_evaluator.py` (tool_ref / expr / nl-only paths,
  unknown-entity rejection, the "same code path handles both blocking axioms"
  DoD, and the function-call/traversal stop condition), `test_fsm_tracker.py`
  (advance / block-and-route / reject), `test_phase4_dod.py` (Scene 4
  end-to-end: blocking axiom fires, recovery flow taken automatically,
  production_planning never invoked, deterministic across runs). Phase 2 + 3
  DoD tests unchanged and green.
- **Verified live (Vertex, `gemini-2.5-flash`), both scenarios.** The
  deterministic floor caught the LLM where Phase 3 could not: supply_planning
  hallucinated a line (`Line_A`/`Plant_North`; and `LINE-1`/`PLANT-A` on the
  promo run) and the grounding check returned `unknown_entity` → the blocking
  axiom fired → `request_production` was **blocked, not executed**. The FSM
  tracker advanced real lifecycles live (RequestLifecycle draft→submitted→
  approved, PurchaseOrderLifecycle draft→transmitted). **Agency surface healthy**
  (CLAUDE.md heuristic): agents cite system mechanics in their reasoning
  ("updated the PurchaseOrder's status from draft to transmitted using
  advance_fsm", supply_planning reasoning about the "topology hinge" and its
  fulfillment options) — operational reasoning, not identity-discovery or
  menu-picking. **Grounding still absent** (hallucinated line names persist) —
  exactly the Phase 3 precursor/grounding split, except Phase 4 now *enforces*
  the gap instead of silently passing it. This is the Phase 5 reader-tool
  pull-forward signal: the agent reasons agentically but cannot ground its
  references until the Tool meta-construct + reader tools land. Local artifacts:
  `runs/phase4-conflict-live.jsonl`, `runs/phase4-promo-live.jsonl`.
- **Upstream signal (for the ontology session).** `respect_lead_time` still
  declares only `expr` (`{quantum.required_by} >= today() + {quantum.supplier.
  lead_time_days}`), which uses both a function call and an entity traversal —
  outside the slot subset, so it currently evaluates *non-enforcing* (its FSM
  guard passed by default live). Per the Phase 4 stop condition ("the right move
  is more tool_ref migrations upstream, not more interpreter features"), it
  should gain `tool_ref: evaluate_respect_lead_time` (the callable is already
  registered here). The evaluator's "same code path handles both blocking
  axioms" is proven in `test_axiom_evaluator.py` via the tool path; once the
  ontology declares the tool_ref it routes there at runtime too.

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
