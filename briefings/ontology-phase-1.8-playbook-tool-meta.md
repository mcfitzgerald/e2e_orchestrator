# Phase 1.8 — Playbook + Tool meta-constructs + Scene 5 Playbook

**From:** orchestrator session, 2026-05-30
**To:** `e2e_ontology` session
**Type:** substantive upstream contract change — largest since Phase 1. Two new
meta-constructs, the first authored Playbook, the first authored Tool
instances. Touches `scont_meta.yaml`, `scont_bodies.py` (regen),
`supply_chain_demo.yaml`, `ontology_service/views.py` + snapshots,
`ontology_primer.md`.

## TL;DR

1. Add `scont:Playbook` + `PlaybookBody` to `scont_meta.yaml`.
2. Add `scont:Tool` + `ToolBody` to `scont_meta.yaml`.
3. Author `resolve_capacity_conflict` Playbook in `supply_chain_demo.yaml`,
   anchored to `(supply_planning, capacity_conflict_detected)`.
4. Author four reader-tool instances: `query_plants_for_sku`,
   `query_line_load`, `query_commitments_in_window`, `query_supplier_for_sku`.
5. Extend role-view rendering with "Playbooks anchored to me" + "Tools
   available to me" sections; regen snapshots.
6. Update primer to teach LLMs how to read the new constructs.

This unblocks orchestrator Phase 5 (reader tools + Playbook execution +
Scene 5 — the load-bearing demo moment).

## Why now

Orchestrator Phases 2/3/4 have landed. Phase 3 live verification surfaced
the **hallucinated-grounding** pattern (supply_planning invented
plant/line names). Phase 4's deterministic floor catches it (axiom rejects
with `unknown_entity`) but doesn't *prevent* it. Phase 5 prevents it by
giving agents reader tools to query world state rather than invent it —
which requires the Tool meta-construct upstream.

In parallel, Phase 5's Scene 5 demo moment requires the Playbook
meta-construct to scaffold cross-domain context assembly + decision under
heterogeneous evidence — the §3 case-1 demonstration the architecture's
whole thesis turns on.

## The §2 trap — read this first

Playbook fields are the project's most §2-sensitive authoring decisions.
The Phase 5 stop condition in `plan_of_attack.md` is literally:

> *If Scene 5 doesn't produce different resolutions across runs with
> different LLM seeds, the agency has been structured away — revisit the
> playbook against the §2 design rule.*

The trap: Playbook fields look natural to write as policy.

| Field shape | World or policy? | In or out? |
|---|---|---|
| `context_assembly: [check_otif_exposure, ...]` | World — queries exist + are relevant | **In** |
| `selects_one_of: [shift_to_coman, ...]` | World — paths are available | **In** |
| `synchronization: wait_all` | World — orchestrator's compose semantics | **In** |
| `criteria_refs: [tolerable_otif_penalty, ...]` | World — advisory axioms exist | **In** |
| `always_fires: [...]` | World — structural post-resolution effects | **In** |
| `prefer: shift_to_coman` | Policy — ranking | **Out** |
| `selection_order: [...]` | Policy — ordering | **Out** |
| `fallback_if_unavailable: [...]` | Policy — fallback chain | **Out** |
| `threshold: otif_penalty_usd > 50000` | Policy — preference as number | **Out** |
| `default_resolution: shift_to_coman` | Policy — default choice | **Out** |
| `expected_outcome: ...` | Policy — preferred result | **Out** |

Authoring test for every Playbook field:

> *Can it be answered without referring to a runtime instance, a preference,
> or a ranking?*

If you find yourself wanting to encode "this path is usually right" or
"try X first, fall back to Y" — that's the trap. Reject.

**Critical subtlety for `selects_one_of`:** the YAML list order **does not
imply priority**. A naive reader (human or LLM) reads top-to-bottom as
ranking. The renderer + primer must explicitly say this. Suggested:
present the list alphabetically or otherwise neutralized in the rendered
prompt; primer says "order is arbitrary; the agent picks via judgment."

