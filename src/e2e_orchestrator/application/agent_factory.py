"""Agent factory — builds a `RoleHandler` for a given role.

Three concrete handler shapes:

  - `LlmAgentHandler` (default): wraps an ADK `LlmAgent`. The system prompt is
    rendered from the Ontology Service. The seven tools are bound as Python
    closures (per-invocation, via `make_toolkit`). Used when a real LLM is
    available.

  - `BoundaryStubHandler`: scripted responder for boundary roles
    (`is_boundary: true`). Boundary roles don't reason — they emit canned
    responses for query flows or are dispatched-to-but-do-nothing for handoff
    flows. Phase 2 needs `demand_sensing` as an ingress simulator (handled
    separately at the runtime entry) and `supply_planning` as a no-LLM stub
    that just acknowledges the handoff.

  - `ScriptedAgentHandler`: a test double — replays a pre-declared sequence
    of tool calls. Lets `test_phase2_dod.py` exercise the full orchestrator
    surface without needing an API key.

The factory dispatches based on the role's `is_boundary` flag and an env-var
mode. Default mode is "llm" for real roles; "stub" forces stub agents for
every non-boundary role (useful for CI). Tests pass `handler_overrides` to
inject `ScriptedAgentHandler` per role.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ontology_service import OntologyService

from ..durability.interface import EventKind
from .orchestrator import Orchestrator, RoleHandler, ToolContext
from .tools import make_toolkit


# ---------------------------------------------------------------------------
# Stub handlers (no LLM)
# ---------------------------------------------------------------------------


class BoundaryStubHandler:
    """Default for non-ingress boundary roles. Acknowledges incoming handoffs
    without further action; responds to query flows with an empty response (a
    real boundary simulator would script per-flow responses — Phase 3 work)."""

    def __init__(self, role: str, orch: Orchestrator):
        self.role = role
        self._orch = orch

    async def invoke(self, ctx: ToolContext, message: str) -> dict[str, Any]:
        signal = getattr(ctx, "response_signal", None)
        if signal is not None:
            # Query flow — respond with empty payload so the source agent
            # doesn't hang. Phase 3 will replace this with scripted responses.
            self._orch.respond_to_query(
                signal_name=signal,
                response={"_stub": True, "role": self.role, "phase": "phase_2_default_stub"},
                response_class=getattr(ctx, "expected_response_class", None),
            )
            return {"kind": "boundary_query_stub_response"}
        return {"kind": "boundary_handoff_ack", "role": self.role}


class InternalStubHandler:
    """Phase-2 stand-in for an internal role whose real agent has not been
    built yet (e.g. `supply_planning` until Phase 3). Just acknowledges + emits
    a trace entry. Distinct class from `BoundaryStubHandler` so the trace
    distinguishes 'external boundary' from 'not-yet-implemented role'."""

    def __init__(self, role: str, orch: Orchestrator):
        self.role = role
        self._orch = orch

    async def invoke(self, ctx: ToolContext, message: str) -> dict[str, Any]:
        signal = getattr(ctx, "response_signal", None)
        if signal is not None:
            self._orch.respond_to_query(
                signal_name=signal,
                response={"_stub": True, "role": self.role, "phase": "phase_2_internal_stub"},
                response_class=getattr(ctx, "expected_response_class", None),
            )
            return {"kind": "internal_query_stub_response", "role": self.role}
        return {"kind": "internal_handoff_ack", "role": self.role}


# ---------------------------------------------------------------------------
# Scripted agent (test double)
# ---------------------------------------------------------------------------


@dataclass
class ScriptedToolCall:
    """One pre-declared tool call. `tool` is the toolkit attr name
    ("handoff", "emit_event", ...); `kwargs` are passed verbatim."""
    tool: str
    kwargs: dict[str, Any]


class ScriptedAgentHandler:
    """Test handler: replays a pre-declared sequence of tool calls. The
    orchestrator cannot tell the difference between this and a real LlmAgent —
    same surface.

    `script` is either a flat list (replayed for every invocation, regardless of
    which flow triggered it) or a dict mapping incoming-flow name → list (so a
    role that receives more than one flow — e.g. `supply_planning` handling both
    `submit_supply_request` and a `escalate_capacity_conflict` recovery — acts
    appropriately for each). A `"*"` key in the dict is the default for any flow
    not otherwise listed. This is test scaffolding only; the generic agent
    template (`LlmAgentHandler`) and the seven tools are untouched."""

    def __init__(
        self,
        role: str,
        orch: Orchestrator,
        script: list[ScriptedToolCall] | dict[str, list[ScriptedToolCall]],
    ):
        self.role = role
        self._orch = orch
        self._script = script

    def _script_for(self, incoming_flow: str | None) -> list[ScriptedToolCall]:
        if isinstance(self._script, dict):
            if incoming_flow is not None and incoming_flow in self._script:
                return self._script[incoming_flow]
            return self._script.get("*", [])
        return self._script

    async def invoke(self, ctx: ToolContext, message: str) -> dict[str, Any]:
        tk = make_toolkit(self._orch, ctx)
        results: list[dict] = []
        for step in self._script_for(ctx.incoming_flow):
            tool_fn = getattr(tk, step.tool)
            out = tool_fn(**step.kwargs)
            if hasattr(out, "__await__"):
                out = await out
            results.append({"tool": step.tool, "result": out})
        return {"kind": "scripted", "role": self.role, "calls": results, "incoming_flow": ctx.incoming_flow}


# ---------------------------------------------------------------------------
# LLM agent handler (ADK)
# ---------------------------------------------------------------------------


class LlmAgentHandler:
    """Wraps ADK's LlmAgent + Runner. Constructed lazily per invocation so each
    invocation gets a fresh toolkit with closures over its own ToolContext."""

    def __init__(self, role: str, orch: Orchestrator, *, model: str | None = None):
        self.role = role
        self._orch = orch
        # `gemini-flash-latest` is the AI Studio shorthand and 404s on Vertex
        # regional endpoints; ADK's own documented default is `gemini-2.5-flash`.
        self._model = model or os.environ.get("E2E_AGENT_MODEL", "gemini-2.5-flash")
        self._prompt = self._orch.service.render_role_view(role).as_agent_prompt()

    async def invoke(self, ctx: ToolContext, message: str) -> dict[str, Any]:
        # Late-import ADK so the rest of the package imports cleanly without it.
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        toolkit = make_toolkit(self._orch, ctx)
        agent = LlmAgent(
            name=self.role,
            model=self._model,
            instruction=self._prompt,
            description=f"Generic ontology-driven agent for role {self.role}",
            tools=toolkit.as_list(),
        )
        session_service = InMemorySessionService()
        # ADK's App.name validator only allows [A-Za-z0-9_-]; no `:`.
        app_name = f"e2e_orchestrator_{self.role}"
        user_id = "orchestrator"
        session_id = ctx.invocation_id
        await _maybe_await(
            session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        )
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

        content = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])
        reasoning: list[str] = []
        final_text: str | None = None
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            text = _extract_text(event)
            if text:
                reasoning.append(text)
                self._orch.backend.append(
                    EventKind.AGENT_REASONING,
                    {"role": self.role, "invocation_id": ctx.invocation_id, "text": text},
                )
            if hasattr(event, "is_final_response") and event.is_final_response():
                final_text = text
        return {"kind": "llm", "role": self.role, "final_text": final_text, "reasoning_chunks": len(reasoning)}


async def _maybe_await(x):
    if x is None:
        return None
    if hasattr(x, "__await__"):
        return await x
    return x


def _extract_text(event) -> str | None:
    content = getattr(event, "content", None)
    if content is None:
        return None
    parts = getattr(content, "parts", None) or []
    chunks = [getattr(p, "text", None) for p in parts if getattr(p, "text", None)]
    if not chunks:
        return None
    return "".join(chunks).strip() or None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


HandlerFactoryFn = Callable[[str, Orchestrator], RoleHandler]


def build_default_handler_factory(
    service: OntologyService,
    *,
    overrides: dict[str, RoleHandler] | None = None,
    mode: str | None = None,
) -> HandlerFactoryFn:
    """Returns a factory the Orchestrator will call when it first dispatches
    into each role.

      - `overrides`: per-role handlers (used by tests + the runtime to wire
        `InternalStubHandler` for not-yet-implemented internal roles).
      - `mode`: "llm" (default) or "stub". In "stub" mode every non-boundary
        role without an override becomes an `InternalStubHandler` — useful for
        CI runs without API keys.
    """
    mode = mode or os.environ.get("E2E_AGENT_MODE", "llm")
    overrides = dict(overrides or {})

    def factory(role: str, orch: Orchestrator) -> RoleHandler:
        if role in overrides:
            return overrides[role]
        view = service.render_role_view(role)
        if view.identity.is_boundary:
            return BoundaryStubHandler(role, orch)
        if mode == "stub":
            return InternalStubHandler(role, orch)
        return LlmAgentHandler(role, orch)

    return factory
