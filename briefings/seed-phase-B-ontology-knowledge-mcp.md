# Phase B seed — 7-O: the ontology knowledge-MCP (read-the-model)

*Paste-ready, self-contained. A single coding session in the **`e2e_ontology`**
repo. Driver: `briefings/roadmap-2026-06-04.md` §2 Phase B. This is the *planned*
Phase 7 that got swapped for the 7-S front door — see
`[[two-phase-7-mcp-surfaces]]`. Read-only, low §2 risk.*

---

## 0. Orientation

**Goal.** Make the CSCO's Q1 answer *interactive*: let a knowledge worker **ask the
model questions about the supply-chain structure** over MCP. The headline DoD: *"if
Megalomart's promo slips a week, who's affected?"* answered by traversing the
ontology — roles, flows, quanta, entities, playbooks. This is the live proof of
"the ontology is the operating logic, and it's legible."

**Two MCP surfaces — do not conflate (this is 7-O, not 7-S):**
- **7-S (built, orchestrator repo):** `ingress_quantum` + read a *run's* event log.
  **Drive-the-system.**
- **7-O (this build, ontology repo):** read/traverse the *ontology structure*.
  **Read-the-model.** Reuses **none** of 7-S's ingress code — it wraps the
  **Ontology Service**, not the orchestrator.

**What it wraps.** The **Ontology Service** only (`render_role_view`, the schema,
the playbooks/flows/quanta/entity graph). **No orchestrator, no event log, no agent
dispatch.** Pure projection of the world model.

**§2 (low risk, but hold it).** The ontology has no policy fields, so traversal
surfaces *structure* — facts, relationships, action vocabulary — never ranking or
preference. If you find yourself wanting to **score/rank** impact results ("most
affected first"), stop: that's policy. Return the **structural set**; let the client
(an LLM) reason over it.

---

## 1. Current MCP / FastMCP API (pinned from context7, 2026-06-04 — cutoffs lie about MCP)

FastMCP v3.x (match the version already pinned by the 7-S server in the orchestrator
repo so both servers agree):

```python
from fastmcp import FastMCP

mcp = FastMCP("ontology-knowledge")

# Tool — schema auto-derived from the signature + docstring. Note: bare @mcp.tool.
@mcp.tool
def impact_analysis(entity_id: str, change: str = "slip_one_week") -> dict:
    """Who/what is affected if `entity_id` undergoes `change`."""
    ...

# Resource — static
@mcp.resource("ontology://source")
def ontology_source() -> str: ...

# Resource template — URI parameters bind to function args
@mcp.resource("roleview://{role}")
def role_view(role: str) -> str: ...

# Query params + wildcards are supported: "data://{id}{?format}", "files://{path*}"
```

Verify the exact decorator form against the installed FastMCP before relying on it;
the 7-S server (`e2e_orchestrator/mcp/server.py`) is your working in-repo reference.

---

## 2. Architecture — mirror the 7-S split

Mirror 7-S's transport-agnostic structure exactly (it's the house pattern):

- **`mcp_server/core.py`** — `OntologyKnowledgeService` (or similar): all logic,
  constructed over the **real Ontology Service**, **unit-tested directly** (no MCP
  transport needed). This is where traverse/impact/read live as plain methods.
- **`mcp_server/server.py`** — thin FastMCP wiring: `@mcp.tool` / `@mcp.resource`
  functions that delegate to the core, plus the entry point (e.g. `e2e-ontology-mcp`).
- **Stdio transport**, `--mode`-free (there's no LLM here — it's a read surface).

Before building, read: the Ontology Service API (how to enumerate + render roles,
flows, quanta, playbooks, entities), `e2e_orchestrator/mcp/{core,server}.py` as the
structural template, and the §12/§7 sections of `agent_system_design.md` /
`plan_of_attack.md`.

---

## 3. Tools (read-the-model)

| Tool | Returns |
|---|---|
| `read_role(role)` | the rendered role view (`render_role_view(role)` — identity, flows it touches, playbooks anchored, tools available) |
| `read_flow(flow)` | flow definition: source/target roles, the quantum it carries |
| `read_quantum(quantum)` | quantum schema: fields, types |
| `read_playbook(playbook)` | playbook structure: context_assembly, criteria, selects_one_of, always_fires |
| `traverse(from_id, relation?)` | structural neighbors in the ontology graph (role→flows→quanta→entities) |
| `impact_analysis(entity_id, change?)` | **the headline** — transitive closure of what's reachable/affected from an entity or event (the roles/flows/quanta/entities downstream) |
| `walk_scenario(scenario)` | read-only narration of a registry scenario's flow sequence — what *would* happen, without running it |

All return structural data (dicts/strings); no scoring, no orchestrator calls.

---

## 4. Resources

| URI | Projection |
|---|---|
| `ontology://source` | the ontology YAML (the model itself) |
| `narrative://demo` | `demo_narrative.md` (the story) |
| `roleview://{role}` | rendered role view (template resource) |
| `docs://{name}` | the grand design docs (`agent_system_design.md`, etc.) if useful |

Resources = the model's source/docs/narrative (the "read the structure" surface),
mirroring how 7-S resources project the event log.

---

## 5. DoD

- **Headline (the demo):** an MCP client asks *"if Megalomart's promo slips a week,
  who's affected?"* and `impact_analysis` (or a traverse chain) returns the affected
  roles/flows/quanta/entities — answered from the **structure**, no run required.
- **Stub/test DoD:** an **in-memory client** test (mirror 7-S's in-memory
  `ClientSession` DoD) exercising each tool + resource against the real Ontology
  Service; ontology suite green.
- **No-key:** there's no LLM in 7-O — it runs without any API key.

---

## 6. Constraints (must hold)

1. **Read-only.** No writes, no orchestrator, no event log, no agent dispatch.
2. **Wraps the Ontology Service, not the orchestrator** — zero reuse of 7-S ingress.
3. **No per-role code.** `read_role`/`traverse`/`impact_analysis` are generic over
   the ontology — no `if role == ...`. (Standing stop condition: per-role branching
   = abstraction leaking → surface to dev-manager.)
4. **§2 structure-not-policy.** Surface relationships/facts/action-vocab; never rank,
   prefer, or score. The ontology has no policy fields — keep it that way at the edge.

---

## 7. What stays OUT

- **No drive-the-system surface** — that's 7-S, already built; don't duplicate
  ingress here.
- **No write/mutation tools** — read-the-model only.
- **No impact *scoring/ranking*** — structural closure only (§2).
- **No new ontology fields** — 7-O is a *reader* over the existing model.

> Single ontology-repo session. User commits; dev-manager stages. After 7-O lands,
> Phase C (the demo UI) can visualize either MCP surface.
