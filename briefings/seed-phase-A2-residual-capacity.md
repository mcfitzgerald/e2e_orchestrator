# Mini-seed — residual-capacity model (line-magnitude realism)

*Paste-ready, paired. Closes the Phase-A "toy line" credibility hole flagged in
Session 1. Driver: `briefings/roadmap-2026-06-04.md` §3 Decision Point 3. Run as
two coding sessions, **ontology first**. No live LLM run without explicit sign-off.*

---

## 0. Why, and the one invariant you must hold

A CSCO reads "a line that makes 6,500 cases/wk and one SKU tips it over" as a *pilot
cell*, not a line. A real line runs ~30 SKUs at ~50k cases/wk; the conflict is the
promo's demand exceeding the line's **residual** capacity after everything else
already scheduled — not exceeding the whole line.

**The invariant (non-negotiable):** the **shortfall stays exactly what it is today
(1,500)** and the **Seed-A baseline stays 1,500/wk**. Only the line's *representation*
changes from "capacity 5,000 (toy)" to "capacity_total ~50,000, committed ~45,000,
**residual available 5,000** (realistic)." Nothing downstream of the shortfall moves.
This is a **modeling reframe, not a rescale** — if you find yourself changing the
shortfall, the baseline, or the resolution numbers, stop: you've left the brief.

---

## 1. The reframe

Today (toy): `shortfall = demand(6500) − capacity(5000) = 1500`.

After (realistic): introduce **one aggregate fact** on the line —
`committed_load` (cases/wk already scheduled to other SKUs) — and derive:

```
available  = capacity_total − committed_load        # 50000 − 45000 = 5000
shortfall  = demand − available                      # 6500 − 5000   = 1500   (unchanged)
utilization = committed_load / capacity_total        # 90%  (realistic 70–95%)
```

`committed_load` is **one aggregate number**, NOT a modeled set of competing SKUs.
Modeling the other ~30 SKUs as individual claimants would be *multiple decisions on
shared capacity* = the Tier-2 / `[[static-world-model-deferral]]` trigger
(Decision Point 1) — explicitly **out of scope**. Keep it a single fact.

(Illustrative numbers above; tune `capacity_total`/`committed_load` to any
realistic pair whose difference reproduces the current `available`. Preserve the
shortfall and baseline exactly.)

---

## 2. SESSION 1 — Ontology (`e2e_ontology`) — lands first

1. **`world_state.yaml`** — give the conflict line `capacity_total` (~50k) and
   `committed_load` (~45k) so `available` reproduces today's effective capacity.
   Keep SKU/pallet magnitudes consistent.
2. **Schema** — add the `committed_load` field (+ `capacity_total` if the current
   field is just `capacity`) wherever line capacity is defined; mirror existing
   capacity fields. Schema must validate `--strict`.
3. **The `line_capacity_not_exceeded` axiom** — evaluate against **`available`
   (= capacity_total − committed_load)**, not raw capacity. This is the load-bearing
   semantic change: the constraint is now "demand ≤ residual." §2 clean —
   `committed_load` is a *fact* (what's scheduled), `available` is *derived from
   facts*; still a statement of what is POSSIBLE, never a preference.
4. **`query_line_load` reader Tool** — return `capacity_total`, `committed_load`,
   `available` (and `utilization` if cheap) so `plant_scheduler` / `supply_planning`
   ground their reasoning in the *residual*, not the toy capacity.
5. **Render / narrative** — make sure the role view + `demo_narrative.md` express
   the line in residual terms ("X committed of Y total → Z available"). Anchor the
   credibility there.
6. **The capacity-locking test(s)** — update whichever test pins the old
   `5000 → 6500 → 1500` to the new decomposition, asserting `available = 5000` and
   `shortfall = 1500` (unchanged).

**§2 review:** `committed_load` answers "what is already scheduled" (fact);
`available` is arithmetic over facts. No threshold/preference/ranking. Pass.

**Session-1 DoD:** schema validates `--strict`; the conflict line reads as
~50k-total / ~90%-utilized / 5,000-residual; **shortfall still 1,500**; **Seed-A
baseline still 1,500**; `query_line_load` returns the three fields; ontology suite
green. Commit (contract for Session 2).

---

## 3. SESSION 2 — Orchestrator (`e2e_orchestrator`)

1. **Bump the ontology dep** to the Session-1 revision (editable-local).
2. **Conflict math / axiom evaluator** — compute `available = capacity_total −
   committed_load` and `shortfall = demand − available`. The shortfall it produces
   must be **identical (1,500)** to before.
3. **`query_line_load` impl** — return `capacity_total` / `committed_load` /
   `available` from the enriched fixture (mirror the Phase-A reader impls in
   `application/reader_tools.py`).
4. **Capacity-locking test** (`tests/test_world_state.py` or wherever it lives) —
   update to the decomposition; assert `available == 5000`, `shortfall == 1500`.
5. **Stub canonical numbers / golden traces** — reconcile `narrative.py` /
   Phase-5/6/7 DoD / playbook traces so they read in residual terms; the
   *resolution* numbers don't change (only the line's framing does). `--mode stub`.
6. **Run suites** — orchestrator + ontology green.

**Session-2 DoD:** `query_line_load` grounds the residual; shortfall preserved at
1,500; both suites green; the agent (in stub) reasons over `available`, not raw
capacity.

---

## 4. Overall DoD + the credibility bar

- **Structural:** both suites green; shortfall and Seed-A baseline numerically
  unchanged; the line reads ~50k-total / residual-tight everywhere it surfaces.
- **The bar:** a CSCO reading the fixture/trace sees a *believable line under load*
  (90% committed, a promo eating into the last 5k of residual) — not a one-SKU cell.
  That's the whole point of this mini-seed.

This mini-seed is a **prerequisite for the Phase-A live verification** — we want the
single live run to land on credible magnitudes (per the roadmap: residual-capacity
→ one live verification → Phase B).

---

## 5. What stays OUT

- **No change to the shortfall, the Seed-A baseline, or any resolution number** —
  representation only.
- **No per-SKU modeling of committed load** — one aggregate fact; per-SKU claimants
  = Tier-2, deferred.
- **No new policy/ranking/threshold** — `committed_load` is a fact, `available` is
  derived.
- **No transit-lane / new-entity modeling** — separately deferred.

> Ontology commits first; orchestrator consumes. User commits; dev-manager stages.
