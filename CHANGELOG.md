# Changelog

All notable changes to the orchestrator + generic agent runtime are documented
in this file. Format and voice follow the `e2e_ontology` sibling repo —
date-stamped session entries, no tagged releases yet, everything under
[Unreleased] until we cut a first version.

## [Unreleased]

### 2026-05-31 — Cut redundant context: `my_view` returns a pointer; capture cached tokens

- **`read_ontology("my_view")` no longer returns the full role view.** That view
  is *already* the agent's system instruction, so fetching it duplicated a large
  payload into the conversation that then rode along in every subsequent turn
  (and, by injecting mid-context, could defeat prefix caching). It now returns a
  short pointer. Measured on `demand-anomaly`: one `supply_planning` invocation
  dropped **669k → 316k total tokens (−53%)**. (Caveat: n=1 and the LLM is
  non-deterministic — the duplicated-payload removal is the deterministic win;
  the tool-call drop 23→13 is partly that, partly run variance.) Scripts/tests
  that call `my_view` are unaffected — they don't depend on the return content.
- **Usage stamp now also captures `cached_tokens`** (`cached_content_token_count`,
  a subset of `prompt_tokens`). On that run, **151k of 306k input tokens (~49%)
  were implicit-cache-discounted** → real cost ≈ **$0.30** vs ≈$0.47 uncached.
  Confirms Gemini implicit caching is active. Note: cached tokens are a *cost*
  discount, not freed context — they still occupy the window.

### 2026-05-31 — Cost visibility: token stamping + three runaway-loop trips

- **Token usage stamped per invocation.** `LlmAgentHandler.invoke` sums ADK's
  per-turn `usage_metadata` (prompt / candidates / total tokens) and returns it;
  it lands in the `AGENT_INVOCATION_COMPLETED` event's `outcome.usage`. Per-run
  cost is now computable from the trace with zero billing lag. This immediately
  surfaced a real exposure: one `supply_planning` invocation on `demand-anomaly`
  burned **~669k tokens (~$1)** — flagged for investigation (likely the prompt
  re-sending the full role view + accumulated tool results each turn).
- **Three runaway-loop trips** (deterministic, in-code — billing lags ~a day):
  - **Layer 1 — per-invocation LLM calls.** `agent_factory` now passes
    `RunConfig(max_llm_calls=...)` to `run_async` (`E2E_MAX_LLM_CALLS`, default
    50). Previously unset → ADK's default of **500** was the only ceiling.
  - **Layer 2 — per-run tokens.** The orchestrator accumulates the stamped
    usage and halts if cumulative tokens exceed `E2E_MAX_RUN_TOKENS` (default
    2,000,000 ≈ $3). Direct cost cap.
  - **Layer 3 — per-run invocations.** The orchestrator caps total agent
    dispatches at `E2E_MAX_INVOCATIONS` (default 25) — catches flow ping-pong /
    infinite auto-reroute loops that Layer 1 can't see (they span invocations).
  - A trip emits the new `RUNAWAY_GUARD_TRIPPED` event and raises
    `RunawayGuardError`, halting the run with the reason in the trace. Defaults
    are loose tripwires (above the heaviest observed legit run), tunable via env.
  - Tests: `test_runaway_guards.py` pins Layers 2 + 3 deterministically in stub
    mode (Layer 1 is ADK-native, fires only against a live model). 66 tests pass.

### 2026-05-31 — Model: actually move to `gemini-3.5-flash` (GA) + record the model in traces

- **The record correction first (this matters more than the change).** The
  2026-05-30 "migration to `gemini-3-flash-preview`" never took effect at
  runtime: it edited `.env.example` and removed the code fallback, but the active
  `.env` stayed on `gemini-2.5-flash`. **Every live run through Phase 5 — Phases
  2, 3, 4, and 5 — actually ran on `gemini-2.5-flash`.** The "verified on
  gemini-3-flash-preview" claims in the 2026-05-30 and Phase 5 entries are wrong
  and have been marked inline. Root cause it stayed hidden: **the trace never
  recorded which model ran**, so the claim drifted with nothing to check it
  against.
- **`gemini-3-flash-preview` does not work on this project.** It 404s
  (`Publisher Model ... not found or your project does not have access`) on both
  `us-east4` and `global` — it is Pre-GA and region-gated. We were never able to
  use it; the prior "works on us-east4" note was false.
