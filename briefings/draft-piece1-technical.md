# Draft — Piece 1 (technical, Medium canonical + X thread)

Status: **Draft 4**, 2026-08-12. Re-anchored to the ontagent rebuild
(phasing step 9). Vocabulary sweep, scenario transplant to promo-caused
allocation under shortage, new History and Boundary sections (front door
folded into the latter as the inbound half), machine-assembled context,
derived-causality and emission-rights beats, 45k story dropped, Limits
rewritten. Exhibit slots `[EXHIBIT n]` map to `../ontagent/docs/exhibits.md`
(13 exhibits, each verified against the repo at 96 tests green). Spine per
`seed-piece1-reanchor.md` (all three parts) plus session ratifications
(machine-assembled context, computed scope, winnability beat, cold-reader
beat, divergence-as-acceptance, committed-failure discipline).

---

# Why Not Just Spawn Agents on the Fly?

*Notes from building a supply chain ontology and using ephemeral agents to
take on its roles.*

Code: [ontagent]

---

[header image candidate: screenshot of `docs/world-graph.html` — the whole
declared world as a rendered graph, causality edges drawn. Resolves the
Draft-3 visual note.]

I built an ontology of a fictional consumer-goods supply chain — its entities,
roles, flows, lifecycles, and invariants — and an orchestrator that spawns
agents from it. When work reaches a role, the system renders that role's view
of the world and binds it as the instruction of a freshly created agent; the
agent acts through a small set of generic tools and is discarded. There is no
per-role code and no agent registry. The role is durable; the agent is
ephemeral.

I encountered two articles along the way that sharpened what this project is about.
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

Rather than a tour of the repo, here is the minimum set of elements I think
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

`[EXHIBIT 2: no policy, structurally — the playbook lists options and refuses
to order them, and the meta test proves no slot in the schema can hold a
ranking]`

**The ontology instance.** The one domain-specific element: the operating
model, declared. Roles — the seats in the organization, what each is
responsible for, what it can send and receive; and not only the internal
seats. The retailers, the carrier, and the plant's scheduling desk are
declared as roles too — boundary parties the work crosses to. (This build's
world settled on four seats and three boundary parties; the pull-forward
lever, for instance, belongs to the plant's scheduling surface — a party,
not a fifth seat.) Flows — the channels work moves through, each declaring a
sender, a receiver, and the shape of what travels. Work units — the typed
messages that do the traveling: a purchase order, an allocation notice.
Lifecycles — for long-lived things like a purchase order, the states it can
occupy and the legal transitions between them. Invariants — conditions that
must hold no matter who is acting: a week's scheduled hours stay under the
line's ceiling; a freight booking that changes nothing books nothing. And
playbooks — for recurring situations that call for judgment. A playbook
declares the evidence worth assembling — for the shortage review, the
accounts' penalty exposure and the freight options, as required queries —
the considerations that apply, and the resolution options that exist.
Options listed, never ranked. The shortage playbook's guidance ends with the
reason the situation reaches an agent at all: *"the arithmetic will not
close this decision, which is why it reaches this seat."*

The instance grows to whatever reflects the reality of the operation — the
counts of roles and flows in this build are where a demonstration stopped,
not a recommendation. I author it in LinkML YAML: humans can read it,
machines can validate it, and version control can diff it. Just as
important, it formally expresses a graph structure — and in this build that
cast does real work. The whole declared world renders to an interactive
graph, 86 nodes and 142 edges, regenerated from the ontology by an
extractor. Rendered, never drawn: the diagram cannot drift from the world,
because the world is its only source.

`[EXHIBIT 8: the world as a graph — the causality edges are visible as
edges: flow —emits→ event, invariant —on failure emits→ event, event
—re-derives→ invariant]`

**World state.** Master data and operational data — and they deserve
different treatment, because they have different provenance. Master data is
declared alongside the ontology: the SKU, the plant, the line, three
retailers and their penalty regimes. The regimes are real published
programs — an on-time-in-full charge at three percent of cost, a fill-rate
program, a handshake account with no program at all — carried under
fictional names, with the source cited on each value; a CI check keeps the
names fictional, structurally. Operational data — on-hand, orders,
shipments — is never authored at all. It enters the system only as events,
which is its own section below.

