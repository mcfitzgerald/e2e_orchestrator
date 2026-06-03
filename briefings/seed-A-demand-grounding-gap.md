# Seed A — Close the demand-side grounding gap + heuristic reconciliation

**Type:** paired coding-session seed (ontology change lands first; orchestrator
reader impl consumes it). Self-contained — assume zero context from any other
session.
**Track:** A (demo credibility — protects the demo's *numbers*). Runs in parallel
with Seed B (Phase 7 MCP), which touches a disjoint surface.
**Source of truth:** `briefings/phase-6-live-research-report.md` §5 + §7 (items 1 & 2).

---

## TL;DR

The live `demand_planning` agent sized a promo `SupplyRequest` to **45,000 units**
(stub script: 3,000). Not a hallucination — **ungrounded estimation**. The
ontology hands `demand_planning` a `volume_uplift_factor` (3.0×) but **no readable
baseline demand** to multiply, and `demand_planning` has **zero reader tools**
(`tools_available_to(demand_planning) == []`). So it invented a baseline (~1,000
units/day) and every downstream number — the 43,500 shortfall, the $36,975 co-man
premium — is arithmetically correct *given that invented base*. Nothing
downstream hallucinated; the base itself was ungroundable.

The fix mirrors the Phase 5 grounding move **exactly** — the same family that
closed hallucinated *entity* references, applied now to an ungrounded *quantity*:

1. **Ontology:** add a schema-validated **baseline-demand fixture** + a
   `query_baseline_demand` reader `scont:Tool` anchored to `demand_planning`.
2. **Orchestrator:** add the deterministic reader impl over that fixture, mirroring
   `application/reader_tools.py`. `demand_planning` then applies the 3.0× multiplier
   to a *real* number instead of inventing one.
3. **CLAUDE.md:** reconcile the agency-surface heuristic from "four-pattern" to the
   actual **six** patterns, folding in *ungrounded quantity* as a distinct pattern
   whose fix family is **grounding (reader tool)** — not a rejection floor, not a
   prompt nudge.

The primary fix is the **reader tool**, not a new rejection floor. A 45,000
`decimal` is schema-valid and references real entities; the existing floors
(`unknown_entity`, schema validity) correctly can't catch it. Quantity
plausibility is judgment, not a hard gate.

---

## Why (the traced root cause — from report §5)

- `PROMO-MGM-FLAG-2026Q2` carries `volume_uplift_factor: 3.0` over a 15-day window
  (days 142–156). Both are grounded in the promo quantum, and the agent used them
  correctly ("incorporating the 3.0x uplift factor over the 15-day promotion
  window").
- What it **could not** ground is the **baseline** the multiplier multiplies:
  - the `TradePromotion` quantum carries no base volume;
  - the `SKU` entity has no baseline-demand / run-rate slot;
  - `world_state.yaml` has a baseline **production** schedule (`production_schedule`,
    by line/sku/week) but **no baseline demand/forecast** figure per SKU;
  - `demand_planning` has **zero** reader tools (vs `supply_planning`'s four), so it
    has nothing to query even if a baseline existed.
- `SupplyRequest.volume` is a free absolute `decimal` with no axiom bounding it.

So converting "3.0× baseline → absolute units needed" is **structurally
ungroundable** for `demand_planning` as the demo stands. The multiplier is
grounded; the base is invented; the absolute volume is therefore ungrounded.

This is **acceptable for a Phase 6 demo of *structure*** (the six-scene flow, the
deterministic floor, the agency all hold and read healthy) — but the demand-side
grounding gap must close **before the numbers are put in front of an executive
audience**, or $36,975-type figures won't survive scrutiny.

---

## §2 check (world-vs-policy) — this is clean

A reader tool that returns *what the baseline demand is* is **world model**, not
policy. It answers without referring to a preference or ranking — it reports a
fact from world state. It is the exact shape of the four Phase 1.8 reader tools
(`query_plants_for_sku`, `query_line_load`, …), which are already §2-clean and
shipped. Authoring test passes: "Can `query_baseline_demand(sku, window)` be
answered without a runtime preference or ranking?" → yes, it's a fixture lookup.

The **optional** advisory axiom (below) is also §2-safe **only because it is
advisory, non-blocking** — it surfaces a plausibility signal the agent weighs, it
does not encode a preferred quantity or a hard threshold-as-policy. Keep it
advisory or drop it.

---

## Schema vs data — the split that must stay clean (read this first)

The `e2e_ontology` **repo** holds two different things; do not conflate them (an
earlier draft of this seed did, and it set off a correct alarm):

- **`supply_chain_demo.yaml` = the ontology (schema / vocabulary).** Class *shapes*,
  roles, flows, axioms, Tool *declarations*. **No demo values ever go here.** The
  `SKU` class lives here; the value `TP-FLAG-6OZ` does **not** (confirmed: it appears
  zero times in this file). Baseline-demand piece that belongs here: the
  `BaselineDemand`/`BaselineDemandQuery` **class shapes** + the `query_baseline_demand`
  **Tool declaration** — vocabulary, exactly like `SKU` itself.
- **`world_state.yaml` = the world fixture (data).** Instances + numbers, loaded at
  boot, read-only. The `TP-FLAG-6OZ` *instance* lives here. Baseline-demand piece
  that belongs here: the **actual baseline numbers**. This is data *provided to* the
  ontology-shaped world — never *in* the ontology.

Rule: **no value touches `supply_chain_demo.yaml`.** Shape and tool-declaration only.

### This reader tool is an *outbound edge* — the fixture is a shim

Per `briefings/design-memo-ontology-exposes-handshakes.md`: `query_baseline_demand`
is an **outbound edge** (the agent reaching out for data). The **durable artifact is
the `scont:Tool` handshake contract** (typed input/output + a symbolic
`implementation` name). The fixture-reading callable is an explicit **stand-in** for
a real demand/forecast integration (which in production could be REST / MCP / A2A
behind the *same* contract — "the agent doesn't know the difference," `§9`). Build
the shim for the POC, but frame it honestly in code comments + the live report:
**the contract is real and permanent; the fixture is the demo's placeholder for the
system on the other side of the handshake.** Phase 7 (Seed B) realizes the *first*
such edge (inbound, as MCP); this is its outbound cousin.

## The change — `e2e_ontology` repo: two files, different roles (lands FIRST; it is the contract)

Mirror the Phase 1.8 Tool + query-entity pattern exactly
(see `supply_chain_demo.yaml` ~line 596 for the query-entity block and ~line 1485
for the `scont:Tool` declarations).

### 1. Query + result entity classes (`supply_chain_demo.yaml`, plain entities)

Minimal slots — only what the reader impl needs:

```yaml
  BaselineDemandQuery:
    description: >-
      Input to query_baseline_demand: the baseline (pre-promo) demand for a SKU
      over a window.
    annotations:
      scont:domain: demand
    attributes:
      sku:
        description: "SKU to read baseline demand for"
        range: SKU
        required: true
      window_start_day:
        description: "Window start (day-of-year). Optional; omit for the SKU's standing run-rate."
        range: integer
        required: false
      window_end_day:
        description: "Window end (day-of-year)."
        range: integer
        required: false

  BaselineDemand:
    description: >-
      Output of query_baseline_demand: the baseline (pre-promo) demand run-rate
      for a SKU, from world state. The promo multiplier applies on top of this.
    annotations:
      scont:domain: demand
    attributes:
      sku:           { range: SKU, required: true }
      units_per_week: { range: decimal, required: true }
      window_start_day: { range: integer, required: false }
      window_end_day:   { range: integer, required: false }
```

(Pick `units_per_week` vs `units_per_day` to match how `production_schedule` is
keyed — it's weekly by `week_start_day`. Weekly keeps the two fixtures
commensurable; see the consistency note below. The coding session may rename, but
keep it minimal.)

### 2. The reader Tool (`supply_chain_demo.yaml`, `scont:Tool` block)

```yaml
  query_baseline_demand:
    instantiates: [scont:Tool]
    annotations:
      scont:domain: demand
      scont:tool: >-
        {
          "description": "Returns the baseline (pre-promo) demand run-rate for a SKU over a window, from world state. The promo volume_uplift_factor multiplies this baseline.",
          "category": "reader",
          "input_class":  "BaselineDemandQuery",
          "output_class": "BaselineDemand",
          "implementation": "query_baseline_demand",
          "deterministic": true,
          "available_to": ["demand_planning"]
        }
      scont:llm_prompt_hint: >-
        Read the SKU's baseline demand before applying a promo's
        volume_uplift_factor. Multiply the real baseline by the uplift over the
        promo window instead of estimating the base — the SupplyRequest volume
        must trace to a readable baseline, not a guess.
```

### 3. The fixture (`world_state.yaml`)

Add baseline-demand data, schema-validated. **CONSISTENCY CONSTRAINT (load-bearing
— read this):** the baseline you pick for `TP-FLAG-6OZ` must keep the Scene-4
conflict intact and the canonical stub numbers green. `world_state.yaml` already
encodes a **1,500/week** baseline *production* for `TP-FLAG-6OZ` on `NJ-L1`
(`production_schedule`, week_start_day 140/147) and the documented conflict math
(`5000 rated`, `3500 baseline load`, `6500 with 3× promo → 1500/week shortfall`).
Set the baseline **demand** for `TP-FLAG-6OZ` to **1,500/week** so it tracks the
existing production baseline; then a grounded `demand_planning` applying 3.0× lands
near the stub's tuned 3,000 (incremental) figure, the derived conflict still fires,
and `tests/test_world_state.py`'s conflict-math assertions stay green. Do **not**
pick a number that changes the derived shortfall.

Two acceptable shapes — the ontology session picks one to match house precedent:
- **Entity instances** of `BaselineDemand` (schema-validated against the class
  above) — matches the resume seed's "schema-validated like every other fixture"
  language and the Phase 1.8 query/result-entity precedent. **Recommended.**
- A supplementary `baseline_demand:` top-level list (like `production_schedule`,
  which is deliberately *not* modeled as a class) — looser, but consistent with the
  existing schedule precedent.

Recommend the entity-instance shape unless the ontology session has a reason to
keep demand supplementary like production. Either way it must be schema/shape
validated in `tests/test_world_state.py`.

### 4. Renderer / snapshots

`render_role_view('demand_planning').as_agent_prompt()` must now show a **TOOLS
AVAILABLE TO ME** section with `query_baseline_demand` (it currently shows none).
Regenerate the `demand_planning` snapshots; the drift is intentional and committed.

---

## The change — orchestrator repo (consumes the contract)

All in `e2e_orchestrator`, after the ontology change lands.

### 1. Reader impl in `application/reader_tools.py`

Add `query_baseline_demand(input, world_state) -> ReaderToolResult`, registered in
`DEFAULT_READER_TOOLS`. Follow the existing four exactly — uniform
`(input: dict, world_state: WorldState)` signature, grounding miss → `output=None`
with the `UNKNOWN_ENTITY` evidence floor, valid-but-empty → empty typed output.
Sketch:

```python
def query_baseline_demand(input: dict, world_state: WorldState) -> ReaderToolResult:
    """Baseline (pre-promo) demand run-rate for a SKU. The promo multiplier
    applies on top of this — grounding the base so demand_planning multiplies a
    real number instead of inventing one (the report §5 ungrounded-quantity gap)."""
    sku = _entity_id(input.get("sku"), "sku_code")
    if sku is None or world_state.get_sku(sku) is None:
        return ReaderToolResult(output=None,
            evidence=f"{UNKNOWN_ENTITY}: sku={sku!r} not found in world state")
    # read the baseline fixture (BaselineDemand instances OR baseline_demand rows)
    # ... window filter optional; return the units_per_week the contract declares
```

If the ontology shipped `BaselineDemand` as entity instances, read them via
`world_state.find("BaselineDemand", sku=sku)` / `instances_of`. If it shipped a
supplementary `baseline_demand:` list, add a thin typed accessor on `WorldState`
mirroring `query_line_load` (keep the query surface generic — no per-domain
accessor leakage; a `find`-style read is preferred). A SKU with no baseline row is
a **valid-but-empty** miss, distinct from an unknown SKU.

### 2. Optional, secondary — advisory axiom on `submit_supply_request`

Only if it earns its keep. An **advisory (non-blocking)** axiom flagging a
`SupplyRequest.volume` wildly inconsistent with `baseline × uplift × window`.
Advisory severity, surfaced to the agent as evidence, never a hard gate — quantity
plausibility is judgment. The **primary** fix is the reader tool; do not lead with
this and do not make it blocking. Defer entirely if it complicates the DoD.

---

## What NOT to do

- **Do not** add a blocking rejection floor for the quantity. The existing floors
  check entity existence + schema validity by design; a valid decimal over real
  entities is correctly outside their remit. A blocking quantity gate would encode
  a policy threshold (§2 violation) and kill legitimate agency over volume.
- **Do not** fix this with a prompt nudge ("estimate conservatively"). CLAUDE.md is
  explicit: ungrounded grounding is fixed by *grounding*, not by prompt text.
- **Do not** hard-code the baseline in the orchestrator or the agent template. It's
  world-state fixture data read through a generic tool — same as every other
  reader. Per-role code = abstraction leak.
- **Do not** change the derived Scene-4 conflict numbers. The baseline must keep
  `tests/test_world_state.py` conflict math green (see the consistency constraint).
- **Do not** store the baseline as a policy-shaped field (a "target", a "preferred
  volume", a ranking). It's a run-rate fact.

---

## CLAUDE.md reconciliation (do this in the orchestrator repo)

The agency-surface heuristic in `CLAUDE.md` and the memory index still say
"four-pattern." It is now **six**:

1. Healthy + grounded
2. Identity-discovery regression
3. Menu-picking regression
4. Hallucinated-grounding regression (entities)
5. **Playbook-ref hallucination** (Phase 1.8 — `[[playbook-ref-hallucination-variant]]`;
   fix family: deterministic floor `unknown_playbook`)
6. **Ungrounded quantity** (this finding — a schema-valid number with no readable
   anchor; fix family: **grounding / reader tool**, *not* a rejection floor and
   *not* a prompt nudge)

Fold #6 in as a **distinct** pattern. Be explicit that its fix family differs from
#4 and #5: #4/#5 are caught by deterministic floors (`unknown_entity`,
`unknown_playbook`); #6 cannot be (the value is schema-valid and references real
entities), so the only correct fix is grounding it. Update the CLAUDE.md prose and
the relevant memory file(s) so the canonical diagnostic is six patterns.

---

## DoD (Seed A is done when all hold)

1. A **live** run where `demand_planning` calls `query_baseline_demand`, reads a
   real baseline, and the promo `SupplyRequest.volume` is grounded in it — no
   free-floating 45,000. Capture the trace (`runs/`), confirm the agent's
   `agent_reasoning` cites the baseline it read.
2. **Stub canonical-numbers traces still green** — the derived Scene-4 conflict and
   `tests/test_world_state.py` conflict math unchanged.
3. Orchestrator + ontology suites green (current counts: ontology 249, orchestrator
   72 — both should rise with new tests, not fall).
4. `render_role_view('demand_planning')` shows `query_baseline_demand` under TOOLS
   AVAILABLE TO ME; snapshots regenerated + committed.
5. The **six-pattern** heuristic is canonical in `CLAUDE.md` (and the memory index).
6. Agency surface re-read against the (now six-pattern) heuristic on the live run:
   still healthy + grounded, and the ungrounded-quantity caveat from report §4 is
   gone.

---

## Cross-repo sequencing

1. **Ontology first** — fixture + `BaselineDemand`/`BaselineDemandQuery` entities +
   `query_baseline_demand` Tool + renderer/snapshots + `test_world_state` validation.
   This is the contract. Commit upstream.
2. **Then orchestrator** — reader impl + registry wiring + (optional) advisory axiom
   + CLAUDE.md reconciliation + live verification.

Pair the two so the ontology change and the reader wiring don't drift (same pattern
as the Phase 1.8 / Phase 5 pairing). The orchestrator's Phase 5 reader-tool wiring
is generic — a fifth reader tool should land as registry + impl with **no** change
to the agent template or the seven tools. **If wiring `query_baseline_demand`
requires editing the agent template or the tool-dispatch core, the abstraction is
leaking — stop and surface it before pressing on** (the standing no-per-role-code
stop condition).

---

## Lower-priority ride-along (optional, from report §4 / §7.3)

Agents re-fired some context-assembly queries twice live (`wait_all` held;
decisions well-grounded). Mild efficiency signal → an upstream **Playbook-rendering**
nudge, *not* an orchestrator patch. It can ride along in this seed's ontology work
or wait. Do **not** patch it in the orchestrator.
