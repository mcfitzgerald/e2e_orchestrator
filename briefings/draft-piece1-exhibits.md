# Piece 1 — exhibits (companion to draft-piece1-technical.md)

Status: first assembly, 2026-07-31. One section per `[EXHIBIT]` slot in the
draft, in slot order. Everything here is pulled from the real repos — file
and line references under each exhibit. Captions bridge repo vocabulary
(quantum, axiom, FSM) to piece vocabulary (work unit, invariant, lifecycle).
Open items are flagged inline and summarized at the bottom.

---

## Exhibit 1 — meta-model snippet: the choice space, never the preference

Slot: "The declared world → A meta-model."

Source: `e2e_ontology/scont_meta.yaml` lines 532–555, verbatim.

```yaml
PlaybookDecision:
  class_uri: scont:PlaybookDecision
  description: >-
    The decision shape of a Playbook: the advisory criteria relevant to the
    choice and the resolution flows available. The agent picks; the playbook
    declares the choice space, never the preference.
  attributes:
    criteria_refs:
      description: >-
        Names of advisory axioms (severity: advisory) the agent should weigh
        as viability inputs. The orchestrator evaluates each against the
        assembled context before surfacing the decision; the agent reads
        typed evaluation results, not just names.
      multivalued: true
      range: string
      required: true
    selects_one_of:
      description: >-
        Resolution flow names. The agent picks exactly one. Order in this
        list does NOT imply priority — the renderer presents the list
        neutralized and the primer reinforces the rule.
      multivalued: true
      range: string
      required: true
```

**Caption (draft):** From the meta-model — the schema of the schema. This is
the shape every playbook decision must fit: advisory criteria the agent
weighs, and a set of resolution options it picks from. There is a slot for
the options and a slot for the considerations; there is no slot for a
ranking, a default, or a tiebreak. The design principle is checkable at
authoring time, not aspirational. (The repo calls invariants "axioms.")

---

## Exhibit 2 — one role, one flow, one playbook

Slot: "The declared world → The ontology instance."

Sources: `e2e_ontology/supply_chain_demo.yaml` — role at 875, flow at 1389,
playbook at 1614. Guidance-prose annotations trimmed with `…` for length;
structure verbatim.

### A role

```yaml
supply_planning:
  instantiates: [scont:Role]
  annotations:
    scont:domain: supply_netops
    scont:role: >-
      {
        "description": "Network-level planning function with cross-plant /
         cross-co-man / cross-DC visibility. Mediates between demand and
         execution: decides where and how to fulfill, assigns production to
         plants, and is the hub for cross-domain conflict resolution.",
        "llm_prompt_hint": "Receives SupplyRequest from demand_planning and
         fans out to procurement (raw materials) and production_planning
         (capacity). When manufacturing escalates a capacity conflict, this
         role assembles cross-domain context … and either resolves
         autonomously or surfaces the decision to a human … Trade-off
         reasoning happens here, not in the orchestrator.",
        "human_involvement": "conditional"
      }
```

### A flow

```yaml
escalate_capacity_conflict:
  instantiates: [scont:InformationFlow]
  annotations:
    scont:domain: manufacturing
    scont:flow: >-
      {
        "source_role":   "production_planning",
        "target_role":   "supply_planning",
        "quantum":       "CapacityConflict",
        "trigger_event": "capacity_conflict_detected"
      }
```

### A playbook

```yaml
resolve_capacity_conflict:
  instantiates: [scont:Playbook]
  annotations:
    scont:domain: supply_netops
    scont:playbook: >-
      {
        "role": "supply_planning",
        "triggered_by": "capacity_conflict_detected",
        "input_quantum": "CapacityConflict",
        "context_assembly": [
          { "flow": "check_otif_exposure",      "required": true, … },
          { "flow": "check_promo_flexibility",  "required": true },
          { "flow": "check_coman_availability", "required": true, … }
        ],
        "synchronization": "wait_all",
        "closed_set": true,
        "decision": {
          "criteria_refs": [
            "viable_promo_renegotiation",
            "viable_coman_shift",
            "tolerable_otif_penalty",
            "viable_partial_fill"
          ],
          "selects_one_of": [
            "request_promo_revision",
            "re_request_production",
            "shift_to_coman",
            "allocate_partial_fill"
          ]
        },
        "always_fires": [
          { "event": "capacity_resolved" },
          { "flow":  "plan_fulfillment" }
        ]
      }
```

