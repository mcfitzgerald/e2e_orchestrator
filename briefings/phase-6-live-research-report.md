# Phase 6 — live full-narrative research report

> Authored 2026-05-31 from the Phase 6 build session. Memorializes the two live
> `gemini-3.5-flash` runs that closed the Phase 6 DoD, and a deep dive into the
> one finding that warrants a follow-up: the live `demand_planning` agent sizing
> the promo `SupplyRequest` to **45,000 units**. Traces:
> `runs/phase6-live-capres-A.jsonl`, `runs/phase6-live-fulldemo.jsonl`.

---

## 1. Executive summary

Phase 6 ("Resolution + full demo, Scene 6") is complete: three resolution paths,
the full promo-whiplash narrative from one seed, a trace renderer + replay, and
72 passing tests. Two live runs on `gemini-3.5-flash` closed the live half of the
DoD and produced a **stronger** result than the structural tests alone:

- **The most complex example runs live, end-to-end.** `--scenario full-demo`
  traversed all six scenes from a single promo seed on a real LLM — the first
  time Scenes 1–3 (the multi-role promo→forecast→network chain) have run on a
  Gemini 3.x model at all.
- **Irreducible agency, demonstrated live.** Two runs chose **different**
  resolutions (`shift_to_coman` vs `request_promo_revision`). This is the §10/§6
  "chosen path materially differs across runs" criterion met with direct
  evidence, and it **closes the Phase 5 "everything converges to shift_to_coman"
  concern.** Two of three resolution paths are now exercised live.
- **The conflict derived honestly live.** The grounded agent did *not* dodge the
  derived conflict this time — it assigned the full uplift, the deterministic
  floor blocked it, and the orchestrator auto-rerouted. Live derivation can
  traverse the whole narrative; injection (`capacity-resolution`) remains the
  *reliable* path but is not *required*.
- **Guards survive the full narrative with margin** — the heaviest run used 12/25
  invocations and 0.59M/2M tokens. The defaults hold.

One finding warrants a follow-up (§5): the absolute order **quantity** that
`demand_planning` produced is **ungrounded** — not hallucinated, but estimated
without any grounding source, because the ontology gives a *multiplier* with no
readable *baseline*, and `demand_planning` has no reader tools. This is the same
grounding-gap family Phases 4–5 closed for entity references, surfacing now as an
ungrounded *quantity*.

---

## 2. The two runs

| | Run A — `capacity-resolution` | Run B — `full-demo` |
|---|---|---|
| Scope | Scenes 4–6 (conflict **injected**) | **Scenes 1–6 from one seed** (conflict **derived**) |
| Model | gemini-3.5-flash | gemini-3.5-flash |
| Invocations | 9 | 12 |
| Total tokens | 323,871 | 594,290 |
| Cached (of prompt) | 204,504 (≈63%) | 303,843 (≈51%) |
| Output tokens | 2,033 | 3,539 |
| Runaway guard | not tripped | not tripped |
| `quantum_rejected` | 0 | 0 |
| `wait_all` unsatisfied | 0 | 0 |
| **Resolution chosen** | **`shift_to_coman`** | **`request_promo_revision`** |
| Est. cost | ~$0.05 | ~$0.11 |

Both runs reached a clean terminal state: a validated `decision_surfaced`,
`capacity_resolved` emitted, and `plan_fulfillment` fired (re-convergence).

---

## 3. What the full run proved

1. **End-to-end live narrative.** Scene 1 (`submit_promo_plan` ingress) → Scene 2
   (`demand_planning` revises the forecast, advances `TradePromotionLifecycle`
   proposed→aligned→committed, emits `forecast_revised`) → Scene 3
   (`supply_planning` assigns production, fires `request_production`) → Scene 4
   (the `line_capacity_not_exceeded` floor **blocks** it; the orchestrator
   auto-reroutes `escalate_capacity_conflict` with no LLM in the routing) → Scene
   5 (the `resolve_capacity_conflict` playbook runs; three context-assembly
   queries fan out; a validated decision is surfaced) → Scene 6 (one resolution
   chosen; `plan_fulfillment` re-converges).

2. **Agency is real and tracks evidence.** Run A weighed a $1,275 co-man premium
   against a $7,200 OTIF penalty and shifted to co-man. Run B faced a *much*
   larger co-man premium ($36,975, because the order was far larger — see §5) and
   chose to renegotiate the still-`aligned` Walmart promo instead. Different
   evidence, different rational choice — exactly the irreducible-judgment the
   architecture is supposed to preserve.

3. **The deterministic floor held throughout.** Every routing decision, axiom
   verdict, and FSM transition was deterministic code; the LLM never routed.
   Zero `quantum_rejected` — every quantum the agents built was schema-valid on
   the first try.

