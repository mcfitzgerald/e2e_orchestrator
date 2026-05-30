# Phase 1.8 design memo — Playbook + Tool meta-constructs

**Status:** Pre-briefing. This memo explores the design space for the
largest upstream change to date. Once we agree the shape, it gets compressed
into a paste-ready briefing for the ontology session in the same style as
`ontology-respect_lead_time-tool_ref.md`.

**What Phase 1.8 lands (upstream, in `e2e_ontology`):**
1. `scont:Playbook` meta-construct + `PlaybookBody` in `scont_meta.yaml`.
2. `scont:Tool` meta-construct + `ToolBody` in `scont_meta.yaml`.
3. The first authored Playbook: `resolve_capacity_conflict`.
4. The first authored Tool instances (the reader tools Phase 5 needs).
5. Renderer updates so role views include "Playbooks anchored to me" and
   "Tools available to me" sections.
6. Snapshot regeneration; primer updates; tests.

**Why this needs a memo, not just a briefing:** Two new meta-constructs plus
the project's most §2-sensitive authoring decision (Scene 5 Playbook).
Getting any one field wrong reintroduces policy into the world model and
quietly kills the architecture's thesis. The Phase 5 stop condition is
literally *"if Scene 5 doesn't produce different resolutions across runs,
the agency has been structured away — revisit the playbook against the §2
design rule."* The fields decided here are exactly what gets revisited.

---

## 1. The §2 trap, made concrete

`agent_system_design.md §2`:

> *The ontology models the world and the action vocabulary. It never models
> the decision policy. World model: what exists, what can happen, what state
> things can be in, what actions are available, what counts as viable. Policy:
> what to do, in what order, under what conditions, with what preferences,
> with what fallback chain.*

For Playbook fields, the line runs through here:

| Field shape | World or policy? | Verdict |
|---|---|---|
| `context_assembly: [check_otif_exposure, check_promo_flexibility, check_coman_availability]` | World (these queries *exist and are relevant*) | In |
| `selects_one_of: [shift_to_coman, request_promo_revision, re_request_production]` | World (these paths *are available*) | In |
| `synchronization: wait_all` | World (the orchestrator's wait semantics for this Playbook — structural fact about how to compose the queries, not which to prefer) | In, but verify carefully |
| `criteria_refs: [viable_promo_renegotiation, tolerable_otif_penalty, viable_coman_shift]` | World (these advisory axioms exist and are relevant inputs) | In |
| `always_fires: [{event: capacity_resolved}, {flow: plan_fulfillment}]` | World (these always happen on resolution regardless of which path was chosen) | In |
| `prefer: shift_to_coman` | Policy | **Out** |
| `selection_order: [shift_to_coman, re_request_production, ...]` | Policy | **Out** |
| `fallback_if_unavailable: [...]` | Policy | **Out** |
| `threshold: otif_penalty_usd > 50000` | Policy (a threshold *is* a preference encoded as a number) | **Out** |
| `default_resolution: shift_to_coman` | Policy | **Out** |

Authoring test for every Playbook field: *can it be answered without
referring to a runtime instance, a preference, or a ranking?*

The Playbook is a **scaffold of declared world content** (these queries exist,
these criteria exist, these paths are available, this event always fires on
resolution). The LLM does the irreducible judgment of choosing among the
paths. The Playbook never tells it which to choose.

## 2. PlaybookBody shape — proposal

Based on `agent_system_design.md §6.1`'s sketch, with field-by-field §2
review.

```yaml
PlaybookBody:
  attributes:
    role:                  # required; the role the Playbook is anchored to
      required: true
      description: "Role whose agent runs this playbook on the trigger event."

    triggered_by:          # required; event class that fires the playbook
      required: true
      description: "Event that triggers playbook execution at the anchored role."

    input_quantum:         # required; the typed payload the trigger carries
      required: true
      description: "Quantum class that arrives with the trigger event."

    context_assembly:      # optional list of query-flow steps
      required: false
      multivalued: true
      description: >-
        Query flows the playbook calls before deciding. Each step names a
        declared `returns:` flow that the anchored role can fire. The
        agent's job is to invoke each and integrate the responses. The
        playbook does NOT declare which to fire first or which to prefer.
      inlined_as_list: true
      range: PlaybookQueryStep

    synchronization:       # required when context_assembly present
      range: PlaybookSynchronization   # enum: wait_all | wait_any
      required: false
      description: >-
        Wait semantics for the context-assembly queries. World-model fact
        about how the orchestrator composes responses for this playbook,
        not a preference. Default wait_all means downstream decision must
        see every typed response. wait_any only legitimate when responses
        are interchangeable evidence (rare).

    decision:              # required for playbooks that resolve a conflict
      required: false
      range: PlaybookDecision
      description: >-
        Decision shape: which advisory criteria are relevant inputs, which
        resolution flows are available. The agent picks; the playbook
        declares the choice space.

    always_fires:          # optional list of effects that always happen
      required: false
      multivalued: true
      range: PlaybookAlwaysFires
      description: >-
        Events/flows that fire on every successful playbook completion,
        regardless of which resolution path was chosen. Structural — these
        are post-resolution effects the system always emits.
      inlined_as_list: true

    llm_prompt_hint:
      required: false
      description: >-
        Narrative supplement, never load-bearing. Should NOT contain phrases
        like "prefer", "in order of", "fallback", "if X then Y" — those would
        be policy. See `agent_system_design.md` §6.5.
```

Three sub-bodies:

```yaml
PlaybookQueryStep:
  attributes:
    flow:       # required; query flow name (must have a `returns:` class)
      required: true
    required:   # bool, defaults true
      required: false

PlaybookDecision:
  attributes:
    criteria_refs:                # advisory axioms relevant to the decision
      multivalued: true
      required: true
    selects_one_of:               # the resolution flows the agent picks among
      multivalued: true
      required: true

PlaybookAlwaysFires:
  attributes:
    event:                        # event name (mutually exclusive with flow)
      required: false
    flow:                         # flow name (mutually exclusive with event)
      required: false
```

### Open questions inside the Playbook design

**a. `synchronization`: enum vs. always wait_all.** The simplest defensible
position is "all context_assembly queries are wait_all; if you want
different semantics, make two Playbooks." That keeps the meta-construct
small. But §6.1's sketch named the field explicitly, so the design
contemplates non-wait_all cases. **Recommendation: ship the enum with
`wait_all` and `wait_any` permitted values, default `wait_all`.**
Future-proofs without adding complexity now.

**b. Playbook composition (§12.4 open question).** What if two Playbooks
could fire for the same role + event? §12 says "Default: single playbook per
(role, event); revisit if the demo content demands it." Demo doesn't demand
it yet. **Recommendation: enforce single-playbook-per-(role, event) at
validation time, with a clear error if violated.** Keeps the rule visible.

**c. Decision criteria_refs resolution semantics.** When the agent reads
`criteria_refs: [tolerable_otif_penalty]`, what does it actually see? Three
options:
- (i) Just the criterion name (agent reads `nl:` from the role view).
- (ii) The criterion *evaluated* against the current quantum (with the
  query responses incorporated) — the orchestrator runs the advisory axiom
  and presents pass/fail per criterion.
- (iii) The criterion *evaluated* AND its `expr:` / `tool_ref` evidence.

§6.3 says criteria are advisory axioms; the rendered prompt already
includes their `nl:`. Option (i) is the minimum.

For Scene 5 to be demo-defensible, option (ii) is probably right — the
agent should see "OTIF penalty: viable" or "OTIF penalty: $87K, exceeds
tolerable threshold" rather than a free-text criterion description.

**Recommendation: option (ii). The orchestrator evaluates advisory criteria
in the Playbook's `criteria_refs` against the assembled context (quantum +
query responses) before surfacing the decision. The agent reads typed
evaluation results, not just criterion names.** This is §6.3-aligned; the
"named viability inputs" become typed viability *values* at decision time.

**d. The `DecisionSurface` quantum (§12.3).** Probably defer — model it in
the orchestrator as an emergent dict in Phase 5, promote to a typed quantum
only if it earns its keep. The Playbook itself doesn't need to declare a
`decision_surface` field; the orchestrator assembles the surface from
`context_assembly` responses + evaluated `criteria_refs`.

## 3. ToolBody shape — proposal

§6.2 names two categories:

> *Compute tools — pure functions over typed input. Reader tools — read from
> world state.*

```yaml
ToolBody:
  attributes:
    description:
      required: true
    category:                # required enum: compute | reader
      range: ToolCategory
      required: true
    input_class:             # required; quantum/entity class for the input
      required: true
    output_class:            # required; quantum/entity class for the output
      required: true
    implementation:          # required; name the orchestrator binds at boot
      required: true
      description: >-
        Symbolic name the orchestrator resolves to a Python callable at boot.
        Not a path, not a code reference — a contract identifier. Same
        shape as `tool_ref` on axioms.
    deterministic:           # required bool; default true
      required: false
    llm_prompt_hint:
      required: false
```

Then on the role body, an addition: `tools: [<tool_name>, ...]` declaring
which tools the role can call. The renderer reads this and includes a
"Tools available to me" section.

### Open questions inside the Tool design

**a. Where does the role's tool list live?** Two options:
- (i) New `tools:` slot on `RoleBody` (the role declares its own tools).
- (ii) Reverse — Tool instances declare which roles can call them.

