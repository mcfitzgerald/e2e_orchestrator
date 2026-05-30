"""Orchestrator — the deterministic backbone every agent invocation sits on.

Owns dispatch (handoff + query + boundary ingress), validation, axiom
evaluation, idempotency, event logging, and agent invocation. The seven tools
are closures over a per-invocation `ToolContext` that the orchestrator
constructs when it dispatches into a role's agent.

The orchestrator does **not** know domain semantics. It learns the world
through the ontology (`OntologyService`); it validates quanta against schema;
it routes by `target_role`. The LLM never decides routing or evaluates axioms.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from linkml_runtime.utils.schemaview import SchemaView

from ontology_service import FlowSummary, OntologyService

from ..durability.interface import DurabilityBackend, EventKind
from .axiom_evaluator import AxiomEvaluator
from .flow_router import FlowNotFoundError, FlowRouter
from .fsm_tracker import FsmResult, FsmTracker
from .quantum_validator import QuantumValidator, ValidationResult


# ---------------------------------------------------------------------------
# Results returned to tool callers (agents see these as tool responses).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandoffResult:
    status: str                    # "accepted" | "rerouted" | "rejected"
    flow: str
    route: str                     # target role actually dispatched to
    quantum_id: str
    reason: str = ""
    axiom_outcomes: tuple[dict, ...] = ()


@dataclass(frozen=True)
class QueryResult:
    status: str                    # "answered" | "timeout" | "rejected"
    flow: str
    response_class: str | None
    response: dict | None = None
    reason: str = ""


@dataclass(frozen=True)
class DispatchResult:
    """Top-level result of an entire ingress run (boundary signal → terminal)."""
    seed_event_seq: int
    events_appended: int


# ---------------------------------------------------------------------------
# Per-invocation context — what the seven tool closures need to know.
# ---------------------------------------------------------------------------


@dataclass
class ToolContext:
    """Per-invocation envelope. Tool closures use it for idempotency keys,
    tracing (which agent emitted which call), and FSM lookups against the
    quantum currently in this agent's hands."""
    invocation_id: str
    role: str
    incoming_flow: str | None             # how this invocation was triggered
    incoming_quantum_id: str | None
    incoming_quantum_class: str | None
    incoming_payload: dict | None
    sequence: int = 0                     # tool-call counter, monotonic per invocation


# ---------------------------------------------------------------------------
# Role handler protocol — what counts as "an agent" to the orchestrator.
# ---------------------------------------------------------------------------


class RoleHandler(Protocol):
    """The orchestrator dispatches into a role through this surface. Both the
    real LLM-backed agent and the stub responders implement it."""

    role: str

    async def invoke(self, ctx: ToolContext, message: str) -> dict[str, Any]:
        """Run the agent against `message`. Return a dict the orchestrator
        appends to the trace (free-form; typically `{"final_text": ...}` or
        `{"tool_calls": [...]}` for stub agents)."""
        ...


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------


HandlerFactory = Callable[[str, "Orchestrator"], RoleHandler]


class UnknownRoleError(KeyError):
    pass


