"""The seven-tool kit — every role gets exactly these tools.

Each tool is a Python closure over `(orchestrator, ctx)`. ADK auto-generates the
JSON schema from each function's signature + docstring, so the wire shape
between LLM ↔ tool is set by what's declared here. Keep signatures tight:
primitives + dict, no Pydantic in the parameter list (ADK passes dicts to the
function; we validate inside).

Tools never mutate state by themselves — they call back into the orchestrator,
which writes the event log and routes. The boundary between LLM judgment and
deterministic backbone runs through these closures."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ...durability.interface import EventKind
from ..orchestrator import HandoffResult, Orchestrator, QueryResult, ToolContext


@dataclass
class ToolKit:
    """Bundle returned by `make_toolkit`. ADK's `LlmAgent(tools=...)` accepts a
    list of callables; we expose the list as `as_list()` and also keep handles
    by name for test-time invocation."""
    read_ontology: Callable[..., dict]
    emit_event: Callable[..., dict]
    handoff: Callable[..., dict]
    query: Callable[..., dict]
    advance_fsm: Callable[..., dict]
    call_tool: Callable[..., dict]
    surface_decision: Callable[..., dict]
    respond_to_query: Callable[..., dict]   # used by query-targeted invocations

    def as_list(self) -> list[Callable]:
        # Order is stable so renderers / debug traces can rely on it.
        return [
            self.read_ontology,
            self.emit_event,
            self.handoff,
            self.query,
            self.advance_fsm,
            self.call_tool,
            self.surface_decision,
            self.respond_to_query,
        ]


def make_toolkit(orch: Orchestrator, ctx: ToolContext) -> ToolKit:
    """Construct closures bound to a single agent invocation. Every tool
    increments `ctx.sequence` on side-effecting calls so idempotency keys are
    stable across replays of the same invocation."""

    backend = orch.backend
    svc = orch.service

    def _log_tool_call(name: str, args: dict[str, Any], result: Any) -> None:
        backend.append(
            EventKind.AGENT_TOOL_CALL,
            {
                "tool": name,
                "role": ctx.role,
                "invocation_id": ctx.invocation_id,
                "sequence": ctx.sequence,
                "args": _safe_dict(args),
                "result": _safe_dict(result),
            },
        )

    # ---- 1. read_ontology -------------------------------------------------

    def read_ontology(query: str, target: str = "") -> dict:
        """Look up structured information in the supply chain ontology.

        Use this whenever you need to refresh your understanding of your
        environment, e.g. checking an axiom's recovery route, finding a flow's
        target role, or inspecting a state machine.

        Args:
            query: What to look up. Supported values:
                - "role:<name>"     — return identity for a role.
                - "flow:<name>"     — return source/target/quantum for a flow.
                - "axioms_on_flow:<flow>" — return the axioms attached to a flow.
                - "events_observed_by:<role>" — return events the role observes.
                - "events_emitted_by:<role>" — return events the role emits.
                - "my_view"         — return my full role view (the same one
                                       rendered into my system prompt).
            target: Unused — kept for forward compatibility with structured queries.

        Returns:
            A JSON-shaped dict with the resolved view, or {"error": "..."} on
            unknown query.
        """
        result: dict[str, Any]
        try:
            if query == "my_view":
                result = svc.render_role_view(ctx.role).as_json()
            elif query.startswith("role:"):
                view = svc.render_role_view(query.split(":", 1)[1])
                result = view.as_json()
            elif query.startswith("flow:"):
                flow = orch.router.resolve(query.split(":", 1)[1])
                result = flow.model_dump(mode="json")
            elif query.startswith("axioms_on_flow:"):
                axs = svc.axioms_on_flow(query.split(":", 1)[1])
                result = {"axioms": [a.model_dump(mode="json") for a in axs]}
            elif query.startswith("events_observed_by:"):
                events = svc.events_observed(query.split(":", 1)[1])
                result = {"events": [{"name": e.name, "description": e.body.description} for e in events]}
            elif query.startswith("events_emitted_by:"):
                events = svc.events_emitted(query.split(":", 1)[1])
                result = {"events": [{"name": e.name, "description": e.body.description} for e in events]}
            else:
                result = {"error": f"unknown query: {query}"}
        except Exception as exc:
            result = {"error": str(exc)}
        _log_tool_call("read_ontology", {"query": query, "target": target}, result)
        return result

    # ---- 2. emit_event ----------------------------------------------------

    def emit_event(name: str, payload: dict | None = None) -> dict:
        """Fire an event into the bus. The event must be one your role is
        declared to emit (per `events_emitted_by:<your_role>`). The
        orchestrator records the emission; downstream flows triggered by this
        event will fire when their source role next invokes.

        Args:
            name: Event name (e.g. "forecast_revised").
            payload: Optional dict carrying any inline context the trace should record.

        Returns:
            {"status": "emitted"} on success; {"error": "..."} otherwise.
        """
        ctx.sequence += 1
        result: dict[str, Any]
        emitted = {e.name for e in svc.events_emitted(ctx.role)}
        if name not in emitted:
            result = {"error": f"role {ctx.role} is not declared to emit event {name}", "allowed": sorted(emitted)}
        else:
            backend.append(
                EventKind.EVENT_EMITTED,
                {
                    "name": name,
                    "by_role": ctx.role,
                    "invocation_id": ctx.invocation_id,
                    "sequence": ctx.sequence,
                    "payload": payload or {},
                },
                idempotency_key=f"event:{ctx.role}:{ctx.invocation_id}:{ctx.sequence}:{name}",
            )
            result = {"status": "emitted", "name": name}
        _log_tool_call("emit_event", {"name": name, "payload": payload}, result)
        return result

    # ---- 3. handoff -------------------------------------------------------

    def handoff(flow: str, quantum: dict) -> dict:
        """Fire an outgoing handoff flow carrying a typed quantum. The
        orchestrator validates the quantum against its declared class, evaluates
        any axioms on the flow, and routes deterministically to the target
        role. On a blocking axiom failure, the recovery flow declared by
        `on_failure_route_to` is taken automatically.

        Use this for flows you source whose body has no `returns:` field
        (responsibility transfers downstream). For request-response flows, use
        `query` instead.

        Args:
            flow: Outgoing flow name (one of your declared outgoing handoffs).
            quantum: Dict matching the flow's declared quantum class.

        Returns:
            A dict with status, route, quantum_id, and axiom outcomes:
              {"status": "accepted"|"rerouted"|"rejected",
               "flow": str, "route": str, "quantum_id": str,
               "reason": str, "axiom_outcomes": [...]}
        """
        result_obj: HandoffResult = orch.schedule_handoff(flow_name=flow, quantum=quantum, ctx=ctx)
        result = _handoff_to_dict(result_obj)
        _log_tool_call("handoff", {"flow": flow, "quantum": quantum}, result)
        return result

    # ---- 4. query ---------------------------------------------------------

    async def query(flow: str, query_quantum: dict) -> dict:
        """Request-response over a query flow. The orchestrator validates the
        query payload, dispatches it to the target role, and awaits the typed
        response. Use this only for flows that declare a `returns:` class.

        Args:
            flow: Outgoing query flow name.
            query_quantum: Dict matching the flow's declared quantum class.

        Returns:
            {"status": "answered"|"timeout"|"rejected",
             "flow": str, "response_class": str, "response": {...}, "reason": str}
        """
        result_obj: QueryResult = await orch.schedule_query(flow_name=flow, query=query_quantum, ctx=ctx)
        result = _query_to_dict(result_obj)
        _log_tool_call("query", {"flow": flow, "query_quantum": query_quantum}, result)
        return result

    # ---- 5. advance_fsm ---------------------------------------------------

    def advance_fsm(quantum_id: str, fsm: str, trigger: str) -> dict:
        """Request a lifecycle transition on a quantum you own. The orchestrator
        evaluates the guard axiom deterministically; if it passes, the state
        advances. If the guard is a blocking axiom and fails, the orchestrator
        follows `on_failure_route_to` instead.

        Args:
            quantum_id: The quantum_id returned by the original ingress/handoff.
            fsm: Name of the StateMachine.
            trigger: Name of the trigger event on a declared transition.

        Returns:
            {"status": "transitioned"|"blocked"|"rejected", "from": str, "to": str, "reason": str}
        """
        # The quantum currently in this agent's hands is what the guard is
        # evaluated against. The orchestrator writes the FSM event(s), evaluates
        # the guard via the shared deterministic evaluator, and auto-follows the
        # recovery route on a blocking guard failure.
        result_obj = orch.advance_fsm(
            quantum_id=quantum_id,
            fsm=fsm,
            trigger=trigger,
            quantum=ctx.incoming_payload or {},
            ctx=ctx,
        )
        result = {
            "status": result_obj.status,
            "fsm": result_obj.fsm,
            "trigger": result_obj.trigger,
            "from": result_obj.from_state,
            "to": result_obj.to_state,
            "reason": result_obj.reason,
            "rerouted_to": result_obj.recovery_flow,
        }
        _log_tool_call("advance_fsm", {"quantum_id": quantum_id, "fsm": fsm, "trigger": trigger}, result)
        return result

    # ---- 6. call_tool -----------------------------------------------------

    def call_tool(name: str, input: dict | None = None) -> dict:
        """Invoke a declared specialist tool. Specialist tools (capacity solver,
        OTIF calculator, schedule reader, etc.) are declared in the ontology
        and wired by the orchestrator. None are declared in Phase 2 — the Tool
        meta-construct lands in Phase 5.

        Args:
            name: Declared tool name.
            input: Tool input dict.

        Returns:
            {"status": "no_such_tool"} in Phase 2; tool output dict from Phase 5.
        """
        result = {"status": "no_such_tool", "name": name, "phase": "phase_5_lands_tools"}
        _log_tool_call("call_tool", {"name": name, "input": input}, result)
        return result

    # ---- 7. surface_decision ---------------------------------------------

    def surface_decision(playbook: str, context: dict | None = None, options: list[str] | None = None) -> dict:
        """Surface a decision: present a structured decision surface to the
        orchestrator. Per the role's declared `human_involvement` and the
        orchestrator's policy, the decision may be resolved autonomously,
        escalated to a human, or rejected (e.g. autonomous-only role).

        Args:
            playbook: Name of the playbook framing this decision (Phase 5).
            context: Structured context bundle (responses gathered, exposure metrics).
            options: List of resolution flow names the decider can pick from.

        Returns:
            {"status": "deferred", "phase": "phase_5_lands_decision_surface"} in Phase 2.
        """
        ctx.sequence += 1
        backend.append(
            EventKind.DECISION_SURFACED,
            {
                "playbook": playbook,
                "role": ctx.role,
                "invocation_id": ctx.invocation_id,
                "context": context or {},
                "options": list(options or ()),
                "phase": "phase_2_stub",
            },
            idempotency_key=f"decision:{ctx.role}:{ctx.invocation_id}:{ctx.sequence}",
        )
        result = {"status": "deferred", "playbook": playbook, "phase": "phase_5_lands_decision_surface"}
        _log_tool_call("surface_decision", {"playbook": playbook, "context": context, "options": options}, result)
        return result

    # ---- (8) respond_to_query --------------------------------------------

    def respond_to_query(response: dict) -> dict:
        """When you are invoked because a query flow arrived at your role,
        produce the typed response by calling this tool. The orchestrator
        will deliver it to the awaiting source agent.

        Args:
            response: Dict matching the flow's `returns:` class.

        Returns:
            {"status": "delivered"} or {"error": "..."} if no query is in flight.
        """
        signal_name = getattr(ctx, "response_signal", None)
        expected_cls = getattr(ctx, "expected_response_class", None)
        if signal_name is None:
            result = {"error": "respond_to_query called outside a query invocation"}
        else:
            orch.respond_to_query(signal_name=signal_name, response=response, response_class=expected_cls)
            result = {"status": "delivered", "signal": signal_name, "response_class": expected_cls}
        _log_tool_call("respond_to_query", {"response": response}, result)
        return result

    return ToolKit(
        read_ontology=read_ontology,
        emit_event=emit_event,
        handoff=handoff,
        query=query,
        advance_fsm=advance_fsm,
        call_tool=call_tool,
        surface_decision=surface_decision,
        respond_to_query=respond_to_query,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handoff_to_dict(r: HandoffResult) -> dict:
    return {
        "status": r.status,
        "flow": r.flow,
        "route": r.route,
        "quantum_id": r.quantum_id,
        "reason": r.reason,
        "axiom_outcomes": list(r.axiom_outcomes),
    }


def _query_to_dict(r: QueryResult) -> dict:
    return {
        "status": r.status,
        "flow": r.flow,
        "response_class": r.response_class,
        "response": r.response,
        "reason": r.reason,
    }


def _safe_dict(o: Any) -> Any:
    """Make `o` JSON-serializable. Plain dicts/lists/primitives pass through;
    dataclasses/Pydantic get model_dump; everything else stringifies."""
    if o is None or isinstance(o, (str, int, float, bool)):
        return o
    if isinstance(o, dict):
        return {k: _safe_dict(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe_dict(x) for x in o]
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    try:
        json.dumps(o)
        return o
    except Exception:
        return str(o)
