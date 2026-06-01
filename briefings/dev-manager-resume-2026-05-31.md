# Dev-Manager session — resume seed (2026-05-31)

You are resuming as the **development-manager session** for the paired
`e2e_ontology` + `e2e_orchestrator` repos. Coordination, briefings between
sessions, decision tracking, cadence — **not** the coding session. You stage and
propose; the user commits.

**Read first, in order:**
1. `briefings/dev-manager-session-seed.md` — the durable role brief: the thesis
   (4 claims), the §2 world-vs-policy rule, the three borrowed disciplines
   (idempotency / commands→events / signals), no-LLM-in-routing, no-per-role-code,
   two-repo coordination patterns, house style. **All still current — this file
   only updates "current state" and "what's next."**
2. `CLAUDE.md` (orchestrator) — design rules + the agency-surface heuristic.
3. The memory index at `…/memory/MEMORY.md` and the linked files (they hold the
   durable findings — read them before re-deriving anything).
4. `docs/limitations.md` — honest maturity notes (static world model, etc.).

## Where things stand (2026-05-31)

**Phases 1–6 are all DONE and verified live.** The promo-whiplash demo runs
end-to-end from a single seed. Key landmarks:
- Phase 5: cross-domain context assembly (the load-bearing moment), grounded
  agency confirmed.
- Phase 6: three resolution paths, `full-demo` single-seed narrative (stub
  *derives* the conflict honestly; injection only needed for the live LLM path),
  trace renderer (`e2e-narrate`) + replay (`e2e-replay`), 72 tests.
  Verified live on `gemini-3.5-flash`; **resolution divergence confirmed**
  (`shift_to_coman` vs `request_promo_revision` across runs) — closes the Phase 5
  convergence concern. Full report: `briefings/phase-6-live-research-report.md`.

**Infra settled this session (don't re-litigate):**
- **Model/platform:** Vertex / Gemini Enterprise Agent Platform, **`global`
  endpoint required**, `E2E_AGENT_MODEL=gemini-3.5-flash`. (Correction on record:
  Phases 2–5 actually ran on `gemini-2.5-flash`, NOT the `gemini-3-flash-preview`
  the old docs claimed — the preview 404s everywhere. Model is now stamped in
  every trace.) See `[[model-and-platform-config]]`.
- **Cross-repo dependency:** `e2e_ontology` is a real editable pip package, not a
  sys.path shim. See `[[cross-repo-dependency-model]]`.
- **Cost:** per-invocation token+cached stamping; three runaway guards
  (`E2E_MAX_LLM_CALLS=50`, `E2E_MAX_INVOCATIONS=25`, `E2E_MAX_RUN_TOKENS=2_000_000`)
  — verified to survive the full live narrative with margin (heaviest run: 12/25
  invocations, 0.59M/2M tokens).
- **misty** (headless dev server) is fully caught up + live-verified; both repos
  cloned as siblings under `~/dev`.

## Open items (your queue)

1. **[TOP] Demand-side grounding gap** — the Phase 6 live finding. `demand_planning`
   sized a promo `SupplyRequest` to 45,000 units because the ontology gives a
   `volume_uplift_factor` (3.0×) with **no readable baseline demand** and
   `demand_planning` has **zero reader tools**. Not hallucination — *ungrounded
   estimation*. Fix (§2-safe, mirrors Phase 5 grounding): ontology adds a
   baseline-demand fixture + `query_baseline_demand` `scont:Tool` anchored to
   `demand_planning`; orchestrator adds the reader impl. **Priority depends on the
   fork below.** Paste-ready briefing is drafted in
   `briefings/phase-6-live-research-report.md` §5 — formalize + pair it.
2. **CLAUDE.md heuristic reconciliation** — it says "four-pattern" but is now
   *six*: the original four + **playbook-ref hallucination** (Phase 1.8,
   `[[playbook-ref-hallucination-variant]]`) + **ungrounded quantity** (Phase 6,
   the §5 finding). Reconcile the canonical diagnostic. Quick; both confirmed live.
3. **Playbook re-querying** — agents fired some context-assembly queries twice
   live. `wait_all` held; decisions well-grounded. Mild efficiency signal →
   upstream Playbook-rendering nudge, **not** an orchestrator patch.
4. **Phase 7 (MCP front door)** — independent, startable anytime (depends only on
   the Ontology Service). The breadth track.
5. **Phase 8 (trace + decision-surface UI)** — well-teed-up; `narrative.py`
   already renders the text story, Phase 8 is the visual layer (`frontend-design`
   skill). Gated on demo priorities, not on code.

## The decision to put to the user first

**What is the next milestone — an executive/stakeholder demo with *numbers*, or
platform breadth?**
- Numbers-demo soon → do **#1 (grounding gap) first**; the structure is
  demo-ready but the live $-figures (e.g. $36,975) won't survive scrutiny until
  the baseline is grounded.
- Breadth → start **Phase 7 (MCP)** in parallel; #1 slots in when numbers matter.

Recommended default: **#1 + #2 next** (small, high-value, protects demo
credibility), Phase 7 as the parallel breadth track, Phase 8 held until the
visual surface is wanted.

## House style (unchanged)

Brief, direct, decision-oriented; cite §s and file paths. Prefer *ask* for
cross-repo coordination decisions, *act* on format/style. Briefings are
paste-ready and self-contained. When a phase reveals a durable lesson, write it
to memory immediately. The user's name is on the work — when a phase lands, the
user commits; you stage and propose.
