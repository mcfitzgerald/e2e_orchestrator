# Design memo — the ontology exposes the *handshakes*; the fixture + seeded boundaries are shims

**Type:** design-direction memo (dev-manager, 2026-06-01). Paste-ready for the
`e2e_ontology` session to fold into `agent_system_design.md` §12 (open questions)
and `docs/limitations.md`. Not a build task — a frame that reweights Phase 7 and
keeps the POC's shims honest.
**Status:** OPEN design question, deliberately resolved *by experiment* (Phase 7),
not on paper.

---

## TL;DR

The system has two kinds of edge to the outside world:

| Edge | Ontology construct (today) | Shimmed in the POC by | Realized in production as |
|---|---|---|---|
| **Inbound** (world → us) | **boundary role** (`is_boundary: true`) | seeded/scripted boundary responders | a standard handshake — **MCP front door (Phase 7)** |
| **Outbound** (us → world/data) | **`scont:Tool`** (reader) | `world_state.yaml` fixture + a fixture-reading callable | a real integration — REST / **MCP / A2A** |

The ontology **already declares both edges** (a boundary role; a `scont:Tool` with a
typed input/output contract + a symbolic `implementation` name). What the POC
*shims* is the **transport behind each edge**. The insight: a `scont:Tool` is
already ~90% of an MCP tool spec (name + description + typed I/O), and a boundary
role is its inbound dual. So the durable artifacts are the **declared edge
contracts**; the fixture and the seeded responders are stand-ins for the real
systems on the other side of those handshakes.