---

## 4. Agency-surface assessment (the four-pattern heuristic, CLAUDE.md)

Both runs read **healthy + grounded**:

- **Operational stance (✓):** agents cite system mechanics — "according to the
  playbook `resolve_capacity_conflict`", "surfaced this structured decision",
  "routed the trade promotion back across the commercial boundary via the
  `request_promo_revision` flow". No "as supply_planning, what should I do?"
  identity-discovery framing.
- **No menu-picking (✓):** the resolver weighed **all three** paths with
  quantified trade-offs before choosing, in both runs.
- **Grounded entity references (✓):** every plant/line/SKU/commitment/promo cited
  is real (`NJ-L1`, `TP-FLAG-6OZ`, `TP-SEC-6OZ`, `PROMO-WMT-FLAG-2026Q2`,
  `conf-…`, Target/Walmart). No invented entities.
- **One caveat — ungrounded *quantity* (see §5):** the order *volume* was not
  grounded. This is a new variant of the hallucinated-grounding pattern: not a
  fake entity, but a number with no readable anchor.

Minor observation (not a regression): in both runs the agent re-fired some
context-assembly queries (Run A: each of the three twice; Run B: two of them
repeated). `wait_all` was satisfied and the decisions were well-grounded, but the
redundant re-querying is a mild efficiency / playbook-orientation signal that
stronger Playbook rendering would tighten. This is an upstream rendering nudge,
not an orchestrator patch.

---

## 5. Deep dive: why `demand_planning` sized the promo to 45,000 units

**The concern.** In Run B the live `demand_planning` produced a `SupplyRequest`
for **45,000 units** (vs the stub script's 3,000), which drove a 43,500-unit
shortfall and a $36,975 co-man premium. Is that a hallucination? A wonky example?
A missing control?

**What actually happened (traced, not inferred).**

- The `TradePromotion` it received carries `volume_uplift_factor: 3.0` and a
  15-day window (days 142–156). Its `forecast_revised` reasoning states it built
  the volume "incorporating the 3.0x uplift factor over the 15-day promotion
  window." So it correctly used the **multiplier (3.0×)** and the **window**,
  both of which *are* grounded in the promo quantum.
- The number it could **not** ground is the **baseline demand** the multiplier
  multiplies. 45,000 ≈ a baseline of ~1,000 units/day × 15 days × 3.0. The
  ~1,000/day base is the agent's own estimate.
- The deterministic floor then did its job **correctly** on that input: 3,500
  scheduled + 45,000 requested = 48,500 > 5,000 rated → shortfall **43,500**,
  stamped into the `CapacityConflict`. The resolver later read that back and
  computed 43,500 × $0.85 = **$36,975** — arithmetic that is exactly right *given
  the input*. Nothing downstream was hallucinated; everything traces.

**Root cause: a grounding gap in the ontology + world state + tool surface.**

The ontology asks `demand_planning` to do a conversion it has no grounding source
for. Specifically:

- `TradePromotion.volume_uplift_factor` is documented as *"Multiplier on baseline
  demand during the promo window."* The ontology **presupposes a baseline demand**
  — but never provides one the agent can read:
  - the `TradePromotion` quantum carries **no base volume**;
  - the `SKU` entity has **no baseline-demand / run-rate slot**;
  - `world_state.yaml` has a baseline **production** schedule (by line/SKU/week)
    but **no baseline demand/forecast** figure for a SKU;
  - and critically, **`demand_planning` has zero reader tools**
    (`tools_available_to(demand_planning) == []`), whereas `supply_planning` has
    four. It has nothing to query even if a baseline existed.
- `SupplyRequest.volume` is an **absolute** "units needed" (a free `decimal`).
  There is no axiom bounding it to anything plausible for the SKU.

So converting "3.0× baseline" → an absolute "units needed" is **structurally
ungroundable** for `demand_planning` as the demo stands. The multiplier is
grounded; the base is invented; the absolute volume is therefore ungrounded —
and **no deterministic floor catches it**, because the floors check entity
*existence* (`unknown_entity`) and schema *validity*, not quantity *plausibility*.
A 45,000 `decimal` is a perfectly valid `SupplyRequest.volume`.

**Answering the four hypotheses directly:**

1. *"Because it has no other information?"* — **Yes, primarily.** It had the
   multiplier and window but no readable baseline demand and no tool to fetch one.
   It filled the gap with a plausible estimate.
2. *"Did it hallucinate the large number?"* — **No, not in the entity sense.** It
   did not reference any non-existent entity, and every downstream number is
   correctly derived from its estimate by deterministic code. It is **ungrounded
   estimation**, not hallucinated grounding. (The stub's 3,000 is *also* an
   ungrounded estimate — just a smaller, conflict-tuned one. The LLM exposed the
   gap the script papered over.)
3. *"Is our contrived example wonky?"* — **Partly.** The demo deliberately models
   the promo as a commercial *multiplier* and assumes the baseline lives in demand
   planning's head. The stub picked a base tuned to sit just over the conflict
   threshold; the live agent, with no anchor, picked a larger, internally-coherent
   base. The narrative numbers in `demo_narrative.md` are illustrative, not
   grounded in a baseline the agent can reach.
4. *"Do we lack the right controls in the ontology?"* — **Yes — this is the core
   finding.** The same grounding-gap family Phases 4–5 closed for *entity*
   references is open for *quantities* on the demand side.

**This is a new variant for the four-pattern heuristic.** Phase 3 had
hallucinated *entities*; Phase 1.8 had hallucinated *playbook refs*; both were
closed by deterministic floors (`unknown_entity`, `unknown_playbook`). This is
**ungrounded *quantity***: a schema-valid number with no readable anchor. The
existing floors can't catch it (it's a valid decimal referencing real entities),
so the fix is **grounding**, not a new rejection floor — and, per CLAUDE.md, **not
a prompt nudge.**

