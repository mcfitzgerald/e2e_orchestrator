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
