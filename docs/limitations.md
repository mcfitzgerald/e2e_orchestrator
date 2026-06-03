# Limitations & maturity notes

Honest accounting of what is POC-grade **by design** versus what would change for
production. Stated plainly so the architecture conversation (incl. with
stakeholders) pre-empts the skeptical question instead of being caught by it.

The through-line: **the POC proves the coordination architecture** — generic
agents parameterized by the ontology, a deterministic orchestrator that routes
and keeps state without domain semantics, LLM judgment only where it's
irreducible. The items below are deliberately deferred. None of them touch the
agents or the routing when upgraded; they are swaps behind interfaces that
already exist.

---

## 1. The world model is a static snapshot (the consequential one)

**What it is.** `world_state/loader.py` loads `e2e_ontology/world_state.yaml`
once at boot into a `WorldState` that is *read-only after construction*. Every
instance is schema-validated against its ontology class (it's real data shaped by
the real schema, not ad-hoc dicts), and the query surface is generic
(`find(class, **slots)` + thin typed wrappers — no per-domain accessors).

**What it can't do.** It does **not evolve as agents act.** There is no
write-back: when `supply_planning` schedules production on a line, the world
model's `production_schedule` is not updated, so a subsequent capacity check sees
the same frozen baseline — not the consequence of what just happened. Concretely:
**the world model and the event log are disconnected.** The event log records what
agents did; the world fixture the axioms read never sees those events. Queries are
also linear scans (fine for a fixture of a dozen entities; not a database).

**Why this is fine for the POC.** The demo is a *single* conflict
(derived in stub mode, injected for the live LLM path) → resolution →
re-convergence. It never requires action A to change what action B sees within a
run. None of the four thesis claims depend on the world evolving — the
orchestrator is "dumb in the right way" whether the world it validates against is
static or live, and the deterministic floor already works (it catches
hallucinated entities via `unknown_entity` against the static fixture).

**When it becomes critical (the trigger).** The moment a scenario needs **two
interacting decisions on shared state** — resolve conflict 1, which consumes
capacity, which then constrains decision 2 in the same run; or inventory drawing
down across sequential commitments. The current narrative does not; a future
"phase 2" demo might.

**Upgrade path (and the cheap first increment).** Make world state a
**projection of the event log**: scheduling production is an event → the
line-load view recomputes → the next axiom check sees it. The world becomes a
materialized view of what has happened rather than a frozen YAML. The cheapest
first step, when triggered, is narrow: have `query_line_load` fold in
scheduled-production *events* from the current run so a second request sees the
first — no need to build the full event-sourced world model at once.

---

## 2. Runtime/orchestration state is a reference implementation

Distinct from the world model. The event log, materialized views, idempotency
table, signals, and per-quantum FSM lifecycle have the **correct production
shape** — commands→events (CQRS), stable idempotency keys, signal-based waits —
but the **implementations are the thinnest thing that satisfies the
`DurabilityBackend` interface**:

- Event log → append-only JSONL file.
- Views / FSM state → in-memory `dict`.
- Idempotency → in-memory dict/set.
- Signals → `asyncio.Future`.
- MCP front door (Phase 7) run lifecycle → an in-memory `run_id → RunRecord`
  registry, one orchestrator + trace file per ingress, ingress serialized by a
  single lock, and a `idempotency_key → run_id` map for wire-level retry dedup.
  Same shape, same caveat: a production front door reserves the key and runs
  dispatches concurrently, backed by the durable layer rather than a process-
  local dict.

This is not durable across process restarts, not concurrency-safe, and not
multi-process. That's intentional: production swaps this layer for
**Temporal/Restate** behind the same `DurabilityBackend` Protocol, and the
application layer (router, axioms, FSM, orchestrator, the seven tools) does not
move. The "dumb backend" is a reference impl, not a shortcut that leaks.

---

## 3. Replay determinism is scoped (and that's correct)