**Caption (draft):** A role, a flow, and a playbook from the instance. The
flow declares sender, receiver, and the shape of what travels — the repo
calls the typed work unit a "quantum" (a naming choice I would not repeat).
The playbook declares the evidence worth assembling, the considerations that
apply, and the four resolutions that exist. Note what the decision block
contains — criteria and options — and what it cannot: an ordering. The
playbook's own guidance text ends: *"The listed order of the paths is not a
ranking."*

---

## Exhibit 3 — the rendered role view

Slot: "One authoritative reader."

Source: live output of
`OntologyService.load("supply_chain_demo.yaml").render_role_view("supply_planning").as_agent_prompt()`,
first 46 lines of ~42,000 characters. Regenerate any time — it is a pure
function of the ontology.

```text
You are an LLM-backed agent embedded in an ontology-driven coordination
system. Read this orientation before reading your role view below.

How this system works:

- The ontology models the world and the action vocabulary. Your role view
  (below) is your slice of it. The ontology declares what exists, what
  can happen, and what actions are available. It does NOT declare what
  you should prefer, which order to try things in, or how to break ties —
  those are judgments you make.

- You are ephemeral. You exist only for this one invocation. State lives
  in the event log and materialized views, which the orchestrator owns
  and you do not read. Act on what just arrived; don't try to "remember"
  across invocations.

- Routing is deterministic. When you fire a handoff or query, the target
  role is declared by the flow body — the orchestrator looks it up and
  dispatches. You don't choose who receives your output.

- Validation, axiom evaluation, and FSM guards are deterministic and run
  before your action lands. If a quantum you emit is malformed or blocked
  by an axiom, you'll see a structured rejection — that's the system's
  safety floor, not something to argue with.

[…]

ROLE: supply_planning

domain: supply_netops
is_boundary: false
human_involvement: conditional

Network-level planning function with cross-plant / cross-co-man / cross-DC
visibility. Mediates between demand and execution: decides where and how to
fulfill, assigns production to plants, and is the hub for cross-domain
conflict resolution.
```

**Caption (draft):** The opening of a rendered role view — the entire
identity an agent gets, generated from the ontology at the moment of
dispatch. The full render runs ~42,000 characters: identity, incoming and
outgoing flows with their payload schemas, invariants, playbooks, and reader
tools. No part of it is hand-written per role.

**⚠ Honesty note for the draft:** the piece says "the same role view
rendered twice — agent instruction and onboarding doc." Today
`as_agent_prompt()` and `as_markdown()` return the *same text* (both open
with the agent orientation). The "onboarding document" is a claim about the
content, not a second render path that exists. Either (a) soften the exhibit
to one render and keep the piece's "could serve as" phrasing — which is
already accurate — or (b) add a human-facing render variant upstream first.
Recommend (a); no upstream work needed.

---

## Exhibit 4 — run A vs run B: same conflict, different economics, different resolution

Slot: "Where the agency lives."

Sources: `briefings/phase-6-live-research-report.md` §2–§5 and
`CHANGELOG.md` (2026-05-31 Phase 6 entry) — both written the day of the
runs.

| | Run A | Run B |
|---|---|---|
| Scenario | conflict injected (Scenes 4–6) | full narrative from one promo seed (Scenes 1–6) |
| Model | gemini-3.5-flash | gemini-3.5-flash |
| Agent invocations | 9 | 12 |
| Co-man premium | **$1,275** (1,500 units × $0.85) | **$36,975** (43,500 units × $0.85) |
| Service (OTIF) penalty | $7,200 | $7,200 |
| Schema rejections | 0 | 0 |
| Resolution chosen | **shift to co-manufacturer** | **renegotiate the promotion** |

**Caption (draft):** Two live runs, same conflict shape, opposite calls —
and both defensible given the evidence each faced. The unit rate ($0.85) and
the penalty are authored fixtures; the volumes and totals are the run's own
arithmetic. Run B's larger order is the 45,000-unit request described in
"Watching it fail" — its economics descend from the ungrounded baseline,
which is exactly why grounding was the fix. At the time of these runs the
playbook offered three resolutions; the fourth (partial fill) was authored
in later.

