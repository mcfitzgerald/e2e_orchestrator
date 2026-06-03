# Dev-Manager session — resume seed (2026-06-01)

You are resuming as the **development-manager session** for the paired
`e2e_ontology` + `e2e_orchestrator` repos. Coordination, briefings between
sessions, decision tracking, cadence — **not** the coding session. You stage and
propose; the user commits.

**Read first, in order:**
1. `briefings/dev-manager-session-seed.md` — the durable role brief: the thesis
   (4 claims), the §2 world-vs-policy rule, the three borrowed disciplines
   (idempotency / commands→events / signals), no-LLM-in-routing, no-per-role-code,
   two-repo coordination patterns, house style. **All still current.**
2. `briefings/dev-manager-resume-2026-05-31.md` — the prior resume seed. Its
   "where things stand" (Phases 1–6 done + verified live; model/platform/cost
   infra settled) and its open-items queue are all still accurate. **This file
   supersedes only the decision-fork: the milestone call has now been made.**
3. `CLAUDE.md` (orchestrator) — design rules + the agency-surface heuristic.
4. The memory index at `…/memory/MEMORY.md` and the linked files.
5. `docs/limitations.md` — honest maturity notes (static world model, etc.).
6. `briefings/phase-6-live-research-report.md` — §5 is the source-of-truth for
   Track A below; §7 enumerates the action items.

## Decision made (2026-06-01): run BOTH tracks in parallel

The milestone question (numbers-demo vs breadth) resolved to **both, concurrently**:

- **Track A — demo credibility (spans both repos).** Close the demand-side
  grounding gap + reconcile the agency heuristic. Protects the demo's *numbers*.
- **Track B — platform breadth (orchestrator-side).** Phase 7: the MCP front
  door. Proves the architecture generalizes outward.

The tracks are largely independent (Track A touches the ontology + the reader-tool
surface; Track B is the orchestrator's external interface over the Ontology
Service), so they can run as two separate coding sessions without colliding.

## Your first job: produce the two coding-session seeds

Each must be **paste-ready and self-contained** (the house standard). Stage them
under `briefings/`; the user commits.

### Seed A — "Close the demand-side grounding gap + heuristic reconciliation"

Source of truth: `phase-6-live-research-report.md` §5 + §7 (items 1 & 2). The
finding: live `demand_planning` sized a promo `SupplyRequest` to 45,000 units —
not a hallucination, but **ungrounded estimation**, because the ontology gives a
`volume_uplift_factor` (3.0×) with **no readable baseline demand**, and
`demand_planning` has **zero reader tools**. The §2-safe fix mirrors the Phase 5
grounding move exactly:

- **Ontology repo:** add a **baseline-demand fixture** to `world_state.yaml`
  (units/day or /week per SKU, optionally per retailer/window), schema-validated
  like every other fixture; add a reader `scont:Tool`
  `query_baseline_demand(sku, window) -> BaselineDemand` **anchored to
  `demand_planning`**. (Reader tools are world-model, not policy — stays clear of §2.)
- **Orchestrator repo:** add the deterministic reader implementation over that
  fixture (mirror `application/reader_tools.py` / the Phase 5 `supply_planning`
  readers). Then `demand_planning` applies the multiplier to a *real* number.
- **Optional, secondary:** an *advisory* (non-blocking) axiom on
  `submit_supply_request` flagging a volume wildly inconsistent with baseline ×
  uplift. Primary fix is the reader tool, **not** a new rejection floor — the
  existing floors check entity-existence + schema-validity, and a 45,000 decimal
  is schema-valid. Quantity plausibility is judgment, not a hard gate.
- **CLAUDE.md reconciliation (item #2):** the heuristic says "four-pattern" but is
  now **six** — the original four + **playbook-ref hallucination** (Phase 1.8,
  `[[playbook-ref-hallucination-variant]]`) + **ungrounded quantity** (this
  finding). Fold ungrounded-quantity in as a distinct pattern whose fix family is
  *grounding (reader tool)*, not a deterministic floor and not a prompt nudge.
- **DoD for Seed A:** a live run where `demand_planning` reads a baseline and the
  promo volume is grounded (no free-floating 45,000); stub canonical-numbers
  traces still green; the six-pattern heuristic is canonical in CLAUDE.md.
- **Cross-repo sequencing:** ontology fixture + Tool meta-construct lands first
  (it's the contract); orchestrator reader impl consumes it. Pair the briefing so
  the ontology change and the reader wiring don't drift.

### Seed B — "Phase 7: MCP front door"

Independent track; depends only on the Ontology Service. This is the *breadth*
proof — exposing the system through MCP. Before writing the seed, **pull current
MCP + ADK-MCP guidance via `context7`** (training cutoffs lie about both). The
seed should pin: what surface MCP exposes (ingress of a quantum? trace/decision
read? the seven-tool kit?), the §2/ no-per-role-code constraints that still hold
at the boundary, and a crisp Phase 7 DoD. Keep it from regressing the
no-LLM-in-routing and commands→events disciplines.

## Housekeeping done this session (don't redo)

- **Real retailer names scrubbed (2026-06-01).** Walmart→Megalomart,
  Target→Bullseye, Kroger→Greenfield (IDs WMT→MGM, TGT→BUL, KRG→GRN), across both
  repos incl. snapshots/docs/traces. P&G/Colgate intentionally **kept** as
  industry-grounding refs. Both suites green (ontology 249, orchestrator 72), all
  pushed. Full policy + surgical-replace lesson: `[[no-real-company-names]]`. When
  inventing any new demo entity, use a fictional name.

## Remaining queue items (lower priority, not in either track yet)

- **Playbook re-querying** (report §4 / §7.3): agents fired some context-assembly
  queries twice live; `wait_all` held, decisions well-grounded. Mild efficiency
  signal → an upstream Playbook-**rendering** nudge, *not* an orchestrator patch.
  Could ride along in Seed A's ontology work or wait.
- **Phase 8 (trace + decision-surface UI):** well-teed-up (`narrative.py` renders
  the text story); held until the visual surface is wanted (`frontend-design`
  skill). Not in this round.
- **Static-world-model upgrade:** deliberately deferred (`[[static-world-model-deferral]]`);
  trigger = two interacting decisions on shared state. Not yet.

## House style (unchanged)

Brief, direct, decision-oriented; cite §s and file paths. *Ask* for cross-repo
coordination decisions, *act* on format/style. Briefings are paste-ready and
self-contained. When a phase reveals a durable lesson, write it to memory
immediately. The user's name is on the work — when a phase lands, the user
commits; you stage and propose.
