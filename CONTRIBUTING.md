# Contributing to e2e_orchestrator

This repo is the runtime that consumes the ontology developed in
`e2e_ontology`. A handful of design rules govern every contribution; they exist
because retrofitting them later is expensive and most "obvious" extensions
violate them. Read this whole file before opening a PR.

## The world-vs-policy rule (durable)

> **The ontology models the world and the action vocabulary. It never models
> the decision policy.**

The ontology repo's `CONTRIBUTING.md` enforces this on the ontology side. We
enforce the symmetric rule on the orchestrator side: **the orchestrator must
not consume ontology fields that smell like policy.** If a PR introduces code
that reads a hypothetical `prefer:`, `priority_order:`, `fallback_chain:`, or
`if X then Y` field from an ontology body, the PR is wrong — either the field
is illegal upstream, or the reader is.

Authoring test for any new field the orchestrator wants to consume: can the
ontology answer it without referring to a runtime instance, a preference, or a
ranking? If yes, it's world model — fine. If no, it's policy — belongs at
runtime (i.e. derived by the LLM from rendered context, or by the
orchestrator from operator configuration outside the ontology).

## Three borrowed disciplines (from durable execution + event-driven systems)

These are not optional. Every meaningful runtime change keeps them intact.

1. **Idempotency keys on every flow firing.** Every handoff/query/event/FSM
   transition gets a stable idempotency key derived from `(source_role,
   target_role, flow, quantum_id, sequence)` (or the equivalent for
   non-handoff events). Replaying the event log never double-fires downstream
   effects. The durability backend is responsible for honoring the key — see
   `JsonlBackend.append`. A new event kind that lacks an idempotency key needs
   a justification in the PR.

2. **Commands → events (CQRS / event sourcing).** Agents emit *commands*
   (`handoff(...)`, `emit_event(...)`); the orchestrator validates and writes
   *events* (`handoff_executed`, `axiom_evaluated`); downstream effects are
   driven from events, not from the original command. Lets us replay
   scenarios end-to-end from the log. **Never** drive a downstream
   dispatch directly from a tool function — go through the orchestrator.

3. **Signals as the primitive for waits.** When an agent is awaiting a query
   response, multiple parallel responses, or a human decision, model it as a
   signal awaited by the suspended invocation, not as an in-process blocking
   call. The durability layer's `await_signal` / `notify_signal` is the only
   primitive that crosses that boundary; tools must not introduce their own.

## No LLM in the routing path

Routing is deterministic from the ontology. We do **not** use ADK's
`transfer_to_agent` or any LLM-driven dispatch primitive. The flow router
(`application/flow_router.py`) is the single source of truth for "which role
receives this flow." A contributor reaching for `sub_agents` to do routing has
duplicated the source of truth; redirect them to the router.

## No per-role code in the agent template

If adding a second or third role to the system requires editing the agent
template (`application/agent_factory.py`) or any of the seven tools
(`application/tools/agent_toolkit.py`), the abstraction is leaking. Revisit
the template before adding role N. (This is also Phase 3's stop condition in
the ontology repo's `plan_of_attack.md`.)

## What lives where

Quick reference for "in which repo does this go?":

| Concern | Ontology repo | Orchestrator repo |
|---|---|---|
| LinkML schemas, exploder, editor, MCP server | ✅ | — |
| Ontology Service (Pythonic role-scoped view) | ✅ | consumes |
| World state YAML fixture | ✅ (data) | loads it (runtime) |
| Orchestrator (application + durability) | — | ✅ |
| Generic Agent template (ADK `LlmAgent`) | — | ✅ |
| Boundary simulators + stubs | — | ✅ |
| Specialist tools (capacity, OTIF, etc.) | — | ✅ (Phase 5+) |
| Trace + replay UI | — | ✅ (Phase 8) |

**Dependency direction:** the orchestrator depends on the ontology repo.
Never the other way.

## Working with the ontology repo

By default the orchestrator looks for `e2e_ontology` as a sibling directory of
this repo's root (see `src/e2e_orchestrator/_bootstrap.py`). Override via the
`E2E_ONTOLOGY_PATH` env var:

```sh
E2E_ONTOLOGY_PATH=/some/other/checkout uv run pytest
```

When the ontology repo grows a `pyproject.toml`, switch this to a real
dependency entry and delete `_bootstrap.py`.

## How to run things

```sh
uv sync --extra dev           # set up venv
uv run pytest                 # full test suite (includes Phase 2 DoD)
uv run e2e-orchestrator --mode stub             # one round trip, no LLM
uv run e2e-orchestrator --mode stub --print-events
uv run e2e-orchestrator                         # default; uses ADK + Gemini
```

`E2E_AGENT_MODE=stub` and `E2E_AGENT_MODEL=...` are honored by the agent
factory. ADK credentials follow `google-adk`'s usual conventions
(`GOOGLE_API_KEY` or `GOOGLE_GENAI_USE_VERTEXAI=true` + Vertex env).

## Tests

- `tests/test_phase2_dod.py` is the load-bearing assertion of the current
  phase. If it breaks, do not press forward by editing the test — the
  contract between the Ontology Service, the Generic Agent, and the
  Orchestrator is what every subsequent phase builds on (per `plan_of_attack.md`
  Phase 2 stop condition).
- Unit tests cover the durability backend, validator, router, and factory
  surface. Add a test alongside any new application-layer module.

## Style

- Type-annotated. Prefer plain dataclasses + Pydantic for I/O surfaces.
- One short comment per non-obvious block; let names carry meaning. Avoid
  docstrings that restate the signature.
- Logged events have stable JSON shapes — adding a new field is safe; removing
  or renaming is a breaking change to replay readers and the trace UI. Bump
  the schema version on `EventKind` if shapes change.
