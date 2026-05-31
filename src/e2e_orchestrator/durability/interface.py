"""Durability contract — the small interface the application layer depends on.

If a backend implements this Protocol, the application layer can sit on top of
it without modification. POC ships `JsonlBackend`; production will ship a
Temporal/Restate-backed implementation behind the same Protocol.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


# Event kinds the orchestrator writes. Tight enum so log readers (replay,
# trace UI) can switch on them. Add new kinds intentionally — every kind is
# part of the wire contract.
class EventKind:
    BOUNDARY_INGRESS = "boundary_ingress"
    HANDOFF_REQUESTED = "handoff_requested"
    HANDOFF_EXECUTED = "handoff_executed"
    HANDOFF_BLOCKED = "handoff_blocked"
    QUERY_REQUESTED = "query_requested"
    QUERY_ANSWERED = "query_answered"
    AXIOM_EVALUATED = "axiom_evaluated"
    FSM_TRANSITIONED = "fsm_transitioned"
    FSM_BLOCKED = "fsm_blocked"
    EVENT_EMITTED = "event_emitted"
    AGENT_INVOCATION_STARTED = "agent_invocation_started"
    AGENT_INVOCATION_COMPLETED = "agent_invocation_completed"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_REASONING = "agent_reasoning"
    DECISION_SURFACED = "decision_surfaced"
    QUANTUM_REJECTED = "quantum_rejected"
    WAIT_ALL_UNSATISFIED = "wait_all_unsatisfied"
    RUNAWAY_GUARD_TRIPPED = "runaway_guard_tripped"


@dataclass(frozen=True)
class LoggedEvent:
    """One line in the event log. Strict shape so the JSONL is grep-able."""
    seq: int
    ts: str                       # ISO-8601 UTC
    kind: str                     # see EventKind
    idempotency_key: str | None   # None for read-only or trace-only events
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppendedEvent:
    event: LoggedEvent
    fresh: bool                   # False if the idempotency key was already present


@dataclass(frozen=True)
class IdempotencyHit:
    """The key was already present; here's the prior event."""
    prior: LoggedEvent


@dataclass(frozen=True)
class IdempotencyMiss:
    pass


class SignalTimeout(Exception):
    """`await_signal` waited longer than its timeout. Caller decides recovery."""


class DurabilityBackend(Protocol):
    """The interface application code depends on. Implementations must be
    safe to use from `asyncio` code; `append_event` may block briefly on a
    file write but must not be slow enough to block agent dispatch."""

    def append(self, kind: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> AppendedEvent:
        """Append a single event. If `idempotency_key` is provided and already
        present, the prior event is returned with `fresh=False` and nothing is
        written. Caller drives the dedupe decision off `fresh`."""
        ...

    def check_idempotency(self, key: str) -> IdempotencyHit | IdempotencyMiss:
        """Pure lookup; never writes."""
        ...

    def read_events(self) -> list[LoggedEvent]:
        """Snapshot of the log (cheap for the POC; bounded by event count). Used
        by the trace view and replay."""
        ...

    async def await_signal(self, name: str, timeout: float | None = None) -> dict[str, Any]:
        """Suspend until `notify_signal(name, payload)` lands or the timeout
        elapses. Returns the signal payload. Raises `SignalTimeout` on expiry."""
        ...

    def notify_signal(self, name: str, payload: dict[str, Any]) -> None:
        """Deliver a signal. Idempotent at the name level — late notifies after
        a timeout are silently dropped to keep callers simple."""
        ...

    def read_view(self, view: str, key: str) -> Any | None:
        """Materialized view lookup. POC backend keeps these in memory."""
        ...

    def put_view(self, view: str, key: str, value: Any) -> None:
        """Materialized view write."""
        ...
