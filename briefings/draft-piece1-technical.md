# Draft — Piece 1 (technical, Medium canonical + X thread)

Status: **Draft 3**, 2026-07-28. Blends the three-layer "minimum system"
scaffold into Draft 2, with all of Michael's line edits applied. General
claims in the prose; demo specifics as evidence and exhibits. Exhibit slots
marked `[EXHIBIT]`. Uncommitted until Michael says otherwise.

---

# Why Not Just Spawn Agents on the Fly?

*Notes from building a supply chain ontology and using ephemeral agents to
take on its roles.*

Code: [e2e_ontology] · [e2e_orchestrator]

---

I built an ontology of a fictional consumer-goods supply chain — its entities,
roles, flows, lifecycles, and invariants — and an orchestrator that spawns
agents from it. When work reaches a role, the system renders that role's view
of the world and binds it as the instruction of a freshly created agent; the
agent acts through a small set of generic tools and is discarded. There is no
per-role code and no agent registry. The role is durable; the agent is
ephemeral.

I read two articles along the way that sharpened what this project is about.
The first, [Why AI Agents Fail to Deliver Supply Chain Results], argues that
agents fail for want of operational context, and that the durable work is
building the context layer. I agree with nearly all of it. The claim I reject
is this one: *"The agent may be reusable. The operating context never is."*
This project is the counterexample I built.