**Recommended fix (paste-ready for the ontology session), §2-safe.**

Give `demand_planning` a grounding source for baseline demand, mirroring exactly
how `supply_planning` was grounded in Phase 5:

- Add a **baseline-demand fixture** to `world_state.yaml` (e.g. baseline
  units/day or units/week per SKU, optionally per retailer/window), validated
  against the schema like every other fixture.
- Add a **reader `scont:Tool`** anchored to `demand_planning`, e.g.
  `query_baseline_demand(sku, window) -> BaselineDemand`, with a deterministic
  implementation in `application/reader_tools.py` over that fixture. Then
  `demand_planning` reads the base and applies the promo multiplier to a *real*
  number, instead of inventing one. (Reader tools are world-model, not policy —
  this stays clear of §2.)
- *Optionally* add an advisory axiom on `submit_supply_request` that flags a
  `SupplyRequest.volume` wildly inconsistent with the SKU's baseline × uplift
  (advisory, not blocking — quantity plausibility is judgment, not a hard gate).
  This is secondary; the primary fix is the reader tool, not a new floor.

Until then, the **stub** scenarios remain the canonical-numbers traces (they
encode a sensible base), and live runs will produce internally-coherent but
baseline-arbitrary volumes. That is acceptable for a Phase 6 demo of *structure*
(the six-scene flow, the floor, the agency) — but the demand-side grounding gap
should be closed before the numbers themselves are put in front of an executive
audience, or the $36,975-type figures won't withstand scrutiny.

---

## 6. Reproduction

```sh
# Run A (Scenes 4–6, injected conflict) — reliable resolution arc, live:
uv run e2e-orchestrator --mode llm --scenario capacity-resolution --log runs/capres.jsonl

# Run B (Scenes 1–6 from one seed) — the full narrative, live:
uv run e2e-orchestrator --mode llm --scenario full-demo --log runs/fulldemo.jsonl

# Render either trace into the readable Scene 1→6 story:
uv run e2e-narrate runs/fulldemo.jsonl

# Confirm deterministic orchestration replay (stub, structural equivalence):
uv run e2e-orchestrator --mode stub --scenario full-demo --log runs/a.jsonl
uv run e2e-orchestrator --mode stub --scenario full-demo --log runs/b.jsonl
uv run e2e-replay runs/a.jsonl runs/b.jsonl
```

Captured artifacts: `runs/phase6-live-capres-A.jsonl`,
`runs/phase6-live-fulldemo.jsonl`.

---

## 7. Action items for the dev-manager / ontology session

1. **Close the demand-side grounding gap** (§5): baseline-demand fixture +
   `query_baseline_demand` reader tool anchored to `demand_planning`. Highest
   priority before the demo's *numbers* are shown externally; the *structure* is
   demo-ready now.
2. **Track "ungrounded quantity" as a sixth agency-surface pattern** in CLAUDE.md
   — distinct from hallucinated entity/playbook refs; the fix family is grounding
   (reader tool), not a deterministic rejection floor.
3. **Tighten Playbook rendering** so context-assembly queries are fired once each
   (the redundant re-querying observation, §4). Upstream rendering, not an
   orchestrator patch.
4. **Resolution divergence is confirmed live** — no action needed; this resolves
   the Phase 5 convergence concern. Keep `re_request_production` covered by the
   scripted test (the LLM won't reliably select it live).