Option (i) follows the existing role-centric pattern (role declares its
incoming/outgoing flows already exist implicitly via flow source/target;
events_observed is derived; etc. — wait, that's mostly derived). Hmm.

Actually most role surface fields are *derived*, not declared on RoleBody.
Events come from flows. Lifecycles come from flow lifecycle_refs.

**Recommendation: option (ii) — Tool declares `available_to: [role_name, ...]`
on its body.** Symmetric with how flows declare source/target (the flow
declares which roles touch it, not the role declaring which flows touch
it). Role view rendering derives "Tools available to me" by filtering
all `scont:Tool` instances for `available_to includes my_role`.

**b. Reader vs compute distinction visible in agent prompt?** Likely
yes — the agent should understand that calling a reader tool is reading the
world (no side effects) vs. calling a compute tool is invoking math. The
category enum gets surfaced in the rendered "Tools available to me" block.

**c. What about `evaluate_line_capacity_not_exceeded` and
`evaluate_respect_lead_time` — are those Tools now?** They're already
registered in `application/axiom_tools.py` via the orchestrator's tool_ref
mechanism. Two options:
- (i) They become first-class `scont:Tool` instances, and the axiom's
  `tool_ref:` resolves through the Tool registry.
- (ii) Axiom evaluators stay separate; only reader tools + future
  specialist compute tools (OTIF calc, capacity solver) are `scont:Tool`.

**Recommendation: option (ii) for Phase 1.8.** Keep the scope tight —
`scont:Tool` is for agent-callable tools (`call_tool`), axiom evaluators are
internal to the deterministic backbone. The two registries can unify later
if it earns its keep, but unifying now would force `available_to` on every
axiom evaluator, which feels wrong (axioms aren't called by agents). Note
this as §12-style open: "Consider unifying tool_ref registry and Tool meta-construct
when the runtime has both at scale."

## 4. The Scene 5 Playbook — `resolve_capacity_conflict`

Based on §6.1's sketch + the §2 trap review above:

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
          { "flow": "check_otif_exposure",      "required": true },
          { "flow": "check_promo_flexibility",  "required": true },
          { "flow": "check_coman_availability", "required": true }
        ],
        "synchronization": "wait_all",
        "decision": {
          "criteria_refs": [
            "viable_promo_renegotiation",
            "viable_coman_shift",
            "tolerable_otif_penalty"
          ],
          "selects_one_of": [
            "shift_to_coman",
            "request_promo_revision",
            "re_request_production"
          ]
        },
        "always_fires": [
          { "event": "capacity_resolved" },
          { "flow":  "plan_fulfillment" }
        ]
      }
    scont:llm_prompt_hint: >-
      Cross-domain conflict resolution. The three context-assembly queries
      gather typed evidence from the affected domains (logistics, commercial,
      external co-manufacturing). The decision is yours — weigh the three
      criteria against the assembled responses, pick one resolution. The
      orchestrator surfaces the decision to a human if its human_involvement
      policy says to.
```

### §2 audit of this Playbook, field by field

- `role`, `triggered_by`, `input_quantum`: structural, world. ✓
- `context_assembly`: declares which queries exist + are relevant. World. ✓
- `synchronization: wait_all`: structural fact about how the orchestrator
  composes responses. World. ✓
- `decision.criteria_refs`: names advisory axioms that exist. World. ✓
- `decision.selects_one_of`: declares which resolution flows are
  available — not which to prefer, not in what order. World. ✓ (Critical:
  the list order in the YAML doesn't imply priority. We'll need to make
  this explicit in the renderer + primer.)
- `always_fires`: structural post-resolution effects. World. ✓
- `llm_prompt_hint`: narrative; explicitly says "the decision is yours."
  Should NOT contain "in order of", "prefer", "fallback if".

### Things deliberately absent

- No `default_resolution`, no `prefer`, no `fallback_chain`.
- No `threshold_usd` on OTIF penalty acceptability — the criterion
  `tolerable_otif_penalty` carries an `nl:` definition but the threshold
  itself is policy (operator-configurable, not world).
- No `expected_outcome`. The Playbook scaffolds the decision; the
  outcome emerges from LLM judgment.

## 5. Reader tools to author (Phase 1.8 ships these as Tool instances)

These are what Phase 5 will need wired in the orchestrator. Each is a
declared `scont:Tool` with `category: reader`.

| Name | Input | Output | Purpose |
|---|---|---|---|
| `query_plants_for_sku` | `PlantQuery` (sku) | `list[ProductionLine]` or wrapper | What plants/lines can produce this SKU? |
| `query_line_load` | `LineLoadQuery` (plant, line, window) | `LineLoad` | What's already scheduled on this line in this window? |
| `query_commitments_in_window` | `CommitmentQuery` (sku, retailer, window) | `list[RetailerCommitment]` | What retailer commitments touch this SKU/window? |
| `query_supplier_for_sku` | `SupplierQuery` (sku) | `Supplier` | Which supplier provides materials for this SKU? |

Open: probably need a couple more (a `today()` accessor as a Tool? a
calendar-window helper?). Recommend authoring exactly what reader tools
the Scene 5 path demands and adding others when Phase 5 surfaces the need.

The non-reader compute tools (`calculate_otif_exposure`, `evaluate_coman_premium`)
are deferred — Phase 5 simulates them via scripted query-flow responses
from the boundary roles + logistics_planning. Real implementations are
Phase 6+ specialist tooling.

## 6. Rendered prompt — what changes in role views

After Phase 1.8 lands, every role's `as_agent_prompt()` should include:

```
---
PLAYBOOKS ANCHORED TO ME

