# Mini-seed — balanced scenario variant (agency-variation + plant_scheduler live)

*Paste-ready, paired. Closes the one open item from the Phase-A live verification
(2026-06-04): the canonical conflict is **determinate** — co-man and internal
re-plan are genuinely infeasible on the facts, so every live run correctly
converges to `request_promo_revision`. That's grounded agency, **not** a wobble —
but it means we have not yet **demonstrated** (a) agency *varying* across runs and
(b) `plant_scheduler` firing live. This mini-seed adds balanced fixture variants
where a different lever is grounded-viable, so both show on screen. Driver:
`briefings/roadmap-2026-06-04.md` (Phase A live-verification open item) + north
star `briefings/csco-brief.md`. No live LLM run without explicit user sign-off.*

---

## 0. The finding this seed acts on (read first)

The Phase-A live runs (`[[phase-a-session2-orchestrator]]`) all resolved via
`request_promo_revision` because the canonical world fixture makes the other two
levers **genuinely infeasible**, and a grounded agent reads that:

- **Co-man** for `TP-FLAG-6OZ`: qualified, but `open_window 1000 < 1500` needed and
  `moq 2000 > 1500` → correctly rejected.
- **Internal re-plan** (`re_request_production` → `plant_scheduler`): the only line
  that **currently schedules** `TP-FLAG-6OZ` is `NJ-L1`, and it's maxed (residual
  5000, conflict needs 6500). `query_plants_for_sku` grounds "which lines can make a
  SKU" on the **production schedule** (a line that *runs* the SKU can make it —
  `reader_tools.py:55`), so no qualified alt line surfaces with headroom.
- **Promo revision**: the Megalomart flagship promo's `commitment_status` is
  negotiable, so `viable_promo_renegotiation` passes → the one open lever.