`runtime/replay.py` defines `structural_signature` — the replay-invariant
projection of a trace (routing + axiom verdicts + FSM, with random ids/usage
stripped). **Deterministic orchestration replay is guaranteed**: same seed + same
agent decisions → identical signatures, courtesy of the commands→events backbone
+ stable idempotency keys.

**LLM-level replay is NOT guaranteed** and is not a goal — Vertex/Gemini via ADK
exposes no seed that makes a tool-using agent bit-reproducible, and Scene 6
*should* vary across runs (that's the agency surviving structure). What stays
invariant even across seeds is the **deterministic frame** (the context-assembly
query set, the axiom floor, the routing) — exactly what the Phase 5/6 DoD rests
on. "Replay" means the orchestration is reproducible, not that the LLM is.

---

## 4. Operational constraints (config, not architecture)

- **Model + endpoint are pinned by availability, not preference.**
  `gemini-3.5-flash` (GA) requires `GOOGLE_CLOUD_LOCATION=global` on the current
  GCP project — it 404s on regional endpoints; `gemini-3-flash-preview` 404s
  everywhere (Pre-GA). Model is config (`E2E_AGENT_MODEL`), not code. See
  `.env.example`.
- **Cost guards are deterministic tripwires, not budgets.**
  `E2E_MAX_LLM_CALLS` / `E2E_MAX_INVOCATIONS` / `E2E_MAX_RUN_TOKENS` halt a run
  that overshoots (billing lags ~a day). Defaults are loose; verified to survive
  a full live run with margin.
- **Cross-repo coupling** is an editable local package today (`e2e-ontology` via
  `[tool.uv.sources]`); pin to a git rev for reproducible/CI builds.

---

## 5. The world fixture + seeded boundaries are shims behind declared edges

`world_state.yaml` (read via reader tools) and the scripted boundary responders
stand in for the enterprise's systems of record and external participants. The
*durable* artifacts are the declared edge contracts — boundary roles (inbound) and
`scont:Tool` reader declarations (outbound). In production these bind to real
integrations (REST / MCP / A2A) behind the *same* typed contracts; the agent and
the routing don't change (*"the agent doesn't know the difference,"*
`agent_system_design.md` §9). Phase 7 realizes the first such edge (inbound, as
MCP). Whether the transport itself becomes declarative (a connector construct in
the ontology) is `agent_system_design.md` §12.8 — deliberately resolved by
experiment, not on paper.

**§12.8 resolved (2026-06-03) — principle settled, construct deferred.** With the
outbound edge now built (Seed A's `query_baseline_demand` reader), three edge cells
agree on *contract-in/wire-out* (typed I/O = world model in the ontology;
endpoint/auth/transport = wire/config). The one thing that wanted declaring —
idempotency/session — turned out to be a *command* property (it did not resurface at
the read-only outbound edge), not a general edge property. **Verdict: do not build a
`scont:Connector`;** if idempotency is ever declared it attaches to the boundary
flow. The only unbuilt cell is outbound-command (A2A), the sole site idempotency
could recur — that is the trigger that would reopen the construct question.

**Now realized (inbound edge).** Phase 7 built the MCP front door
(`src/e2e_orchestrator/mcp/`, entry point `e2e-mcp`): `ingress_quantum(flow,
payload, idempotency_key?)` forwards to `dispatch_boundary_ingress`, and
read-only resources (`trace://`, `narrative://`, `decisions://`, `roleview://`)
project the event log / Ontology Service. The evidence it produced for §12.8 — how
much of the edge the existing contract already covers, what wanted to be
*declared* vs *wired*, and whether the inbound/outbound edges unify — is in
`briefings/phase7-live-report-mcp-front-door.md`.

---

## What is deliberately *not* a limitation

Worth stating so these aren't mistaken for gaps: schema-validated world data, a
generic domain-agnostic query surface, the working grounding floor
(`unknown_entity`), deterministic ontology-lookup routing with no LLM in the
path, and per-invocation token/model stamping for cost visibility. These are
load-bearing and intentional.