- resolve_capacity_conflict
    triggered_by: capacity_conflict_detected
    input_quantum: CapacityConflict
    context_assembly (parallel, wait_all):
      - check_otif_exposure  (returns OTIFExposure)
      - check_promo_flexibility  (returns PromoFlexibility)
      - check_coman_availability  (returns ComanAvailability)
    advisory criteria:
      - viable_promo_renegotiation: <nl>
      - viable_coman_shift: <nl>
      - tolerable_otif_penalty: <nl>
    resolution paths (pick one):
      - shift_to_coman  (to co_manufacturing)
      - request_promo_revision  (to customer_development)
      - re_request_production  (to production_planning)
    always fires on completion:
      - event: capacity_resolved
      - flow: plan_fulfillment

---
TOOLS AVAILABLE TO ME

(reader) query_plants_for_sku: <description>
    input:  PlantQuery
    output: list[ProductionLine]

(reader) query_line_load: ...

(reader) query_commitments_in_window: ...
```

The Tools section uses the per-role filter on `Tool.available_to`. The
Playbooks section uses anchor-based filter.

## 7. Open decisions to confirm before drafting the paste-ready briefing

These are the choices that need user/coordination sign-off before the
briefing goes upstream:

1. **synchronization field**: ship as enum `wait_all | wait_any`, default
   `wait_all`? Or hardcode `wait_all` for Phase 1.8 and add the field
   later? *Recommended: ship the enum.*
2. **criteria_refs resolution semantics**: agent sees just names + nl
   (option i), or evaluated viability values (option ii)? *Recommended:
   option ii. Orchestrator evaluates advisory criteria against assembled
   context before surfacing the decision.*
3. **Tool ↔ Role linkage**: `Tool.available_to` (recommendation) vs
   `Role.tools` slot. *Recommended: Tool.available_to.*
4. **Axiom tool_ref vs scont:Tool unification**: keep separate registries
   for Phase 1.8 and revisit later, or unify now? *Recommended: keep
   separate. Tool meta-construct is for agent-callable; axiom evaluators
   are internal to the deterministic backbone.*
5. **DecisionSurface as typed quantum**: defer to Phase 5 emergent dict,
   promote to typed class only if needed? *Recommended: defer.*
6. **Reader tools scope for Phase 1.8**: just the four named, or add
   more (date/calendar helpers, supplier lookup, etc.)? *Recommended: the
   four named; add others only when Phase 5 surfaces the need.*
7. **Multi-playbook (§12.4)**: enforce single-playbook-per-(role, event)
   at validation? *Recommended: yes, with clear error.*

Once these are settled, the briefing for the ontology session is roughly
60% mechanical — the body shapes go into `scont_meta.yaml`, the Scene 5
Playbook + reader-tool instances into `supply_chain_demo.yaml`, the
renderer adds two sections, snapshots regenerate.

## 8. What the briefing will NOT contain

- Implementation details for the orchestrator-side reader-tool registry
  or `call_tool` dispatch. Those are Phase 5 work in this repo, downstream
  of 1.8. Naming them in the briefing would couple repos.
- Tool implementations themselves. The ontology declares the Tool's
  contract; the orchestrator binds the implementation. Phase 5 work.
- The `human_involvement` threshold for surface_decision (e.g. "escalate
  if OTIF penalty > $50K"). That's policy — orchestrator-side configuration,
  not world model.

## 9. After Phase 1.8 lands

The Phase 5 seed prompt (already drafted in this conversation, will be
re-issued) opens the orchestrator coding session. Phase 5 then implements:
- `application/reader_tools.py` — implementations of the declared Tools
- `call_tool` dispatch wiring (currently a no-op stub)
- Playbook-execution mechanism (the agent reads the Playbook, fires the
  query fan-out, integrates responses, picks a resolution)
- `--scenario capacity-resolution` end-to-end
- Two-run trace diff verifying the Phase 5 DoD

The orchestrator-side Phase 5 work is small in lines of code (the
`call_tool` dispatch + the four reader-tool implementations + a Playbook
execution coordinator). Most of Phase 5 is what the ontology declares, not
what the orchestrator runs.
