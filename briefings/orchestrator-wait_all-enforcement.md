# Work note for the orchestrator session — enforce `wait_all` as a deterministic gate

**From:** dev-manager session — 2026-05-30
**To:** `e2e_orchestrator` coding session (Phase 5 follow-up; do before Phase 6)
**Type:** small orchestrator-side backbone addition (a synchronization gate)
**Decision authority:** the project owner adjudicated this on 2026-05-30 — the
fix lives in the orchestrator, not in ontology rendering. Reasoning below.

## TL;DR

The `resolve_capacity_conflict` Playbook declares three `required: true`
context-assembly query flows with `synchronization: wait_all`. **Nothing in the
backbone enforces that.** A Phase 5 live run fired only 2 of the 3 and proceeded
to `surface_decision` anyway. Add a deterministic gate: `surface_decision` for a
`wait_all` Playbook is rejected until every `required` context-assembly flow has
a recorded response for the active decision; the rejection names the missing
flow(s); the agent re-fires and proceeds. Generic over `PlaybookBody`, §2-safe,
signal-based.

## Why this is an orchestrator fix, not an ontology rendering nudge

The Phase 5 coding session filed the 2-of-3 short-circuit as the menu-picking
pattern → "strengthen Playbook rendering upstream." That reflex (don't add
orchestrator code, brief the ontology session) is the right default for this
project — but it misfires here. Three reasons:

1. **`wait_all` is currently a declared-but-unconsumed contract field.** It
   appears only as a comment in the scripted stub path
   (`runtime/main.py:180` — *"wait_all is a join — sequential await suffices"*).
   No code in `application/` reads `synchronization` or the per-flow `required`
   flags. The rulebook says "all three required"; the runtime never checks. That
   is the same smell §2 warns about, pointed the other way — a contract the
   system ignores.

2. **Enforcing it is the backbone's job, not policy.** "Gather all declared
   required evidence before the decision is allowed to surface" is a structural
   precondition, exactly like the axiom floor ("a quantum must pass its blocking
   axioms before handoff"). It gates on **evidence completeness**, never on
   **which resolution** — so it does not rank, prefer, or order the
   `selects_one_of` paths. The agent's judgment is untouched; only its homework
   is enforced. This is the "dumb-in-the-right-way" orchestrator doing what it's
   for: validate, route, persist, evaluate axioms, **synchronize waits**.

3. **It's the native home for borrowed discipline #3** ("signals as the
   primitive for waits"). `wait_all` is a signal-join; the durability layer
   already exposes `await_signal` / `notify_signal`. Leaving the join to LLM
   discretion means the menu-picking stop condition keeps firing intermittently
   no matter how emphatic the rendering gets — "usually complies" is not
   "always."

**§2 self-check (must hold after implementation):** the gate reads
`context_assembly[].required` and `synchronization`. It must NOT read
`selects_one_of`, `criteria_refs`, or anything about *which* path the agent
leans toward. If your implementation branches on resolution-flow names or
ordering, you've leaked policy into the backbone — stop and rethink.

## The change

Add a generic synchronization gate in the application layer, keyed off the
active Playbook:

- **Gate point:** `surface_decision` (the "I'm about to decide" moment; its
  docstring already references `context_assembly`). The resolution handoff
  (`selects_one_of` flow firing) is a reasonable secondary backstop if you want
  defense in depth, but the primary gate is `surface_decision`.
- **Check:** resolve the Playbook named in the `surface_decision` call (already
  validated to exist by the Phase 5 playbook-ref floor). If its
  `synchronization == "wait_all"`, collect its `context_assembly` entries with
  `required: true`. For each, verify a query **response** has been recorded for
  the active decision context (correlate by the mechanism you built for the
  Phase 4/5 query fan-out — quantum/invocation/role context, whatever you
  already key responses on).
- **Reject if incomplete:** deterministic rejection in the same family as
  `quantum_rejected` / `unknown_entity` — evidence names the missing flow(s),
  e.g. `wait_all_unsatisfied: no response for check_coman_availability`. Emit it
  as an event so it's visible in the trace (the gap should be *visible*, like
  the Phase 4 `unknown_entity` gate, not silently swallowed).
- **Recovery:** the agent re-fires the missing `query(...)` then re-calls
  `surface_decision` → passes. Same retry shape as a rejected quantum. No LLM in
  the gate logic.
- **Scope guard:** the gate is inert when there's no Playbook, when
  `synchronization` is absent/not `wait_all`, or when no flows are `required`.
  Generic over `PlaybookBody` — no `resolve_capacity_conflict`, no role names,
  no flow names hard-coded.

## Tests

- Extend `tests/test_playbook_execution.py`: a scripted run that fires 2 of 3
  required queries then calls `surface_decision` → expect the
  `wait_all_unsatisfied` rejection naming the missing flow; fire the third →
  `surface_decision` passes. Assert the rejection is emitted as a trace event.
- A negative test: a `surface_decision` with no Playbook, or a Playbook without
  `wait_all`, is unaffected (no gate).
- `tests/test_phase5_dod.py` must still pass unchanged — the gate only *enforces*
  the "same query set" half of the DoD that the DoD test already asserts; it must
  not touch the "swappable resolution" half.

## Acceptance

- All tests green (was 62; +2–3 here).
- Re-run `--scenario capacity-resolution` live: a run that would have
  short-circuited now hits the gate, the rejection appears in the trace naming
  the missing flow, and the agent recovers by firing it. The 2-of-3 behavior is
  now structurally impossible, not just discouraged.
- `--scenario promo`, `--scenario capacity-conflict`, `--scenario demand-anomaly`
  regress cleanly.
- Confirm the agency surface stays healthy (CLAUDE.md heuristic): the gate must
  read as "the system made me finish my homework," not as the orchestrator
  making the decision. The resolution choice must remain visibly the agent's.

## Out of scope (don't bundle)

- Strengthening the Playbook *rendering* upstream is a separate, optional
  belt-and-suspenders the owner did NOT request. Don't open an ontology briefing
  for it as part of this work item.
- The `JsonlBackend` append-vs-truncate behavior (re-running a live scenario
  into an existing log path appends rather than truncates) is a known footgun,
  tracked separately. Use fresh log paths for the gate's live verification; do
  not fix the backend here.