## PlaybookBody — exact shape

In `scont_meta.yaml`:

```yaml
PlaybookBody:
  class_uri: scont:PlaybookBody
  description: >-
    Shape of the `scont:playbook` annotation on a class instantiating
    `scont:Playbook`. A Playbook is a named multi-flow choreography
    anchored to a (role, trigger_event) pair. It scaffolds *how an agent
    assembles context and identifies the choice space* for a class of
    situation. It declares world content — which queries to run, which
    criteria are relevant, which resolution paths are available — and
    never declares policy (which to prefer, in what order, what defaults).
    See `agent_system_design.md` §6.1 and §2.
  attributes:
    role:
      description: "Role whose agent runs this playbook when the trigger fires."
      required: true
    triggered_by:
      description: "Event class that triggers this playbook at the anchored role."
      required: true
    input_quantum:
      description: "Quantum class that arrives with the trigger event."
      required: true
    context_assembly:
      description: >-
        Ordered list of query-flow steps the playbook fans out to gather
        context before the decision. Each step names a declared `returns:`
        flow that the anchored role can fire. Order in the YAML is
        authoring convenience and does NOT imply priority or sequence —
        the orchestrator composes responses per `synchronization`.
      multivalued: true
      inlined_as_list: true
      range: PlaybookQueryStep
      required: false
    synchronization:
      description: >-
        Wait semantics for context_assembly. wait_all (default) means the
        decision sees every typed response. wait_any is legitimate only
        when responses are interchangeable evidence (rare).
      range: PlaybookSynchronization
      required: false
    decision:
      description: >-
        The decision shape: advisory criteria relevant to the choice, and
        the resolution flows available. The agent picks; the playbook
        declares the choice space.
      range: PlaybookDecision
      required: false
      inlined: true
    always_fires:
      description: >-
        Events and/or flows that fire on every successful playbook
        completion, regardless of resolution path. Structural — these are
        post-resolution effects the system always emits.
      multivalued: true
      inlined_as_list: true
      range: PlaybookAlwaysFires
      required: false
    llm_prompt_hint:
      description: >-
        Narrative supplement, never load-bearing. Must NOT contain
        phrases like 'prefer', 'in order of', 'fallback', 'if X then Y',
        'default to' — those are policy. See `agent_system_design.md` §6.5.
      required: false

PlaybookQueryStep:
  class_uri: scont:PlaybookQueryStep
  attributes:
    flow:
      description: "Query flow name (must have a `returns:` class)."
      required: true
    required:
      description: "Whether this query must complete successfully. Defaults true."
      required: false

PlaybookSynchronization:
  permissible_values:
    wait_all:
      description: "Decision proceeds only when every required query has responded."
    wait_any:
      description: "Decision can proceed on the first response. Rare; needs justification."

PlaybookDecision:
  class_uri: scont:PlaybookDecision
  attributes:
    criteria_refs:
      description: >-
        Names of advisory axioms (severity: advisory) the agent should
        consider as viability inputs. The orchestrator evaluates each
        criterion against the assembled context (quantum + query
        responses) before surfacing the decision; the agent reads typed
        evaluation results, not just criterion names.
      multivalued: true
      required: true
    selects_one_of:
      description: >-
        Resolution flow names. The agent picks exactly one. **Order in
        this list does NOT imply priority** — the renderer presents the
        list neutralized and the primer reinforces the rule.
      multivalued: true
      required: true

PlaybookAlwaysFires:
  class_uri: scont:PlaybookAlwaysFires
  attributes:
    event:
      description: "Event name. Mutually exclusive with `flow`."
      required: false
    flow:
      description: "Flow name. Mutually exclusive with `event`."
      required: false
```

