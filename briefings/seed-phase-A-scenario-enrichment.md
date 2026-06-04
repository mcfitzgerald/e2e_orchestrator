# Phase A coding-session seed — scenario enrichment (CSCO-credible + T4 proof)

*Paste-ready, self-contained. Two coding sessions, run in order: **Session 1
(ontology) lands first** (it's the contract), then **Session 2 (orchestrator)**
consumes it. Driver: `briefings/roadmap-2026-06-04.md` §2 Phase A; north star:
`briefings/csco-brief.md`. No live LLM run without explicit user sign-off.*

---

## 0. Orientation

**Goal.** Make the promo-whiplash scenario one a CSCO recognizes as *"yeah, this is
Tuesday,"* and let the realism double as a live proof of **T4** (a new role costs
≈ zero). Research (2026-06-04) found a CSCO would nod at the *situation* but flag
three things in the *handling*; this phase closes exactly those:

1. the call is a weekly **S&OE forum with role-owners** — we only have
   `demand_planning` + `supply_planning`;
2. **allocation / partial-fill** is the reflexive *first* move and is missing;
3. **co-man can't be a 1-week rescue** — it's ungated today.

**The §2 line you must hold (the trap).** The resolution research is full of
decision math (*"pick the lever minimizing penalty + premium + lost-margin"*).
**That math is the agent's judgment — do NOT encode it.** Into the ontology and
fixtures go only **facts** (penalty rate, premium %, MOQ, qualification status,
open capacity, promo flexibility). The weighting / threshold / tie-break / "who to
short first" stays OUT. Test every field: *does it state what is TRUE / LEGAL /
POSSIBLE, or does it make the CHOICE?* If it makes the choice, it's policy — refuse
it.

**The stop condition (this phase's hard gate).** Adding `plant_scheduler` and
`trade` must require **zero edits to the agent template or the seven tools**. If it
doesn't, the abstraction is leaking — **stop and surface to the dev-manager
session**, don't code around it. (Standing Phase-3 stop condition; this phase is its
live test.)

---

## 1. Design decisions (pinned by the dev-manager — implement these, flag if wrong)

**D1 — Lever-owners are rendered roles; the resolution hands off to them.** Each
resolution lever is owned by a different human in a real S&OE room. Realize that:
the `resolve_capacity_conflict` playbook still *selects* the lever, but the selected
action **hands off to the role that owns it**, which confirms feasibility and fires
the downstream events:

| Lever (action) | Owning role |
|---|---|
| `request_promo_revision` | **`trade`** (internal; engages the retailer boundary) |
| `re_request_production` | **`plant_scheduler`** (internal re-plan feasibility) |
| `shift_to_coman` | existing sourcing/co-man responder (leave as-is for Phase A) |
| `allocate_partial_fill` *(new)* | `supply_planning` (the holding move) |