This is **already the stated architecture** — `agent_system_design.md` says it in
three places (lines ~204, ~219, and §9 line ~412: *"In production: replaced by the
enterprise's systems of record. Reader tools wrap the integrations. The agent
doesn't know the difference."*). This memo only develops the one-liner into an
explicit frame and a tracked open question.

---

## The fork (the actual open question)

The current design keeps the integration **opaque**: the ontology declares a typed
contract + a symbolic `implementation`; the orchestrator binds that name to a
fixture-reader (demo) or a real integration (prod), and *"the agent doesn't know
the difference."* The candidate move is to make the **handshake explicit** — declare
the transport (REST / MCP / A2A), endpoint, and discovery as part of the model.

- **Keep transport opaque (today's design).** *"The agent doesn't know the
  difference"* is a **thesis asset** — generality. The agent reasons over typed
  contracts, blind to whether data is fixture / REST / A2A. Pushing transport into
  the ontology risks coupling the world model to infrastructure.
- **Expose the handshake (the proposed direction).** In a real deployment, *where a
  capability lives and how it's reached* is a structured fact that varies per
  enterprise and needs a declarative home. The ontology is the natural one, and it
  makes the system self-describing/discoverable — which is exactly what MCP/A2A are
  built for.

**Likely resolution shape (to be confirmed by experiment, not decided here):** the
**contract** (that a handshake exists; its typed I/O; reader vs compute) is **world
model → stays in the ontology**; the **wire** (endpoint, auth, transport) is a
**binding/connector layer → probably *not* in the ontology**, or a thin separate
`scont:Connector`-style declaration distinct from `scont:Tool`. The clean line is
*contract in, wire out* — but where exactly it falls is what Phase 7 will teach us.

### §2 check

"A handshake to system X exists, with typed contract Y" answers without a
preference or ranking → **world model, eligible.** "Prefer system X over Y" /
"fall back to Z" would be policy → rejected. The transport detail (endpoint/auth)
is neither world nor policy — it's *infrastructure*, which argues for a connector
layer rather than the ontology proper.

---

## Why this reweights Phase 7

Phase 7 (the MCP front door, orchestrator Seed B) is **not just "a nice external
interface."** It is the **first time the system realizes a standard handshake
end-to-end** — the inbound edge, as MCP. That makes it the **reference pattern for
every edge** and the **experiment that informs the fork above**: building one real
MCP edge will show concretely whether transport wants to live in the ontology or in
a connector/binding layer — far better than deciding on paper.

A2A (agent-to-agent) is the **outbound/agent dual** of the same idea: where a
reader tool today reads a fixture, in production it might reach another agent or
system via A2A or MCP. Phase 7 inbound + the reader-tool outbound edges are two
faces of one concept.

### What the Phase 7 session should *observe* (feeds this question)

- When `ingress_quantum` is realized as a real MCP tool, how much of the
  declaration is already covered by the existing `scont:Tool`/boundary-role
  contract vs. what had to be added at the orchestrator/transport layer?
- Did anything transport-shaped (endpoint, session, auth, idempotency-at-the-wire)
  want to be *declared* rather than *wired*? If so, that's evidence for a connector
  construct.
- Could the inbound MCP surface and an outbound reader tool be described by the
  *same* edge/handshake abstraction? If yes, that's the unification; if they
  diverge, note why.

Capture these observations in the Phase 7 live report; they are the inputs to
closing this open question.

---

## Evidence from Phase 7 (2026-06-01) — the experiment delivered

Phase 7 built the inbound edge (MCP front door) and produced concrete answers to
all three observation questions. Full report:
`briefings/phase7-live-report-mcp-front-door.md`.

1. **Contract coverage: high → contract-in, wire-out confirmed.** Everything
   `ingress_quantum` needed to route + validate was *already declared* (the role's
   `is_boundary`, the flow's quantum class + `QuantumValidator`, the router). The
   only new material was non-semantic wire — `run_id`, an in-memory run registry,
   the resource-URI scheme, retry dedup. None of it is world model.
2. **One thing wanted *declaring*: idempotency/session identity.** It needed a home
   at *both* the wire layer (did this client call already happen?) and the in-run
   layer (did this dispatch already fire?). That a single concept spanned both
   layers is the strongest evidence for a thin **`scont:Connector`** that declares
   idempotency/session *once*. Endpoint/transport/auth, by contrast, stayed pure
   config — exactly the "infrastructure, neither world nor policy" the §2 check
   predicted.
3. **Unification viable at the contract level.** Inbound (`(flow, payload) → run
   pointer`) and outbound (`(tool, input) → typed output`) are duals: name + typed
   I/O + symbolic implementation, transport invisible to the agent. They diverge
   only at command-vs-query — which the system already distinguishes (handoff vs
   query flows; MCP tools vs resources). A `scont:Connector` of kind
   `{inbound|outbound}` + typed I/O + bound transport would cover both.

**Where this leaves §12.8 (as of Phase 7).** Directionally answered (*contract-in,
wire-out*; a `scont:Connector` is the concrete candidate for the one thing that
wanted declaring). **Still open — do not build the construct yet.** This is *inbound*
evidence only; let an **outbound** edge add its half before designing
`scont:Connector` (the repo ethos: build it, see what's needed). Seed A's
baseline-demand reader is the next outbound edge — it should be read against these
same three questions and its findings appended here. Close §12.8 when both edges
agree on the construct.

---

## Evidence from Seed A (2026-06-03) — the outbound edge, and §12.8 closes

Seed A built the first **outbound** edge: the `query_baseline_demand` reader
(`application/reader_tools.py`, declared as a `scont:Tool` in the ontology). Read
against the same three questions:

1. **Contract coverage: high again → contract-in/wire-out, a third time.** The
   `scont:Tool` declared the name, typed I/O (`BaselineDemandQuery` →
   `BaselineDemand`), and a symbolic `implementation`. The orchestrator added only
   the wire: the Python callable + the fixture read + the registry binding. Nothing
   semantic crossed into the orchestrator; nothing infrastructural crossed into the
   ontology.
2. **Did anything want *declaring*? No — and that is the decisive finding.** At the
   inbound edge, idempotency/session wanted a home at both layers. At the outbound
   *reader* it **does not resurface**: a read is naturally idempotent (no dedup, no
   session). So the thing that motivated `scont:Connector` is a **command** property,
   not a general edge property. Endpoint/auth again stayed pure config.
3. **One abstraction for both directions? Only at the contract level — and the
   divergence is exactly idempotency.** Inbound and outbound share {name, typed I/O,
   symbolic implementation, edge-kind}; they diverge on idempotency, which lives only
   on the *command* side. A bidirectional `scont:Connector` whose headline was
   idempotency would over-fit: the directions rhyme on contract but split on the one
   property that justified the construct.

### Verdict — principle resolved, construct deferred

The {inbound, outbound} × {command, query} 2×2 now has **three cells realized** —
inbound-command (`ingress_quantum`), inbound-query (MCP resources), outbound-query
(the reader) — **all agreeing contract-in/wire-out.** Only **outbound-command (A2A)**
is unbuilt, and it is the *sole* remaining site where idempotency could recur.

- **Principle: settled.** Typed I/O contract = world model (stays in the ontology);
  endpoint / auth / transport = wire (stays config). The agent keeps reasoning over
  typed contracts, blind to transport.
- **Construct (`scont:Connector`): do not build it.** Its sole justification
  (idempotency/session) is inbound-command-only on the evidence so far. If ever
  declared, idempotency attaches to the **boundary flow**, not a new bidirectional
  construct.
- **Trigger to reopen:** the first **outbound-command (A2A)** edge — a boundary role
  reaching an external agent/system. That is the second idempotency site and the only
  thing that can confirm or kill the bidirectional-connector idea. Building the
  construct before then is the construct-first move §12.7 warns against.

Recorded in `agent_system_design.md` §12 #8 (resolution paragraph) and
`docs/limitations.md`.

---

## Proposed `agent_system_design.md` §12 entry (new open question)

> **8. The ontology exposes the handshakes (edge transport).** The world fixture and
> seeded boundary responders are shims for real external systems. The ontology
> already declares both edges — boundary roles (inbound) and `scont:Tool` (outbound)
> — but keeps the transport opaque (symbolic `implementation`, bound at boot;
> *"the agent doesn't know the difference,"* §9). Open question: should the
> ontology *expose the handshake* — transport (REST/MCP/A2A), endpoint, discovery —
> as a declared connector, or does that stay a binding/connector layer outside the
> ontology? Leaning: **contract in, wire out** — the typed I/O contract is world
> model; endpoint/auth is infrastructure, likely a thin `scont:Connector` separate
> from `scont:Tool`, or pure orchestrator binding. **Resolve by experiment:** Phase 7
> (the MCP front door) is the first realized edge; let it inform the answer rather
> than deciding abstractly. A2A is the outbound/agent dual. Relates to §12.6
> (boundary role implementation) and §6.2 (Tool meta-construct).

## Proposed `docs/limitations.md` note (orchestrator repo)

A short addition to the "static world model" / "reference implementation" family:

> **The world fixture + seeded boundaries are shims behind declared edges.**
> `world_state.yaml` (read via reader tools) and the scripted boundary responders
> stand in for the enterprise's systems of record and external participants. The
> *durable* artifacts are the declared edge contracts — boundary roles (inbound)
> and `scont:Tool` reader declarations (outbound). In production these bind to real
> integrations (REST/MCP/A2A) behind the *same* typed contracts; the agent and the
> routing don't change. Phase 7 realizes the first such edge (inbound, as MCP).
> Whether the transport itself becomes declarative (a connector construct in the
> ontology) is `agent_system_design.md` §12.8, deliberately resolved by the Phase 7
> experiment.

---

## What NOT to do now

- **Do not** design a `scont:Connector` / transport construct up front. Let Phase 7
  produce the evidence first (the repo's "build it, see what the narrative needs"
  ethos — §12.7).
- **Do not** push endpoint/auth/transport into `scont:Tool` or the ontology yet.
- **Do not** change the POC's shimming. Fixture + seeded boundaries remain correct
  for the demo; this memo changes *framing and record-keeping*, not the build.
- **Do not** lose *"the agent doesn't know the difference."* Whatever the resolution,
  the agent must keep reasoning over typed contracts, blind to transport — that
  generality is the thesis.

---

## Cross-refs

- Seed A (`seed-A-demand-grounding-gap.md`) — the baseline-demand reader is an
  **outbound edge**, fixture-shimmed; its `scont:Tool` contract is the durable part.
- Seed B (`seed-B-phase7-mcp-front-door.md`) — Phase 7, the **inbound edge** and the
  experiment that informs this memo.
- Memory: `[[ontology-exposes-handshakes-edge-frame]]`, related to
  `[[static-world-model-deferral]]` and `[[ontology-context-breadth-tradeoff]]`.