- **Moved to `gemini-3.5-flash` (GA since 2026-05-19).** Verified live on this
  machine: `--scenario demand-anomaly` (clean, 0 `quantum_rejected`) and the
  load-bearing `--scenario capacity-resolution` (Scene 5: 3 context-assembly
  queries fired, `wait_all_unsatisfied: 0`, decision surfaced + validated,
  resolution `shift_to_coman`, `plan_fulfillment` fired). **First time the
  project has run on a Gemini 3.x model at all.** Agency surface **healthy +
  grounded** per the CLAUDE.md heuristic — real entities via reader tools
  (`NJ-L1`, `TP-FLAG-6OZ`, `COM-TGT-SEC-Q2`), operational stance, genuine
  OTIF-vs-co-man trade-off reasoning; it even adapted reader-tool queries
  (`TGT` vs `Target`) rather than hallucinating. Traces:
  `runs/local-3.5-global.jsonl`, `runs/local-3.5-capres.jsonl`.
- **`gemini-3.5-flash` requires `GOOGLE_CLOUD_LOCATION=global`** on this project
  (404s on `us-east4`). Newer GA models land on the global endpoint first.
- **Platform decision recorded.** Staying on **Vertex AI / Gemini Enterprise
  Agent Platform** (not the Gemini Developer API key path): it's the
  enterprise/GCP deployment target ADK co-designs for, the auth setup is already
  paid, and switching is a one-env-var toggle if that ever changes. The
  Developer-API-key path stays documented in `.env.example` as the low-friction
  escape hatch.
- **`agent_factory` / orchestrator:** the `AGENT_INVOCATION_STARTED` event now
  stamps `model` (the model the handler used; `None` for boundary/stub handlers),
  so every trace self-documents the model and this class of drift can't recur.
  64 tests pass; added/adjusted nothing in the structural DoD.

### 2026-05-31 — Cross-repo dependency: `e2e-ontology` as an editable package

- **The ontology is now a declared dependency**, not a `sys.path` shim. `pyproject.toml` lists `e2e-ontology` and installs it via `[tool.uv.sources]` as an editable local checkout (`../e2e_ontology`); a commented git-pin recipe (`{ git = ..., rev = <sha> }`) documents the reproducible/CI path when a version pin is wanted.
- **Removed `src/e2e_orchestrator/_bootstrap.py`** and its side-effecting import. `exploder` / `ontology_service` resolve as normal installed modules, and the YAML data-file paths now come from `ontology_service.paths` (`SUPPLY_CHAIN_DEMO_YAML`, `WORLD_STATE_YAML`) instead of being derived from the bootstrap-resolved repo path. Callers updated: `runtime/main.py`, `application/orchestrator.py`, `tests/conftest.py`.
- **Why.** A fresh clone or CI run previously failed unless a sibling `e2e_ontology` happened to sit at the conventional path, and nothing recorded which ontology version the orchestrator was verified against. The package dependency fixes both — and pinning to a git rev closes the version-pin gap entirely when reproducibility matters.
- **Verified.** 64 tests green; stub scenario unchanged; imports + data-file resolution confirmed CWD-independent (from an unrelated working directory).

### 2026-05-30 — Phase 5 follow-up: `wait_all` enforced as a deterministic gate

- **`wait_all` is now a consumed contract, not a comment.** The
  `resolve_capacity_conflict` Playbook declares three `required: true`
  context-assembly queries with `synchronization: wait_all`; nothing in the
  backbone enforced it, and a Phase 5 live run fired only 2 of 3 then decided
  anyway. New `Orchestrator.wait_all_missing(playbook, role, invocation_id)`
  returns the required context-assembly flows lacking a recorded query response
  for the active decision (correlated on `by_invocation` so a prior
  escalate-round's responses don't count). `surface_decision` calls it after the
  playbook-ref floor: a `wait_all` playbook may not surface until every required
  query is answered. Missing → `WAIT_ALL_UNSATISFIED` event (new EventKind) +
  `{"status": "wait_all_unsatisfied", "missing": [...]}`, in the family of
  `quantum_rejected` / `unknown_entity` — the gap is *named and visible in the
  trace*. The agent re-fires the missing `query(...)` and re-calls; same retry
  shape as a rejected quantum.
- **Why orchestrator, not ontology rendering** (owner-adjudicated): this is an
  unenforced declared contract the deterministic backbone is meant to hold (like
  the blocking-axiom floor), not an LLM-reliability gap. It gates on *evidence
  completeness*, never on *which* resolution — reads only `synchronization` +
  `context_assembly[].required`, never `selects_one_of` / `criteria_refs`. §2
  holds: agency untouched, no per-role/flow names hard-coded, inert when there's
  no matching `wait_all` playbook or no required flows.
- **Live-verified.** Across three `--scenario capacity-resolution` runs, two
  would have short-circuited (fired coman+otif, then tried to decide); the gate
  rejected each naming `check_promo_flexibility`, and the agent recovered —
  reasoning explicitly: *"my previous attempt to surface the decision failed …
  `wait_all_unsatisfied` … I must execute all queries specified in the
  context_assembly."* All three ended with the complete query set. The 2-of-3
  short-circuit is now structurally impossible, not just discouraged, and the
  agency surface stays healthy ("finish my homework", not "decide for me").
  Side effect: with complete evidence the agent now reliably weighs promo
  flexibility and chose `request_promo_revision`.
