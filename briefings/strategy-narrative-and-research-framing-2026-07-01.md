# Strategy session seed — narrative + research framing (2026-07-01)

*Paste-ready. Continues the Phase-D **strategy / thought-partner** session (not a
coding session). Two jobs: (1) continue the publication-strategy discussion where
it left off, and (2) give a fresh session a clean **understanding of what we have
in hand** — the narrative spine, the vocabulary, the evidence, and the positioning.
Read this whole file before doing anything. Do NOT edit code or run suites unless
explicitly asked; your value is sharp questions, honest pushback, structure, prose.*

---

## 0. Where we are

The build is done, merged, green (orchestrator ~100 tests, ontology ~287). This is
the **Phase-D pivot**: look back, sharpen the theses, and decide how to **publish**
— foremost to build the user's external/community technical credibility (public
record of thinking + deliverables, for job/prospect security and technical bona
fides); secondarily to make the ontology bet real for internal leadership.

The prior seed is `briefings/pm-session-seed-2026-06-11.md` (retrospective + theses
+ publishing objectives). THIS seed supersedes it on the **narrative framing**,
which we worked out since: the story is told **through the failure modes**, under
a **rapid-iterative-development** register (not a pre-registered experiment).

**Standing decisions (from memory):**
- Goal priority: publish-first for external credibility > internal leadership > "we
  have an architecture." Audience: technical peers. (`[[publishing-goals-and-story-nesting]]`)
- Story nesting: **A (moat) = thesis · C (agency/third-way) = proof · B
  (architecture) = mechanism · D (practice) = call to action.**
- No real company names (fictional placeholders; P&G/Colgate kept as industry
  refs). (`[[no-real-company-names]]`)

---

## 1. The narrative arc (the spine)

The nesting is A→C→B→D, but the **engine** that drives it is the failure-mode
through-line. As a reader experiences it:

1. **Open on the thesis (A — the moat).** Frontier AI is a commodity; everyone
   rents the same models. The durable asset is *your* encoding of how your business
   actually works — the world model. Stop buying agents; author your world.

2. **Hit the wall everyone hits.** The moat story always dies on one question:
   *"fine, but how do you actually GET an ontology? Isn't that a multi-year
   boil-the-ocean program?"* This is where most "ontology-grounded agents" talk
   goes vague. It's the objection that kills the pitch in the room.

3. **The engine — the failure-driven loop (THE UNLOCK of this session).**
   *The agent's failure modes were the ontology's backlog.* You don't design the
   world model top-down and pray. You run a generic agent against the model, watch
   exactly where its reasoning lacks world model, and that failure tells you what to
   author next. Every substantive feature after the first slice exists because a
   live agent failed in a specific, named way. This is the concrete answer to "how
   do you author one," and nobody in the incumbent chorus is describing it.

4. **The proof (C — the third way).** The false fork: workflow automation (reliable,
   no judgment) vs. free-range agents (judgment, ungrounded, unauditable). The third
   way: **judgment exactly where it pays, on a deterministic floor it can't argue
   with.** Shown, not asserted — the floor *catches the hallucination and blocks it*
   (emotional center: the system never silently shipped a bad number), and agency
   *survives* (different levers across runs, dollar-quantified trade-offs, and
   convergence that is fact-driven, not collapsed).

5. **The mechanism (B — one paragraph + one diagram, kept short).** Identity
   rendered from the model at runtime; deterministic routing, no LLM in the path;
   seven generic tools; role N+1 is a YAML edit (zero code).

6. **The call to action (D — the practice).** How you'd start Monday: world-vs-policy
   as the authoring test; the fix-family routing as the discipline; validation as
   the contract.

**Register (settled this session):** tell it as **rapid iterative development under
a fixed discipline** — fast build→run-live→watch-it-fail→fix-same-session loop, with
one thing held constant: *where fixes are allowed to land*. NOT "pre-registered
experiment." Git is a back-pocket footnote ("it's all dated if you want to check"),
never the spine. The forensic register oversells and reads as trying too hard.

---

## 2. How we discuss the features + mental models (the vocabulary)

- **"Routing-with-refusals" is the thesis — not "iterate on failures."** Every
  failure routes to a structurally distinct HOME: render gap → ontology; fake
  reference (entity or playbook) → deterministic floor; ungrounded number →
  grounding reader; reasoning-shape regression → render fix. And two fixes are
  **forbidden every time: prompt nudges and orchestrator/policy patches.** The
  refusals make it a method, not error triage. The one line that needs zero
  chronological precision and is simply TRUE: *"the routing held for all eight; it
  never once collapsed to a prompt patch"* — provable by where the diffs are.

