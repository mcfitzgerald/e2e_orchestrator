# Briefing for the ontology session — migrate `respect_lead_time` to `tool_ref`

**From:** orchestrator session, Phase 4 (deterministic backbone) — 2026-05-30
**To:** `e2e_ontology` session
**Type:** small upstream contract change (a Phase 1.7-style `tool_ref` migration)

## TL;DR

Add `tool_ref: evaluate_respect_lead_time` to the `respect_lead_time` axiom on
the `submit_procurement_request` flow in `supply_chain_demo.yaml`. The
orchestrator already registers the callable; this one-line ontology edit makes
the axiom deterministically *enforced* instead of *non-enforcing*.

## Why

Phase 4 landed the real axiom evaluator. Dispatch is by what the axiom declares:

1. `tool_ref` → registered deterministic callable `(quantum, world_state)`
2. else `expr` → **slot-level subset only**: `{quantum.<slot>}` resolved against
   the payload; comparisons / boolean / arithmetic. **No function calls, no
   entity traversal** — that is the named Phase 4 stop condition ("if the expr
   interpreter grows function-call support, `expr:` was the wrong abstraction;
   pivot to `tool_ref`").
3. else `nl`-only → advisory pass.

`respect_lead_time` currently declares only:

```
"expr": "{quantum.required_by} >= today() + {quantum.supplier.lead_time_days}"
```

That expression uses **both** a function call (`today()`) and an **entity
traversal** (`{quantum.supplier.lead_time_days}` — resolve the referenced
`Supplier`, then read a slot). Both are deliberately outside the slot subset.
So the evaluator reports it **non-enforcing** with evidence like:

```
expr not machine-evaluable in slot subset (entity traversal
'quantum.supplier.lead_time_days'); candidate for tool_ref
```

In the live Phase 4 run this was observable: the `RequestLifecycle`
`submitted → approved` transition (guard `respect_lead_time`) passed by default
— the guard did not actually enforce lead time, because its `expr` can't be
evaluated in the subset and we will not grow the interpreter to do so.

`today()` is world-state (the injectable clock, §9) and the supplier traversal
is world-state (resolve the `Supplier` instance). Both are exactly what
`tool_ref` exists for — the same reasoning that moved `line_capacity_not_exceeded`
to `tool_ref` in Phase 1.7.

## The change

In `supply_chain_demo.yaml`, the `respect_lead_time` axiom on
`submit_procurement_request` (currently ~line 820):

```yaml
{
  "name": "respect_lead_time",
  "scope": "flow",
  "expr": "{quantum.required_by} >= today() + {quantum.supplier.lead_time_days}",
  "tool_ref": "evaluate_respect_lead_time",          # <-- ADD THIS LINE
  "nl":   "A procurement request's required-by date must not fall inside its supplier's lead time.",
  "severity": "blocking",
  "message":  "Required-by date is inside supplier lead time",
  "references": {"metrics": ["supplier_lead_time"]},
  "on_failure_route_to": "replan_on_infeasible_request"
}
```

Keep `expr` and `nl` as-is (`tool_ref` wins over `expr`; `nl` stays
authoritative for human/LLM reading). No schema change is needed — `tool_ref`
already exists on `AxiomBody` as of Phase 1.7.

## Orchestrator side: already done

- `evaluate_respect_lead_time(quantum, world_state)` is implemented and
  registered in `application/axiom_tools.py` (`DEFAULT_AXIOM_TOOLS`). It reads
  the injectable clock (`world_state.today()`) and resolves the supplier from
  world state; it grounds the supplier (unknown supplier → `unknown_entity`).
- `tests/test_axiom_evaluator.py::test_same_code_path_handles_both_world_state_axioms`
  already proves the evaluator handles `respect_lead_time` and
  `line_capacity_not_exceeded` through the identical tool path (it constructs the
  axiom with `tool_ref` set). Once the ontology declares the `tool_ref`, it
  routes there at runtime — no orchestrator change required.

## Acceptance after the edit

`uv run e2e-orchestrator --scenario demand-anomaly --mode stub` is unaffected.
A procurement path run (or a unit test) should show `respect_lead_time`
evaluated via the tool — `required_by 120 < today(100) + lead_time 28 = 128 for
supplier SUP-MENTHOL-002` — and block with `replan_on_infeasible_request` when
infeasible, instead of the current non-enforcing pass.