- **Tests (+2, 62 → 64).** `test_playbook_execution.py`: a 2-of-3 scripted run is
  gated (rejection names the missing flow, ordered before the surfaced decision)
  then recovers on the third query; a scope-guard test pins inertness (unknown
  playbook / wrong role / no queries). `test_phase5_dod.py` unchanged — the gate
  only *enforces* the "same query set" half the DoD already asserts.

### 2026-05-30 — Phase 5: Playbook execution + reader tools (the load-bearing claim)

- **Reader tools land (`application/reader_tools.py`).** Four deterministic
  world-state readers behind a registry mirroring `axiom_tools.py` (name →
  callable, bound at boot via `Orchestrator.reader_tools`): `query_plants_for_sku`
  (derives capable lines from the production schedule — `ProductionLine` has no
  capability slot), `query_line_load`, `query_commitments_in_window`,
  `query_supplier_for_sku`. A grounding miss returns `output=None` +
  `unknown_entity` evidence (the axiom-tool floor); `query_supplier_for_sku` is
  an honest miss — the demo world declares no SKU→supplier link, and the tool
  refuses to fabricate one.
- **`call_tool` wired** (`agent_toolkit.py`). Resolves the role's `scont:Tool`
  decl, validates `input`/`output` against the declared classes via
  `QuantumValidator`, dispatches to the registry. Undeclared name →
  `no_such_tool`; grounding miss → `unknown_entity`. No per-tool branching in the
  orchestrator. **The Phase 1.8 reach now connects** — the stub it hit is gone.
- **`surface_decision` validates playbook refs.** Cited playbook checked against
  `svc.playbooks_anchored_to(role)`; unknown → deterministic `unknown_playbook`
  (mirrors `no_such_tool` / the axiom `unknown_entity` floor — rejects
  non-existent names, **never ranks real ones**, §2-safe). Closes the
  `fulfill_supply_request` playbook-ref hallucination the 1.8 trace surfaced. It
  surfaces + validates only; it never executes or picks the resolution.
- **`read_ontology` gains `playbook:<name>` + `playbooks_anchored_to:<role>`**,
  so the Scene-5 agent's first action — reading its anchored playbook — resolves.
- **Scene 5 scenario (`--scenario capacity-resolution`).** Design pivot worth
  recording: the scenario **injects** the `CapacityConflict` straight into
  supply_planning (seeder `inject_capacity_conflict`) rather than deriving it
  from an upstream production assignment. Why — the first live run proved a
  reader-tool-*grounded* supply_planning sizes the request to fit (or shifts to
  an empty window: it assigned 4500 to NJ-L1 in days 129–135, dodging the
  140–146 conflict). **The grounding fix works so well the agent avoids the
  conflict** — so the playbook path has to begin with the conflict already
  detected, per `plan_of_attack` §5. The three cross-domain query responders are
  wired in **both** modes (new `responders` scenario key) so the live agent
  weighs *real typed evidence* (§3 case-1 trade-off), with supply_planning the
  only real LLM under test.
- **always_fires is agent-driven, not orchestrator-enforced.** The orchestrator
  has zero event→flow triggering; auto-firing `capacity_resolved` +
  `plan_fulfillment` would add a primitive *and* playbook-specific knowledge to
  the backbone (§2 violation). The agent fires them from the rendered playbook.
  Soft guarantee, on-brand: the floor is axioms, not playbook completeness.
- **Tests (+14, 48 → 62).** `test_reader_tools.py` (typed outputs + grounding
  floor + output-class validation), `test_playbook_execution.py` (full Scene 5
  wiring + the `surface_decision` rejection), `test_phase5_dod.py` (the §10
  thesis made deterministic: two variants differing ONLY in resolution prove the
  context-assembly query set is identical and independent of the choice).