Authoring the master data included engineering the decision space. The
demonstration scenario is a trade promotion landing on a week that cannot
cover it, and the numbers are set so that no lever dissolves the judgment:
the gap is near 4,800 cases; expediting the inbound shipment recovers
3,000; pulling production forward recovers 1,500; both together still leave
the week roughly 260 short. Someone has to decide who bears it, in every
run.

### One authoritative reader

Some service must be the single place that reads the declared world and
answers for it, so that every consumer — agent, human, runtime — sees the
same world. Two capabilities look irreducible: **query** (answer questions
about the declared world, deterministically) and **render** (project one
role's slice of the world into a consumable form). And one hard rule rides
on the render: it is the *only* source of agent identity. No hand-authored
prompts anywhere in the repo.

Two properties of the render turned out to matter more than I first gave
them credit for. **Scope is computed, never configured**: a seat's view
contains the entity types reachable from its own work units, widened one
hop — nothing else. The transportation seat's rendered world contains no
retailers and no penalty regimes; it literally cannot see whom a shortage
hurts. That is not access control bolted on; it falls out of the
declarations. And **the render has to be holdable**: this build's largest
view is about 15,000 characters — against a 42,000-character dump in an
earlier iteration — and a test fails any role view that exceeds 20,000. A
related rule earned its place the hard way: declared meaning must render.
Descriptions are part of the contract; a description that never reaches the
seat is dead world knowledge. (The failure that taught this is below.)

I used to claim the same render could serve as a new hire's onboarding
document — one function, two consumers. The rebuild let me test a version
of that claim: legibility to an outsider was made an acceptance item. A
fresh agent session with no prior context followed the README to a trace
and explained the architecture back — correctly, citing exact records — and
surfaced structural observations the repo's own prose never states. The map
reads.

`[EXHIBIT 3: the rendered role view — the agent's entire identity, generated
at dispatch]`

### The deterministic machine

Everything the ontology declares, something in the runtime enforces — each
kind of declaration gets exactly one deterministic counterpart. Flows get a
**router**: when work arrives, its destination is a lookup against the
declared flows, and no model call decides who runs next. Declared schemas,
references, and invariants get a **validation stack**, described under
"Watching it fail." Lifecycles get a **tracker** — and even the tracker
takes no instructions: a transition names the declared event that triggers
it, and the tracker advances each object from the log as those events land.
There is no imperative path to a state. And the router knows a flow the
machine cannot run: when a flow's payload is something only its seat can
author, the machine does not guess — the triggering event makes the flow
*due from that seat*. The ontology declares obligations, not just
automations.

Playbooks get the counterpart I'd defend hardest. A playbook opens on a
declared event, and it declares the evidence that matters — for the
shortage review, the accounts' penalty exposure and the freight options, as
required queries. The machine runs those queries itself, waits for all of
them, evaluates the declared criteria, and only then invokes one ephemeral
agent — with the dossier already assembled. The agent does not gather its
own evidence and cannot skip any of it. What arrives at the model is: here
is the situation, here is everything the world declares relevant, here are
the options that exist. Weighing them is the entire job.

The declaration I did not expect to write down is **consequence**. A flow
declares what its commitment emits: committing an allocation emits
`allocation_committed` — declared, never chosen. An invariant declares what
its failure emits, and this is the beat I keep returning to: **no one
decides there is a shortage.** The coverage check — does the week's
grounded demand fit inside the available supply? — is advisory arithmetic
against the log, and its failure *is* the shortage: the machine emits
`shortage_declared`, stamped with the check that derived it. The same
declaration lists the events that re-derive it, so when a confirmed lever
moves the supply picture — a freight booking, a production pull-forward —
the check re-runs against its last input and the review re-opens on the
smaller gap, mechanically. Even the event that summons the judgment is
deterministic; the only thing left to the agent is the judgment itself. The
machinery does not shrink the agency — it corners it.

`[EXHIBIT 1: the invariant's declaration on the left; on the right, the
trace obeying it twice — short 4,760 cases, then, after the booking
confirms, short 1,760]`

The counterpart that took me longest to see is **who may say what**. Every
event declares which seats or boundary parties may state it directly; an
event with no declared emitter is machine-only, entering the log solely
through declared consequence. The machine refuses an undeclared emission
before it looks at the payload, so a well-formed fact from the wrong seat
is named as what it is — a forgery, not a formatting error. Who may state a
fact is itself a fact.

This build's orchestrator is the barest-bones version of that machine, and
I make no claim it is the way to orchestrate — orchestration is a deep
field and any capable engine could hold these responsibilities. The claim
is only the division of labor: **the machinery decides who runs next and
what happens to outputs; the agent decides only within its dispatch.** The
orchestrator contains no model calls. Two disciplines keep it honest: every
action is recorded to a permanent log before its effects happen, and every
action carries a key so that a retry can never fire twice. The log carries
more weight than "audit trail" suggests — enough that it gets its own
section below. The build satisfies all of this with a file of JSON lines; a
production system would use a durable-execution engine.

**The agent factory** is the hinge of the whole approach. When work lands
on a role, it renders the role's view, binds it to a freshly created agent,
and discards the agent when the work is done. Nothing persists per agent —
no registry, no drift between an agent's self-conception and the declared
role. Everything durable lives in the ontology and the log.

**The toolkit** is the agent's entire action surface: a small, closed set
of generic tools, identical for every role, covering three needs — *read*
the declared world and its state, *act* by sending work through a flow or
stating a declared fact, and *decide* by surfacing a judgment to a human.
Every tool call routes back through the machinery, so an agent cannot act
outside the recorded, validated path. This build settled on six tools; the
number is an artifact of the build. What an agent can read is not even in
the six — readers are declared in the ontology like everything else, so
extending an agent's reach is an authoring task too. The closed set and the
generality are the point: they are what make adding a role an authoring
task instead of an engineering task.

## History — the log is the run

Operational state is never authored. On-hand inventory enters the log as a
counted fact; purchase orders arrive as events; every view — the supply
position, the open orders — is a reducer over the log. There is
deliberately no other write path: an imperatively writable view is a
fixture that can disagree with the log, so the build deleted the construct
entirely.

Two things follow, and both are queries rather than features. First,
history: "as of" is a question you ask the log, not a fixture you swap in.
Ask the demonstration scenario for the world as of record 60 and it prints
mid-story — 13,000 cases available, all three purchase orders open. As of
record 117, the ending — zero available, everything allocated and
acknowledged. Same log, two questions.

Second, audit: the log reproduces its own conclusions. A replay checker
re-derives every recorded invariant verdict against the log exactly as it
stood at that moment, and re-checks every lifecycle transition against the
declaration. The test suite tampers with a recorded verdict and the checker
names it — an edited log is caught, not believed. Determinism here is a
tested property, not an adjective: a fresh run of the scripted scenario
reproduces the committed trace byte for byte.

`[EXHIBIT 6: --as-of 60 beside --as-of 117, and the tamper test]`

## The boundary

The ontology declares parties and flows — never systems. The retailers, the
carrier, the plant's scheduling desk are boundary roles; an integration
point is nothing more than a flow that crosses one. At boot, each crossing
flow binds to an adapter; a real EDI or TMS connector would substitute with
zero ontology change. In this build the connectors are scripted mocks,
labeled as such — the claim is that "connected" has a declared shape, not
that an ERP was integrated.

What the mocks demonstrate is the loop closing. An outbound booking goes to
the carrier as a command; the confirmation comes back asynchronously, as an
event in the log; and the machine reacts to the event — the confirmed
booking re-derives the shortage check, and the review re-opens on the
smaller gap. Allocation notices go out to three retailers; three
acknowledgements come back; three purchase-order lifecycles advance to
their end state. Commands out, events back, consequence derived.

`[EXHIBIT 7: the boundary loop in the trace — booking confirmed, gap
re-derived; three notices, three acknowledgements, three lifecycles
closing]`

The same declaration serves the inbound direction. The system's front door
is an MCP server, and the design question was what the write primitive
should be. Not "run this flow" — process consequence belongs to the
machine. The write primitive is the one the world already has: state a
declared fact, as a declared boundary party, through the same seam the
genesis events and the adapters use. The door adds exactly one guard of its
own — you may speak *for* a boundary party, never *as* an internal seat,
because seat identity exists only through render-and-invocation. Everything
else is the machine's own floors, unchanged and in their usual order:
unknown event, undeclared emitter, invalid payload, then whatever blocking
invariants the stated fact causes.

The claim this earns is narrow: **the edge added a caller, not a
capability** — and it is proven as an equality rather than asserted. A test
has an external client emit the genesis facts over the protocol and
compares the resulting log against the in-process seeder's: byte-for-byte
identical. Try to lie to the door and the layers answer in their own
vocabulary: a retailer stating the inventory count is refused as an
undeclared emitter; an empty purchase order is refused with each missing
field named; wearing an internal seat is refused at the door itself. And an
outside caller learns its contract exactly the way an internal seat does —
by reading its rendered role view, which lists the events it may emit and
their shapes. One render mechanism, two audiences.

`[EXHIBIT 11: the byte-for-byte equality test]`
`[EXHIBIT 12: three lies, three layers answering]`
`[EXHIBIT 13: a boundary party reading its own contract]`

Both directions bind to the same declaration — parties and flows, one bound
to an adapter, one to a protocol.

## Watching it fail

The working method for the whole build: spawn the agent, watch the trace,
and when it misbehaves, fix the map, not the agent. Every failure got the
same question — *what deterministic check could have caught this?* — and
the checks that accumulated became the validation stack. One discipline
kept the method honest: every failure below has its trace committed in the
repo, beside the fix. The failures are artifacts, not anecdotes.

First contact with live models produced four, in order:

1. **The runaway.** A seat with no reader tools invented sixty-eight tool
   names and emitted bare-name events with empty payloads — and the machine
   believed the bare names. Two fixes, neither a prompt: reader tools were
   declared, so the seat had something real to read; and the meta-model
   gained the rule that an event is a typed fact — every emission validates
   against the event's declared payload shape, whoever the source is.

2. **The silently wrong number.** The demand seat grounded the week at
   12,960 cases instead of 17,760 — it read the promoter's order and took
   it for total demand. Schema-valid, real entities, past every floor:
   nothing deterministic can object, and a blocking threshold would smuggle
   policy into the world model. The root cause was subtler than a missing
   read: the field's meaning was declared in the world, but the renderer
   dropped descriptions, so the meaning never reached any seat. The proof
   is clean because the first fix failed — sharpening the world alone did
   not land (the next run repeated the miss); rendering the declared
   meaning did. Hence the rule above: descriptions are part of the
   contract.

3. **The stalled cascade.** Notices never went out, because "this flow
   fires on the allocation event" rendered like a description of
   automation — the seat waited for a machine that was waiting for the
   seat. The declarations were already sufficient to derive the truth: a
   flow whose payload the triggering event can supply is executed by the
   machine; one whose payload only the seat can author is *due from that
   seat*, and now renders that way. A render fix; the world did not change.

4. **The double expedite.** Two seats booked the same shipment onto the
   same expedited service — twice the freight spend for zero additional
   supply. A spend gate was considered and rejected: that is a policy
   judgment, and policy does not enter the world model. What entered
   instead is a fact about what a booking is: a booking that changes
   nothing books nothing — a blocking invariant.

The pattern across all four is the lesson I'd weight most: **an agent asked
for a value it cannot read will manufacture one, and the fix is never a
prompt nudge — it is extending what the world makes readable.** Declare
more world, ground more reads, or floor the machine; across every failure
of this build, the prompts never changed.

And the floors teach. In one committed run, a seat's first freight booking
passes — it genuinely changes the service — and its second is blocked:
"booking svc_team_expedite changes nothing." For the rest of that run,
every time an expedite is requested, the transportation seat reads shipment
status first, sees the expedite already in flight, and concludes without
acting. The behavior was learned from the rejection, inside a single run,
not from prose.

`[EXHIBIT 5: the floor is in code, not the prompt — and it teaches in one
run]`

> **Aside.** Mid-build I met the same problem from the other side: the pace
> of agentic development outran my own mental model of the system, and the
> fix was writing it down — changelogs and briefings until the picture came
> back. The ontology is to the agent what those documents were to me.

## Where the agency lives

The fair objection: declared flows, deterministic routing, guardrail
invariants, machine-assembled evidence — isn't this workflow automation?
Mostly, yes. Everything that could be enumerated is nailed down. The agent
exists for what cannot be enumerated.

In the demonstration scenario, a trade promotion lands on a week that
cannot cover it. The machine derives the shortage, opens the playbook,
assembles the dossier, and puts the question to the supply-planning seat:
whom to short, and whether to buy the gap smaller. Four options are
declared, because a veteran planner would name the same four — allocate
fair-share, allocate protect-and-short, expedite the inbound shipment, pull
production forward. Enumerating the options that exist is describing the
world. What the ontology cannot do is rank them: the list is alphabetized
on render, and there is no branch condition because there is no field to
hold one. The agent weighs the dossier, selects, and explains why.

Whether the judgment was real had its own acceptance test, designed before
the live runs: fix the declared world, vary only the opening numbers, and
require the runs to diverge — different levers *and* different allocations.
If every run converged on the scripted storyline, the agency had been
structured away, and the build failed. It passed:

`[EXHIBIT 10: the divergence table — four fixtures, same declared world,
different levers, different bearers of the short]`

The live runs inverted the scripted storyline — they protected the growth
account and the handshake account and concentrated the shortage on the
promoter, with the relationship arithmetic written down. At the thin
margin, the seat declined a 3,000-case expedite against a 380-case gap and
bought one overtime hour instead. Restraint is a judgment too. (Genesis is
a parameter set, never a world edit — the declared world is the constant of
the experiment. The whole live campaign was eight runs, six or seven
dollars.)

What the record holds for each run is a rationale, and the rationales are
the part I'd print:

`[EXHIBIT 4: the protect-and-short rationale, verbatim from the trace]`

Every number in it traces to a read; the priced and the unpriced sit in the
same paragraph — a $112.32 penalty exposure weighed against a twelve-year
record no rate card prices; and the ranking that decided it appears nowhere
in the repo.

**The boundary**: judgment is unconstrained, execution is gated. An option
flow that spends money will not execute without an approved, surfaced
decision — the gate is enforced in the machine, and it gates execution,
never judgment. One structural observation a cold reader spotted before I
did: the gate sits at the seat that judges the money, not the seat that
executes it. Transportation books the freight ungated; the decision to
spend was gated upstream.

## Role N+1

Adding a role is an authoring task, not an engineering task — and in this
build that claim graduated from an anecdote to an executable assertion. A
grep test walks every file of the machine and fails if any declared world
name — any role, flow, event, invariant, playbook, entity — appears in it;
the same test forbids any LLM import. Its companion goes the other way: it
authors a fifth seat *in YAML only*, appends it to a copy of the world, and
watches the unmodified reader render it and the unmodified machine route a
typed work unit to it. Zero code edits, by test.

`[EXHIBIT 9: the no-per-role-code claim as an executable assertion]`

That is the basis for inverting the first article's claim. In an
architecture of one agent per use case, with context wired into each
deployment, "the operating context never is [reusable]" is true. Here the
agent is reusable because it is empty, and the context is reusable because
it is formalized: author the ontology once, and every role renders from it.
Across companies the instance content is yours to author — nobody escapes
drawing their own map — but the meta-model, the discipline, and the
machinery transfer.

The ontology also stays maintained for an unsentimental reason: it is
load-bearing. Enterprise ontologies have died as shelf-ware because nothing
broke when they went stale. Here, staleness produces visible misbehavior in
traces. Maintenance is a pull request, not a governance committee.

## Limits

An earlier version of this piece carried a longer Limits section. The
rebuild's job, in large part, was to delete its paragraphs: world state no
longer loads as a snapshot (it derives from the log); the system no longer
stops at the decision (the loop closes through the boundary); fixtures can
no longer disagree with events (the writable-view construct is gone).

What honestly remains. One scenario, not many. The scripted storyline's
judgments are scripted by construction — the live traces are where the
judgment is real. The boundary connectors are mocked; the protocol is real,
but the client is ours — no third-party system has integrated against the
front door. The world is constructed: every capacity and rate is an
authored fixture, with real published rates cited on the values, and the
dollar totals are the agents' arithmetic over them. The live runs used a
small, fast model. No deployment, no savings claim, no benchmark.

One deliberate omission is worth explaining, because the reasoning is the
architecture's own. There is no live-model run behind the front door. The
equality test makes such a run unmeasurable: a client-driven session is
byte-identical to an in-process one, so a live seat behind the door
receives exactly the invocation the committed live traces already
captured — the transport has no mechanism to influence the judgment, and
the run would have measured sampling noise. The committed traces already
are the system's behavior behind the door. A small, honest example of
proving something instead of demonstrating it.

Everything above reproduces from a clone: the structural claims run as 96
tests in CI, and none of it needs an API key.

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
model, penned down, made executable. The machinery does not shrink the
agent's role; it corners it — in this build even the event that summons the
judgment is derived, and what is left to the agent is exactly the judgment.
Models will keep getting smarter, and it will not close this gap, because
the gap was never intelligence. **The limit is not intelligence; the limit
is reality's rate of disclosure.** An agent can only reason over what the
world has made readable. Drawing the map, and keeping it honest, is the
work.

---

*Previous work: [Whither Ontologies]. Cited: [Why AI Agents Fail to Deliver
Supply Chain Results] · [Maybe Intelligence Ain't All That].*

---

## Draft notes (not part of the piece)

- **Draft 4 changes (the re-anchor):** every code link and exhibit now
  sources from ontagent; scenario transplanted to promo-caused allocation
  under shortage; History and Boundary sections added (front door folded
  into Boundary as the inbound half); machine-assembled context, derived
  causality, emission rights, computed scope, winnability, cold-reader,
  divergence-as-acceptance, and committed-failure beats added; 45k story
  dropped (decided 2026-08-12 — the step-7 arc carries every argument it
  carried, in-world); Limits rewritten around what the rebuild built away.
  ~2,700 words — above the Draft-3 length; hold the cut-pass call until
  read whole.
- **Jargon ledger:** dissolved. The repo now speaks the prose vocabulary
  natively (work unit, invariant, lifecycle, guidance) — exhibits no longer
  need bridging captions. "Rejection floor" kept, defined inline. "Seat"
  appears in exhibits; prose uses "role/seat" interchangeably where natural.
- **Exhibit slots:** `[EXHIBIT n]` numbers map to
  `../ontagent/docs/exhibits.md` (13 exhibits, verified file:line, with a
  refresh procedure). All 13 are placed; none invented.
- **Header image:** candidate is a `docs/world-graph.html` screenshot
  (rendered, never drawn — the caption writes itself). Resolves the
  Draft-3 open visual note.
- **Title:** working title retained; still not sold. Candidates: "Why Not
  Just Spawn Agents on the Fly?" / "The Role Is Durable; the Agent Is
  Ephemeral" / "Agents From the Map" / "Render, Act, Discard: Notes on
  Ontology-Driven Agents."
- **Link slots:** ontagent repo (needs public URL before Code link goes
  live), Whither Ontologies, Oliveira SCB article, Sosin tweet.
- **Superseded:** Draft 3's fact-check ledger and its open editorial call
  (run-B/45k entanglement) are moot — every exhibit now comes from
  post-grounding ontagent traces. `draft-piece1-exhibits.md` deleted
  2026-08-12 (git history preserves it).
- **X thread:** re-cut after this draft settles — old spine is stale
  (referenced the two-runs card and the 45k beat). Candidate new spine:
  spawn-question → no-one-decides-there-is-a-shortage → divergence table →
  the rationale → floors-teach-in-one-run → byte-for-byte door → close.
