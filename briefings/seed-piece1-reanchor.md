# Seed — Piece 1 re-anchor to ontagent

Written 2026-08-03, from the ontagent build session that closed phasing
steps 5–6 (machine complete, stub scenario green end-to-end, history +
replay verification). Purpose: when the re-anchor session opens
`draft-piece1-technical.md`, this memo is the map — what survives, what
sweeps, what expands, and where every new exhibit comes from.

**Timing dependency:** re-anchor properly happens after ontagent step 7
(live ADK/Gemini runs + divergence acceptance + six-pattern review),
because "Watching it fail" and "Where the agency lives" want fresh live
traces. Everything else below can be drafted before that.

## The verdict on the spine

The spine survives 1:1 — the rebuild deliberately kept the same
three-layer anatomy. Changes: one mechanical sweep, two new sections,
one sharpened beat inside an existing section, and a Limits section that
largely dissolves (its former entries became capabilities).

Old spine → new spine:

| Draft section | Fate |
|---|---|
| The idea | keep; vocabulary sweep |
| Previous work | keep |
| The system, in three layers | keep structure; upgrades below |
| — The declared world | + real graph cast, LinkML-native, world-graph exhibit |
| — One authoritative reader | keep; new render is holdable (~15k chars vs 42k) — say so |
| — The deterministic machine | + derived causality beat (see below) |
| **History (NEW)** | the log is the run: genesis events, as-of, replay proof |
| **The boundary (NEW)** | the loop closes through mocked adapters |
| Watching it fail | keep the 45,000 story as history + add step-7 live material |
| Where the agency lives | keep; human gate now enforced in execution; rationale-as-record |
| Role N+1 | keep; now backed by a grep test you can quote |
| Limits | rewrite — three of its admissions are now built (see below) |
| What I'd claim | keep the five; fold causality corollary into prose, no claim #6 |

## The sweep (mechanical)

- Vocabulary: quantum → **work unit**, axiom → **invariant**, FSM →
  **lifecycle**, llm_prompt_hint → **guidance**. "Orchestrator" stays
  (ratified: the word is contested territory worth holding).
- Scenario transplant: every narrative example moves to **promo-caused
  allocation under shortage** — one SKU (BrightWave 32 oz), one line
  (Riverton), three retailers with real published penalty regimes under
  fictional names (Megalomart Walmart-shaped OTIF, Bullseye
  Target-shaped, Greenfield handshake), one inbound shipment whose
  standard ETA misses the dock cutoff by one day.
- Code links point at `ontagent` only (ratified decision §10.4).

## The two new sections

### History — "the log is the run"

The draft admits: *"World state loads as a snapshot at startup; deriving
it from the event log is designed, not built."* Built. Say it as
capability:

- Operational state is never authored: on-hand enters as an
  `on_hand_counted` event, POs as `po_received`; views are reducers
  over the log; there is no fixture that can disagree with it.
- "As of" is a query, not a fixture swap:
  `uv run python -m scenarios.promo_allocation --as-of 60` prints the
  world mid-story (available 13,000, all POs open);
  `--as-of 117` prints the ending (available 0, all acknowledged).
- The log reproduces its own conclusions: `--verify-replay` re-derives
  every recorded invariant verdict against the log *as it stood at that
  moment* and re-checks every lifecycle transition. The DoD test
  tampers with a recorded verdict and the checker catches it — an
  edited log is caught, not believed.

### The boundary — closing the loop, honestly mocked

The draft admits: *"the system stops at the decision — the agent does
not transact… Agents can only transact if connected, and that
integration work was deliberately out of scope."* No longer out of
scope, and the framing flips from disclaimer to demonstration:

- The ontology declares **parties** (boundary roles) and flows — never
  systems. An integration point is a flow crossing a boundary role,
  bound to an adapter at boot; a real EDI/TMS connector substitutes
  with zero ontology change.
- Real message vocabulary: POs in, allocation notices out, carrier
  quotes and bookings, a pull-forward against the plant's scheduling
  surface — and every outbound transaction's **asynchronous
  confirmation lands back in the event log** (via the signals
  primitive): `booking_confirmed`, `pull_forward_confirmed`,
  `notice_acknowledged` driving the PO lifecycle to `acknowledged`.
- Honesty stays in the text: the connector is a scripted mock,
  labeled as such. The claim is that "connected" has a declared shape,
  not that an ERP was integrated.

## The sharpened beat — derived causality (inside "The deterministic machine")

New since the old build, ratified as ontagent design §10.7: the world
declares *process consequence*, still zero policy:

- `Flow.emits` — committing an allocate flow emits
  `allocation_committed`; declared, never chosen.
