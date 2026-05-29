# Changelog

All notable changes to the orchestrator + generic agent runtime are documented
in this file. Format and voice follow the `e2e_ontology` sibling repo —
date-stamped session entries, no tagged releases yet, everything under
[Unreleased] until we cut a first version.

## [Unreleased]

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