The second, [Maybe Intelligence Ain't All That], argues that a model's
reasoning fills the space between known facts but does not produce new facts —
*"the takeoff story assumed the limit was thinking. It isn't. The limit is
contact with reality."* I had believed something like this for a while without
having the words for it. The two articles point at the same place from
different directions: what limits an agent is not its intelligence but the
world it can read. That conviction is under every design decision below — the
engineering problem is not making the agent smarter; it is making the
operation readable to it.

## The idea

The project started when I tried to pen a supply chain ontology — an
experiment to see, literally, what one looks like: how you author it, how you
visualize it. It expanded while I was learning Google's Agent Development
Kit, when a question joined the two efforts: if the ontology already declares
the roles — who exists, what they are responsible for, what they can send and
receive — why hand-write an agent for each one? Why maintain an agent
registry at all? Put the agent primitives in the ontology, keep the agent
layer thin, and render each agent at the moment of dispatch.

## Previous work

In [Whither Ontologies] I looked at a specific enterprise problem: most
enterprise data lives in relational tables, and migrating an enterprise data
foundation from relational to graph is a massive undertaking. The alternative
I proposed was to describe the graph to an LLM and let it virtualize the
graph in its context window. I have no formal proof, but the idea seems to
work.

This project extends it twice. First, don't stop at a data ontology — encode
the operating model itself: roles, processes, flows, transactions. A virtual
twin of the organization. Second, don't just let agents read the twin: spawn
the twin's roles as agents.

## The system, in three layers

Rather than a tour of the repos, here is the minimum set of elements I think
any system of this shape needs — with this build as one instance of each.

### The declared world

**A meta-model.** Before authoring the domain, you decide what kinds of
statements the ontology may contain — and, by omission, what it cannot. The
meta-model is the schema of the schema, checked at authoring time. Its value
is that design principles become checkable instead of aspirational. The
principle this build enforces: **the ontology declares the world, never
policy.** What exists, what connects, what must hold — in. Anything that
would make the decision in advance — preferences, priorities, fallback
orders — out. Guidance is allowed: playbooks carry considerations for the
agent to weigh. What the ontology never carries is the answer. The point of
the discipline is to let the agent reason.

The idea underneath it: tradeoffs in an operational decision — cost, cash,
service — are ordinal, not cardinal. They cannot be collapsed onto one scale
in advance, but they can be ordered in a specific situation. That ordering is
judgment, and the architecture exists to keep judgment live rather than
freeze it into the artifact.

`[EXHIBIT: meta-model snippet — the body shapes, and what they cannot say]`

**The ontology instance.** The one domain-specific element: the operating
model, declared. Roles — the seats in the organization, what each is
responsible for, what it can send and receive. Flows — the channels work
moves through, each declaring a sender, a receiver, and the shape of what
travels. Work units — the typed messages that do the traveling: a supply
request, a capacity response. Lifecycles — for long-lived things like an
order or a promotion, the states they can occupy and the legal transitions
between them. Invariants — conditions that must hold no matter who is acting:
"line capacity is not exceeded." And playbooks — for recurring situations
that call for judgment: the evidence worth assembling, the considerations
that apply, and the resolution options that exist. Options listed, never
ranked.

The instance grows to whatever reflects the reality of the operation — the
counts of roles and flows in this build are where a demonstration stopped,
not a recommendation. I author it in LinkML YAML: humans can read it,
machines can validate it, and version control can diff it. Just as important
for what follows, it can formally express a graph structure.

`[EXHIBIT: one role, one flow, one playbook in YAML]`

**World state.** Master data and operational data. The ontology declares what
kinds of things exist; world state declares which things exist right now, and
their numbers — plants, lines, run rates. Kept separate because they change
on different clocks.

### One authoritative reader

Some service must be the single place that reads the declared world and
answers for it, so that every consumer — agent, human, runtime — sees the
same world. Two capabilities look irreducible: **query** (answer questions
about the declared world, deterministically) and **render** (project one
role's slice of the world into a consumable form). The same render that
becomes an agent's instruction could serve as a new hire's onboarding
document — one function, two consumers. And one hard rule rides on it: the
render path is the *only* source of agent identity. No hand-authored prompts
on the side.

`[EXHIBIT: the same role view rendered twice — agent instruction and
onboarding doc]`

### The deterministic machine

Everything the ontology declares, something in the runtime enforces — each
kind of declaration gets exactly one deterministic counterpart. Flows get a
**router**: when work arrives, its destination is a lookup against the
declared flows, and no model call decides who runs next. Declared schemas,
references, and invariants get a **validation stack**, described in the next
section. Lifecycles get a **tracker** that holds each object's current state
and refuses illegal transitions.

This build's orchestrator is the barest-bones version of that machine, and I
make no claim it is the way to orchestrate — orchestration is a deep field
and any capable engine could hold these responsibilities. The claim is only
the division of labor: **the machinery decides who runs next and what happens
to outputs; the agent decides only within its dispatch.** Two disciplines
keep it honest: every action is recorded to a permanent log before its
effects happen, and every action carries a key so that a retry can never fire
twice. The log is the source of truth — the current state of the world can
always be reconstructed, and disputed, from history. The build satisfies this
with a file of JSON lines; a production system would use a durable-execution
engine.

**The agent factory** is the hinge of the whole approach. When work lands on
a role, it renders the role's view, binds it to a freshly created agent, and
discards the agent when the work is done. Nothing persists per agent — no
registry, no drift between an agent's self-conception and the declared role.
Everything durable lives in the ontology and the log.

**The toolkit** is the agent's entire action surface: a small, closed set of
generic tools, identical for every role, covering three needs — *read* the
declared world and the world state, *act* by sending work through a flow or
advancing a lifecycle, and *decide* by surfacing a judgment to a human. Every
tool call routes back through the machinery, so an agent cannot act outside
the recorded, validated path. This build settled on seven tools; the number
is an artifact of the build. The closed set and the generality are the point:
they are what make adding a role an authoring task instead of an engineering
task.

## Watching it fail

The working method for the whole build: spawn the agent, watch the trace, and
when it misbehaves, fix the map, not the agent. Every failure got the same
question — *what deterministic check could have caught this?* — and the
checks that accumulated became the validation stack. Malformed output:
schema validation catches it. Well-formed output that cites things that do
not exist — a plant, a line, a playbook: a rejection floor catches it,
meaning the claim bounces back as a machine-generated event ("unknown
entity"), not as a prompt correction. A result that violates a declared
invariant: the evaluator blocks it and the router responds.

Then there is the class no check can catch: the output is well-formed,
everything it cites is real, and it is still wrong. In one run, the
demand-planning agent sized a promotional supply request at 45,000 units — a
valid number built on an invented baseline, because the agent had no way to
read the actual run rate. No validator can object. A blocking threshold would
smuggle policy back into the world model. The only fix is grounding: give the
agent a tool that reads the real baseline, so it multiplies a read number
instead of a guessed one. That generalizes into the lesson I'd weight most:
**an agent asked for a value it cannot read will manufacture one, and the fix
is never a prompt nudge — it is extending what the world makes readable.**

A second family of failures — reasoning shape, like an agent rediscovering
its identity on every invocation — does not reduce to checks. Those are field
notes, fixed upstream in how the role view or playbook renders.

`[EXHIBIT: failure→fix table, two families separated]`

Mid-build I met the same problem from the other side: the pace of agentic
development outran my own mental model of the system, and the fix was writing
it down — changelogs and briefings until the picture came back. The ontology
is to the agent what those documents were to me.

## Where the agency lives

The fair objection: declared flows, deterministic routing, guardrail
invariants — isn't this workflow automation? Mostly, yes. Everything that
could be enumerated is nailed down. The agent exists for what cannot be
enumerated: the ambiguous goal.

In the demonstration scenario, a trade promotion lands on a constrained week
and supply planning catches a capacity conflict. The conflict has four
defensible resolutions — renegotiate the promotion, re-plan the internal
lines, shift volume to a co-manufacturer, or allocate a partial fill. A
veteran planner would list the same four, so the ontology lists them:
enumerating the options that exist is describing the world. What the ontology
cannot do is rank them. The option list is alphabetized on render, and there
is no branch condition because there is no field to hold one. The agent
assembles the declared evidence — service exposure, promotion flexibility,
co-manufacturer availability — weighs it, selects, and explains why.

Two live runs hit the same conflict under different fixture economics (I
authored every number; the behavior is what emerged). One faced a $1,275
co-manufacturing premium against a $7,200 service penalty and shifted volume
to the co-manufacturer. The other faced a $36,975 premium and went back to
renegotiate the promotion. No rule made the choice; the reasoning traces show
the arithmetic.

`[EXHIBIT: run A vs run B — same conflict, different economics, different
resolution]`

The boundary: judgment is unconstrained, execution is gated. The agent's
decision surfaces to a human per the role's involvement policy.

## Role N+1

Late in the build I added two roles to a system that had been running one,
with zero edits to the agent template and zero edits to the toolkit. Adding a
role is an authoring task, not an engineering task.

That is the basis for inverting the first article's claim. In an architecture
of one agent per use case, with context wired into each deployment, "the
operating context never is [reusable]" is true. Here the agent is reusable
because it is empty, and the context is reusable because it is formalized:
author the ontology once, and every role renders from it. Across companies
the instance content is yours to author — nobody escapes drawing their own
map — but the meta-model, the discipline, and the machinery transfer.

The ontology also stays maintained for an unsentimental reason: it is
load-bearing. Enterprise ontologies have died as shelf-ware because nothing
broke when they went stale. Here, staleness produces visible misbehavior in
traces. Maintenance is a pull request, not a governance committee.

## Limits

Every number above is a fixture I authored; the divergent behavior is
emergent, the dollars are not. One scenario, not many. World state loads as a
snapshot at startup; deriving it from the event log is designed, not built.
The live runs used a small, fast model. And the system stops at the decision —
the agent does not transact against an ERP. Agents can only transact if
connected, and that integration work was deliberately out of scope. No
deployment, no savings claim, no benchmark.

## What I'd claim

1. Context is king.
2. Context management should be a formal discipline, not a per-agent craft
   project.
3. Ontologies are a mature formalism for exactly that.
4. Authoring one maps your people, processes, and systems — valuable before
   any agent shows up.
5. Spawning agents from the ontology — identity rendered from the map, roles
   as ephemeral agents, zero per-role code — is, as far as I can tell, the
   new part.

The first four are close to consensus. The fifth is the experiment, and it
held long enough to write down.

This is one piece of the necessary parts of an agentic operation: the mental
model, penned down, made executable. Models will keep getting smarter, and it
will not close this gap, because the gap was never intelligence. **The limit
is not intelligence; the limit is reality's rate of disclosure.** An agent
can only reason over what the world has made readable. Drawing the map, and
keeping it honest, is the work.

---

*Previous work: [Whither Ontologies]. Cited: [Why AI Agents Fail to Deliver
Supply Chain Results] · [Maybe Intelligence Ain't All That].*

---

## Draft notes (not part of the piece)

- **Draft 3 changes:** three-layer scaffold replaces "What got built" and
  absorbs "The one rule" (→ meta-model) and "Fix the map" (→ "Watching it
  fail," method-first); all line edits applied (opening sentence rephrased,
  "mock"→"fictional" in body only, Code links under title, "I read two
  articles" opening, no author name-drops, Sosin paragraph integrated with
  the shared-conclusion line, origin corrected to ontology-first, LinkML
  graph-structure note added, counts de-enumerated, jargon simplified).
  ~1,950 words — above the Draft-2 target; flagged for a cut pass if it
  reads long.
- **Jargon ledger (decided):** "idempotency key" → "a key so a retry can
  never fire twice"; "quantum" → "work unit"; "axiom" → "invariant";
  "state machine" → "lifecycle"; "rejection floor" kept but defined inline.
  Repo vocabulary differs (quanta, axioms, FSM) — exhibits will show repo
  terms, so captions should bridge ("the repo calls work units 'quanta'").
- **Title:** working title retained; he's not sold. Candidates: "Why Not
  Just Spawn Agents on the Fly?" / "The Role Is Durable; the Agent Is
  Ephemeral" / "Agents From the Map" / "Render, Act, Discard: Notes on
  Ontology-Driven Agents."
- **Link slots:** ontology repo, orchestrator repo, Whither Ontologies,
  Oliveira SCB article, Sosin tweet.
- **Punch-list addition (his):** repos need clear instructions and
  reproducibility before the Code links go live.
- **Fact-check flags before publish:** run economics vs `runs/phase6-live` +
  Phase 6 report; 45,000 story vs Seed A briefing; role-count wording ("added
  two roles… running one") vs Phase A changelog; "small, fast model" vs the
  2026-05-31 model-naming correction; `allocate_partial_fill` vs
  `shift_to_coman` demo contradiction resolved before any WHIPLASH link.
- **X thread:** cut after this draft settles — candidate spine:
  spawn-question → declared-world/one-rule → who-picks-the-branch →
  two-runs card → 45k → ladder → close.