- **The taxonomy is derivable from the type system, not just empirical** (blunts
  "artifact of one project"): schema-invalid → validator catches it; schema-valid
  but refutable against world state → deterministic floor; schema-valid AND
  irrefutable (a plausible number) → only grounding works; reasoning-shape → only a
  reader can see it. Anecdotes *instantiate* the structure. And half of it is
  **mechanized** — `unknown_entity`, `unknown_playbook`, `wait_all_unsatisfied` are
  trace events, not vibes.

- **§2 world-vs-policy is the constraint that makes the moat honest** — *"facts and
  action-vocabulary in, decisions out."* Not a thesis itself; the discipline that
  keeps fixes from freezing policy into the model. Exemplar: `committed_load` is a
  fact, `available` is arithmetic over facts — but a capacity *threshold* would be
  policy, and was refused.

- **"Generic" is a liability word** — always *generic runtime / role-agnostic code*,
  never *general-purpose LLM with no grounding*.

- **Features are introduced through the failure that motivated them, never as a
  catalog.** Not "we have an orientation preface + slot schemas." Instead: "the first
  live agent guessed field names and got lucky on a retry — so slot schemas became
  rendered world model." The feature is the *answer* to a pain the reader already felt.

- **The flanks are named, not hidden** — the self-disclosure IS the credibility move
  (a rationalized portfolio piece never does it). See §5.

---

## 3. The evidence — the failure→fix loop (told lightly)

Eight failure→fix pairs, each a live agent failure answered by a fix in its claimed
structural home. **The claim is discipline-under-iteration, not forensic chronology.**

| Failure (a live agent did this) | Fix | Home | Forbidden fix avoided |
|---|---|---|---|
| Guessed `SupplyRequest` slot names | render quantum slot schemas (Phase 1.5) | ontology render | prompt nudge |
| Thin, identity-rediscovering reasoning | domain-agnostic orientation preface (1.6) | ontology render | prompt nudge |
| Capacity axiom would force an `expr` interpreter | `tool_ref` → declared callable (1.7/1.8) | ontology | interpreter creep |
| Hallucinated plant/line names | `unknown_entity` floor (Ph4) → reader tools (Ph5) | deterministic floor → grounding | prompt nudge |
| Cited a non-existent playbook | `unknown_playbook` floor (Ph5) | deterministic floor | prompt nudge |
| Decided on 2-of-3 required queries | `wait_all` enforced gate (Ph5) | deterministic gate | orchestrator policy |
| Invented a baseline → sized promo at **45,000** | `query_baseline_demand` reader (Seed A) | grounding reader | rejection floor / nudge |
| Fired each context query twice (sweep) | `inputs_from_quantum`+`closed_set` (Seed C) | playbook schema | orchestrator patch |