- **Live verification — the thesis holds, with two agency wobbles to brief
  upstream.** Across live runs (`runs/phase5-live-{A,B,C}.jsonl`,
  ~~`gemini-3-flash-preview`~~ **[CORRECTION 2026-05-31: these runs actually ran
  on `gemini-2.5-flash` — the active `.env` was never moved off it; see the
  2026-05-31 entry]**): supply_planning reads the playbook, fans out the
  context-assembly queries, surfaces a **validated** decision, picks one
  resolution, fires always_fires. **Hallucinated-grounding is gone** — both
  entity refs (NJ-L1, COM-TGT-SEC-Q2, inferred TP-SEC-6OZ/Target) and the
  playbook ref are real and validated; the reasoning weighs the advisory criteria
  and cites system mechanics (healthy agency surface per CLAUDE.md). **Judgment
  tracks evidence**: with degraded boundary-stub evidence the agent chose
  `re_request_production`; with real cross-domain evidence it chose
  `shift_to_coman` (demo_narrative Scene 6's outcome). Two findings for the
  ontology session, **not** orchestrator patches (per the Phase 5 stop
  conditions): (a) resolutions *converged* across seeds (all `shift_to_coman`) —
  within the DoD's "may differ", and genuine: the evidence strongly favours
  co-man (qualified + capacity, low OTIF penalty) so consistent rational judgment,
  not structured-away agency; (b) one run fired **2 of 3** context-assembly
  queries — short-circuiting `wait_all` once co-man looked viable (the
  menu-picking edge). The fix for both is stronger Playbook rendering / the
  orientation that all three `context_assembly` queries are required before
  deciding — upstream, never an orchestrator patch.

### 2026-05-30 — Phase 1.8 paired upstream + early reader-tool reach signal

- **Phase 1.8 landed in `e2e_ontology`** (largest upstream change since Phase
  1): `scont:Playbook` + `scont:Tool` meta-constructs in `scont_meta.yaml`,
  the `resolve_capacity_conflict` Playbook anchored to (supply_planning,
  capacity_conflict_detected), and four reader-tool instances
  (`query_plants_for_sku`, `query_line_load`, `query_commitments_in_window`,
  `query_supplier_for_sku`). 249 tests pass upstream; 48 still pass here
  (purely additive — no signature gotcha like Phase 1.5 surfaced).
- **Two §2-sensitive disciplines worth recording** for future ontology
  contributors: (a) `llm_prompt_hint` deliberately lives as a sibling
  annotation, not a `PlaybookBody` field — matches the FlowBody precedent,
  pinned by `test_llm_prompt_hint_in_body_rejected` so a future edit can't
  silently let it back in-body; (b) `selects_one_of` is alphabetized in the
  authored YAML AND in the renderer output, with the label "(pick one; order
  arbitrary)" plus `test_resolution_paths_neutralized` as the guard so no
  future edit can let list position read as priority. The architecture's
  thesis depends on these.
- **Live verification on `--scenario capacity-conflict`.** The new sections
  of the rendered role view are reaching the agent: `supply_planning`'s
  first action (`seq 8`) was `call_tool("query_plants_for_sku", {sku: ...})`
  — the **first time in the project an agent has reached for a reader tool
  from its declared `tools_available_to`**. `call_tool` is still a stub
  (Phase 5 wires the dispatch), so the call returned `no_such_tool` and the
  agent improvised — but the *reach* is the signal. Phase 1.8 surfaced the
  tools in the prompt; the LLM used them correctly on the first attempt.
  Trace at `runs/phase4-post-1.8-live.jsonl`.
- **One new pattern observation worth tracking.** The same trace surfaced an
  unexpected variant of the hallucinated-grounding pattern: the agent
  invoked `surface_decision` referencing a playbook name
  (`fulfill_supply_request`) that **doesn't exist in the ontology** — there
  is only `resolve_capacity_conflict` anchored to a different event. This
  is hallucinated-grounding applied to *playbook references* rather than
  *entity references*. Same fix family (Phase 5 wiring will validate playbook
  names against declared playbooks at `surface_decision` call time, same
  way the axiom evaluator rejects unknown entity refs). Worth noting in the
  four-pattern heuristic when Phase 5 wraps; for now, captured here so we
  don't forget.
- **Housekeeping.** Dev-manager seed updated to mark Phase 1.8 done. Phase 5
  seed prompt (drafted earlier this session) is now unblocked — gate
  condition (Playbook + Tool sections in supply_planning's rendered prompt)
  is met.
- **Briefings committed for posterity.** `briefings/phase-1.8-design-memo.md`
  (the design exploration with the seven decisions we converged on) and
  `briefings/ontology-phase-1.8-playbook-tool-meta.md` (the paste-ready
  briefing that went upstream). Useful templates for future substantive
  upstream changes (e.g. Phase 5.5 if surface_decision needs a typed
  `DecisionSurface` quantum).

### 2026-05-30 — Model migration to `gemini-3-flash-preview` + Phase 1.7b pairing + dev-manager seed

> **[CORRECTION 2026-05-31]** This entry is inaccurate. The "migration" changed
> only `.env.example` and the code fallback — it never moved the *running* model.
> The active `.env` stayed on `gemini-2.5-flash`, so the "live re-verification on
> gemini-3-flash-preview" below **did not happen on that model** (it ran on
> 2.5-flash). `gemini-3-flash-preview` in fact 404s on this project (Pre-GA,
> not available on us-east4 *or* global). See the 2026-05-31 entry for the real
> migration to `gemini-3.5-flash`. The claim "the preview works on us-east4" is
> false.

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