Cross-ref validation in `exploder.py` should:
- Verify `role` resolves to a declared Role.
- Verify `triggered_by` resolves to a declared Event.
- Verify `input_quantum` resolves to a declared class.
- Verify every `context_assembly[].flow` resolves to a flow with
  `returns:` declared (it's a query flow).
- Verify every `decision.criteria_refs[]` resolves to an axiom with
  `severity: advisory`.
- Verify every `decision.selects_one_of[]` resolves to a declared flow.
- Verify every `always_fires[].event` or `.flow` resolves.
- **Enforce single-playbook-per-(role, triggered_by)** at validation —
  a clear error if violated. §12.4's open question gets a defaulted
  answer; revisit when demo content demands.

## ToolBody — exact shape

```yaml
ToolBody:
  class_uri: scont:ToolBody
  description: >-
    Shape of the `scont:tool` annotation on a class instantiating
    `scont:Tool`. A Tool is a declared deterministic service the
    orchestrator can wire and an agent can invoke via `call_tool`.
    Two categories: **reader** (reads world state, no side effects) and
    **compute** (pure function over typed input). See §6.2.
  attributes:
    description:
      required: true
    category:
      range: ToolCategory
      required: true
    input_class:
      description: "Quantum/entity class for the input. Validated by the orchestrator before invocation."
      required: true
    output_class:
      description: "Quantum/entity class for the output. Validated by the orchestrator before returning to the agent."
      required: true
    implementation:
      description: >-
        Symbolic identifier the orchestrator resolves to a Python callable
        at boot. Not a path, not a code reference — a contract name. Same
        shape as `tool_ref` on axioms.
      required: true
    deterministic:
      description: "Always true for now; declared for forward compatibility."
      required: false
    available_to:
      description: >-
        List of role names that may invoke this tool via `call_tool`.
        The role-view renderer filters Tools by membership in this list.
      multivalued: true
      required: true
    llm_prompt_hint:
      required: false

ToolCategory:
  permissible_values:
    reader:
      description: "Reads world state; no side effects. Safe to call freely."
    compute:
      description: "Pure function over typed input; no side effects."
```

Cross-ref validation:
- `input_class` and `output_class` resolve to declared classes.
- Every name in `available_to` resolves to a declared Role.
- `implementation` need not resolve to anything in the ontology — the
  orchestrator binds it at boot, same as axiom `tool_ref`.

Note: Tool meta-construct is **separate** from axiom `tool_ref` registry.
Tools are agent-callable via `call_tool`; axiom evaluators are internal
to the deterministic backbone. Unifying the two registries is deferred
as a §12 open question.

## The Scene 5 Playbook

In `supply_chain_demo.yaml`:

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
            "request_promo_revision",
            "re_request_production",
            "shift_to_coman"
          ]
        },
        "always_fires": [
          { "event": "capacity_resolved" },
          { "flow":  "plan_fulfillment" }
        ]
      }
    scont:llm_prompt_hint: >-
      Cross-domain conflict resolution. The three context-assembly queries
      gather typed evidence from logistics (OTIF exposure), commercial
      (promo flexibility), and external co-manufacturing (availability +
      premium). The decision is yours — weigh the three advisory
      criteria against the assembled responses, pick one resolution. The
      orchestrator surfaces the decision to a human per its
      human_involvement policy on supply_planning.
```

`selects_one_of` is alphabetized in the YAML to make explicit that order
doesn't imply priority. The renderer should preserve this neutralization
when surfacing the list.

### Implied work (probably already mostly there, verify)

- `viable_promo_renegotiation`, `viable_coman_shift`, `tolerable_otif_penalty`
  should already exist as advisory axioms attached to the relevant flows
  (they appear in the demo narrative). If they don't yet exist or aren't
  advisory, author them now — each with an authoritative `nl:` definition
  of what "viable" / "tolerable" means.

## The four reader-tool instances

```yaml
query_plants_for_sku:
  instantiates: [scont:Tool]
  annotations:
    scont:domain: supply_netops
    scont:tool: >-
      {
        "description": "Returns the production lines (plant + line + capacity) that can produce the given SKU, based on world state.",
        "category": "reader",
        "input_class":  "PlantQuery",
        "output_class": "PlantQueryResult",
        "implementation": "query_plants_for_sku",
        "deterministic": true,
        "available_to": ["supply_planning"]
      }