So **convergence is fact-driven determinism.** The fix is **not** to add agency
back (it's there) — it's to add **fixtures where the facts make a *different* lever
viable**, so live runs *show* the agent (a) picking among ≥ 2 genuinely-open levers
(may vary by seed) and (b) routing through `plant_scheduler`. This is the honest
demonstration: agency follows facts; change the facts, the resolution moves.

**§2 (the line you must hold).** We change **facts only** — never a preference. "An
alt line is qualified-and-open for this SKU" and "this promo is contractually
locked" are statements of what is **TRUE / LEGAL / POSSIBLE**. We add **no ranking,
no tie-break, no 'prefer internal over promo'**. The whole point is that *more than
one lever becomes viable* and the **choice stays the agent's**. If you find yourself
encoding which lever to take, stop — that's the §2 leak this seed exists to avoid.

---

## 1. The two knobs — and where each is actually read (verified 2026-06-05)

The two levers we flip live in **two different read paths**. This distinction is
load-bearing — it was wrong in the first draft of this seed and is now corrected:

| Knob | What it does | Operative mechanism | §2 check |
|---|---|---|---|
| **K1 — viable internal re-plan** | Makes `re_request_production` → `plant_scheduler` a *grounded* lever → exercises `plant_scheduler` live | **Fixture data.** Add a `production_schedule` row so a **second** line currently schedules `TP-FLAG-6OZ`, on a line whose **residual available − scheduled ≥ 1500** (the shortfall). Read by the `query_plants_for_sku` / `query_line_load` **reader tools** over the real `WorldState`. | Fact: "this line runs this SKU and has residual headroom." Not a preference. ✓ |
| **K2 — close the promo lever** | Removes `request_promo_revision` as viable → forces the agent onto an internal lever → `plant_scheduler` deterministic | **Responder variant, NOT a fixture flip.** On the `capacity-resolution` path, promo flexibility is answered by the `check_promo_flexibility` **responder** (`_CAPRES_CUSTOMER_DEV`, `main.py:367`) — simulated in **every mode incl. `--mode llm`** (`build_scenario_orchestrator:609`). Add a *locked* responder returning `commitment_status: contractually_locked`, `can_shift_timing: false`, `can_reduce_volume: false` so the agent reads "closed." | The boundary responder models the retailer's **current negotiating stance** (a fact about what the retailer will accept now). Not a preference of ours. ✓ |

**Why K2 is NOT a fixture edit (the correction).** `world_state.yaml`'s
`trade_promotions[].commitment_status` is **not on the `capacity-resolution` read
path** — no reader tool reads it there; the agent learns promo flexibility only by
*querying* `check_promo_flexibility`, which a boundary responder answers. Flipping the
fixture field would never reach the live agent. So K2 is correctly an
**orchestrator-side scenario variant** (a second responder), and there is **no
`world_state_locked.yaml`** — which also kills the drift risk of a near-duplicate
fixture.

**Net: one fixture change (K1) + one responder variant (K2).** No new ontology
fields, no schema change, no reader/axiom/seven-tool edit. K1 is ontology-first
(the fixture lives in `e2e_ontology`); K2 is orchestrator-only.

---

## 2. The two variants — ONE fixture, two scenarios

Both variants share **one** balanced fixture (K1). They differ only in the
`check_promo_flexibility` responder (K2):

- **`capacity-resolution-balanced`** = balanced fixture + the **existing (aligned)**
  responder. Internal re-plan AND promo revision are **both** open → the agent has a
  genuine multi-lever choice; the resolution **may vary by seed**, and when it picks
  internal re-plan, `plant_scheduler` fires. *The agency-variation headline.* Co-man
  stays gated out (leave it as-is).
- **`capacity-resolution-locked`** = balanced fixture + a **locked** responder.
  Promo revision **closed**, internal re-plan **open** → forces `re_request_production`
  → `plant_scheduler` **deterministically**, and — the strong grounding signal —
  shows the agent *abandoning its prior attractor* (`request_promo_revision`)
  precisely because a fact (the retailer's locked stance) closed it. *The reliable
  `plant_scheduler` demo take.*

> **Picking the K1 line.** `NJ-L2` (same plant `PLANT-NJ`, `mfg_lead_time 7` → 1-week
> window respected) is the natural candidate. Two coupled edits make it a *grounded,
> viable* alt line:
> 1. Add a small `TP-FLAG-6OZ` `production_schedule` row on `NJ-L2` (weeks 140 & 147)
>    so `query_plants_for_sku` returns it as qualified ("currently runs the SKU").
> 2. Ensure `NJ-L2`'s **free residual ≥ 1500** *after* that row, because the line-
>    capacity axiom checks `scheduled_units + proposed ≤ available`. `NJ-L2` today:
>    `available = 50000 − 46500 = 3500`, scheduled `MW-CLAS 1800`. Adding e.g.
>    `TP-FLAG 500` → scheduled 2300, free 1200 — **too tight** (< 1500). So **also
>    lower `NJ-L2.committed_load`** to ~`45500` (available 4500; free after the row =
>    4500 − 2300 = 2200 ≥ 1500, util 91% — still realistic). Verify the arithmetic in
>    the fixture comment.
> Do **not** touch `NJ-L1` — its 5000-residual / 1500-shortfall invariant is
> load-bearing (`[[phase-a-session2-orchestrator]]`, `test_world_state.py`).

---

## 3. SESSION 1 — Ontology (`e2e_ontology`) — lands first

**Read first:** `CLAUDE.md` / `CONTRIBUTING.md`, `world_state.yaml` (esp.
`production_lines`, `production_schedule`, `trade_promotions` + the `PromoFlexibility`
/ `commitment_status` story in `supply_chain_demo.yaml`), and confirm `--strict`
schema validation passes on any new fixture.

**Tasks:**
1. **Create `world_state_balanced.yaml`** — copy `world_state.yaml`, apply **K1**
   (the only fixture change in this whole mini-seed):
   - add a `TP-FLAG-6OZ` `production_schedule` row on `NJ-L2` for weeks 140 & 147
     (small, e.g. 500/wk) so it reads as qualified;
   - lower `NJ-L2.committed_load` to ~`45500` so its **free residual after the row is
     ≥ 1500** (see §2 arithmetic). Update the `NJ-L2` capacity comment to match.
   Change **nothing else** — `NJ-L1`'s numbers, the shortfall, the Seed-A baseline all
   stay exactly as-is. There is **no `world_state_locked.yaml`** (K2 is a responder,
   not a fixture — §1).
2. **Schema-validate** `--strict`. Must load clean as the same world model.
3. **§2 review:** walk K1 through TRUE/LEGAL/POSSIBLE-vs-CHOICE — it's a fact ("this
   line runs this SKU and has residual headroom"). Confirm **no** ranking/preference/
   threshold; confirm we added no field that says which lever to take.
4. **Drift guard (recommended):** add a tiny test asserting `world_state_balanced.yaml`
   differs from `world_state.yaml` **only** in the intended `NJ-L2` rows (see §5).

**Session-1 DoD:** `world_state_balanced.yaml` schema-validates `--strict`; `NJ-L1`
residual still 5000 / shortfall still 1500; `NJ-L2` now schedules `TP-FLAG-6OZ` with
free residual ≥ 1500; ontology suite green. Commit (contract for Session 2).

---

## 4. SESSION 2 — Orchestrator (`e2e_orchestrator`) — consumes + wires + live-verifies

**Read first:** `runtime/main.py` (`SCENARIOS`, `build_scenario_orchestrator`),
`application/orchestrator.py` (`Orchestrator(n=...)` / `_load_default_n` /
`WORLD_STATE_YAML`), `world_state/loader.py` (`WorldState.load`).

**Tasks:**
1. **Bump the ontology dep** to the Session-1 revision (editable-local per
   `[[cross-repo-dependency-model]]`).
2. **Thread an optional world fixture through the scenario spec (the only code
   change).** Today `build_scenario_orchestrator` lets `Orchestrator` default to
   `WORLD_STATE_YAML`. Add an optional `world_state` key to a scenario `spec`; when
   present, `WorldState.load(path, schemaview)` it and pass `n=` into `Orchestrator(
   service=..., backend=..., n=..., handler_factory=...)`. **Generic — no per-role
   code, no `if scenario ==`.** (If `Orchestrator` doesn't already accept an injected
   world alongside `service`, it does via the `n` param — verify the wiring path.)
3. **Add a locked `check_promo_flexibility` responder (K2).** Add
   `_CAPRES_CUSTOMER_DEV_LOCKED` mirroring `_CAPRES_CUSTOMER_DEV` (`main.py:367`) but
   returning `commitment_status: "contractually_locked"`, `can_shift_timing: False`,
   `can_reduce_volume: False`, and a `notes` string that reads true ("retailer has
   locked the promo contractually; no timing or volume change available"). This is
   the operative K2 mechanism — it reaches the live agent because responders run in
   every mode.
4. **Add two scenario entries** mirroring `capacity-resolution`:
   - `capacity-resolution-balanced` → `world_state: world_state_balanced.yaml`,
     responders include the **existing (aligned)** `_CAPRES_CUSTOMER_DEV`.
   - `capacity-resolution-locked`   → `world_state: world_state_balanced.yaml` (same
     fixture), responders swap in `_CAPRES_CUSTOMER_DEV_LOCKED`.
   Same seeder/`_CAPRES_LOGISTICS`/`_CAPRES_COMAN`/scripts as `capacity-resolution`.
   **Stub scripts are ignored in `--mode llm`** (`[[phase-a-session2-orchestrator]]`)
   — that's the point; the *facts* (the balanced fixture) and the *responder* (the
   lock) steer the live path, not a script. For `--mode stub` coherence, the locked
   variant's script should resolve via `re_request_production` (so the stub trace
   reads true to the forced lever); the balanced variant can keep the canonical
   script (stub determinism is fine — the *live* run is where variation shows).
5. **Resolve the variant fixture path** the same way `WORLD_STATE_YAML` resolves
   (via the ontology package, `[[cross-repo-dependency-model]]` — `ontology_service.
   paths` or the existing constant's mechanism). Don't hard-code an absolute path.
6. **Tests (stub, no key):** a structural test that `capacity-resolution-balanced`
   loads the balanced world (asserts `NJ-L2` schedules `TP-FLAG-6OZ` and its free
   residual ≥ 1500) and that `capacity-resolution-locked` wires the locked responder
   (asserts its `check_promo_flexibility` response is `contractually_locked`); both
   build + seed without error; orchestrator + ontology suites green. **Do not** assert
   a particular *live* lever in a test — the live choice is agency, not a fixture
   invariant.

**Session-2 DoD:** both variant scenarios build and run in `--mode stub`; the world-
fixture threading is generic (no per-role code); the locked responder is wired into
`capacity-resolution-locked`; suites green. Commit.

---

## 5. Drift control (one near-copy fixture)

Only **one** near-copy fixture exists now (`world_state_balanced.yaml` = canonical +
the K1 `NJ-L2` rows); K2 is a responder, so there's no second fixture to desync.
Mitigate the one copy:

- **Keep it minimal** — `world_state.yaml` + the K1 `NJ-L2` delta, nothing else.
  Document the exact deltas in a header comment in the variant file.
- **Add the §3 drift guard test** — load both fixtures; assert they are identical
  except on the named `NJ-L2` rows (the added `TP-FLAG-6OZ` schedule rows + the
  lowered `committed_load`). If a future edit to `world_state.yaml` breaks it, that's
  the signal to re-derive the variant, not to loosen the test.
- *(Optional, only if it stays clean)* a thin overlay mechanism (base fixture + a
  small per-scenario delta dict applied at load) instead of a copy — but **do not**
  build a config language for it. For a one-delta variant, the copy + guard test is
  simplest. Don't over-engineer a demo.

---

## 6. Live verification (separate, explicit user sign-off — mirror Seed A/C discipline)

With sign-off, run (caps in place: `E2E_MAX_LLM_CALLS=50`, `E2E_MAX_INVOCATIONS=25`,
`E2E_MAX_RUN_TOKENS=2000000`; traces to `runs/`, gitignored):

- **`capacity-resolution-balanced` ×N** (`--mode llm`): expect the agent to read the
  residual picture, **discover the second qualified line via `query_plants_for_sku`**,
  find it has headroom, and — at least sometimes — resolve via `re_request_production`
  → **`plant_scheduler` fires live** (T4 live for the third new role). Across N runs,
  watch for **lever variation** (some internal re-plan, some promo revision) — that's
  the agency-variation demonstration. If it *always* picks one lever, that's still
  honest (note it), but the multi-viable fixture is what gives variation a chance.
- **`capacity-resolution-locked` ×1–2** (`--mode llm`): expect the agent to **read
  the lock** (the locked responder returns `commitment_status: contractually_locked`,
  `can_shift_timing: false`, `can_reduce_volume: false` on `check_promo_flexibility`),
  conclude promo revision is closed, and route to `plant_scheduler` — **deterministic
  `plant_scheduler` live**, and the strong signal: the agent *abandons* the prior
  attractor because a fact closed it.

Read every `agent_reasoning` against the **six-pattern heuristic**: every cited line/
lever/quantity must trace to something read (no hallucinated alt line, no invented
residual). Verdict bar: **a CSCO watching says "right — when the promo's locked, you
go back to the plant; when you've got open capacity elsewhere, that's a real
choice."** Update `[[phase-a-session2-orchestrator]]` with the result and close the
open item.

---

## 7. What stays OUT (scope + guardrails)

- **No new ontology fields, no schema change** — K1 is fixture data over an existing
  field; K2 is an existing responder shape with different fact values.
- **No ranking/preference/threshold/tie-break** (§2) — we make levers *viable*, never
  *preferred*. Multiple-viable-on-facts is the whole mechanism.
- **No change to `NJ-L1`'s residual (5000) / the shortfall (1500) / the Seed-A
  baseline (1500)** — load-bearing invariants; the variants add an *alternative*, they
  don't rescale the conflict.
- **No per-role / per-scenario code** in the world-fixture threading — generic spec
  key only. (Standing stop condition: per-scenario branching in the wiring = leak →
  surface to dev-manager.)
- **No two-decisions-on-shared-state** — still one resolving decision per run; the
  alt line is a *capability fact*, not a second concurrent mutator (that's Tier-2 /
  `[[static-world-model-deferral]]`, deferred).
- **No portfolio triage, no transit-lane modeling** — separately deferred.

> Sequencing recap: **ontology commits first** (the variant fixtures are the
> contract), **orchestrator consumes** (threads the fixture + adds the scenarios +
> live-verifies). Pair the two sessions; don't let the variants drift from the
> canonical. User commits; dev-manager stages and proposes.
