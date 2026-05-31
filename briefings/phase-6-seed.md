# Phase 6 seed prompt — paste into a fresh orchestrator session

> Drafted by the dev-manager session 2026-05-31. Phase 6 = "Resolution and full
> demo (Scene 6)" per `e2e_ontology/plan_of_attack.md`. Scoped to EXCLUDE what
> Phase 5 already shipped — read §0 before assuming anything needs building.

I want to execute Phase 6 of the supply chain orchestrator build. Orient before
any work.

## 0. What Phase 5 already delivered (do NOT rebuild)

Phase 5 landed and is live-verified. Already done — reuse, don't redo:

- **`shift_to_coman` resolution path** executes end-to-end, and **`plan_fulfillment`**
  (the playbook's `always_fires` flow) fires on `capacity_resolved`. Phase 6's
  6.1/6.2 are therefore *partly done*.
- **Cross-domain responders wired in both stub and llm modes** (`responders`
  scenario key in `runtime/main.py`) for `co_manufacturing`, `customer_development`,
  `logistics_planning` — the Scene 5 context-assembly query targets.
- **`--scenario capacity-resolution`** exists (seeder `inject_capacity_conflict`);
  the `resolve_capacity_conflict` playbook runs, 3 context-assembly queries fan
  out under `wait_all`, decision is surfaced + validated, one resolution chosen.
- **Reader tools** (`application/reader_tools.py`, 4 readers), `call_tool`
  dispatch, `surface_decision` playbook-ref validation (`unknown_playbook` floor),
  `read_ontology` `playbook:` / `playbooks_anchored_to:` forms, the `wait_all`
  enforcement gate.
- 66 tests pass.

**So the real remaining Phase 6 work is:** the *other two* resolution paths, the
full single-seed end-to-end narrative + re-convergence, and 6.3 (trace narrative
+ replay).

## 1. Environment & infra changes since the Phase 5 seed (READ — these bit us)

- **Model is `gemini-3.5-flash` on the `global` endpoint** (Vertex / Gemini
  Enterprise Agent Platform). `GOOGLE_CLOUD_LOCATION=global` is **required** —
  `gemini-3.5-flash` 404s on `us-east4` for this project, and
  `gemini-3-flash-preview` 404s everywhere (Pre-GA). `.env.example` documents it.
  Every prior phase (2–4) was actually verified on `gemini-2.5-flash`; only
  Scene 5 has run on 3.5-flash. **Phase 6's full end-to-end run is the
  re-verification of the whole chain on the current model.**
- **`e2e_ontology` is now a pip dependency** (editable local source), not a
  sys.path shim. Run from the orchestrator dir with the sibling repo present;
  `uv sync --extra dev`.
- **Runaway-loop guards are live** and will halt a run that trips them
  (`RUNAWAY_GUARD_TRIPPED` event + `RunawayGuardError`):
  `E2E_MAX_LLM_CALLS=50` (per invocation), `E2E_MAX_INVOCATIONS=25` (per run),
  `E2E_MAX_RUN_TOKENS=2000000` (per run). **CRITICAL for Phase 6:** the full
  six-scene narrative is the longest, heaviest run in the project — it may
  legitimately exceed `E2E_MAX_INVOCATIONS=25` and/or `E2E_MAX_RUN_TOKENS=2M`.
  **Measure the full run's invocation count + cumulative tokens; if a guard
  false-trips on legitimate work, raise it via env for the demo run and report
  the real numbers back to the dev-manager session** (the defaults may need
  revisiting for the full narrative). Do NOT just disable the guards.
- **Traces stamp `model` (on `agent_invocation_started`) and token `usage`
  (incl. `cached_tokens`, on `agent_invocation_completed.outcome.usage`).** This
  is gold for 6.3 — the narrative renderer and cost story read straight from the
  log. `read_ontology("my_view")` now returns a pointer (its full view is the
  system prompt), so don't expect the full view back from that query.

## 2. Confirm the gate + read order

Phase 6 depends on Phase 5 (done). Read, in order:

- This repo: `CLAUDE.md` (four-pattern agency heuristic — Phase 6's full run is
  where you confirm grounded agency holds across the *whole* narrative on
  3.5-flash), `CHANGELOG.md` (the 2026-05-31 entries: model move, guards, token
  stamping, my_view), `briefings/phase-5-seed.md`,
  `briefings/dev-manager-session-seed.md`.
- This repo code: `runtime/main.py` (`SCENARIOS` registry, the
  `capacity-resolution` scenario, `inject_capacity_conflict` seeder, `responders`
  wiring), `application/orchestrator.py` (auto-recovery routing, the guards),
  `application/fsm_tracker.py`, `application/axiom_tools.py`.
- Ontology repo: `plan_of_attack.md` Phase 6; `demo_narrative.md` Scene 6 + the
  "Domains and roles summary" + executive punchline; `agent_system_design.md`
  §10 (full demo), §12.5 (replay/determinism — confirm what ADK gives for free),
  §12.3 (DecisionSurface — still deferred as a typed quantum unless Phase 6
  forces it). The resolution flows in `supply_chain_demo.yaml`:
  `re_request_production` (`capacity_resolved` → supply_planning →
  production_planning, revised `ProductionRequest`), `request_promo_revision`
  (supply_planning → customer_development, `TradePromotion`), `shift_to_coman`
  (done), `plan_fulfillment` (done).

## 3. Phase 6 deliverables (per `plan_of_attack.md` §6)

### 6.1 — the two remaining resolution paths (shift_to_coman is done)
- **`re_request_production`** — internal re-entry. supply_planning constructs a
  **revised `ProductionRequest`** (reduced volume / different line / shifted
  window) that **now passes** the `line_capacity_not_exceeded` axiom, and hands
  off to production_planning. This is the narrative's "request_production
  re-evaluated, axiom now passes" — i.e. demonstrate the deterministic floor
  *accepting* the corrected plan, not just blocking the bad one.
- **`request_promo_revision`** — skeletal boundary handoff to
  `customer_development` (the promo-renegotiation path), carrying a
  `TradePromotion`. Boundary responder may be a stub.
- All three paths are **ontology flows** — selecting among them stays the agent's
  judgment; no per-role/per-path branching in the orchestrator or agent template.

### 6.2 — `plan_fulfillment` + re-convergence
- `plan_fulfillment` already fires on `capacity_resolved`. Phase 6 shows the
  system **re-converges on the happy path** after *each* resolution path:
  production proceeds / logistics updates the fulfillment plan / OTIF
  commitments preserved, and the run reaches a clean terminal state.
- Handle the Scene 6 **autonomous-vs-escalated** distinction: per the playbook's
  `human_involvement` policy on supply_planning, a decision above threshold is
  surfaced to a human. POC-minimum: the `decision_surfaced` event + reasoning in
  the trace are sufficient; a human step may be simulated. Don't model a typed
  `DecisionSurface` quantum unless you actually need it (§12.3 defer).

### 6.3 — trace narrative + replay
- **Trace renderer:** turn the event log into the readable Scene 1→6 story
  (a CLI/text narrative is enough here — the rich UI is Phase 8; this overlaps
  Phase 8 deliberately). Lean on the stamped `model` + `usage` and the existing
  event kinds (`agent_reasoning`, `query_*`, `decision_surfaced`,
  `handoff_executed`, `axiom_evaluated`, `event_emitted`).
- **Replay:** given the same seed signal, the orchestration replays from the
  event log deterministically (the backbone is commands→events). Confirm what
  ADK provides per §12.5; the LLM step itself is not bit-reproducible, so be
  explicit about what "replay" guarantees (deterministic orchestration replay vs.
  re-running the LLM).

### Full end-to-end scenario
- A single command runs the **whole promo-whiplash narrative** from the initial
  promo seed through conflict → resolution → re-convergence. NOTE the Phase 5
  finding: a grounded agent *sizes to fit and dodges a derived conflict*, so the
  conflict is **injected** (`inject_capacity_conflict`) rather than derived. The
  full demo should chain that injection into the complete narrative; flag to the
  dev-manager session if deriving-the-conflict-honestly becomes necessary for
  demo credibility.
- Tests: extend the DoD test to the full narrative (scripted form), plus
  per-path tests for `re_request_production` (revised quantum passes the axiom)
  and `request_promo_revision`.

## 4. Stop conditions to watch

- **Resolutions don't vary across LLM seeds** → agency structured away; revisit
  the playbook against §2 (do NOT patch the orchestrator). Phase 6 adds the other
  two paths, so verify the agent *can* land on `re_request_production` or
  `request_promo_revision` when the evidence favors them — not always
  `shift_to_coman`. (Phase 5 already showed the choice tracks evidence: stub
  evidence → `re_request_production`, real evidence → `shift_to_coman`.)
- **Any per-role / per-resolution-path code** in the agent template or the seven
  tools → abstraction leaking; the paths are ontology flows.
- **A guard false-trips on the legitimate full run** → raise the env limit for
  the demo run and report real numbers; don't disable guards or silently cap.
- **Hallucinated grounding returns on the full run** → reader-tool wiring /
  validation floors, per the four-pattern heuristic — not prompt nudges.
- **DoD fails to hold:** the trace and `demo_narrative.md` must agree. If they
  diverge, fix the run, not the narrative doc (or escalate a narrative change).

## 5. Before any code change

- `uv sync --extra dev`; `uv run pytest -q` → **66 passing**.
- `uv run e2e-orchestrator --mode stub` (default promo path) runs clean.
- `--scenario capacity-resolution --mode stub` runs (Phase 5 path intact).
- Confirm `.env` has `GOOGLE_CLOUD_LOCATION=global` + `E2E_AGENT_MODEL=gemini-3.5-flash`.

## 6. After implementation, before committing

- All tests green.
- **The full end-to-end narrative runs from one command, live (`--mode llm`),
  on `gemini-3.5-flash`.** Capture the trace. Read it against the four-pattern
  heuristic across the whole run.
- **Report the full run's invocation count + cumulative + cached tokens** (and
  whether any guard tripped). This closes the re-verification gap (Phases 3/4
  never ran on 3.5-flash) and tells the dev-manager session whether the 2M /
  25-invocation defaults survive contact with the full narrative.
- Each of the three resolution paths exercised (live or scripted), with
  `re_request_production`'s revised quantum passing the capacity axiom.
- `--scenario promo` / `capacity-conflict` / `demand-anomaly` still pass.
- The §10 "thesis-holds" signal: one seed → full cross-domain narrative → human
  (or autonomous) decision with quantified trade-offs → re-convergence, with the
  trace telling the story and matching `demo_narrative.md`.

Phase 6 is the last build phase before the demo is whole. The code is moderate;
the load-bearing parts (cross-domain assembly, grounded agency, the deterministic
floor) already work — Phase 6 completes the paths, chains the narrative, and
makes the trace tell the story. Take the time to read Scene 6 and §10 so the run
and the narrative agree.
