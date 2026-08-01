# Design doc — the canonical rebuild

Status: draft 1, 2026-08-01. For discussion with Michael before any code.
Home: starts here in `briefings/`; moves to the new repo's root when that
repo exists.

## 1. Purpose

One repo, the canonical reference for the whole approach: a declared world
in a formal ontology, one authoritative reader, a deterministic machine, and
ephemeral agents rendered from the world at dispatch. The current two repos
(`e2e_ontology`, `e2e_orchestrator`) proved the architecture; they carry
build history, phase scar tissue, and a 1,881-line instance nobody can hold
in their head. The rebuild is a fresh construction that borrows everything
proven and re-designs what the first pass got awkward.

**North star (Michael's framing):** the minimum viable example that

1. makes the structure and function clear enough to serve as a
   *generalizable template* — a reader should finish it knowing how to
   author their own domain, and
2. lets someone who clones the repo actually *navigate it and follow the
   logic*.

Function comes first. Smallness is design pressure, not a hard constraint:
every element must earn its place, and any artifact too large to hold in
the head (the 42,000-character role render) is a smell to be designed away,
not a rule violation. Piece 1 (the technical write-up) will be re-anchored
to this repo; its exhibits are excerpts, not the whole codebase.

## 2. The scenario — promo-caused allocation under shortage

One narrative, S&OE altitude ("this is Tuesday"), chosen 2026-08-01 after
web research (report in session task output; sources to be carried into the
repo's scenario doc).

**Cause (borrowed from the incumbent demo):** a trade promotion is aligned;
demand planning grounds the promo volume by *reading* the baseline run rate
and applying the promo's uplift factor. The grounded request exceeds what
the week can supply.

**The decision:** the week is short against competing retailer POs. Whom to
short, and whether to buy your way out. Levers (listed, never ranked):

- **Fair-share cut** across all accounts.
- **Protect** the penalty-regime retailer, short the others.
- **Expedite** inbound supply at premium freight to close part of the gap.
- **Pull forward** production against line capacity.

**Why this scenario is the thesis:** the customer ranking is exactly the
policy the no-policy rule forbids the ontology to hold. The world carries
the facts — penalty rates, freight quotes, margins, relationship notes as
guidance — and the ranking is exercised live by judgment (agent, gated by a
human). The penalty arithmetic never closes the decision: scorecard and
relationship damage have no rate card. That un-formulizable residual is
what keeps it judgment.

**Cast (4 roles + boundary):**

| Role | Owns |
|---|---|
| `demand_planning` | promo intake, grounded volume, forecast revision |
| `supply_planning` | the hub: supply picture, the allocation decision |
| `customer_logistics` | per-retailer penalty regimes, MABD windows, relationship facts |
| `transportation` | freight options, expedite quotes, transit times |
| (boundary) `retail_customers` | POs in, allocations/notifications out |

Optional 5th role (`plant_scheduler`) only if the pull-forward lever needs
an owner; drop if the scenario reads clean without it.

**World (order of magnitude, to be tuned):** one SKU, one plant/line, one
inbound in-transit shipment, three fictional retailers with *distinct,
realistic* penalty regimes — one shaped like Walmart OTIF (3% of COGS on
shorted cases, MABD window), one shaped like Target (fill-rate threshold +
late penalty), one small regional with no formal penalty but a relationship
note. Freight lane with standard vs expedited cost/transit. Fictional names
(Megalomart / Bullseye / Greenfield convention), published-regime numbers —
the piece gets to say "the penalty structure is the real one."

**Hard constraints (deterministic blocks):** cannot allocate cases that
don't exist (available = on-hand + arrivals inside window); a freight mode
whose transit time cannot make the MABD is infeasible, not expensive; line
capacity bounds pull-forward.

**Acceptance test for the scenario (the A3 lesson):** across live runs with
varied seeds/fixtures, resolutions must materially diverge — different
levers chosen *and* different allocation splits within the allocate lever.
If every run converges, the world is too determinate: open a second viable
lever before shrinking anything else.

## 3. The ontology — formal core, LinkML-native

**Formal elements are first-class.** The meta-model declares the classic
ontology triad explicitly — **Entity** (kinds of things: SKU, Plant, Line,
Retailer, PO, Shipment), **Relationship** (typed edges: Line *produces*
SKU, Retailer *committed-to* PO, Shipment *supplies* SKU), **Attribute**
(typed properties with units) — and then the operational constructs on top
of them: role, flow, work unit, lifecycle, invariant, playbook, guidance,
tool. Everything the piece calls "the operating model" is declared over the
entity/relationship substrate, not beside it.

**LinkML is the authoring language, and this time natively.** The current
instance smuggles construct bodies as JSON strings inside YAML annotations
(`scont:role: >- {json...}`) — validation half-lives in Python, and the
graph cast is theoretical. The rebuild defines proper LinkML classes and
slots for every construct so that:

- instances are typed LinkML data validated by the schema, no JSON-in-string
  bodies;
- the instance graph is *formally castable* to RDF/property-graph if we ever
  want it — this is load-bearing for the Whither lineage and must actually
  work (an acceptance test, not a slide claim);
- humans read it, machines validate it, git diffs it.

**Vocabulary ledger (proposed — to ratify before authoring):**

| old (repos) | new (canonical) | note |
|---|---|---|
| quantum | **work unit** | typed message that travels a flow |
| axiom | **invariant** | blocking or advisory |
| FSM / state machine | **lifecycle** | states + legal transitions |
| llm_prompt_hint | **guidance** | freeform how-to-think notes, rendered into views |
| role, flow, playbook | keep | already right |
| world state | **world state** = master data (declared) + **operational state** (derived; see §5) | |
| orchestrator | keep (candidates: machine, runtime) | decide at repo naming |

## 4. Borrowed wholesale (the proven list)

From the two repos, carried over as design (re-implemented cleanly, not
copy-pasted):

- Three-layer architecture: declared world / one authoritative reader /
  deterministic machine.
- The render path as the *only* source of agent identity; render → bind →
  act → discard (agent factory); no per-role code, no registry.
- Every declaration gets exactly one deterministic runtime counterpart:
  flows → router, schemas/references/invariants → validation stack,
  lifecycles → tracker.
- Commands → events; append-only log as source of truth; idempotency keys;
  signals for waits; `DurabilityBackend` seam (JSONL now, durable engine
  later).
- Rejection floors (`unknown_entity`, `unknown_playbook`) + grounding via
  reader tools (the Seed A lesson); the six-pattern agency heuristic as the
  live-run review discipline.
- Closed generic toolkit (read / act / decide); `surface_decision` + the
  role's `human_involvement` gate.
- Playbook shape: context assembly (wait-all), advisory criteria, options
  listed never ranked, always-fires effects.
- Scenario registry + `--mode stub` / `ScriptedAgentHandler` testing
  discipline; DoD-style structural tests; trace narrator + replay checker.
- Boundary ingress seam; MCP front door design (**phase 2** of the rebuild,
  not day one — it's proven and documented, port it once the core runs).

## 5. New build: world-state history

The piece's Limits admits it: world state loads as a snapshot and never
moves. The rebuild completes the architecture's own logic:

- **Master data** (declared): entities, relationships, rates, penalty
  regimes — authored in the world file, changes by pull request.
- **Operational state** (derived): on-hand, committed load, open POs,
  in-transit positions — a materialized view over the event log, never
  authored. A line's committed load *is* the sum of what the log says
  happened.
- Reader tools read the view as-of-now; replay rebuilds it; "world as of
  day 140" is a query, not a fixture swap. Scenario setup seeds the log
  (genesis events), not a parallel state file.

This kills the current awkwardness where fixtures and events can disagree,
and it makes the event log the single source of truth in fact, not just in
principle.

## 6. Repo layout (proposal)

```
<repo>/
  README.md            the front door: what this is, the 10-minute path
  ontology/
    meta.yaml          the meta-model (schema of the schema)
    world.yaml         the instance: entities, relationships, roles, flows,
                       work units, lifecycles, invariants, playbooks, guidance
    master_data.yaml   plants, lines, SKUs, retailers, penalty regimes, lanes
  reader/              the one authoritative reader: query + render
  machine/             router, validation stack, lifecycle tracker,
                       agent factory, toolkit, durability seam
  scenarios/           genesis-event seeds + scripted (stub) agent scripts
  traces/              committed captures (never gitignored — learned that)
  tests/               structural DoD + divergence + graph-cast tests
  docs/                design docs, the piece's exhibits manifest
```

Naming the repo: decide with Michael (candidates to brainstorm; not
blocking the doc).

**Navigability is a first-class requirement (north star #2):** the README
walks the reader in narrative order — world → reader → machine → a trace —
and each directory README says what lives there and what may never live
there (the constraints: no policy fields, no LLM in routing, no per-role
code). The current CLAUDE.md discipline rules carry over as the new repo's
CONTRIBUTING.

## 7. Definition of done (rebuild phase 1)

1. **Runs**: fresh clone → one command → full stub scenario end-to-end;
   live mode with `.env` per `.env.example`.
2. **Divergence**: ≥3 live runs across varied fixtures produce materially
   different allocation outcomes (lever and/or split). The judgment is
   demonstrably alive.
3. **Grounding**: every quantity in agent output traces to a read (tool
   call or work-unit field) — checked against the trace, six-pattern review
   clean.
4. **Generality**: adding role N+1 (e.g., the optional `plant_scheduler`)
   touches only the ontology and world files — zero edits to
   reader/machine. The T4 test, carried over.
5. **Graph cast**: the instance exports to a real graph (RDF or property
   graph) via LinkML tooling, with a test that walks one relationship.
6. **History**: operational state is event-derived; replay reproduces it;
   one as-of query works.
7. **Navigable**: a cold reader (test: a Claude session with no priors on
   the old repos) can follow README → trace and correctly explain the
   architecture back.
8. Traces committed; scrub check (fictional names, no credentials) in CI or
   a pre-commit check.

## 8. Phasing

1. Ratify this doc (scenario, vocabulary, layout, DoD).
2. Meta-model + vocabulary final → `ontology/meta.yaml`.
3. Instance + master data (the scenario's world).
4. Reader (query + render — design the render for holdability this time:
   the hub role's view should be *structured for reading*, not a 42k dump).
5. Machine port (router, validators, tracker, factory, toolkit, durability)
   + stub scenario green.
6. World-state history (event-derived views) + replay.
7. Live runs → divergence test → six-pattern review → commit traces.
8. MCP front door + demo surface (phase 2).
9. Re-anchor Piece 1: regenerate exhibits from the new repo, update draft,
   publish.

## 9. Decisions (ratified by Michael, 2026-08-01)

1. **Repo name: `ontagent`.**
2. **Fictional retailer names, real published rates** (Megalomart carries a
   Walmart-shaped 3%-of-COGS OTIF regime, etc.).
3. **One SKU.** The judgment lives across retailers, not across SKUs; one
   SKU against three POs with asymmetric penalty regimes carries the full
   decision space. Design note: the pull-forward lever needs an authored
   constraint on the earlier window (scheduled line hours or upstream
   material) since no second SKU occupies the line. The second SKU is the
   pre-planned relief valve if the divergence test fails — not a day-one
   element.
4. **Old repos are reference-only during the build.** `ontagent` is fresh
   and self-contained: no links to, and no dependency on, `e2e_ontology` /
   `e2e_orchestrator`. The piece's Code links will point at `ontagent`
   only.
5. **"Orchestrator" stays.** The word is contested territory worth
   holding: in current discourse "agent orchestration" implies an LLM
   supervisor; our claim is the opposite, and "the orchestrator contains
   no model calls" is the sharpest sentence in the architecture.

## 10. Build rules for ontagent's CLAUDE.md (Michael's standing notes)

- **Always use context7 for library/API docs** — verify current LinkML
  practice before authoring the meta-model (the spec may have moved in ways
  that help the graph cast), verify Google ADK usage before the agent
  layer, and so on for every dependency. Training-data knowledge of fast-
  moving libraries is presumed stale.
- Old repos may be *read* for reference during the build; nothing is
  imported from them and no code is copy-pasted without re-justification
  against this design.
- The constraint set carries over as law: no policy fields in the ontology,
  no LLM in the routing path, no per-role code in the agent template or
  toolkit, commands → events, idempotency keys everywhere, signals for
  waits.
- Traces are never gitignored (`traces/` is tracked); scrub check before
  every capture commit.
