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
                - "playbook:<name>" — return a playbook anchored to my role
                                       (context_assembly, criteria, resolution
                                       paths, always_fires).
                - "playbooks_anchored_to:<role>" — list the playbooks anchored
                                       to a role and what triggers each.
                - "my_view"         — reminder that your full role view is
                                       already your system instruction (returns
                                       a short pointer, not the full view).
            target: Unused — kept for forward compatibility with structured queries.

        Returns:
            A JSON-shaped dict with the resolved view, or {"error": "..."} on
            unknown query.
        """
        result: dict[str, Any]
        try:
            if query == "my_view":
                # Your full role view is ALREADY your system instruction.
                # Returning it again duplicates a large payload into the
                # conversation, re-sent every subsequent turn (token bloat, and
                # injecting it mid-context can defeat prefix caching). Return a
                # pointer, not the full view.
                result = {
                    "note": (
                        "Your full role view is already provided as your system "
                        "instruction — re-read it there. No tool fetch needed."
                    )
                }
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
            elif query.startswith("playbook:"):
                name = query.split(":", 1)[1]
                view = svc.render_role_view(ctx.role)
                match = next((pb for pb in view.playbooks_anchored_to if pb.name == name), None)
                if match is None:
                    result = {
                        "error": f"no playbook {name!r} anchored to {ctx.role}",
                        "anchored": [pb.name for pb in view.playbooks_anchored_to],
                    }
                else:
                    result = match.model_dump(mode="json")
            elif query.startswith("playbooks_anchored_to:"):
                view = svc.render_role_view(query.split(":", 1)[1])
                result = {
                    "playbooks": [
                        {"name": pb.name, "triggered_by": pb.triggered_by}
                        for pb in view.playbooks_anchored_to
                    ]
                }
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
        """Invoke a declared reader tool to read world state. Reader tools
        (`query_plants_for_sku`, `query_line_load`, `query_commitments_in_window`,
        `query_supplier_for_sku`) return real entities from the loaded world —
        prefer them over inventing plants, lines, or commitments.

        The orchestrator resolves the tool's declared input/output classes,
        validates your `input` against the input class, runs the bound
        deterministic implementation, and validates its output before returning
        it to you. A tool your role can't call (or that doesn't exist) returns a
        clean `no_such_tool`; a query for an entity absent from world state
        returns `unknown_entity` rather than a fabricated answer.

        Args:
            name: Declared tool name (one of your `tools_available_to`).
            input: Tool input dict matching the tool's declared input class.

        Returns:
            {"status": "ok", "output_class": str, "output": {...}, "evidence": str}
            on success; {"status": "no_such_tool"|"invalid_input"|"unknown_entity"
            |"invalid_output", ...} otherwise.
        """
        payload = input or {}
        # Resolve the tool declaration the acting role is allowed to call. The
        # role-view renderer already filters Tools by `available_to`, so a name
        # absent from this set is either undeclared or not callable by us.
        tools = {t.name: t for t in svc.tools_available_to(ctx.role)}
        tool = tools.get(name)
        if tool is None:
            result: dict[str, Any] = {"status": "no_such_tool", "name": name, "available": sorted(tools)}
            _log_tool_call("call_tool", {"name": name, "input": input}, result)
            return result

        input_class = tool.body.input_class
        output_class = tool.body.output_class
        impl = tool.body.implementation

        iv = orch.validator.validate(input_class, payload)
        if not iv.ok:
            result = {
                "status": "invalid_input",
                "name": name,
                "input_class": input_class,
                "errors": [{"slot": e.slot, "code": e.code, "detail": e.detail} for e in iv.errors],
            }
            _log_tool_call("call_tool", {"name": name, "input": input}, result)
            return result

        fn = orch.reader_tools.get(impl)
        if fn is None or orch.world_state is None:
            result = {
                "status": "no_such_tool",
                "name": name,
                "reason": f"implementation {impl!r} not bound or world state unavailable",
            }
            _log_tool_call("call_tool", {"name": name, "input": input}, result)
            return result

        tool_result = fn(payload, orch.world_state)
        if tool_result.output is None:
            # Grounding miss — surface honestly (mirrors the axiom unknown_entity
            # floor). The agent gets the evidence, never a fabricated entity.
            result = {"status": "unknown_entity", "name": name, "evidence": tool_result.evidence}
            _log_tool_call("call_tool", {"name": name, "input": input}, result)
            return result

        ov = orch.validator.validate(output_class, tool_result.output)
        if not ov.ok:
            # The tool produced something off-contract — surface it rather than
            # passing a malformed entity downstream (this is our bug, not the LLM's).
            result = {
                "status": "invalid_output",
                "name": name,
                "output_class": output_class,
                "errors": [{"slot": e.slot, "code": e.code, "detail": e.detail} for e in ov.errors],
                "evidence": tool_result.evidence,
            }
            _log_tool_call("call_tool", {"name": name, "input": input}, result)
            return result

        result = {
            "status": "ok",
            "tool": name,
            "output_class": output_class,
            "output": tool_result.output,
            "evidence": tool_result.evidence,
        }
        _log_tool_call("call_tool", {"name": name, "input": input}, result)
        return result

    # ---- 7. surface_decision ---------------------------------------------

    def surface_decision(playbook: str, context: dict | None = None, options: list[str] | None = None) -> dict:
        """Surface a structured decision to the orchestrator after assembling the
        context a Playbook called for. The orchestrator validates that the named
        playbook is one actually anchored to your role (an unknown name is
        rejected deterministically, the same way a bad entity reference is) and
        records the decision surface in the trace.

        It does NOT pick for you: the resolution choice is yours and stays yours.
        After surfacing, fire exactly one of the playbook's resolution flows via
        `handoff`, then apply the playbook's `always_fires` effects.

        Args:
            playbook: Name of the playbook framing this decision (must be one
                anchored to your role).
            context: Structured context bundle (responses gathered, exposure metrics).
            options: The resolution flow names you are choosing among (echoed back
                un-reordered; the list carries no priority).

        Returns:
            {"status": "surfaced", "options": [...], "next": str} when the
            playbook is valid; {"status": "unknown_playbook", "anchored_playbooks":
            [...]} when it is not.
        """
        ctx.sequence += 1
        anchored = {pb.name for pb in svc.playbooks_anchored_to(ctx.role)}
        validated = playbook in anchored
        if not validated:
            # Deterministic floor (mirrors call_tool's no_such_tool / the axiom
            # unknown_entity): reject a playbook that doesn't exist for this role.
            # This rejects non-existent names only — it never ranks real ones.
            backend.append(
                EventKind.DECISION_SURFACED,
                {
                    "playbook": playbook,
                    "role": ctx.role,
                    "invocation_id": ctx.invocation_id,
                    "context": context or {},
                    "options": list(options or ()),
                    "validated": False,
                    "anchored_playbooks": sorted(anchored),
                },
                idempotency_key=f"decision:{ctx.role}:{ctx.invocation_id}:{ctx.sequence}",
            )
            result = {"status": "unknown_playbook", "playbook": playbook, "anchored_playbooks": sorted(anchored)}
            _log_tool_call("surface_decision", {"playbook": playbook, "context": context, "options": options}, result)
            return result

        # Synchronization gate: a wait_all Playbook may not surface its decision
        # until every `required` context-assembly query has a recorded response
        # for this invocation. Deterministic, signal-based, in the family of
        # quantum_rejected / unknown_entity — the missing flow is named and the
        # gap is visible in the trace. Gates on evidence completeness, not on the
        # resolution choice (§2-safe).
        missing = orch.wait_all_missing(playbook=playbook, role=ctx.role, invocation_id=ctx.invocation_id)
        if missing:
            backend.append(
                EventKind.WAIT_ALL_UNSATISFIED,
                {
                    "playbook": playbook,
                    "role": ctx.role,
                    "invocation_id": ctx.invocation_id,
                    "missing": missing,
                },
                idempotency_key=f"waitall:{ctx.role}:{ctx.invocation_id}:{ctx.sequence}",
            )
            result = {
                "status": "wait_all_unsatisfied",
                "playbook": playbook,
                "missing": missing,
                "evidence": f"wait_all_unsatisfied: no response for {', '.join(missing)}",
                "next": "fire the missing context-assembly query flow(s) via `query`, then re-call surface_decision",
            }
            _log_tool_call("surface_decision", {"playbook": playbook, "context": context, "options": options}, result)
            return result

        backend.append(
            EventKind.DECISION_SURFACED,
            {
                "playbook": playbook,
                "role": ctx.role,
                "invocation_id": ctx.invocation_id,
                "context": context or {},
                "options": list(options or ()),
                "validated": True,
                "anchored_playbooks": sorted(anchored),
            },
            idempotency_key=f"decision:{ctx.role}:{ctx.invocation_id}:{ctx.sequence}",
        )
        result = {
            "status": "surfaced",
            "playbook": playbook,
            "options": list(options or ()),
            "next": "fire exactly one option via the `handoff` tool, then apply the "
            "playbook's always_fires effects",
        }
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
