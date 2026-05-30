# Phase 5 seed prompt — paste into a fresh orchestrator session

> Finalized by the dev-manager session 2026-05-30 against the landed ontology
> (Phase 1.8) and the `runs/phase4-post-1.8-live.jsonl` trace. Two factual
> corrections vs. the original draft are noted inline where they matter:
> the fourth reader tool is `query_supplier_for_sku` (not
> `query_promo_flexibility_status`, which does not exist), and the Playbook's
> `context_assembly` entries are **query flows** fired via `query(...)`, a
> different mechanism from the four `call_tool(...)` reader tools.

---

I want to execute Phase 5 of the supply chain orchestrator build. Please orient
yourself before any work.

## 0. Starting context — the reach already happened

The last live run (`runs/phase4-post-1.8-live.jsonl`, on `gemini-3-flash-preview`)
is the single most useful thing to internalize before you start. Phase 1.8
surfaced the Playbook + the four reader tools into `supply_planning`'s rendered
role view, and on the *first* invocation the agent's opening action (seq 8) was
`call_tool("query_plants_for_sku", {sku: ...})` — the first time in the project
an agent reached for a reader tool from its declared `tools_available_to`. It
returned `no_such_tool` because `call_tool` is still the Phase-2 no-op stub, so
the agent improvised. **The reach is the signal; the dispatch is what you wire.**
Phase 5 closes a loop that's already half-open: the LLM is reaching for the
right primitive, it just hits a stub.

Same trace surfaced a new variant of hallucinated-grounding worth a deliverable
(see §4): the agent called `surface_decision` citing a playbook name
(`fulfill_supply_request`) that doesn't exist — only `resolve_capacity_conflict`
does, anchored to a different event. Hallucinated-grounding applied to *playbook
references* rather than *entity references*. Same fix family as the axiom
evaluator's `unknown_entity` floor.

## 1. Confirm the upstream gate first

Phase 5 depends on `e2e_ontology` Phase 1.8 having landed:

- `scont_meta.yaml` has `PlaybookBody` and `ToolBody` definitions (and
  `scont:Playbook` + `scont:Tool` meta-classes referenced).
- `supply_chain_demo.yaml` declares the `resolve_capacity_conflict` Playbook
  anchored to `(supply_planning, capacity_conflict_detected)`, with
  `context_assembly` (three **query flows** — see exact names in §3),
  `decision.criteria_refs`, `decision.selects_one_of` (the resolution flows),
  `synchronization: wait_all`, and `always_fires` (`capacity_resolved` event +
  `plan_fulfillment` flow).
- Four reader-tool `scont:Tool` declarations exist:
  **`query_plants_for_sku`, `query_line_load`, `query_commitments_in_window`,
  `query_supplier_for_sku`** — each with typed input/output classes and an
  `implementation` contract name the orchestrator binds to a callable at boot.
  (Note: there is no `query_promo_flexibility_status` tool. Promo flexibility is
  reached as a *query flow* — `check_promo_flexibility` — not a reader tool.
  Keep the two mechanisms distinct; see §2.)
- Snapshots regenerated; tests pass; primer updated for the new
  meta-constructs (it states the `selects_one_of` / `context_assembly`
  list-order-is-arbitrary rule).

If absent or incomplete, **stop.** The Phase 5 contract relies on the Playbook +
Tool meta-constructs existing upstream — building reader tools or playbook
execution here without them would couple orchestrator code to specific
role/flow names, violating the no-per-role-code rule.

## 2. Two distinct mechanisms — do not conflate them

Phase 5 wires **two different primitives**, and the DoD depends on both:

| Mechanism | Tool | What it reads | Sync model | Phase 5 deliverable |
|---|---|---|---|---|
| **Reader tools** | `call_tool(name, input)` | World state (which plants make a SKU, current line load, commitments in a window, supplier for a SKU) | synchronous compute | `application/reader_tools.py` + `call_tool` dispatch |
| **Context-assembly query flows** | `query(...)` | Cross-role typed responses (OTIF exposure, promo flexibility, co-man availability) — assembled by the `resolve_capacity_conflict` Playbook | `wait_all` fan-out + signal-based waits | Playbook execution path |

The grounded happy path uses **reader tools** to pick a *real* `(plant, line,
window)` with provable headroom instead of inventing names (this is what kills
the hallucinated-grounding pattern). The Scene 5 trade-off uses the **query
flows** declared in the Playbook's `context_assembly` to gather cross-domain
evidence before the agent picks a resolution. Wiring one and declaring victory
leaves half the DoD unmet.

