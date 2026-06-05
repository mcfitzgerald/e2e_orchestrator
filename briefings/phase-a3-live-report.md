# Phase A3 live verification — report (2026-06-05)

*5 live runs, `--mode llm`, gemini-3.5-flash, caps held (50/25/2M), no runaway.
Traces local in `runs/a3-{balanced,locked}-*.jsonl` (gitignored). Verifies the
balanced-variant mini-seed (`seed-phase-A3-balanced-variant.md`).*

---

## Verdict: PASS on the primary claims; one sub-goal unmet for a GOOD reason

| Run | Scenario | Resolution | Alt-line grounding |
|---|---|---|---|
| balanced ×3 | `capacity-resolution-balanced` | `shift_to_coman` (TP-SEC) | read CA-L1 every run |
| locked ×2 | `capacity-resolution-locked` | `shift_to_coman` (TP-SEC) | read CA-L1 every run |

**Every run** called `query_plants_for_sku` (2×) and `query_line_load` (1–3×) —
the agent **discovered CA-L1 and read its residual headroom in every case** —
plus `query_coman_availability`, `query_commitments_in_window`, and the three
playbook context queries (otif / promo / coman).

### 1. Grounded agency — STRONGER than before ✅

The richer fixture made the agent ground *more*, not less. It now reads the
alternative-line picture (`query_plants_for_sku` → `[NJ-L1, CA-L1]`, then
`query_line_load` on the candidates) **before** deciding. Every cited entity
traces to a read. Pattern #1 (healthy + grounded), no regressions.

### 2. Lever VARIATION — ACHIEVED ✅

The variant family resolves via **`shift_to_coman`**, distinct from the prior
Phase-A canonical runs (4/4 → `request_promo_revision`). And it's a *clever,
CSCO-credible* path: co-man **cannot** make the flagship in the window
(open_window 1000 < 1500, moq 2000) — but it **can** make the **secondary** SKU
TP-SEC (open_window 6000, moq 1000, premium 0.22), so the agent **moves TP-SEC
to co-man to free NJ-L1's residual for the flagship promo.** That is exactly the
kind of cross-SKU judgment an S&OE planner makes. The agency is real and varies
with context.

### 3. `plant_scheduler` firing live — NOT achieved, and we now know precisely why

The locked variant was *designed* to force `plant_scheduler` by closing the
promo lever. It did not — because **co-man-for-TP-SEC stays open**, and the agent,
**having read CA-L1's availability**, still judged co-man the better path. CA-L1
is in **PLANT-CA** (cross-country from NJ, 10-day mfg lead); co-man-for-TP-SEC has
an open window and a 0.22 premium. Resequencing the flagship to a distant plant
loses, on the merits, to shifting the secondary SKU to a qualified co-man.

**This is grounded judgment, not a grounding gap.** The internal-re-plan lever is
discovered and read every time; it's simply *dominated*. (Contrast the design's
assumption that closing promo would force it — it doesn't, because the seed left
the TP-SEC co-man open as an escape.)

---

## What this teaches (for the writeup + the next scenario)

- **More grounding facts changed the resolution.** On the canonical fixture the
  agent converged on promo revision; on the balanced fixture (alt-line facts
  surfaced) it explores `query_plants_for_sku` and lands on co-man-for-TP-SEC.
  Grounding drives agency — a thesis datapoint, live.
- **A lever is only chosen if it's the best grounded option, not merely viable.**
  CA-L1 is viable AND read AND still not chosen. To *demonstrate* `plant_scheduler`
  live we need a scenario where internal re-plan **dominates**, i.e. is the
  cleanest grounded path — not just available.

## Proposed follow-up (a scenario-design refinement — brief, do not patch)

To put `plant_scheduler` on screen live, make internal re-plan the **dominant**
grounded path in a third variant, e.g.:
- a **same-plant** (PLANT-NJ) toothpaste line with residual headroom and a short
  mfg lead (no cross-plant penalty), so resequencing beats co-man; AND/OR
- close the **TP-SEC co-man** too (a fact: that partner isn't qualified/open for
  TP-SEC in this window) so co-man is fully off the table — leaving internal
  re-plan as the cleanest remaining lever.

Both are §2-clean fact changes (a line that exists with headroom; a co-man that
isn't open). **Do NOT** encode "prefer internal re-plan" — that's policy. Make it
*dominant on facts* and let the agent find it. This is a small paired follow-up
(fixture + responder), gated on the same live sign-off discipline.

> Bottom line: the balanced variant **proved grounded agency + lever variation
> live** — the headline claims. `plant_scheduler`-on-screen is the one remaining
> demo nicety, blocked by *grounded judgment* (co-man wins), and reachable with a
> dominant-internal-re-plan scenario. T4 for `plant_scheduler`/`trade` is already
> proven structurally (zero-edit dispatch) and `trade` fired live in Phase A.
