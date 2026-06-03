"""Transport-agnostic front-door logic — the orchestrator behind a clean edge.

`server.py` binds these methods to FastMCP tools/resources; the tests call them
directly against the *real* orchestrator seams (not mocks), which is why the
logic lives here rather than inside decorated handlers.

Design notes (the load-bearing ones):

- **One simulated world behind the door.** The front door is configured at
  startup with a `world` (a scenario name) and a `mode`. That selects what sits
  *behind* the door — the stub scripts (`--mode stub`) or real LlmAgents
  (`--mode llm`), plus the cross-domain query responders — exactly the wiring the
  CLI uses (`runtime.main.build_scenario_orchestrator`). The MCP client supplies
  the *boundary ingress* in place of the scenario's seeder. So `ingress_quantum`
  changes *who knocks*, not *what's behind the door*; the demo reproduces
  end-to-end through the protocol with zero per-role code at the boundary. This
  mirrors the design memo: the seeded boundary responders + world fixture are
  shims behind the *declared* edges; Phase 7 realizes the inbound edge as MCP.

- **Per-ingress run, addressed by `run_id`.** The CLI runs one scenario per
  process and writes one trace file. The server is long-lived and may field many
  ingresses, so each ingress mints a `run_id`, builds its own orchestrator +
  backend (writing `runs/mcp-<run_id>.jsonl`), and is recorded in an in-memory
  `run_id → RunRecord` registry. Resources read from that registry. This is the
  reference-impl shape (in-memory map), consistent with the rest of the
  durability layer per `docs/limitations.md`.

- **Idempotency at the wire.** MCP clients retry. `ingress_quantum` accepts an
  optional `idempotency_key`; a retried ingress with a known key returns the
  *same* run without re-dispatching (server-level dedup), and the key is also
  folded into a stable `quantum_id` so the orchestrator's own idempotency
  discipline holds within the run. The retry boundary is exactly where this
  earns its keep — see the §12.8 observation in the Phase 7 report about whether
  idempotency-at-the-wire wants to be *declared*.

- **Reads are sourced from events, never live in-memory orchestrator state.** A
  command returns a *pointer* (resource URIs); the client reads the trace.
  Preserves replay + the commands→events invariant.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ontology_service import OntologyService, SUPPLY_CHAIN_DEMO_YAML
from ontology_service import UnknownRoleError as OntologyUnknownRoleError

from ..application.flow_router import FlowNotFoundError, FlowRouter
from ..application.orchestrator import QuantumValidationFailed
from ..durability.interface import LoggedEvent
from ..runtime.main import DEFAULT_SCENARIO, build_scenario_orchestrator
from ..runtime.narrative import render_narrative


# ---------------------------------------------------------------------------
# Records + results
# ---------------------------------------------------------------------------


@dataclass
class RunRecord:
    """Everything a reader resource needs about one run — sourced from the event
    log, addressable by `run_id`."""
    run_id: str
    kind: str                       # "ingress" | "demo"
    flow: str | None
    quantum_id: str | None
    status: str                     # "accepted" | "rejected"
    trace_path: str | None
    events: list[dict] = field(default_factory=list)


@dataclass
class IngressResult:
    """What `ingress_quantum` hands back: the run/quantum id + resource pointers.
    Downstream effects are NOT returned synchronously — read them off the trace
    (commands→events)."""
    run_id: str
    quantum_id: str | None
    flow: str
    status: str
    replayed: bool
    events_appended: int
    trace: str
    narrative: str
    decisions: str
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "quantum_id": self.quantum_id,
            "flow": self.flow,
            "status": self.status,
            "replayed": self.replayed,
            "events_appended": self.events_appended,
            "trace": self.trace,
            "narrative": self.narrative,
            "decisions": self.decisions,
            **({"reason": self.reason} if self.reason else {}),
        }


class UnknownRunError(KeyError):
    """No run with that id is registered."""


# ---------------------------------------------------------------------------
# Front door
# ---------------------------------------------------------------------------


class OrchestratorFrontDoor:
    """The orchestrator system presented through a generic `ingress + read`
    surface. Holds no domain knowledge and no per-role code: `ingress` forwards
    `(flow, payload)` to `Orchestrator.dispatch_boundary_ingress` — the same seam
    the boundary simulators call — and the readers project the event log."""

    def __init__(
        self,
        *,
        mode: str = "llm",
        world: str = "full-demo",
        ontology_yaml: Path | None = None,
        runs_dir: Path | None = Path("runs"),
    ):
        self._mode = mode
        self._world = world
        self._runs_dir = Path(runs_dir) if runs_dir is not None else None
        # Load the ontology once and share it across ingresses (it's read-only
        # and expensive to parse). Resources like `roleview://` read it directly.
        self._service = OntologyService.load(str(ontology_yaml or SUPPLY_CHAIN_DEMO_YAML))
        self._router = FlowRouter(self._service)
        self._runs: dict[str, RunRecord] = {}
        self._idem: dict[str, str] = {}
        # Serialize ingress: each ingress builds + drives its own orchestrator,
        # but the run/idempotency registries are shared mutable state. For the
        # POC a single lock around ingress is the simplest correct discipline
        # (reference-impl shape; a production front door would reserve the
        # idempotency key and run dispatches concurrently).
        self._lock = asyncio.Lock()

    @property
    def service(self) -> OntologyService:
        return self._service

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def world(self) -> str:
        return self._world

    # ---- write side ------------------------------------------------------

    async def ingress(
        self,
        flow: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> IngressResult:
        """Drop a signal into the supply chain at a boundary flow. Generic over
        `(flow, payload)` — it does not enumerate roles or branch on domain.
        Forwards to `dispatch_boundary_ingress` (commands→events); returns the
        run/quantum id + resource pointers, never downstream effects directly."""
        async with self._lock:
            # Wire-level idempotency: a retried ingress with a known key returns
            # the same run without re-dispatching.
            if idempotency_key and idempotency_key in self._idem:
                rec = self._runs[self._idem[idempotency_key]]
                return self._ingress_result(rec, replayed=True)

            # Front-door guard (generic, no role names): the inbound edge only
            # accepts flows whose source is a declared boundary role — "signals
            # enter from outside the orchestration envelope". Derived purely from
            # the ontology (`is_boundary`); rejects unknown/internal flows with
            # the system's normal vocabulary, not a bespoke MCP error.
            guard = self._reject_if_not_boundary(flow)
            if guard is not None:
                run_id = _new_run_id()
                rec = RunRecord(run_id, "ingress", flow, None, "rejected", None, events=[])
                self._runs[run_id] = rec
                if idempotency_key:
                    self._idem[idempotency_key] = run_id
                return self._ingress_result(rec, replayed=False, reason=guard)

            run_id = _new_run_id()
            log_path = self._runs_dir / f"mcp-{run_id}.jsonl" if self._runs_dir else None
            orch, backend, _service, _spec = build_scenario_orchestrator(
                self._world,
                mode=self._mode,
                log_path=log_path,
                service=self._service,
            )
            # Fold the idempotency key into a stable quantum_id so the
            # orchestrator's own idempotency discipline holds within the run.
            qid = _stable_quantum_id(idempotency_key) if idempotency_key else None

            status = "accepted"
            reason = ""
            try:
                await orch.dispatch_boundary_ingress(flow, payload, quantum_id=qid)
            except QuantumValidationFailed as exc:
                # The orchestrator already logged a `quantum_rejected` event; the
                # rejection is readable on the trace. Surface a short reason.
                status = "rejected"
                reason = f"quantum {exc.quantum_class} failed validation for flow {exc.flow}"

            events = _events_as_dicts(backend.read_events())
            effective_qid = qid or _ingress_quantum_id(events)
            rec = RunRecord(
                run_id=run_id,
                kind="ingress",
                flow=flow,
                quantum_id=effective_qid,
                status=status,
                trace_path=str(log_path) if log_path else None,
                events=events,
            )
            self._runs[run_id] = rec
            if idempotency_key:
                self._idem[idempotency_key] = run_id
            return self._ingress_result(rec, replayed=False, reason=reason)

    async def run_demo(self, scenario: str = DEFAULT_SCENARIO, mode: str | None = None) -> IngressResult:
        """Convenience wrapper over `run_scenario`: fire the scenario's *own*
        seeder (the canned boundary signal) and run it to a terminal state, then
        register the run so its narrative/trace are readable as resources. This
        is the 'run the whole canned demo through the protocol' path; the generic
        boundary edge is `ingress`."""
        async with self._lock:
            run_mode = mode or self._mode
            run_id = _new_run_id()
            log_path = self._runs_dir / f"mcp-demo-{scenario}-{run_id}.jsonl" if self._runs_dir else None
            orch, backend, _service, spec = build_scenario_orchestrator(
                scenario, mode=run_mode, log_path=log_path, service=self._service
            )
            await spec["seeder"](orch)
            events = _events_as_dicts(backend.read_events())
            rec = RunRecord(
                run_id=run_id,
                kind="demo",
                flow=None,
                quantum_id=_ingress_quantum_id(events),
                status="accepted",
                trace_path=str(log_path) if log_path else None,
                events=events,
            )
            self._runs[run_id] = rec
            return self._ingress_result(rec, replayed=False)

    # ---- read side (resources) ------------------------------------------

    def read_trace(self, run_id: str) -> str:
        """`trace://<run_id>` — the JSONL event log for a run (read-only
        projection of what happened)."""
        rec = self._require_run(run_id)
        return "\n".join(json.dumps(e, default=str) for e in rec.events)

    def read_narrative(self, run_id: str) -> str:
        """`narrative://<run_id>` — the human-readable Scene 1→6 story, rendered
        from the event log by `runtime.narrative` (reused, not re-implemented)."""
        rec = self._require_run(run_id)
        return render_narrative(rec.events)

    def read_decisions(self, run_id: str) -> str:
        """`decisions://<run_id>` — the decision surface(s) surfaced during the
        run (the `decision_surfaced` event payloads), as JSON."""
        rec = self._require_run(run_id)
        surfaced = [e["payload"] for e in rec.events if e["kind"] == "decision_surfaced"]
        return json.dumps(surfaced, indent=2, default=str)

    def read_roleview(self, role: str) -> str:
        """`roleview://<role>` — `render_role_view(role).as_agent_prompt()`,
        read-only. The cleanest possible MCP resource: a faithful read of the
        ontology-derived identity of any role, no run required. Byte-identical to
        what the orchestrator binds as an LlmAgent's instruction."""
        try:
            return self._service.render_role_view(role).as_agent_prompt()
        except OntologyUnknownRoleError as exc:
            raise UnknownRunError(f"unknown role: {role}") from exc

    def list_runs(self) -> list[str]:
        return list(self._runs)

    def get_run(self, run_id: str) -> RunRecord:
        return self._require_run(run_id)

    # ---- helpers ---------------------------------------------------------

    def _reject_if_not_boundary(self, flow: str) -> str | None:
        """Return a rejection reason if `flow` is not a boundary-ingress flow,
        else None. Generic: reads the ontology's `is_boundary` for the flow's
        source role — no enumeration of roles or flows."""
        try:
            resolved = self._router.resolve(flow)
        except FlowNotFoundError:
            return f"unknown_flow: {flow!r} is not declared in the ontology"
        source = resolved.source_role
        try:
            identity = self._service.render_role_view(source).identity
        except OntologyUnknownRoleError:
            return f"unknown_source_role: {source!r} for flow {flow!r}"
        if not identity.is_boundary:
            return (
                f"not_a_boundary_ingress: flow {flow!r} is sourced by internal role "
                f"{source!r}; the MCP front door only accepts flows entering from a "
                "declared boundary role"
            )
        return None

    def _require_run(self, run_id: str) -> RunRecord:
        rec = self._runs.get(run_id)
        if rec is None:
            raise UnknownRunError(f"unknown run_id: {run_id}")
        return rec

    def _ingress_result(self, rec: RunRecord, *, replayed: bool, reason: str = "") -> IngressResult:
        return IngressResult(
            run_id=rec.run_id,
            quantum_id=rec.quantum_id,
            flow=rec.flow or "",
            status=rec.status,
            replayed=replayed,
            events_appended=len(rec.events),
            trace=f"trace://{rec.run_id}",
            narrative=f"narrative://{rec.run_id}",
            decisions=f"decisions://{rec.run_id}",
            reason=reason,
        )


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def _stable_quantum_id(idempotency_key: str) -> str:
    """Derive a stable `quantum_id` from a client's idempotency key so the
    orchestrator's `boundary:<flow>:<qid>` idempotency key is identical across
    retries (the in-run half of the discipline; the server map is the other
    half)."""
    digest = hashlib.sha1(idempotency_key.encode("utf-8")).hexdigest()[:12]
    return f"q-{digest}"


def _events_as_dicts(events: list[LoggedEvent]) -> list[dict]:
    return [
        {"seq": e.seq, "ts": e.ts, "kind": e.kind, "idempotency_key": e.idempotency_key, "payload": e.payload}
        for e in events
    ]


def _ingress_quantum_id(events: list[dict]) -> str | None:
    """The quantum_id stamped on the seed boundary_ingress event, for runs where
    the orchestrator minted it (no client idempotency key)."""
    for e in events:
        if e["kind"] == "boundary_ingress":
            return e["payload"].get("quantum_id")
    return None
