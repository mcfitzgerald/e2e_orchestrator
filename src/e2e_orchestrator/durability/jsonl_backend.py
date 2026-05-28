"""POC durability backend: append-only JSONL log + in-memory views/signals.

Replaceable: any class with the same `DurabilityBackend` shape (Temporal,
Restate, an SQL-backed log) substitutes without touching the application
layer.
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .interface import (
    AppendedEvent,
    DurabilityBackend,
    IdempotencyHit,
    IdempotencyMiss,
    LoggedEvent,
    SignalTimeout,
)


class JsonlBackend(DurabilityBackend):
    """Append-only JSONL + in-memory state. One file, one process. The lock
    guards against re-entrant appends from tool closures; we don't claim
    cross-process safety."""

    def __init__(self, log_path: Path | str | None = None, *, loop: asyncio.AbstractEventLoop | None = None):
        self._log_path = Path(log_path) if log_path is not None else None
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[LoggedEvent] = []
        self._idempotency: dict[str, LoggedEvent] = {}
        self._views: dict[tuple[str, str], Any] = {}
        self._signals: dict[str, dict[str, Any]] = {}
        self._signal_waiters: dict[str, list[asyncio.Future]] = {}
        self._lock = threading.Lock()
        self._loop = loop  # captured lazily on first await_signal if None

    # ---- log ---------------------------------------------------------------

    def append(self, kind: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> AppendedEvent:
        with self._lock:
            if idempotency_key is not None:
                prior = self._idempotency.get(idempotency_key)
                if prior is not None:
                    return AppendedEvent(event=prior, fresh=False)
            seq = len(self._events)
            ev = LoggedEvent(
                seq=seq,
                ts=datetime.now(timezone.utc).isoformat(),
                kind=kind,
                idempotency_key=idempotency_key,
                payload=payload,
            )
            self._events.append(ev)
            if idempotency_key is not None:
                self._idempotency[idempotency_key] = ev
            if self._log_path is not None:
                with self._log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(_event_to_jsonable(ev), default=_jsonable_default) + "\n")
        return AppendedEvent(event=ev, fresh=True)

    def check_idempotency(self, key: str) -> IdempotencyHit | IdempotencyMiss:
        with self._lock:
            prior = self._idempotency.get(key)
        return IdempotencyHit(prior=prior) if prior is not None else IdempotencyMiss()

    def read_events(self) -> list[LoggedEvent]:
        with self._lock:
            return list(self._events)

    # ---- signals -----------------------------------------------------------

    async def await_signal(self, name: str, timeout: float | None = None) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        with self._lock:
            if name in self._signals:
                # Already delivered before anyone awaited.
                return self._signals.pop(name)
            fut: asyncio.Future = loop.create_future()
            self._signal_waiters.setdefault(name, []).append(fut)
        try:
            if timeout is None:
                return await fut
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise SignalTimeout(name) from exc

    def notify_signal(self, name: str, payload: dict[str, Any]) -> None:
        with self._lock:
            waiters = self._signal_waiters.pop(name, [])
            if not waiters:
                # No one waiting yet — buffer for late awaiters.
                self._signals[name] = payload
                return
        for fut in waiters:
            loop = fut.get_loop()
            if not fut.done():
                loop.call_soon_threadsafe(fut.set_result, payload)

    # ---- materialized views ------------------------------------------------

    def read_view(self, view: str, key: str) -> Any | None:
        with self._lock:
            return self._views.get((view, key))

    def put_view(self, view: str, key: str, value: Any) -> None:
        with self._lock:
            self._views[(view, key)] = value


def _event_to_jsonable(ev: LoggedEvent) -> dict[str, Any]:
    return {
        "seq": ev.seq,
        "ts": ev.ts,
        "kind": ev.kind,
        "idempotency_key": ev.idempotency_key,
        "payload": ev.payload,
    }


def _jsonable_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)