class Orchestrator:
    """Single application-layer entry point. Owns the durability backend and
    the deterministic backbone; binds role names to handlers via a factory
    supplied at construction (so the runtime can wire LLM agents, stubs, or
    scripted-test agents without touching the orchestrator)."""

    def __init__(
        self,
        service: OntologyService,
        backend: DurabilityBackend,
        handler_factory: HandlerFactory,
        *,
        clock: Callable[[], int] | None = None,
        world_state: Any | None = None,
    ):
        self._svc = service
        self._backend = backend
        self._handler_factory = handler_factory
        self._clock = clock or (lambda: 0)
        self._router = FlowRouter(service)
        sv = self._schemaview()
        self._validator = QuantumValidator(sv)
        # World state loaded once at boot (§9). The axiom evaluator reads it for
        # tool-backed axioms; if the fixture is absent, evaluation degrades to
        # non-enforcing (logged) rather than crashing.
        self._world = world_state if world_state is not None else _load_default_world_state(sv)
        self._axioms = AxiomEvaluator(service, self._world)
        self._fsm = FsmTracker(service, self._axioms, backend)
        self._handlers: dict[str, RoleHandler] = {}
        self._pending: list[asyncio.Task] = []

    # ---- accessors used by tool closures + tests --------------------------

    @property
    def service(self) -> OntologyService:
        return self._svc

    @property
    def backend(self) -> DurabilityBackend:
        return self._backend

    @property
    def router(self) -> FlowRouter:
        return self._router

    @property
    def world_state(self) -> Any | None:
        return self._world

    def _schemaview(self) -> SchemaView:
        # The Ontology Service hides SchemaView but the orchestrator legitimately
        # needs it for schema-driven validation. Reach through `ontology` (the
        # documented escape hatch in service.py).
        ont = self._svc.ontology
        # `Ontology` exposes its SchemaView as `.sv` in the exploder; fall back
        # to constructing one from the source if the attribute name shifts.
        sv = getattr(ont, "schema_view", None) or getattr(ont, "schemaview", None) or getattr(ont, "sv", None)
        if sv is None:
            raise RuntimeError("Could not obtain SchemaView from the loaded ontology")
        return sv

    def _get_handler(self, role: str) -> RoleHandler:
        if role not in self._handlers:
            self._handlers[role] = self._handler_factory(role, self)
        return self._handlers[role]

    # ---- boundary ingress -------------------------------------------------

    async def dispatch_boundary_ingress(
        self,
        flow_name: str,
        payload: dict[str, Any],
        *,
        quantum_id: str | None = None,
    ) -> DispatchResult:
        """Seed a run with a quantum at a boundary flow. Validates, logs
        `boundary_ingress`, and dispatches to the target role. Boundary roles
        are not LLMs — they don't 'decide' to fire the flow; the simulator
        calls this directly."""
        flow = self._router.resolve(flow_name)
        qid = quantum_id or _new_quantum_id()
        idem = f"boundary:{flow_name}:{qid}"

        validation = self._validator.validate(flow.quantum, payload)
        if not validation.ok:
            self._backend.append(
                EventKind.QUANTUM_REJECTED,
                {
                    "where": "boundary_ingress",
                    "flow": flow_name,
                    "quantum_class": flow.quantum,
                    "quantum_id": qid,
                    "errors": [_err(e) for e in validation.errors],
                    "payload": payload,
                },
                idempotency_key=f"reject:{idem}",
            )
            raise QuantumValidationFailed(flow_name, flow.quantum, validation)

        seed = self._backend.append(
            EventKind.BOUNDARY_INGRESS,
            {
                "flow": flow_name,
                "source_role": flow.source_role,
                "target_role": flow.target_role,
                "quantum_class": flow.quantum,
                "quantum_id": qid,
                "trigger_event": flow.trigger_event,
                "payload": payload,
            },
            idempotency_key=idem,
        )

        await self._dispatch_into_role(
            target_role=flow.target_role,
            incoming_flow=flow_name,
            quantum_id=qid,
            quantum_class=flow.quantum,
            payload=payload,
        )
        # Drain any handoff tasks the inner agents scheduled.
        await self.drain()

        events = self._backend.read_events()
        return DispatchResult(seed_event_seq=seed.event.seq, events_appended=len(events))

    async def drain(self) -> None:
        """Run pending dispatches scheduled by `handoff` closures. Called by
        the runtime entrypoint and by `dispatch_boundary_ingress`. Idempotent
        — a fully-drained orchestrator returns immediately."""
        while self._pending:
            batch = self._pending
            self._pending = []
            await asyncio.gather(*batch)

    # ---- tool-facing dispatch (called by closures, not directly) ----------

    def schedule_handoff(
        self,
        *,
        flow_name: str,
        quantum: dict[str, Any],
        ctx: ToolContext,
    ) -> HandoffResult:
        """Synchronous from the agent's POV: validates + writes the
        `handoff_requested` event + returns immediately. The actual downstream
        invocation runs as a task drained by `drain()`. Keeps the source
        agent's invocation small and avoids re-entrant blocking."""
        ctx.sequence += 1
        flow = self._router.resolve(flow_name)

        if flow.source_role != ctx.role:
            return HandoffResult(
                status="rejected",
                flow=flow_name,
                route=flow.target_role,
                quantum_id="",
                reason=f"role mismatch: {ctx.role} cannot source {flow_name} (declared source: {flow.source_role})",
            )
        if flow.returns:
            return HandoffResult(
                status="rejected",
                flow=flow_name,
                route=flow.target_role,
                quantum_id="",
                reason=f"{flow_name} is a query flow (returns={flow.returns}); use the `query` tool instead",
            )

        qid = _new_quantum_id()
        idem = f"handoff:{ctx.role}:{flow.target_role}:{flow_name}:{qid}:{ctx.sequence}"

        validation = self._validator.validate(flow.quantum, quantum)
        if not validation.ok:
            self._backend.append(
                EventKind.QUANTUM_REJECTED,
                {
                    "where": "handoff",
                    "flow": flow_name,
                    "quantum_class": flow.quantum,
                    "errors": [_err(e) for e in validation.errors],
                    "payload": quantum,
                    "by_role": ctx.role,
                    "invocation_id": ctx.invocation_id,
                },
                idempotency_key=f"reject:{idem}",
            )
            return HandoffResult(
                status="rejected",
                flow=flow_name,
                route=flow.target_role,
                quantum_id=qid,
                reason=f"quantum failed validation: {[_err(e) for e in validation.errors]}",
            )

        axiom_eval = self._axioms.evaluate(flow_name, quantum)
        self._backend.append(
            EventKind.AXIOM_EVALUATED,
            {
                "flow": flow_name,
                "quantum_id": qid,
                "outcomes": [
                    {"name": o.name, "severity": o.severity, "passed": o.passed, "evidence": o.evidence}
                    for o in axiom_eval.results
                ],
                "ok": axiom_eval.ok,
            },
            idempotency_key=f"axioms:{idem}",
        )

        if not axiom_eval.ok:
            # Phase 4 hard gate: a blocking axiom failed. The original handoff
            # is NOT executed — the floor is in code, not the LLM. Record the
            # block, then automatically follow `on_failure_route_to` when there
            # is both a recovery flow and a recovery quantum to carry. A
            # grounding failure (unknown_entity) yields no recovery quantum, so
            # the run halts at the gate and the gap is visible in the trace.
            failed = [o for o in axiom_eval.results if not o.passed]
            self._backend.append(
                EventKind.HANDOFF_BLOCKED,
                {
                    "flow": flow_name,
                    "quantum_class": flow.quantum,
                    "quantum_id": qid,
                    "rerouted_to": axiom_eval.recovery_flow,
                    "failed_axioms": [_outcome_dict(o) for o in failed],
                    "by_role": ctx.role,
                    "invocation_id": ctx.invocation_id,
                },
                idempotency_key=f"blocked:{idem}",
            )
            if axiom_eval.recovery_flow and axiom_eval.recovery_quantum is not None:
                self._dispatch_recovery(
                    recovery_flow=axiom_eval.recovery_flow,
                    recovery_quantum=axiom_eval.recovery_quantum,
                    origin_idem=idem,
                    source_invocation=ctx.invocation_id,
                    blocked_flow=flow_name,
                )
                return HandoffResult(
                    status="rerouted",
                    flow=flow_name,
                    route=axiom_eval.recovery_flow,
                    quantum_id=qid,
                    reason="blocking axiom failed; orchestrator followed on_failure_route_to",
                    axiom_outcomes=tuple(_outcome_dict(o) for o in axiom_eval.results),
                )
            return HandoffResult(
                status="blocked",
                flow=flow_name,
                route=axiom_eval.recovery_flow or "",
                quantum_id=qid,
                reason=(
                    "blocking axiom failed; no recovery dispatched "
                    "(no on_failure_route_to or unconstructable recovery quantum, e.g. unknown_entity)"
                ),
                axiom_outcomes=tuple(_outcome_dict(o) for o in axiom_eval.results),
            )

        appended = self._backend.append(
            EventKind.HANDOFF_EXECUTED,
            {
                "flow": flow_name,
                "source_role": flow.source_role,
                "target_role": flow.target_role,
                "quantum_class": flow.quantum,
                "quantum_id": qid,
                "trigger_event": flow.trigger_event,
                "payload": quantum,
                "by_invocation": ctx.invocation_id,
            },
            idempotency_key=idem,
        )

        if appended.fresh:
            task = asyncio.create_task(
                self._dispatch_into_role(
                    target_role=flow.target_role,
                    incoming_flow=flow_name,
                    quantum_id=qid,
                    quantum_class=flow.quantum,
                    payload=quantum,
                )
            )
            self._pending.append(task)

        return HandoffResult(
            status="accepted",
            flow=flow_name,
            route=flow.target_role,
            quantum_id=qid,
            axiom_outcomes=tuple(_outcome_dict(o) for o in axiom_eval.results),
        )

    async def schedule_query(
        self,
        *,
        flow_name: str,
        query: dict[str, Any],
        ctx: ToolContext,
        timeout: float | None = 30.0,
    ) -> QueryResult:
        """Query flows are request-response. The orchestrator validates +
        dispatches + awaits a signal. The target role's handler is expected
        to call `respond_to_query` when it has the typed answer."""
        ctx.sequence += 1
        flow = self._router.resolve(flow_name)
        if not flow.returns:
            return QueryResult(
                status="rejected",
                flow=flow_name,
                response_class=None,
                reason=f"{flow_name} is a handoff flow (no returns); use the `handoff` tool instead",
            )
        validation = self._validator.validate(flow.quantum, query)
        if not validation.ok:
            return QueryResult(
                status="rejected",
                flow=flow_name,
                response_class=flow.returns,
                reason=f"query payload failed validation: {[_err(e) for e in validation.errors]}",
            )
        qid = _new_quantum_id()
        idem = f"query:{ctx.role}:{flow.target_role}:{flow_name}:{qid}:{ctx.sequence}"
        signal_name = f"query_response:{qid}"

        self._backend.append(
            EventKind.QUERY_REQUESTED,
            {
                "flow": flow_name,
                "source_role": flow.source_role,
                "target_role": flow.target_role,
                "quantum_class": flow.quantum,
                "quantum_id": qid,
                "returns": flow.returns,
                "payload": query,
                "by_invocation": ctx.invocation_id,
                "signal": signal_name,
            },
            idempotency_key=idem,
        )

        # Dispatch the query as its own invocation and wait for the target's
        # handler to call `respond_to_query`.
        asyncio.create_task(
            self._dispatch_into_role(
                target_role=flow.target_role,
                incoming_flow=flow_name,
                quantum_id=qid,
                quantum_class=flow.quantum,
                payload=query,
                expected_response_class=flow.returns,
                response_signal=signal_name,
            )
        )

        try:
            response_payload = await self._backend.await_signal(signal_name, timeout=timeout)
        except Exception:
            return QueryResult(
                status="timeout",
                flow=flow_name,
                response_class=flow.returns,
                reason="no response within timeout",
            )

        return QueryResult(
            status="answered",
            flow=flow_name,
            response_class=flow.returns,
            response=response_payload,
        )

    def respond_to_query(self, *, signal_name: str, response: dict[str, Any], response_class: str | None = None) -> None:
        """Handler-side primitive: deliver a typed response back to the
        awaiting source agent. Phase 5 will harden response validation."""
        self._backend.append(
            EventKind.QUERY_ANSWERED,
            {"signal": signal_name, "response": response, "response_class": response_class},
            idempotency_key=f"answer:{signal_name}",
        )
        self._backend.notify_signal(signal_name, response)

    # ---- FSM advance (tool-facing) ----------------------------------------

    def advance_fsm(
        self,
        *,
        quantum_id: str,
        fsm: str,
        trigger: str,
        quantum: dict[str, Any],
        ctx: ToolContext,
    ) -> FsmResult:
        """Request a lifecycle transition. The guard axiom is evaluated by the
        same deterministic evaluator as flow axioms (§8.3); on a blocking guard
        failure with a constructable recovery quantum, the orchestrator follows
        `on_failure_route_to` — the same auto-recovery as the handoff path."""
        ctx.sequence += 1
        idem = f"fsm:{ctx.role}:{quantum_id}:{ctx.sequence}:{trigger}"
        result = self._fsm.advance(
            quantum_id=quantum_id,
            fsm=fsm,
            trigger=trigger,
            quantum=quantum,
            by_role=ctx.role,
            invocation_id=ctx.invocation_id,
            idempotency_key=idem,
        )
        if result.status == "blocked" and result.recovery_flow and result.recovery_quantum is not None:
            self._dispatch_recovery(
                recovery_flow=result.recovery_flow,
                recovery_quantum=result.recovery_quantum,
                origin_idem=idem,
                source_invocation=ctx.invocation_id,
                blocked_flow=f"{fsm}:{trigger}",
            )
        return result

    # ---- recovery dispatch (deterministic on_failure_route_to) -------------

    def _dispatch_recovery(
        self,
        *,
        recovery_flow: str,
        recovery_quantum: dict[str, Any],
        origin_idem: str,
        source_invocation: str,
        blocked_flow: str,
    ) -> None:
        """Fire the recovery flow named by a failed blocking axiom's
        `on_failure_route_to`. The recovery quantum is built by the (domain-
        aware) axiom tool; the orchestrator only validates it against the
        recovery flow's class and routes — no axiom-specific code here."""
        rflow = self._router.resolve(recovery_flow)
        rqid = _new_quantum_id()
        ridem = f"recovery:{origin_idem}:{recovery_flow}:{rqid}"

        validation = self._validator.validate(rflow.quantum, recovery_quantum)
        if not validation.ok:
            self._backend.append(
                EventKind.QUANTUM_REJECTED,
                {
                    "where": "recovery",
                    "flow": recovery_flow,
                    "quantum_class": rflow.quantum,
                    "errors": [_err(e) for e in validation.errors],
                    "payload": recovery_quantum,
                },
                idempotency_key=f"reject:{ridem}",
            )
            return

        appended = self._backend.append(
            EventKind.HANDOFF_EXECUTED,
            {
                "flow": recovery_flow,
                "source_role": rflow.source_role,
                "target_role": rflow.target_role,
                "quantum_class": rflow.quantum,
                "quantum_id": rqid,
                "trigger_event": rflow.trigger_event,
                "payload": recovery_quantum,
                "by_invocation": source_invocation,
                "recovery_for": blocked_flow,
            },
            idempotency_key=ridem,
        )
        if appended.fresh:
            task = asyncio.create_task(
                self._dispatch_into_role(
                    target_role=rflow.target_role,
                    incoming_flow=recovery_flow,
                    quantum_id=rqid,
                    quantum_class=rflow.quantum,
                    payload=recovery_quantum,
                )
            )
            self._pending.append(task)

    # ---- internal dispatch helper ----------------------------------------

    async def _dispatch_into_role(
        self,
        *,
        target_role: str,
        incoming_flow: str,
        quantum_id: str,
        quantum_class: str,
        payload: dict,
        expected_response_class: str | None = None,
        response_signal: str | None = None,
    ) -> None:
        if self._svc.get_role(target_role) is None:
            self._backend.append(
                EventKind.QUANTUM_REJECTED,
                {
                    "where": "dispatch",
                    "reason": "unknown_role",
                    "target_role": target_role,
                    "flow": incoming_flow,
                    "quantum_id": quantum_id,
                },
            )
            raise UnknownRoleError(target_role)

        handler = self._get_handler(target_role)
        invocation_id = _new_invocation_id()
        ctx = ToolContext(
            invocation_id=invocation_id,
            role=target_role,
            incoming_flow=incoming_flow,
            incoming_quantum_id=quantum_id,
            incoming_quantum_class=quantum_class,
            incoming_payload=payload,
        )
        # Attach query-response metadata when applicable (the toolkit can use
        # it; the handler is also free to consult it via the ctx envelope).
        if response_signal is not None:
            setattr(ctx, "response_signal", response_signal)
            setattr(ctx, "expected_response_class", expected_response_class)

        self._backend.append(
            EventKind.AGENT_INVOCATION_STARTED,
            {
                "role": target_role,
                "invocation_id": invocation_id,
                "incoming_flow": incoming_flow,
                "quantum_id": quantum_id,
                "quantum_class": quantum_class,
                "expects_response": expected_response_class,
            },
        )

        message = _render_invocation_message(
            target_role=target_role,
            incoming_flow=incoming_flow,
            quantum_class=quantum_class,
            payload=payload,
            expected_response_class=expected_response_class,
        )

        outcome: dict[str, Any] = {}
        try:
            outcome = await handler.invoke(ctx, message)
        except Exception as exc:
            outcome = {"error": str(exc)}
            self._backend.append(
                EventKind.AGENT_INVOCATION_COMPLETED,
                {"role": target_role, "invocation_id": invocation_id, "outcome": outcome},
            )
            raise
        finally:
            self._backend.append(
                EventKind.AGENT_INVOCATION_COMPLETED,
                {"role": target_role, "invocation_id": invocation_id, "outcome": outcome},
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class QuantumValidationFailed(RuntimeError):
    def __init__(self, flow: str, quantum_class: str, validation: ValidationResult):
        super().__init__(f"{flow}: quantum {quantum_class} failed validation")
        self.flow = flow
        self.quantum_class = quantum_class
        self.validation = validation


def _load_default_world_state(schemaview: SchemaView):
    """Load the demo world fixture from the sibling ontology repo. Lazy imports
    keep the world_state package off the orchestrator's module-load path (it
    imports back into the application layer). Returns None if the fixture is
    absent so tests/embeddings without a fixture still construct cleanly."""
    from .. import _bootstrap
    from ..world_state import WorldState

    path = getattr(_bootstrap, "WORLD_STATE_YAML_PATH", None)
    if path is None or not path.is_file():
        return None
    return WorldState.load(path, schemaview)


def _new_quantum_id() -> str:
    return f"q-{uuid.uuid4().hex[:12]}"


def _new_invocation_id() -> str:
    return f"inv-{uuid.uuid4().hex[:12]}"


def _err(e) -> dict:
    return {"slot": e.slot, "code": e.code, "detail": e.detail}


def _outcome_dict(o) -> dict:
    return {"name": o.name, "severity": o.severity, "passed": o.passed, "evidence": o.evidence}


def _render_invocation_message(
    *,
    target_role: str,
    incoming_flow: str,
    quantum_class: str,
    payload: dict,
    expected_response_class: str | None,
) -> str:
    """The per-invocation user message that lands on the agent. Spells out
    what arrived and (for query flows) what shape of response is expected."""
    lines = [
        f"You are being invoked because flow `{incoming_flow}` just arrived.",
        f"Incoming quantum class: {quantum_class}",
        "Incoming quantum payload (JSON):",
        _pretty_json(payload),
    ]
    if expected_response_class is not None:
        lines += [
            "",
            f"This is a query flow. Produce a {expected_response_class} response by calling "
            "the `respond_to_query` tool (or emit your decision via `surface_decision` if the "
            "answer is non-trivial). Do not fire another handoff.",
        ]
    else:
        lines += [
            "",
            "Decide your next action against the actions declared in your role view. "
            "Typical next steps: fire one of your outgoing handoffs via the `handoff` tool, "
            "ask a question via `query`, or update lifecycle via `advance_fsm`. "
            "Reason briefly before tool-calling.",
        ]
    return "\n".join(lines)


def _pretty_json(d: Any) -> str:
    import json
    return json.dumps(d, indent=2, default=str)
