# Phase 7 report — the MCP front door (the first realized edge)

**Type:** orchestrator-repo phase report (2026-06-01). Feeds
`agent_system_design.md` §12.8 (should the ontology expose handshake transport?).
**Status:** front door built + green; structural DoD met in stub mode. The live
`--mode llm` reproduction (same `ingress_quantum` driving real LlmAgents through
the protocol) is **gated on explicit permission** and not yet run.

---

## What shipped

- `src/e2e_orchestrator/mcp/` — `core.py` (`OrchestratorFrontDoor`, transport-
  agnostic) + `server.py` (FastMCP wiring) + the `e2e-mcp` entry point.
- **Write side (commands):** `ingress_quantum(flow, payload, idempotency_key?)`
  → `Orchestrator.dispatch_boundary_ingress` (another caller of the same seam the
  boundary simulators use). Optional `run_demo_scenario(scenario, mode)`
  convenience wrapper over the CLI's `run_scenario`.
- **Read side (resources, read-only, sourced from events):** `trace://<run_id>`,
  `narrative://<run_id>`, `decisions://<run_id>`, `roleview://<role>`.
- `runtime/main.py` refactored: `build_scenario_orchestrator` extracted so the
  front door reuses the *identical* CLI wiring (stub scripts / real LlmAgents +
  cross-domain responders) and only swaps the seeder for the client's ingress.
- Tests: `tests/test_phase7_dod.py` (14) — incl. an end-to-end run through a real
  `ClientSession` over the SDK in-memory transport. Full suite: 86 green.

**DoD status:** #1 server + resources ✓ · #2 MCP client drives the demo
end-to-end through the protocol ✓ (stub; live llm pending permission) · #3
disciplines held + idempotency test ✓ · #4 handlers tested against the real
seams ✓ · #5 `roleview://` byte-faithful ✓ · #6 CLAUDE.md note ✓.

---

## The three observations for §12.8

These are the deliverable that feeds the open question. They come from *building*
the realized edge, not from the live run — building is what made them concrete.

### 1. Contract coverage — how much of `ingress_quantum` was already declared?

**High. The ontology already declares the inbound edge; only the wire was extra.**

Everything `ingress_quantum` needs to route + validate is already in the model
and was consumed without addition:

- **Which roles are inbound edges** — `RoleIdentity.is_boundary`. The front door's
  boundary guard (reject any flow not sourced by a boundary role) is *pure
  ontology read* — no enumeration of roles, no new field. "This flow is an
  inbound edge" was already answerable.
- **The typed payload contract** — the flow's declared quantum class +
  `QuantumValidator`. A malformed ingress is rejected with the system's normal
  `quantum_rejected` event, not a bespoke MCP error. Zero schema added at the
  transport layer.
- **Where it routes** — `flow_router` (source/target role, trigger). Untouched.

What the orchestrator/transport layer had to *add* was small and entirely
non-semantic: a `run_id`, an in-memory `run_id → trace` registry, the resource
URI scheme, and wire-level idempotency dedup. None of it is world model. This is
direct evidence for **contract in, wire out**: the edge *contract* was ~fully
covered by the existing boundary-role + quantum declarations; the *wire* (run
addressing, resource URIs, retry dedup) is the only genuinely new material, and
it is infrastructure, not ontology.

### 2. Did anything transport-shaped want to be *declared* rather than wired?

**One candidate surfaced: idempotency-at-the-wire. The rest stayed wire.**

- **Idempotency** is the interesting one. The orchestrator already has an
  idempotency discipline (`boundary:<flow>:<qid>` keys), but it lives *inside a
  run/backend*. At the MCP boundary each external call mints a fresh
  orchestrator+backend, so the in-run key can't dedup a retried *call* — the dedup
  had to move up to a server-level `idempotency_key → run_id` map. So idempotency
  showed up in **two places**: a wire-level concern (did this client call already
  happen?) and an in-run concern (did this dispatch already fire?). The front door
  bridges them by folding the client key into a stable `quantum_id`. That a single
  concept needed a home at *both* layers is mild evidence that idempotency (and
  session identity) is the kind of thing a future `scont:Connector` construct
  might *declare* once, rather than each transport re-inventing.
- **Endpoint / transport / auth** did **not** want to be declared. They were
  pure config (`--transport`, `E2E_MCP_MODE`, `E2E_MCP_WORLD`) with no pull toward
  the world model — exactly the "infrastructure, neither world nor policy" the
  memo's §2 check predicts. Auth is real but was cleanly deferrable (flagged,
  out of POC scope) without touching any contract.

Net: the evidence leans **contract in, wire out**, with idempotency/session as
the one thing that might justify a thin connector-level declaration rather than
living implicitly at each edge.

### 3. One abstraction for both directions (inbound MCP vs outbound reader tool)?

**They rhyme strongly; a single edge/handshake abstraction looks viable.**

Both edges are: *a name + a typed input contract + a typed output contract,
bound at boot to a transport the agent can't see.* The inbound `ingress_quantum`
is `(flow, payload) → run pointer`; an outbound `scont:Tool` reader is
`(tool, input) → typed output`. The shapes are duals — one carries a quantum
*in*, the other pulls data *out* — and both keep *"the agent doesn't know the
difference"* (the agent reasons over the typed contract; the front door / reader
binds the wire). The divergence is direction + lifecycle: inbound *starts* a run
(commands→events, mints a run_id), outbound is *read-only within* a run. So the
unification is real at the **contract** level (name + typed I/O + symbolic
implementation) and diverges only at the **command-vs-query** level — which the
system already distinguishes everywhere else (handoff vs query flows; tools vs
resources in MCP itself). A future `scont:Connector` that declares "an edge of
kind {inbound|outbound}, typed I/O X, bound to transport Y" would cover both.

---

## Live run (pending permission)

Not yet run — the standing rule is no live LLM run without explicit sign-off.
When approved, the live check is: start `e2e-mcp --mode llm`, have an MCP client
call `ingress_quantum("submit_promo_plan", <TradePromotion>)`, and read
`narrative://<run_id>` — the same generic edge, now driving real LlmAgents end-
to-end through the protocol. Watch the agency surface against the CLAUDE.md
heuristic (operational reasoning + grounded references); the front door changes
*who knocks*, so a regression there would point upstream, not at the MCP layer.
The §12.8 observations above are structural and already gathered; the live run
adds the agency confirmation, not new edge evidence.