query_line_load:
  instantiates: [scont:Tool]
  annotations:
    scont:domain: supply_netops
    scont:tool: >-
      {
        "description": "Returns scheduled production load on a (plant, line) for a window, from the world-state production schedule.",
        "category": "reader",
        "input_class":  "LineLoadQuery",
        "output_class": "LineLoad",
        "implementation": "query_line_load",
        "deterministic": true,
        "available_to": ["supply_planning", "production_planning"]
      }

query_commitments_in_window:
  instantiates: [scont:Tool]
  annotations:
    scont:domain: logistics
    scont:tool: >-
      {
        "description": "Returns retailer commitments touching a (sku, retailer, window).",
        "category": "reader",
        "input_class":  "CommitmentQuery",
        "output_class": "CommitmentQueryResult",
        "implementation": "query_commitments_in_window",
        "deterministic": true,
        "available_to": ["supply_planning", "logistics_planning"]
      }

query_supplier_for_sku:
  instantiates: [scont:Tool]
  annotations:
    scont:domain: procurement
    scont:tool: >-
      {
        "description": "Returns the supplier (with lead time) that provides raw materials for the given SKU.",
        "category": "reader",
        "input_class":  "SupplierQuery",
        "output_class": "Supplier",
        "implementation": "query_supplier_for_sku",
        "deterministic": true,
        "available_to": ["supply_planning", "procurement"]
      }
```

The input/output classes (`PlantQuery`, `PlantQueryResult`,
`LineLoadQuery`, `CommitmentQuery`, etc.) need to be authored as plain
entity classes in `supply_chain_demo.yaml`. Slot shapes should be
minimal — just the fields the orchestrator's reader implementation needs.
E.g.:

```yaml
PlantQuery:
  attributes:
    sku: { range: SKU, required: true }
PlantQueryResult:
  attributes:
    lines: { range: ProductionLine, multivalued: true }
```

## Renderer updates (`ontology_service/views.py`)

Two new sections in `as_agent_prompt()` and `as_markdown()`:

**Playbooks anchored to me** — for each `scont:Playbook` where
`body.role == self.role`:

```
PLAYBOOKS ANCHORED TO ME

- resolve_capacity_conflict
    triggered_by: capacity_conflict_detected
    input_quantum: CapacityConflict
    context_assembly (parallel, wait_all):
      - check_otif_exposure  (returns OTIFExposure)
      - check_promo_flexibility  (returns PromoFlexibility)
      - check_coman_availability  (returns ComanAvailability)
    advisory criteria (evaluated against assembled context at decision time):
      - viable_promo_renegotiation: <nl>
      - viable_coman_shift: <nl>
      - tolerable_otif_penalty: <nl>
    resolution paths (pick one; order arbitrary):
      - request_promo_revision  (to customer_development)
      - re_request_production  (to production_planning)
      - shift_to_coman  (to co_manufacturing)
    always fires on completion:
      - event: capacity_resolved
      - flow: plan_fulfillment
    hint: <llm_prompt_hint>
```

**Tools available to me** — for each `scont:Tool` where
`self.role in body.available_to`:

```
TOOLS AVAILABLE TO ME

(reader) query_plants_for_sku: <description>
    input:  PlantQuery (sku: SKU)
    output: PlantQueryResult (lines: ProductionLine[])

