# CSCO Brief — what we're building, why, and the strategy

*Crystallized 2026-06-04. The north star for the build: this brief is the thing
the demo must make true. We answer the CSCO's two questions by **building the
solution and demonstrating it** — the running scenario is the argument.*

The CSCO asked two questions:
1. **What is an ontology, why do we need it, how do we build / get one?**
2. **What is our agentic strategy?**

Below are the answers in his register (senior operator, time-poor, skeptical of
AI hype). The demo is engineered to let him *see* each claim, not just hear it.

---

## Q1 — What is an ontology, why do we need it, how do we get one?

**What it is (plain).** A formal, machine-readable model of how *your* supply
chain actually works — the things that exist (plants, lines, SKUs, retailers,
promos, supply requests), their attributes, how they connect (which lines run
which SKU, which DC serves which retailer), the rules that constrain them (*a
line can't exceed its weekly capacity; a shipment must arrive by the MABD*), and
the moves that can be made (*slip the promo, shift to co-man, partial-fill*).
It's a **system of record for how the business operates** — not the transactional
data, the **operating logic** underneath it.

The honest framing: *you already have an ontology — it's just scattered.* It
lives in ERP config, planning spreadsheets, SOP docs, and your planners' heads.
An ontology makes that explicit, single-source, versioned, and readable by a
machine. It's the difference between a map in each planner's head and one shared,
governed map everyone — human and AI — navigates from.

**Why we need it.** It's the answer to *"why do most enterprise AI pilots fail?"*
— the stat going around is **95% deliver no measurable return** (MIT, 2025), and
the diagnosis everyone converges on is *the agents lack operational context.* The
ontology **is** that context, made formal. Concretely it buys three things:

1. **Trust** — every number an agent uses traces to a real fact in the model; it
   can't invent a baseline or hallucinate a plant.
2. **Auditability** — every rule the agent respects is one *you* wrote and can
   inspect; routing is a deterministic lookup, not an AI guessing who does what.
3. **A safety line between facts and judgment** — the model holds what's *true and
   legal* (capacity, lead times, OTIF terms); it deliberately does **not** hold the
   *decisions* (which lever to pull). That keeps the AI from quietly freezing a bad
   policy into the system.

**How you build / get it.** You don't buy it off the shelf — the *content* is
yours (Palantir/o9 sell the platform; you still author the model). You build it by
formalizing what your planners already know, **incrementally, one scenario at a
time** — start with the smallest end-to-end slice (one promo, one conflict), prove
it round-trips, then grow. You never boil the ocean. The inputs are things you
already own: master data (SKUs, plants, lines) → relationships (BOM, qualified
lines) → rules (capacity, lead times, OTIF targets) → playbooks (your resolution
SOPs). It's a **living, versioned asset that appreciates** — author a rule once and
every agent, scenario, and future role uses it.

One distinction to give him: the *model and rules* are largely reusable across the
enterprise (and even across companies); the *specific numbers* are your master
data, plugged in through integration. **Same engine, your data.**

> **Anticipated pushback:** "build your own ontology" sounds like a multi-year
> program. The credible counter is our own story — **we stood up a working slice
> with a phased vertical-slice approach, scenario by scenario.** It's incremental,
> not boil-the-ocean. That proof is *why* we build before we pitch.

---

## Q2 — What is our agentic strategy?

**In one line:** *Generic AI agents on deterministic rails, grounded in the
ontology* — not a fleet of bespoke bots, and not one big autonomous AI running the
show.

**The strategy is a separation of three jobs, each trustworthy on its own:**

- **The orchestrator** (deterministic, no AI) decides **who acts and when** —
  auditable, repeatable, no LLM in the routing path.
- **The ontology** decides **what each agent is and what it knows** — an agent's
  identity and instructions are *rendered from the world model*, not hand-written.
  That's why a new role (a plant scheduler, a trade lead) drops in at **near-zero
  cost** — no new code, no new bespoke bot.
- **The LLM agent** provides **judgment** — and *only* where judgment is genuinely
  needed (sizing a request, choosing among levers), never where a rule or a lookup
  should decide.

**Why this beats the two things you're being pitched:**

- *vs. buying point-solution agents* (vendors ship five named, purpose-built bots):
  hand-built per function, don't generalize, lock you in. Ours: **one runtime; new
  roles are configuration, not engineering.**
- *vs. one autonomous AI running it*: that's the thing that *fails* — no grounding,
  no audit trail, silently encodes policy. Ours puts the **LLM only where it adds
  judgment, behind deterministic rails**, every decision traceable to facts.

**The operating model he'll recognize:** the agents *augment* the planners in the
weekly S&OE loop — they assemble context, ground the numbers, route the work, and
surface the decision. **The human stays the decision-maker on the hard trade-off**
(take the OTIF fine vs. pay the co-man premium vs. slip the promo). We deliberately
*don't* automate that choice — that's his planners' judgment, and the architecture
is built to protect it, not replace it.

**The one differentiator to land:** nobody else does these two things — **the
ontology generates the agents** (zero per-role code), and **we measure whether the
agent is actually reasoning** (agency-as-eval, with named failure patterns). Most
vendors ground the *data*; we ground the *agent's identity and reasoning* — and we
*prove* it.

---

## How the demo makes each answer visible

| Claim | What the CSCO sees in the demo |
|---|---|
| The ontology *is* the operating logic | Roles, rules, and resolution paths all read out of one model; change the model → behaviour changes, no code |
| New roles cost ~nothing | `plant_scheduler` and `trade` added with **zero** edits to the agent template / tools (live proof of the breadth claim) |
| Agents are grounded, not guessing | Every number traces to a reader-tool fact; the trace shows it |
| Facts vs. decisions stay separated | Ontology holds capacity/OTIF/co-man **facts**; the *choice* of lever is the agent's, varying by run |
| You can ask the model questions | The knowledge-MCP answers "if the promo slips a week, who's affected?" by traversing the ontology |

## Explainability ladder (same content, four altitudes)

This brief is the **base layer**. The other audiences are the same story pitched
up:

1. **CSCO / operator** — *this brief* (what/why/how + strategy, in his terms).
2. **Planner / practitioner** — the scenario walkthrough: the S&OE conflict, the
   roles in the room, the levers, the trade-off.
3. **Architect / engineer** — world-vs-policy (§2), the three disciplines, the
   seven-tool kit, agency-as-eval, T-Box/R-Box/A-Box.
4. **Investor / builder** — the five theses (T1–T5), the inversion vs. the
   incumbents, the wedge.

If the CSCO version lands, every layer above it builds cleanly. Nailing this brief
is the test of whether we can explain the project at all.

## Glossary seed (promote to a project-level GLOSSARY)

`ontology` · `world-vs-policy` · `agentic strategy` · `generic agent / generic
runtime` · `deterministic orchestrator` · `agency-as-eval` · `T-Box / R-Box /
A-Box` · `bullwhip effect / promo whiplash` · `baseline vs. incremental demand` ·
`sell-in vs. sell-through` · `OTIF / MABD` · `co-manufacturer` · `S&OP vs. S&OE` ·
`allocation / partial-fill`.