**⚠ Open items:** (1) The raw traces (`phase6-live-capres-A.jsonl`,
`phase6-live-fulldemo.jsonl`) were never committed — `*.jsonl` is
gitignored — and no longer exist on disk. The card above cites the
contemporaneous report; if we want verbatim reasoning quotes for this
exhibit, we need a fresh live run (needs Michael's sign-off + API key) or
we accept the documented numbers. (2) Whether the caption's disclosure
sentence (run B = the 45k run) stays here or moves into the piece's Limits
section is Michael's call — one of the two should carry it.

A verbatim reasoning excerpt DOES exist from a third captured live run (the
demo console, `demo_ui/data.js` — 27 real `agent_reasoning` events,
gemini-3.5-flash), usable if we want the flavor of an agent explaining
itself. Its economics differ (a $0.22/unit premium, $330 total):

> I will now surface this decision to the orchestrator. I have assembled the
> complete context required by the `resolve_capacity_conflict` playbook:
> **Co-man Availability**: Shifting `TP-SEC-6OZ` to the co-manufacturer is
> highly viable (6,000 units available, MOQ of 1,000 units is met, and a
> premium of only $0.22/unit, which is $330 in total). **OTIF Penalty
> Exposure**: If we accept a delay, the OTIF penalty is $7,200 (affecting a
> shipment value of $240,000). **Promo Flexibility**: The Megalomart
> promotion `PROMO-MGM-FLAG-2026Q2` is negotiable (status is `aligned`, can
> shift timing or redu[ce] …

---

## Exhibit 5 — failure → fix table, two families

Slot: "Watching it fail."

Sources: CLAUDE.md six-pattern heuristic; Phase 3 live verification; Phase
1.8; Phase 6 report §5; Seed A briefing.

### Family 1 — output failures: each got a deterministic check

| What the agent produced | Example from the build | What catches it now |
|---|---|---|
| Malformed output | payload missing a required field | schema validation — bounced as a structured rejection |
| Cites an entity that doesn't exist | Phase 3: invented plant and line names in an otherwise sound plan | rejection floor (`unknown_entity`) — checked against loaded world state |
| Cites a playbook that doesn't exist | an agent invoked a playbook name it made up | rejection floor (`unknown_playbook`) — checked against the role's anchored playbooks |
| Violates a declared invariant | a production plan exceeding line capacity | invariant evaluator blocks it; the router fires the declared recovery flow |
| Schema-valid, everything real, still wrong | the 45,000-unit request built on an invented baseline | **nothing can catch it** — fixed by grounding: a reader tool over a real baseline fixture |

### Family 2 — reasoning-shape failures: field notes, fixed upstream

| Observed shape | What it signaled | Fix |
|---|---|---|
| Agent re-derives its identity each invocation ("As X, what should I do?") | orientation/render regression | fix the role-view render, not the agent |
| Multiple options, one fired without justification | playbook wasn't scaffolding the judgment | fix the playbook construct |
| Same context query fired repeatedly | playbook rendering too loose | tighten the render |

**Caption (draft):** Every output failure got the same question — what
deterministic check could have caught this? — and the checks that
accumulated became the validation stack (rows 1–4). The last row is the
class no check can catch, where the only fix is making more of the world
readable. The second family doesn't reduce to checks at all; those are field
notes, and every fix was upstream in how the world renders — never a patch
to the agent.

---

## Exhibit 6 — the three-layer figure (in-body)

Slot: "The system, in three layers" (and the header-adjacent "visual of the
opening paragraph" note in the draft).

Status: **spec only — art not built yet.** Concept #2 from the header-image
session: the two-layer seam, drawn literal. Working spec:

```
┌─────────────────────────────────────────────────────────┐
│  THE DECLARED WORLD                                     │
│  meta-model → ontology instance → world state           │
│  (roles · flows · work units · lifecycles ·             │
│   invariants · playbooks)      (plants · lines · rates) │
└───────────────────────┬─────────────────────────────────┘
                        │  ONE READER: query · render
                        ▼
        ┌── render → bind → act → discard ──┐   ← agents exist
        │        (the agent factory)        │     only here
        └───────────────────┬───────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│  THE DETERMINISTIC MACHINE                              │
│  router · validation stack · lifecycle tracker          │
│  event log (record everything · never fire twice ·      │
│  wait for signals)                                      │
└─────────────────────────────────────────────────────────┘
```

Build as clean SVG once the draft's figure needs settle (candidate: also
derive the header image caption from it). The `frontend-design` skill
applies when this gets built.

---

## Summary of open items

1. **Exhibit 3 honesty note** — "rendered twice" isn't literally true today;
   recommend showing one render (the piece's "could serve as" wording is
   already accurate).
2. **Phase 6 traces are gone** (gitignored, never committed). Decide:
   fresh live run for verbatim A/B quotes (needs sign-off), or ship the
   card on the contemporaneous report. Punch-list "redact+commit trace
   excerpts" now depends on this.
3. **Run B disclosure** — the sentence tying run B to the 45k story lives in
   the Exhibit 4 caption for now; decide whether it also (or instead)
   belongs in the piece's Limits section.
4. **Exhibit 6 art** — spec only; needs an SVG pass.
5. All YAML/render excerpts are trimmed; before publish, re-check trims
   against the repos at whatever commit the Code links point to.