(reader) query_line_load: ...
```

`render_role_view` returns a `RoleView` with two new tuple fields:
`playbooks_anchored_to: tuple[PlaybookSummary, ...]` and
`tools_available_to: tuple[ToolSummary, ...]`. Phase 1's view already
stubs these as empty tuples (Phase 5 forecast); they become real now.

## Primer additions (`ontology_primer.md`)

A new section after "Axiom body":

```
## Playbook body

A `scont:playbook` body anchors a multi-flow choreography to a (role,
event) pair. It scaffolds *how* an agent assembles context and identifies
the choice space; it never declares which choice to prefer.

- `role`, `triggered_by`, `input_quantum` — structural anchor.
- `context_assembly` — query flows to fan out. Order is not priority.
- `synchronization` — `wait_all` (default) or `wait_any`.
- `decision.criteria_refs` — advisory axioms evaluated against the
  assembled context. The agent reads pass/fail per criterion.
- `decision.selects_one_of` — resolution flows. **Order is arbitrary**;
  the renderer presents them neutralized. The agent picks via judgment.
- `always_fires` — events/flows fired on every successful resolution.

## Tool body

A `scont:tool` body declares a deterministic service the agent can
invoke via `call_tool`. Two categories: **reader** (reads world state)
and **compute** (pure function). `available_to` lists which roles may
invoke the tool; the renderer filters by membership.

## Reading recipes (additions)

- "What playbook fires when X happens at role R?" → find the
  `scont:Playbook` instance with `role == R` and `triggered_by == X`.
  Single-playbook-per-(role, event) is enforced at validation.
- "What tools can role R call?" → filter all `scont:Tool` instances by
  `R in available_to`.
```

## DoD

1. `scont_meta.yaml` validates with strict mode after the additions.
2. `scont_bodies.py` regenerated cleanly via `exploder regen-bodies`.
3. `supply_chain_demo.yaml` parses cleanly; new cross-ref validations
   pass (every Playbook ref resolves, every Tool ref resolves,
   single-playbook-per-anchor enforced).
4. `OntologyService.render_role_view('supply_planning').as_agent_prompt()`
   now includes a PLAYBOOKS ANCHORED TO ME section showing
   `resolve_capacity_conflict` with the structure above, and a TOOLS
   AVAILABLE TO ME section showing the four reader tools.
5. Same call on `production_planning` shows the `query_line_load` tool
   (it's in `available_to`).
6. Snapshot drift in `tests/snapshots/{demand_planning,supply_planning}.{agent_prompt.txt,markdown.md}`
   is intentional and committed.
7. Existing tests still pass; new tests assert Playbook + Tool render
   structure.
8. Primer updated to teach the new constructs.

## What this PR explicitly does NOT contain

- Implementation of any reader tool. The orchestrator binds the
  `implementation` name to a Python callable at boot — that's Phase 5
  work in `e2e_orchestrator`. Naming the implementation logic here
  would couple repos.
- `human_involvement` threshold logic ("escalate if OTIF penalty >
  $50K"). That's policy — orchestrator-side configuration, not world
  model.
- `DecisionSurface` as a typed quantum. §12.3 open question; defer.
  Phase 5 will assemble the decision surface as an emergent dict; we
  promote to a typed class later if it earns its keep.
- Unification of the axiom `tool_ref` registry with the `scont:Tool`
  registry. Add as a §12 open question; revisit when there's reason.
- Multi-playbook composition. Single-playbook-per-(role, event)
  enforced now; §12.4 revisits when demo content demands.

## Phase 5 starts after this lands

The orchestrator session already has its Phase 5 seed prompt drafted.
It gates on Phase 1.8 being complete — specifically checks for the new
sections in `supply_planning.agent_prompt.txt`'s snapshot. Once Phase
1.8 commits upstream, ping the orchestrator side and Phase 5 begins.

Scene 5 is the load-bearing demo moment. Get the Playbook §2-clean here
and the rest follows. Get any field wrong and the whole architecture's
thesis becomes harder to defend.
