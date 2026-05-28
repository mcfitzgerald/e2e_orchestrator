"""Durability layer — boring infrastructure behind a small interface.

Application code talks to `DurabilityBackend` (a Protocol); the POC binds it to
`JsonlBackend`. Production swap-in (Temporal/Restate) is a different class
implementing the same Protocol — the application layer doesn't move.

See `agent_system_design.md` §4.5 for the contract.
"""
from .interface import (
    AppendedEvent,
    DurabilityBackend,
    EventKind,
    IdempotencyHit,
    IdempotencyMiss,
    LoggedEvent,
    SignalTimeout,
)
from .jsonl_backend import JsonlBackend

__all__ = [
    "AppendedEvent",
    "DurabilityBackend",
    "EventKind",
    "IdempotencyHit",
    "IdempotencyMiss",
    "JsonlBackend",
    "LoggedEvent",
    "SignalTimeout",
]
