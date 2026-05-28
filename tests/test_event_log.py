"""JSONL backend: append, idempotency, signals, materialized views."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from e2e_orchestrator.durability import EventKind, JsonlBackend
from e2e_orchestrator.durability.interface import IdempotencyHit, SignalTimeout


def test_append_writes_event_and_assigns_seq(tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "log.jsonl")
    a = backend.append(EventKind.BOUNDARY_INGRESS, {"x": 1})
    b = backend.append(EventKind.HANDOFF_EXECUTED, {"y": 2})

    assert a.event.seq == 0
    assert b.event.seq == 1
    assert a.fresh and b.fresh

    written = [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert written[0]["kind"] == EventKind.BOUNDARY_INGRESS
    assert written[1]["payload"] == {"y": 2}


def test_idempotency_dedupes_on_second_append(tmp_path: Path):
    backend = JsonlBackend(log_path=tmp_path / "log.jsonl")
    first = backend.append(EventKind.HANDOFF_REQUESTED, {"v": 1}, idempotency_key="k1")
    second = backend.append(EventKind.HANDOFF_REQUESTED, {"v": 999}, idempotency_key="k1")

    assert first.fresh is True
    assert second.fresh is False
    assert second.event.seq == first.event.seq  # returned the prior event
    assert second.event.payload == {"v": 1}     # second append's payload is dropped

    check = backend.check_idempotency("k1")
    assert isinstance(check, IdempotencyHit)
    assert check.prior.idempotency_key == "k1"


async def test_signals_deliver_to_awaiter():
    backend = JsonlBackend()
    payload = {"answer": 42}

    async def receiver():
        return await backend.await_signal("sig-1", timeout=2.0)

    task = asyncio.create_task(receiver())
    await asyncio.sleep(0.01)
    backend.notify_signal("sig-1", payload)
    got = await task
    assert got == payload


async def test_signal_delivered_before_await_is_buffered():
    backend = JsonlBackend()
    backend.notify_signal("sig-2", {"early": True})
    got = await backend.await_signal("sig-2", timeout=1.0)
    assert got == {"early": True}


async def test_signal_timeout_raises():
    backend = JsonlBackend()
    with pytest.raises(SignalTimeout):
        await backend.await_signal("never", timeout=0.05)


def test_views_round_trip():
    backend = JsonlBackend()
    backend.put_view("quantum_state", "q-1", {"status": "in_flight"})
    assert backend.read_view("quantum_state", "q-1") == {"status": "in_flight"}
    assert backend.read_view("quantum_state", "missing") is None