- `Invariant.on_failure_emits` — **no one decides there is a
  shortage.** The advisory coverage check fails and that failure *is*
  the shortage: `shortage_declared` is emitted by the machine,
  arithmetic against the log.
- `Invariant.reevaluate_on` — a confirmed lever (booking, pull-forward)
  re-runs the check against its last input; the review re-opens with
  the smaller gap, mechanically.

Why it matters to the thesis: it sharpens the piece's central boundary.
Even the event that summons the judgment is deterministic; the only
thing left to the agent is the judgment itself. The machinery does not
shrink the agency — it corners it, which is the point.

## Rewriting Limits

What honestly remains: one scenario, not many; the stub storyline's
judgments are scripted by construction (live divergence is the step-7
evidence — cite the runs once they exist); boundary connectors are
mocked, not real; constructed world, authored fixtures, real published
rates cited on the values; no deployment, no savings claim, no
benchmark. Drop: the snapshot limit, the stops-at-the-decision limit,
the fixtures-vs-events limit — all built away (that arc itself is a
nice sentence: the rebuild's job was to delete Limits paragraphs).

## Exhibit manifest (regenerate everything from ontagent)

Per the ratified design: exhibits are excerpts, never the whole
codebase. All paths relative to the ontagent repo.

1. **The thesis block** — `ontology/world.yaml`, the
   `demand_within_available_supply` invariant (~12 lines: advisory
   severity, `on_failure_emits: shortage_declared`, `reevaluate_on:
   [booking_confirmed, pull_forward_confirmed]`). Pair with trace
   lines from `traces/stub_promo_allocation.jsonl`: the two
   evaluations — "short 4760 cases → shortage_declared" and, after
   `booking_confirmed`, "short 1760 cases → shortage_declared".
   Declaration on the left, machine obeying it twice on the right.
2. **No policy anywhere** — the playbook `resolve_shortage` block
   (options listed, never ranked) + the meta test
   `test_no_policy_slots_in_meta` (a schema that structurally cannot
   hold a ranking).
3. **Agent identity is rendered** — output of
   `uv run python -m reader supply_planning` (excerpt: orientation +
   the playbook section). Note the holdability number: ~15k chars
   against the old 42k dump.
4. **The judgment on the record** — from the trace: the
   `decision_surfaced` record (option + rationale), the
   `human_responded` approval, then the allocate handoff. The
   protect-and-short rationale text is exhibit-quality (numbers +
   unpriced stakes in one paragraph).
5. **The rejection floor** — a `HANDOFF_BLOCKED` /
   `allocation_within_available_supply` refusal (generate one for the
   exhibit by scripting an over-allocation; the floor is in code, not
   the prompt).
6. **History** — side-by-side `--as-of 60` vs `--as-of 117` output, and
   the tamper test: `test_replay_rederives_every_verdict_and_catches_tampering`.
7. **The boundary loop** — trace excerpt from `book_expedited_freight`
   egress → `booking_confirmed` landing → gap re-derived; and the three
   notices → three `notice_acknowledged` → lifecycles closing.
8. **The world as a graph** — `docs/world-graph.html` screenshots
   (78 nodes, 129 edges; the causality edges are drawn: flow —emits→
   event, invariant —on failure emits→ event, event —re-derives→
   invariant). Rendered, never drawn — say so.
9. **Role N+1 enforcement** — quote the grep test
   (`test_no_llm_and_no_world_names_in_machine`): the no-per-role-code
   claim as an executable assertion.
10. **Live divergence** (pending step 7) — table of ≥3 live runs:
    lever chosen + allocation split per run, against the same declared
    world. The heartbeat exhibit.

## Sources already in the repo

Penalty-rate citations live on the master-data values (`source:` fields
in `ontology/master_data.yaml`); scenario-selection research in
`docs/research-scenario-selection.md`; the 45,000 story's primary
source remains `briefings/phase-6-live-research-report.md` here in the
old repo (cite as history — the disclosure paragraph in the draft
already does this well and should survive nearly verbatim).

---

## Addendum — 2026-08-08: step 7 closed, phase 1 DoD fully met

Everything above stands. This addendum captures what landed after the
memo was written: the live evidence, four new ratified decisions
(ontagent design §10.9–10.12), and lines worth stealing.

### Exhibit 10 exists now — the divergence table (final numbers)

| fixture | pre-lever gap | levers chosen | who bears the short | tokens |
|---|---|---|---|---|
| stub storyline | 4,760 | expedite | Bullseye 1,760 | — |
| baseline | 4,760 | expedite + pull-forward | Megalomart 260 | 531k |
| deep_gap | 9,140 | expedite + pull-forward | Megalomart 4,640 | 502k |
| thin_margin | 380 | one overtime hour, no expedite | nobody | 322k |

The narrative beat: **live judgment inverted the stub's storyline** —
it protected the growth account (Bullseye) and the handshake account
(Greenfield) and shorted the promoter, with the relationship
arithmetic written down in the rationale. At thin_margin it declined a
3,000-case expedite against a 380-case gap and bought one overtime
hour instead. Same declared world every run; only genesis numbers
varied. Traces: `traces/live_baseline.jsonl`, `live_deep_gap.jsonl`,
`live_thin_margin.jsonl` (all replay-clean, six-pattern reviewed).

### "Watching it fail" — the step-7 arc (four fixes, each in its lawful family)

The committed failure captures make this section writable with primary
sources. In order of occurrence:

1. **The runaway** (`live_baseline_run1_pregrounding.jsonl`) — a seat
   with zero reader tools hallucinated 68 tool names and forged
   bare-name events with `{}` payloads that the machine accepted.
   Fix family: grounding (reader tools) + a floor — **an event is a
   typed fact** (§10.9): every emission validates against the event's
   declared payload work unit. Never a prompt nudge.
2. **Promoter-only demand** (`live_baseline_run2_promoter_only_demand.jsonl`)
   — the seat grounded 12,960 instead of 17,760 because field
   semantics lived in the world but the renderer dropped descriptions.
   The proof point: a world-edit alone demonstrably failed (run 3
   repeated the miss); the render fix landed it. **Declared meaning
   must render** (§10.10).
3. **The stalled cascade** (`live_deep_gap_run1_stalled_notices.jsonl`)
   — "fires on event X" rendered as automation, so the seat waited for
   a machine that was waiting for the seat. The declaration already
   existed; the render now distinguishes machine-executed flows from
   seat-due ones: "due when `allocation_committed` lands — this seat
   writes and sends it." **A declared due is not automation** (§10.11).
4. **The double expedite** (observed in baseline + deep_gap, not
   floored at the time) — two seats booked the same shipment onto the
   same expedited service twice. Fix: `booking_changes_service`, a
   blocking invariant that is a *fact about what a booking is* (a
   booking that changes nothing books nothing), never a judgment about
   spend (§10.12).

The meta-lesson for the piece: every failure was fixed by declaring
more world, grounding more reads, or flooring the machine — the
prompts never changed. That is the six-pattern discipline holding
under fire.

### New beat for "the deterministic machine" — emission rights

Ratified §10.12 and built: `Event.emitted_by` — the ontology declares
which seats or boundary parties may emit each event directly; an event
with no `emitted_by` is machine-only, entering the log solely through
declared causality (a flow's emits, an invariant's on_failure_emits, a
playbook's always_fires). The orchestrator refuses an undeclared
emission *before* payload validation, so a well-formed payload from
the wrong seat is named as what it is: `emission_not_declared` — a
forgery. The quotable line (now in the meta itself): **"Who may state
a fact is itself a fact."**

### The floor teaches in one run — candidate exhibit

`traces/live_deep_gap_emission_floors.jsonl` (713,624 tokens), one
trace, three beats:

1. First booking passes — intermodal → team expedite, a real change
   (invariant evaluated, passed, seq 120).
2. Second attempt at the same service is BLOCKED — "booking
   svc_team_expedite changes nothing" (handoff_blocked, seq 144). The
   seat takes the rejection and concludes without forcing anything.
3. Every later expedite request, transportation reads shipment status
   *first*, sees the expedite already in flight, and concludes without
   acting — receipt alone as a valid outcome, learned from the floor
   inside a single run, not from prose.

### Lines from the cold-reader test (outsider legibility, verified)

Phase-1 DoD closed with a fresh session (no priors) following README →
trace. It cited exact records correctly, and it surfaced three framings
the repo's own prose never states — steal them:

- **The human gate sits at the seat that judges the money, not the
  seat that executes it.** (Transportation books the freight with no
  gate; supply_planning's decision to spend was gated.)
- **There is a third flow flavor** beyond machine-executed and
  playbook-chosen: the declared due — the machine cannot author the
  payload, so the event makes the flow *due from its seat*.
- **Scope narrowing is real**: transportation's rendered world
  contains no retailers and no penalty regimes — "it literally cannot
  see whom the shortage hurts."

### Corrections to the manifest above

- Exhibit 8 graph numbers: now **86 nodes, 142 edges** (was 78/129 —
  typed payloads, emission rights, and two reader tools added edges).
- Test count for any prose that cites it: **82 structural tests**, now
  running in CI on every push with the trace-scrub gate (fictional
  retailers structurally checked, credential shapes forbidden).
- Cost honesty if wanted: the whole live campaign was 8 runs,
  ~$6–7 total, gemini-3.5-flash on Vertex.

---

## Addendum 2 — 2026-08-09: phase 2 closed, the front door exists

Phasing step 8 landed (ontagent design §10.13, proposed and ratified
the same session). Everything above still stands; this adds the
inbound edge, which the memo predates. **The re-anchor is now
unblocked on every dependency** — nothing else is pending in the repo.

### Where it goes in the spine — fold, don't add

Recommendation: **do not open a third new section.** The memo's new
"The boundary" section is about the *outbound* edge (the loop closing
through mocked adapters); the front door is the *inbound* edge of the
same idea. Put it there as that section's second half. The unifying
sentence the piece has been missing: *the ontology declares parties
and flows, never systems — and both directions bind to that same
declaration, one to an adapter, one to a protocol.* A separate "MCP"
section would read as tooling news; folded in, it completes an
argument.

### The claim the front door actually earns

Not "it speaks MCP" (everything speaks MCP now). The claim is **the
edge added a caller, not a capability** — and it is proven as an
equality, not asserted:

- An MCP caller is a *declared boundary party* stating typed facts
  through the same `emit_event` seam genesis uses. Flows are not
  exposed: process consequence belongs to the machine, so there is no
  "run this flow" verb to abuse.
- The floors are the machine's own, unchanged and in their ratified
  order: unknown event → **emission_not_declared** → **payload_invalid**
  → blocking invariants on whatever the fact causes. The door adds
  exactly one guard of its own: you may speak *for* a boundary party,
  never *as* an internal seat — because seat identity exists only
  through render-and-invocation.
- A caller learns its own contract the way a seat does: by reading its
  rendered role view, which already lists the events it may emit and
  their payload shapes. **The render path is the only source of
  identity at the boundary too** — that generalization is new here and
  worth a sentence.

### New exhibits (11–13)

11. **The equality** — `tests/test_door_dod.py::
    test_client_genesis_reproduces_the_seeded_run_byte_for_byte`. An
    external client emitting the genesis facts over the protocol
    produces a log **byte-for-byte identical** to the in-process
    seeder's. Quote the assertion; it is the whole architectural claim
    in one line, and it is the reason no live-over-MCP run was needed
    (see the methodological note below).
12. **The floors answering over the wire** — from
    `traces/mcp_stub_demo.jsonl` (121 records, deterministic) or the
    driver's output: a retailer stating the inventory count →
    `emission_not_declared`; a purchase order with no body →
    `payload_invalid` naming each missing field; speaking as an
    internal seat → refused at the door. Three lies, three different
    layers answering, each in the system's own vocabulary.
13. **The boundary party reading its own contract** — the "Events you
    may emit" section of `roleview://retail_customers`, exactly as an
    external client receives it. Pairs with exhibit 3 (rendered
    identity) to show one mechanism serving both an internal seat and
    an outside caller.

The 10-minute path is scripted and reproducible for anyone cloning:
`uv run python -m scenarios.promo_allocation.demo_door`.

### Methodological note worth stealing (for Limits or the close)

No live run behind the door was made, **deliberately**, and the reason
is itself the argument: because the client-driven genesis is provably
byte-identical to the in-process genesis, a live seat behind the door
receives exactly the invocation the committed live traces already
captured — identical render, message, and assembled context. There is
no mechanism by which the transport could influence the judgment, so
the run would have measured sampling noise at ~500k tokens. *The
committed live traces already are the system's behavior behind the
door.* This is a small, honest example of proving something instead of
demonstrating it — and of an equality test retiring an experiment.

### Corrections to the corrections

- **Test count: 96 structural tests** (was 82) — +11 front-door DoD,
  +3 scrub coverage on the new capture. Still CI on every push, still
  no API key needed for any of it.
- Exhibit 8 graph numbers **unchanged at 86 nodes / 142 edges**: phase
  2 touched no ontology. That is itself the point — a whole new
  external interface, zero world change.
- Layout for any prose describing the repo: two edge modules now,
  `live/` (the model edge, the one place an LLM SDK is touched) and
  `door/` (the MCP edge). `machine/` imports neither; grep tests
  enforce both directions.
- Honest limit to keep in Limits: the protocol is real, but the client
  is ours — no third-party system has integrated against it. Same
  posture as the mocked connectors: the shape is declared and
  demonstrated, the integration is not claimed.
