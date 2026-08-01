# Briefing for the ontology session — rename `llm_prompt_hint` → `guidance`

From the orchestrator/write-up session, 2026-07-31. Michael's call: he hates
the name. Paste-ready; no semantic change requested.

**Note before starting:** a possible pivot is under discussion (paring the
demo down to a smaller toy ontology). If that lands, fold this rename into
the rebuild instead of patching the current instance — the rename decision
stands either way.

## What it is (so the rename is honest)

`llm_prompt_hint` is the freeform guidance annotation carried on nearly
every construct — roles, flows, events, playbooks, tools. The structured
body declares what is *true* (source, target, payload shape); the hint says
*how to think about using it*. The role-view renderer weaves the hints into
the rendered view. It is not a prompt template and not LLM-specific — the
same text would serve a human reading the role view.

## Why rename

- The name leaks implementation (LLM, prompt) into the world model. The
  ontology is supposed to declare the world, not its consumer.
- It undersells the content: these are guidance/usage notes, load-bearing
  for the §2 split (world + guidance in; the answer out).
- The write-up now says "guidance" in prose ("Guidance is allowed: playbooks
  carry considerations for the agent to weigh"); repo vocabulary should
  match before the repos go public with the piece.

## Proposed name

`guidance` (annotation: `scont:guidance`). Alternatives considered:
`usage_notes`, `agent_guidance` — rejected; the first is bland, the second
re-introduces the consumer.

## Scope (expected)

1. `scont_meta.yaml` — the attribute/annotation declaration(s) and any
   descriptions that reference the old name.
2. `supply_chain_demo.yaml` + `core.yaml` — every `llm_prompt_hint` /
   `scont:llm_prompt_hint` key (both the sibling-annotation form and keys
   inside JSON bodies).
3. `ontology_service/` — renderer/service references (views, orientation).
4. Tests that assert on the key name.
5. Grep for the string across both repos at the end — the orchestrator side
   reads rendered views, not the raw key, but verify nothing binds to it.

## Constraints

- Pure rename: no content edits to any hint text, no render-shape changes.
- §2 untouched — guidance stays advisory; nothing new that ranks or orders.
- Orchestrator tests must stay green with the sibling checkout after the
  rename (`uv run pytest` in both repos).
