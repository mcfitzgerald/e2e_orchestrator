# Seed C (ontology) — bind `resolve_capacity_conflict`'s context-assembly to the input quantum, and mark the set closed

**Type:** coding-session seed for the `e2e_ontology` repo (dev-manager, 2026-06-02).
**Scope:** edits to one `scont:Playbook` JSON shape + its hint. **No orchestrator
change. No prompt string. No new ontology field that smells like policy.**
**Origin:** the "over-querying" observation from the two Phase 7 live runs
(`runs/mcp-run-ddf198c229f2.jsonl`, `runs/mcp-run-cd439092752c.jsonl`).

---

## The observation (grounded in the live traces)

`supply_planning`, executing `resolve_capacity_conflict`, fired each of the three
context-assembly queries **twice** — once per competing SKU / once per retailer —
and ran extra reader probes. It built the *complete* cross-domain map when the
decision only needed the evidence pinned to the conflict it was handed.

Concretely (run `ddf198`): `check_coman_availability` fired for `TP-FLAG-6OZ`
**then** `TP-SEC-6OZ`; `check_promo_flexibility` for one promo **then** Bullseye/
Greenfield; `check_otif_exposure` for Megalomart **then** Greenfield. Each pair has
distinct idempotency keys (different payloads) so the orchestrator correctly did
**not** dedup them — this is the *agent's* choice, not a wire bug.

**Diagnosis against the CLAUDE.md six-pattern heuristic:** this is **not** a
regression. Not menu-picking (every query was justified in reasoning); not
hallucinated-grounding (it *probed* to validate, e.g. invented `PROMO-FLAG-Q2`
to test ID validity, rather than confidently asserting a fake entity). It is
**healthy, grounded agency that is un-budgeted** — it explores exhaustively
because nothing tells it the evidence set is complete. Roughly 30–40% of the
token spend was exploration past the decision threshold.

Two distinct flavors, two different owners:

| Flavor | Example | Root cause | Fix | Owner |
|---|---|---|---|---|
| **Completeness sweep** | query every retailer/SKU, not just the conflict's | playbook doesn't bind query *inputs* to the input quantum, nor mark the set closed | this seed | ontology (playbook) |
| **Probe-to-ground** | invent `PROMO-FLAG-Q2` to test if an ID is valid; the old `volume=45,000` guess | no grounded local read for identifiers/quantities | **already shipped** | Seed A (demand reader) |

The probe-to-ground half is the demand-grounding gap and is **already closed** by
Seed A — this seed addresses only the completeness sweep.

---

## The fix — enrich the playbook *schema*, not the prompt

Today's `resolve_capacity_conflict` `scont:playbook` block:

```json
"context_assembly": [
  { "flow": "check_otif_exposure",      "required": true },
  { "flow": "check_promo_flexibility",  "required": true },
  { "flow": "check_coman_availability", "required": true }
],
"synchronization": "wait_all",
```

It declares *which* flows to fire but not (1) *with what inputs* nor (2) *that this
set is sufficient*. The agent has to invent both — so it sweeps every entity and
keeps probing. Two additions close it:

**1. Bind the query inputs to the input quantum.** The `CapacityConflict` quantum
already names the affected retailer(s) and SKU(s). Declare that the context-assembly
inputs are **projected from the input quantum** rather than discovered by the agent.
Shape (illustrative — match the repo's JSON idiom):

```json
"context_assembly": [
  { "flow": "check_otif_exposure",
    "inputs_from_quantum": { "retailer": "$.affected_retailers[*]", "sku": "$.sku" },
    "required": true },
  ...
]
```

The exact projection syntax is the ontology session's call (whatever the
`QuantumValidator` / role-view renderer can already express). The *semantic* is:
"the evidence you need is a function of the conflict you were handed."

**2. Mark the assembly closed/sufficient.** `synchronization: "wait_all"` governs
*waiting*, not *sufficiency*. Add the semantic that once these responses are in, the
agent proceeds to `decision` — the set is necessary-and-sufficient, no further
exploration required. A flag (`"closed_set": true`) or a one-line tightening of the
`scont:llm_prompt_hint` ("these three responses are the complete evidence set; once
assembled, proceed to the decision — do not gather more") — pick whichever the repo
treats as schema vs. hint.

---

## What must NOT change — agency stays open

This bounds **evidence-gathering**, never **judgment**. The `decision` block is
untouched:

```json
"decision": {
  "criteria_refs": ["viable_promo_renegotiation","viable_coman_shift","tolerable_otif_penalty"],
  "selects_one_of": ["request_promo_revision","re_request_production","shift_to_coman"]
}
```

`selects_one_of` stays three-wide, "the decision is yours," order-is-not-a-ranking.
The agent's agency lives in *which path it picks given the evidence* — not in *how
exhaustively it reads*. Over-reading is cost, not reasoning; clamping it removes
spend, not agency. **Verify this on the next live run:** the resolution path must
still vary across seeds (the Phase 5 stop condition). If binding the inputs makes
the path deterministic, the assembly binding leaked into the decision — back it out.

### §2 check

"The evidence you need is a function of the conflict you were handed" is **derivable
world-model** (a projection over the input quantum), not a preference/ranking → §2-eligible.
A `"closed_set"` flag asserts *sufficiency*, not *priority* → eligible. Neither
introduces a `prefer`/`priority`/`fallback`-shaped surface. If the projection syntax
starts to encode "try retailer X first," stop — that would be policy.

---

## DoD

1. `resolve_capacity_conflict`'s `context_assembly` binds query inputs to the
   `CapacityConflict` quantum; the set is marked closed.
2. `decision` block byte-identical to today.
3. Both suites green; role-view snapshot for `supply_planning` regenerated
   (the rendered playbook now shows bound inputs).
4. **Live `--mode llm` run** (gated on permission): `resolve_capacity_conflict`
   fires each context query **once**, scoped to the conflict's entities — the
   double-fire is gone — AND the resolution path still varies by seed (agency
   intact). Compare against `runs/mcp-run-cd439092752c.jsonl` (the current
   double-fire baseline; ~488k tokens, of which ~30–40% was the sweep).

## Cross-refs

- The two live traces: `runs/mcp-run-ddf198c229f2.jsonl`, `runs/mcp-run-cd439092752c.jsonl`.
- Seed A (`seed-A-demand-grounding-gap.md`) — closed the probe-to-ground half.
- CLAUDE.md six-pattern heuristic (this is un-budgeted healthy agency, not a regression).
- The §2 world-vs-policy rule; the Phase 5 "resolutions must vary across seeds" stop condition.
- **Stub-vs-live volume interpretation (logged here, not a bug).** Both the stub
  and the live LLM now ground volume in the `query_baseline_demand` read of 1,500/wk
  (Seed A) — but they interpret `volume_uplift_factor: 3.0` differently. The stub
  sizes `volume = 3,000` (baseline-over-window); the live `--mode llm` run
  (`run-cd439092752c`) sized `volume = 9,000` (baseline-over-window × 3.0, shown
  step-by-step in its reasoning). Neither is ungrounded — both read the fixture; they
  differ only in *how the uplift factor composes with the window*. This is a contract
  ambiguity in `volume_uplift_factor`'s definition (uplift on the weekly run-rate vs.
  on the window total), not a grounding failure. If the ontology session wants the
  stub and live numbers to match, the fix is to **pin the semantics of
  `volume_uplift_factor` in the `TradePromotion` class doc** — out of scope for this
  seed, noted so the two numbers don't later read as a contradiction.