## 3. Read this repo's docs in order

- `CLAUDE.md` — particularly the four-pattern agency-surface heuristic. Phase 5
  is where the **hallucinated-grounding** pattern is supposed to disappear
  (reader tools land here) and where the **menu-picking** regression test
  (Scene 5 trade-off resolution) fires for the first time.
- `CHANGELOG.md` — read the Phase 4 entry (the floor catches `line-A/plant-001`
  hallucinations via `unknown_entity`) and the 2026-05-30 Phase 1.8 entry (the
  reader-tool reach signal + the `surface_decision` playbook-ref hallucination).
- `README.md`.
- `briefings/dev-manager-session-seed.md` — project-level summary; the broader
  context any single-phase session lacks.
- `tests/test_phase4_dod.py` and `application/axiom_tools.py` — the `tool_ref`
  dispatch + generic-registry patterns established there are the model for
  reader-tool registration. `reader_tools.py` should mirror `axiom_tools.py`'s
  registry shape (name → callable, bound at boot, domain knowledge lives in the
  tool not the orchestrator).

## 4. Read from the ontology repo

- `plan_of_attack.md` Phase 5 + the **Phase 5 stop condition**: *"If Scene 5
  doesn't produce different resolutions across runs with different LLM seeds,
  the agency has been structured away — revisit the playbook against the §2
  world-vs-policy rule."* The single most important stop condition in the
  project.
- `agent_system_design.md` §3 (where agency irreducibly lives — Scene 5 is the
  §3 case-1 demonstration), §6.1 (Playbook construct), §6.2 (Tool
  meta-construct), §10 (Scene 5 as the load-bearing demo moment).
- `demo_narrative.md` Scene 5 + Scene 6 — cross-domain context assembly +
  resolution.
- The `resolve_capacity_conflict` Playbook in `supply_chain_demo.yaml`
  (~line 1431). Read every field; it is the most §2-sensitive construct in the
  whole ontology. Exact fields you'll wire against:
  - `context_assembly` (all `required: true`): `check_otif_exposure`,
    `check_promo_flexibility`, `check_coman_availability`
  - `synchronization`: `wait_all`
  - `decision.criteria_refs`: `viable_promo_renegotiation`, `viable_coman_shift`,
    `tolerable_otif_penalty` (advisory — they report path *viability*, never
    preference or order)
  - `decision.selects_one_of`: `request_promo_revision`, `re_request_production`,
    `shift_to_coman` (renderer alphabetizes; list order is **not** a ranking)
  - `always_fires`: `capacity_resolved` (event) + `plan_fulfillment` (flow)
  - `scont:llm_prompt_hint` lives as a **sibling annotation**, not a
    `PlaybookBody` field (FlowBody precedent; pinned upstream by
    `test_llm_prompt_hint_in_body_rejected`).

## 5. Phase 5 work (per `plan_of_attack.md` §5)

**The DoD:** across two live runs with different LLM seeds, `supply_planning`
fires the **same three context-assembly query flows** (deterministic context
assembly per the Playbook) but **may pick different resolutions** (irreducible
LLM judgment). The contrast is visible in the trace.

Concrete deliverables:

- **Reader tools registry.** New `application/reader_tools.py` — implementations
  of the four declared `scont:Tool` instances. Each takes typed input + world
  state, returns the typed output class. Registered through the same generic
  registry pattern as `axiom_tools.py`. The orchestrator binds tool name →
  callable at boot. No per-tool branching in the orchestrator.