**Audit verdict (done this session):** routing held for all 8; none was a prompt
nudge or policy patch (provable from diffs). Stop conditions were committed in
`CLAUDE.md` on 2026-05-27, before the phases they govern (pre-registration exists,
but we've DEMOTED it to a footnote per the register decision). The strongest single
pair: the 45,000 failure is named in the Phase-6 commit *body* (2026-05-31), ~2.5
days before the Seed-A fix, in the other repo. **Two honest caveats to state, not
hide:** (a) `runs/*.jsonl` traces are local-only, not committed — failures are
builder-attested via changelog/commit bodies, not third-party artifacts (remediation:
commit redacted trace excerpts for the 2–3 headline pairs); (b) the `wait_all` pair
is co-committed (chronology rests on narrative, not commit separation).

**Live-proof highlights for C (the agency survives):** two Phase-6 live runs chose
*different* resolutions with quantified trade-offs ($1,275 co-man premium vs $7,200
OTIF penalty → co-man; then $36,975 vs $7,200 → renegotiate). Convergence in the
canonical scenario was *fact-driven* (determinate world), not agency collapse — open
a grounded second lever (A3) and it varies by seed. The floor caught a live
hallucination and blocked the dispatch (Phase 4).

---

## 4. Positioning / research context (full — so the next session doesn't re-derive)

From the 2026-06-04 research (roadmap §1, §6). Internalize before any public framing:

- **Narrative is validated + real.** 3.0× promo uplift realistic (scanner data
  2–8×); "sales commits / supply scrambles" is a $200B+ category; **59% of US promos
  lose money (72% global, McKinsey)**; **"promo whiplash" = the bullwhip effect**
  (price promos are a textbook root cause); on-the-nose quote (r4.ai): *"no single
  system connects promotional intent to supply capability before commitments lock in."*

- **"Ontology-grounded agents" is now the INCUMBENT CONSENSUS, not a novel claim** —
  o9 (Enterprise Knowledge Graph), Blue Yonder (Supply Chain Knowledge Graph + an
  Inventory Ops Agent doing *our exact scene*), Palantir (Ontology). Leading with it
  sounds like everyone else. **Differentiate BELOW the tagline.**

- **The two defensible differentiators:** (a) **the ontology renders agent identity +
  routing — zero per-role code** (the inversion; most vendors ground the *data*, we
  ground the *agent's identity + reasoning*); (b) **agency-as-eval** — we *measure*
  whether the LLM is still reasoning, via named failure patterns. Both are ours; the
  chorus has neither.

- **The article-as-foil:** MIT 2025 — *95% of enterprise AI pilots deliver no
  measurable return*; the convergent diagnosis is *agents lack operational context*.
  Our architecture is the textbook answer. Quote the failure, then show the
  architecture.

- **"Generic" is a liability word** (a competitor sells against it). Frame as generic
  *runtime* / role-agnostic *code*, never general-purpose ungrounded LLM.

---

## 5. The honest flanks (name them in the writeup)

- **Static world model** — the world is a read-only fixture, disconnected from the
  event log; it doesn't evolve as agents act. The **"where's the live data?"**
  objection and our biggest exposed flank. Honest answer: contract-in/wire-out +
  Tier-2 as the named next step. (`[[static-world-model-deferral]]`)
- **One conflict, not triage** — a CSCO lives in triage; we show one clean conflict.
  Reads as *illustrative* by construction. Architecture runs N in parallel; unshown.
- **The demo's conflict is injected** for the live replay — a grounded live agent
  sizes-to-fit and *dodges* the conflict (the Phase-5 finding). Honest, and itself a
  finding (grounding works so well it avoids the fight), not a cheat — frame it so.
- **Builder-attested traces** (see §3 caveat a).
- **Gemini-flash on a demo isn't production** — fair; the claims are about structure,
  not model horsepower.

---

## 6. Open decisions (where the strategy discussion resumes)

1. **The publishable unit is UNDECIDED (keep both open):**
   - **(i) One long literate essay** (~15pp): dilemma → thesis (moat) → proof
     (deterministic floor + surviving agency) → mechanism → CTA, repos as footnoted
     evidence. Supply-chain-grounded, complete.
   - **(ii) Focused failure-method piece**: shorter, sharper, on the failure-driven
     authoring method + fix-family routing. The **most portable** idea — not even
     supply-chain-specific; positions the user on *method*, not domain.
   - (Not mutually exclusive — (ii) could be the wedge, (i) the anchor.)

2. **Gate 3 — publication design (NOT yet done):** venue/altitude (technical-peer =
   architect/engineer level), the falsifiable form of the core claim (state it so a
   practitioner can test the taxonomy on their OWN system — that's the "is it useful?"
   test), and the smallest honest publishable claim that invites critique over applause.

3. **Master-story home:** roadmap nominates the **ontology repo** (grand design docs
   already live there). Revisit.

4. **Whether to commit redacted trace excerpts** to close the §3 caveat-(a) flank.

---

## 7. Reading order (substrate)

1. This file.
2. `briefings/csco-brief.md` — the north star (two CSCO questions, explainability
   ladder, the differentiator to land, glossary seed).
3. `briefings/roadmap-2026-06-04.md` — §1 (research settled) + §5 (§2 guardrail) + §6
   (loose-ends ledger).
4. `e2e_ontology/agent_system_design.md` — §1 (thesis / four claims), §2
   (world-vs-policy — the spine), §12 (open-questions register).
5. `e2e_orchestrator/CLAUDE.md` — the durable design rules + the **six-pattern
   agency-surface heuristic** (the genuine intellectual asset; = the fix-family
   taxonomy).
6. Both `CHANGELOG.md` — the chronological record in the project's own voice.
7. `e2e_orchestrator/docs/limitations.md` — the honest flank register.
8. Memory index: `…/memory/MEMORY.md`.

**First move in the new session:** don't draft. Confirm the arc (§1) + register
(§1 last para) still read true, then open the strategy discussion at §6 decision 1
or 2 — the user's call.
