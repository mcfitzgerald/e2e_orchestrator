# CLAUDE.md — guidance for coding agents in this repo

This file is auto-loaded into every Claude Code session here. Read it before
touching code.

## What this repo is

The orchestrator + generic agent runtime that consumes the supply chain
ontology from the sibling `e2e_ontology` repo. We are executing **Phase 2** of
that repo's `plan_of_attack.md`: smallest vertical slice that proves a generic
agent + deterministic orchestrator can round-trip one quantum through the
ontology end-to-end.

Authoritative reading order before non-trivial work:

1. This file
2. `CONTRIBUTING.md` (durable design rules + how to run things)
3. `README.md` (Phase 2 DoD + repo layout)
4. From the ontology repo: `agent_system_design.md` §2 (world-vs-policy),
   §4 (orchestrator landscape), §7 (seven-tool kit), §8 (deterministic
   backbone), §9 (state).

## The rules that matter (short form)

- **No policy fields from the ontology.** Routing is deterministic ontology
  lookup; the orchestrator must refuse any ontology field that resembles
  ranking, preference, or fallback ordering. Long form in `CONTRIBUTING.md`.
- **No LLM in the routing path.** No `transfer_to_agent`, no `sub_agents`. The
  flow router is the single source of truth.
- **No per-role code in the agent template or the seven tools.** Generality
  must hold for role N+1 with zero edits here.
- **Three disciplines:** idempotency keys on every flow firing; commands →
  events; signals as the primitive for waits.

## Architecture mental model

Two layers behind a small contract:

- **Application layer** — `application/` — flow router, quantum validator,
  axiom evaluator, FSM tracker, orchestrator, agent factory, the seven tools.
  Domain-aware (consumes ontology semantics); domain-agnostic (no supply
  chain knowledge hard-coded).
- **Durability layer** — `durability/` — JSONL event log, in-memory views,
  asyncio signals, idempotency table. Anything implementing
  `DurabilityBackend` substitutes. Production will swap to Temporal/Restate.

The seven tools are Python closures over `(orchestrator, ToolContext)` built
fresh per agent invocation. ADK auto-generates their schemas from signatures.

## The agent's identity comes from the ontology, every time

When the orchestrator dispatches into a role, it calls
`OntologyService.render_role_view(role).as_agent_prompt()` and binds that as
the LlmAgent's `instruction`. Never hand-author a per-role prompt here — if
you find yourself wanting to, you're working around a missing field upstream
or a missing render path in the Ontology Service.

## Tooling conventions

- `frontend-design` skill for any UI work (Phase 8 trace + decision surface
  view). Plain React/SVG handwriting fails the design bar.
- `context7` for library/API/CLI questions (ADK in particular moves fast —
  training cutoffs lie about it).
- `uv` is the package manager. Don't run `pip` directly.

## Testing discipline

- The Phase 2 DoD is encoded in `tests/test_phase2_dod.py`. If you break it,
  fix the contract, not the test. The DoD test asserts orchestrator surface
  invariants (idempotency keys, axiom event shape, role dispatch ordering) —
  changing these intentionally requires updating downstream consumers (replay,
  trace UI) at the same time.
- Use `--mode stub` for runs that don't need an LLM. Tests do this by
  default via `ScriptedAgentHandler`.

## Stop conditions

Per `plan_of_attack.md` Phase 2:

> If the DoD doesn't hold within two working sessions, the contract between
> the Ontology Service and the Generic Agent is wrong — fix the contract
> before pressing forward.

Symmetric stop conditions on the orchestrator side:

- If adding a second role (Phase 3) requires editing the agent template or
  the seven tools, the abstraction is leaking. Revisit before adding role 4.
- If the axiom evaluator (Phase 4) turns into a small language implementation,
  `expr:` was the wrong abstraction; pivot to `tool_ref`.
- If Scene 5's playbook execution (Phase 5) doesn't produce different
  resolutions across runs with different LLM seeds, the agency has been
  structured away — revisit the playbook against the §2 world-vs-policy rule.

## Watching the agency surface (live runs)

The structural tests verify the orchestrator surface; they cannot tell you
whether the LLM is still reasoning agentically. At each phase's live run,
read the trace's `agent_reasoning` events against the heuristic established
at Phase 3 live verification (2026-05-29):

- **Healthy agency surface** — agents cite system mechanics in their
  reasoning ("the orchestrator will auto-reroute on a blocking axiom",
  "I'll fire X knowing it gets validated against the SupplyRequest
  schema"). They reason about decisions rather than rediscovering their
  identity each invocation.
- **Identity-discovery regression** — reasoning reverts to "As X, what
  should I do?" framing. Something broke the orientation preface or the
  rendered role view. Investigate `e2e_ontology/ontology_service/`
  upstream first.
- **Menu-picking regression** — agent with multiple available actions
  fires one without justification, or fires all flat. Playbook construct
  (Phase 5) needs to scaffold the judgment. Do NOT patch in the
  orchestrator — that would re-introduce per-role code. Send a
  paste-ready briefing to the ontology session.
- **Hallucinated-grounding regression** — agent confidently references
  entities (plants, lines, suppliers, SKUs) that don't exist in the
  loaded world state. Fix is reader tools (Phase 5 §6.2 Tool
  meta-construct) + a wired world-state loader (Phase 4), NOT prompt
  nudges. If a post-Phase-5 live run still shows this, reader-tool
  wiring is broken or the Tool meta-construct isn't surfacing.

The Phase 3 landmark to compare against: `supply_planning` inventing its
own plant/line/window plan, citing the `line_capacity_not_exceeded` axiom
as a constraint. Important nuance: that run hallucinated the plant/line
names — agency was real, grounding was not. Trace at
`runs/phase3-live.jsonl` in this checkout (local-only). The Phase 3
signal is the **precursor** to grounded agency; Phase 4 (world-state
loader + real axiom evaluator) and Phase 5 (reader tools) close the
loop. Lose either signal — the operational stance OR the grounded
reference — and the architecture has regressed in a way the structural
tests will not catch.

## Common pitfalls

- **Don't store quantum IDs inside the quantum.** The orchestrator stamps a
  fresh `quantum_id` on every handoff/query/ingress; IDs are runtime, not
  world-model. Adding an `id` slot to a quantum class would violate §2.
- **Don't add a "decide" tool.** The agent already has `surface_decision`. A
  bespoke tool that branches on role-specific logic would re-introduce
  per-role code.
- **Don't bypass the orchestrator from a tool.** Tools call back into
  `orch.schedule_handoff`, `orch.schedule_query`, or `orch.respond_to_query`.
  Direct downstream dispatch from a tool closure breaks the
  commands-then-events discipline.