- **`call_tool` wiring.** The seven-tool kit's `call_tool` (currently a no-op
  stub) dispatches to the reader-tool registry. Validates input against the
  declared `input_class`, validates output against the declared `output_class`
  (reuse `QuantumValidator`'s SchemaView-driven path). A call to an undeclared
  tool returns a clean `no_such_tool` (not a crash) — the same way the axiom
  evaluator handles unknown refs.
- **`surface_decision` playbook-ref validation** *(new — from the 1.8 live
  trace).* When `surface_decision` cites a playbook name, validate it against
  the playbooks declared in the ontology (specifically those anchored to the
  acting role). An unknown name is rejected the way the axiom evaluator rejects
  `unknown_entity` — deterministic floor, visible in the trace, **not** a prompt
  nudge. This is §2-safe: it rejects *non-existent* names, it does not rank or
  prefer among real ones. Keep it generic (validate against declared playbooks;
  no hard-coded `resolve_capacity_conflict`).
- **Playbook execution.** When a Playbook-anchored event arrives at a role, the
  orchestrator surfaces the Playbook to the agent (the role view already renders
  Playbooks anchored to it post-1.8). The agent reads the Playbook via
  `read_ontology(playbook:resolve_capacity_conflict)`, then fires the three
  context-assembly queries via `query(...)`. The orchestrator's query mechanism
  (partially built in Phase 4) handles the `wait_all` fan-out + signal-based
  waits.
- **Decision surface assembly.** After all three query responses arrive, the
  agent assembles a structured decision surface (the §12.3 question). **Defer**
  modeling `DecisionSurface` as a typed quantum until you actually need it.
  Phase 5 minimum: the agent's reasoning chunks + the chosen resolution flow are
  enough for the trace; a typed `DecisionSurface` quantum is optional polish.
- **Scene 5 scenario.** New `--scenario capacity-resolution` (or extend
  `--scenario capacity-conflict`): inject the capacity conflict →
  `supply_planning` auto-receives `escalate_capacity_conflict` → the Playbook
  anchored to `(supply_planning, capacity_conflict_detected)` fires → three
  queries fan out (`wait_all`) → typed responses arrive → `supply_planning`
  picks one of `request_promo_revision` / `re_request_production` /
  `shift_to_coman` → resolution flow executes → `capacity_resolved` event +
  `plan_fulfillment` flow fire per the Playbook's `always_fires`.
- **Tests:** `tests/test_reader_tools.py`, `tests/test_playbook_execution.py`,
  `tests/test_phase5_dod.py` (scripted-form Scene 5). Add a focused test for the
  `surface_decision` playbook-ref rejection.

## 6. Phase 5 stop conditions to watch hard

- **Two runs always pick the same resolution.** Agency has been structured away.
  Revisit the Playbook against §2 — likely some field encodes preference or
  fallback ordering. Brief the ontology session; **do not** patch in the
  orchestrator.
- **`supply_planning` fires fewer or more than the three declared queries.**
  Either the Playbook didn't surface (wiring bug here) or the LLM is treating
  the query list as a menu (orientation preface / Playbook rendering not strong
  enough → ontology-session briefing, not an orchestrator patch).
- **Reader tools surface entities that fail downstream validation.** The reader
  tool's `output_class` is misaligned with what downstream consumers (axioms,
  FSM guards) expect. Upstream issue — brief the ontology session.
- **Hallucinated-grounding persists in the Phase 5 trace.** If `supply_planning`
  still invents plant/line/SKU names instead of reaching for
  `call_tool("query_plants_for_sku", ...)`, the Playbook rendering isn't nudging
  strongly enough OR the agent doesn't see the reader tools in its declared
  `tools_available_to`. Diagnose with the four-pattern heuristic in `CLAUDE.md`.
  (Remember: the reach *already* worked once pre-wiring — if it regresses after
  wiring, suspect the dispatch, not the prompt.)
- **Playbook-ref hallucination persists at `surface_decision`.** If the agent
  still cites non-existent playbook names after the validation lands, the
  rejection isn't surfacing in the trace or isn't wired into the
  `surface_decision` path.

## 7. Before any code change

- `uv run pytest -q` → **48 passing**.
- `uv run e2e-orchestrator --mode stub` → default promo path runs.
- Inspect a fresh rendered role view for `supply_planning` and confirm it now
  includes the `resolve_capacity_conflict` Playbook block **and** the four
  reader tools in `tools_available_to`.

## 8. After implementation, before committing

- All tests green.
- **Two live runs** of the Scene 5 scenario with the same env config; capture
  both traces.
- **Diff the traces** — confirm the `query_flow_name` sets are identical
  (deterministic context assembly), confirm `chosen_resolution_flow` *may*
  differ (irreducible judgment).
- Live verification of `--scenario promo` and `--scenario capacity-conflict`
  (Phases 3 + 4 didn't break).
- **Summarize back.** The most important question: does Phase 5 produce the §10
  "thesis-holds" signal — **same structural query set, possibly different LLM
  judgment** — AND has the hallucinated-grounding pattern (entities *and*
  playbook refs) finally disappeared, replaced by reader-tool-grounded
  references?

Don't start writing Phase 5 code until upstream Phase 1.8 has landed AND you've
read all the docs. Phase 5 is the project's load-bearing claim. The Playbook
construct done wrong reintroduces policy into the world model and quietly kills
the whole architecture's thesis. Take time on the read; the code itself is
small.