> **Inspect first.** Before building, check how the three current levers route
> today (rendered role vs. boundary-sim responder vs. terminal event — recall the
> Phase-5 "responders in both modes" pivot). Then *promote* the lever-owners to
> first-class **ontology-rendered roles** where needed. The point of D1 is that
> `plant_scheduler`/`trade` get their identity from `render_role_view(role)` like
> every other role — **no hand-authored per-role prompt** (that's the T4 proof).

**D2 — `allocate_partial_fill` is a single-decision holding move (Tier-2
boundary).** Add it as a new entry in the playbook's `selects_one_of` with its own
criterion (mirror the existing `viable_*` criteria, e.g. `viable_partial_fill`). The
agent decides the split by **reading facts** (per-retailer OTIF exposure, order
sizes) — the *split itself is judgment, never a ranking in the ontology* (no
"biggest retailer first"). **Keep it ONE resolving decision.** Do NOT let it become
two roles concurrently mutating the same constrained capacity — that is the
`[[static-world-model-deferral]]` trigger / Decision Point 1 (Tier-2), which we
decide *after* Phase A exists, deliberately. If you find yourself needing shared
mutable capacity state, **stop and flag it** — that's a feature decision, not a
Phase-A task.

**D3 — Co-man gates are enriched reader facts, NOT a new rejection floor.** Enrich
what the existing `check_coman_availability` context query returns so the
`viable_coman_shift` criterion is evaluated against real facts:
`qualified_for_sku` (bool), `open_window` (capacity available in the promo window),
`moq` (units). The agent *reads* these and concludes co-man is/isn't viable —
grounded agency, exactly like Seed A's `query_baseline_demand`. **Primary fix is the
reader fact, not a floor** (mirrors Seed A: a schema-valid choice isn't caught by a
floor; you ground it instead). *Optional secondary,* only if trivially clean: a
feasibility axiom `coman_must_be_qualified` as a guardrail (mirror
`line_capacity_not_exceeded`). Default: reader facts only.

**D4 — Real magnitudes (research cheat-sheet).** Bring `world_state.yaml` up to
believable numbers, all schema-validated, presented as fixtures **behind the
declared edges** (the integration points): multi-line plants (~50k cases/wk/line),
mid-SKU demand ~1,500 cases/wk (matches the Seed A baseline — keep them consistent),
cases/pallet via Ti×Hi (~48–50), per-retailer OTIF terms (3% of COGS on
non-compliant lines, 90/95/98 targets, $1k/mo waiver), co-man qualification/MOQ/
window (D3), lead times (material 2–8 wk, mfg 1–3 wk, transit 1–5 d).

---

## 2. SESSION 1 — Ontology (`e2e_ontology`) — lands first

**Read first:** `CLAUDE.md` / `CONTRIBUTING.md` (ontology repo), `supply_chain_demo.yaml`,
`world_state.yaml`, `scont_meta.yaml` / `scont_bodies.py`, and the §12 world-vs-policy
sections of `agent_system_design.md`.

**Tasks:**
1. **Roles.** Add `plant_scheduler` and `trade` role declarations — mirror an
   existing role (e.g. `supply_planning`) exactly; their agent identity must render
   from the ontology with no bespoke prompt. Anchor them to the levers per D1.
2. **Playbook.** In `resolve_capacity_conflict`: add `allocate_partial_fill` to
   `selects_one_of` + its `viable_partial_fill` criterion (mirror existing criteria);
   make the three handoff-owning levers target the owning roles (D1). Leave
   `always_fires` (`capacity_resolved`, `plan_fulfillment`) intact. Respect the
   Seed-C `closed_set` / input-binding structure already on this playbook — extend,
   don't fight it.
3. **Co-man gates (D3).** Add `qualified_for_sku` / `open_window` / `moq` to the
   co-man entities in `world_state.yaml`; enrich the `check_coman_availability` /
   `query_coman_availability` reader `scont:Tool` contract so it returns them.
4. **Reader-tool declarations.** For any new world facts the new roles must read
   (e.g. per-retailer OTIF exposure for the allocation split), declare reader
   `scont:Tool`s — mirror `query_baseline_demand` / `query_plants_for_sku`
   (`implementation` contract name + `available_to` capability surface). Anchor each
   to the role that needs it.
5. **Data (D4).** Enrich `world_state.yaml` to real magnitudes; keep the Seed A
   baseline consistent. Schema-validate everything.
6. **Terminology.** Anchor "promo whiplash" → bullwhip effect once in the
   narrative/docs; adopt baseline/incremental where it reads naturally. Light touch.

**§2 review before commit:** walk every new field through the TRUE/LEGAL/POSSIBLE
vs. CHOICE test. No `prefer`/`priority`/`fallback`/threshold/weight surface.

**Session-1 DoD:** schema validates; `render_role_view` produces a coherent agent
prompt for `plant_scheduler` and `trade`; the playbook exposes four levers with the
new criterion; co-man reader returns the three gates; `world_state.yaml` is at real
magnitudes; **ontology test suite green.** Commit (user commits; you stage). This is
the contract Session 2 consumes.

---

## 3. SESSION 2 — Orchestrator (`e2e_orchestrator`) — consumes the contract

**Read first:** `CLAUDE.md` (this repo), `application/reader_tools.py`,
`application/` (agent factory, flow router, FSM, the seven tools),
`runtime/main.py` (`build_scenario_orchestrator`), `tests/test_phase2_dod.py`.

**Tasks:**
1. **Bump the ontology dependency** to the Session-1 revision (editable-local for
   dev per `[[cross-repo-dependency-model]]`).
2. **Reader-tool implementations.** Add deterministic impls for the new world facts
   (co-man gates, per-retailer OTIF exposure, etc.) over the enriched fixture —
   mirror `query_baseline_demand` in `application/reader_tools.py`; register in
   `DEFAULT_READER_TOOLS` keyed by the `implementation` contract name from Session 1.
3. **Roles wire themselves — verify, don't hand-code.** `plant_scheduler` and
   `trade` should dispatch purely via `render_role_view(role).as_agent_prompt()`
   with **zero edits to the agent template or the seven tools.** **This is the T4
   check — make it explicit in the session and in the PR description.** If it
   requires per-role code, **STOP and surface to dev-manager** (D0 stop condition).
4. **Dispatch-ordering / DoD-test reconciliation.** Adding roles + the
   `allocate_partial_fill` lever changes role-dispatch ordering, which
   `test_phase2_dod.py` asserts as a surface invariant. Per the orchestrator
   `CLAUDE.md`: change it intentionally **and update downstream consumers (the DoD
   test, replay, any trace/narrative consumer) in the same change** — don't paper
   over it. Update stub canonical-numbers / golden traces coherently with the new
   magnitudes (`--mode stub`, `ScriptedAgentHandler`).
5. **Run the suites.** Orchestrator tests green, including the reconciled Phase-2 DoD.

**Session-2 DoD:** new reader tools return grounded facts from the enriched fixture;
`plant_scheduler` + `trade` dispatch with **zero template/seven-tool edits** (T4
proven and stated); stub traces + Phase-2 DoD green and coherent with the new world.
Commit.

---

## 4. Phase A DoD (overall) + live verification (separate, user sign-off)

**Structural (no API key):** both suites green; the T4 zero-edit invariant holds and
is documented; the playbook offers four levers; co-man gates are reader-grounded;
the fixture is at real magnitudes.

**Live (only with explicit user sign-off — mirror the Seed A / Seed C verification
discipline):** a run where the capacity conflict resolves through a realistic lever
set, the new roles **participate via handoff** (`trade` / `plant_scheduler`), co-man
is correctly **rejected** when its gates fail (and chosen only when qualified + open
window + ≥ MOQ), and allocation appears as a first holding move — read the trace's
`agent_reasoning` against the six-pattern heuristic (every cited
entity/quantity/role traces to something read; no identity-discovery, menu-picking,
or hallucinated grounding). Verdict bar: **a CSCO reading the trace says "this is
how the call actually gets made."**

---

## 5. What stays OUT of Phase A (scope + guardrails)

- **No decision math in the ontology** (§2) — facts in, the lever choice and the
  allocation split stay agent judgment.
- **No two-decisions-on-shared-state** — allocation is a single resolving decision;
  shared mutable capacity = Tier-2 (Decision Point 1), decided later.
- **No portfolio triage** — one conflict; the N-conflict view is shelved
  (Decision Point 2), handled with scope honesty in the writeup.
- **No per-role code, no LLM in routing, commands→events** — unchanged disciplines.
- **No new policy/ranking fields** of any shape.

> Sequencing recap: **ontology commits first, orchestrator consumes.** Pair the two
> sessions; don't let the contract drift between them. User commits; dev-manager
> stages and proposes.
