"""FSM tracker — per-quantum lifecycle state + guard enforcement.

Per `agent_system_design.md` §8.3: when `advance_fsm` is invoked, the guard
axiom is evaluated by the **same deterministic backbone** as flow axioms. The
quantum advances only if the guard passes; otherwise the orchestrator follows
the recovery route. Per §9, per-quantum FSM state is a materialized view
derived from the event log (held in the durability backend's view store for the
POC).

Generic over `StateMachineBody`: the tracker reads states/transitions/guards
from whatever FSM `lifecycle_ref` names — no per-FSM logic. A guard is an axiom
name; by the ontology's convention it resolves to an axiom declared on a flow
(the exploder enforces resolution), so the guard is found by scanning declared
flow axioms. This is the Phase 4 stop condition for the tracker: if it ever
needs per-FSM branching, the abstraction has leaked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ontology_service import OntologyService

from ..durability.interface import DurabilityBackend, EventKind
from .axiom_evaluator import AxiomEvaluator, AxiomOutcome, _enum_value

FSM_STATE_VIEW = "fsm_state"


@dataclass(frozen=True)
class FsmResult:
    status: str                       # "transitioned" | "blocked" | "rejected"
    fsm: str
    trigger: str
    from_state: str | None
    to_state: str | None = None
    reason: str = ""
    recovery_flow: str | None = None
    recovery_quantum: dict[str, Any] | None = None
    guard: str | None = None
    guard_outcome: AxiomOutcome | None = None


class FsmTracker:
    def __init__(self, service: OntologyService, evaluator: AxiomEvaluator, backend: DurabilityBackend):
        self._svc = service
        self._eval = evaluator
        self._backend = backend

    # ---- state -------------------------------------------------------------

    def _view_key(self, fsm: str, quantum_id: str) -> str:
        return f"{fsm}:{quantum_id}"

    def current_state(self, fsm: str, quantum_id: str) -> str | None:
        sm = self._svc.ontology.get_state_machine(fsm)
        if sm is None:
            return None
        stored = self._backend.read_view(FSM_STATE_VIEW, self._view_key(fsm, quantum_id))
        return stored if stored is not None else sm.body.initial

    # ---- guard resolution (generic) ----------------------------------------

    def _find_guard_axiom(self, guard_name: str) -> Any | None:
        """Resolve a guard name to its AxiomBody by scanning declared flow
        axioms. By convention a guard matches an axiom on a flow; generic, no
        FSM-specific knowledge."""
        for flow_name in self._svc.ontology.flows:
            for ax in self._svc.axioms_on_flow(flow_name):
                if ax.name == guard_name:
                    return ax
        return None

    # ---- advance -----------------------------------------------------------

    def advance(
        self,
        *,
        quantum_id: str,
        fsm: str,
        trigger: str,
        quantum: dict[str, Any],
        by_role: str | None = None,
        invocation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> FsmResult:
        sm = self._svc.ontology.get_state_machine(fsm)
        if sm is None:
            return FsmResult(status="rejected", fsm=fsm, trigger=trigger, from_state=None,
                             reason=f"unknown state machine {fsm!r}")

        cur = self.current_state(fsm, quantum_id)
        candidates = [t for t in sm.body.transitions if t.from_state == cur and t.trigger == trigger]
        if not candidates:
            return FsmResult(status="rejected", fsm=fsm, trigger=trigger, from_state=cur,
                             reason=f"no transition for trigger {trigger!r} from state {cur!r}")
        transition = candidates[0]

        guard_name = transition.guard
        guard_outcome: AxiomOutcome | None = None
        if guard_name:
            ax = self._find_guard_axiom(guard_name)
            if ax is None:
                return FsmResult(status="rejected", fsm=fsm, trigger=trigger, from_state=cur,
                                 guard=guard_name, reason=f"guard axiom {guard_name!r} not resolvable")
            guard_outcome = self._eval.evaluate_axiom(ax, quantum)
            if not guard_outcome.passed and _enum_value(ax.severity) == "blocking":
                self._backend.append(
                    EventKind.FSM_BLOCKED,
                    {
                        "fsm": fsm,
                        "trigger": trigger,
                        "quantum_id": quantum_id,
                        "from_state": cur,
                        "guard": guard_name,
                        "evidence": guard_outcome.evidence,
                        "rerouted_to": guard_outcome.recovery_flow,
                        "by_role": by_role,
                        "invocation_id": invocation_id,
                    },
                    idempotency_key=(f"fsm_blocked:{idempotency_key}" if idempotency_key else None),
                )
                return FsmResult(
                    status="blocked",
                    fsm=fsm,
                    trigger=trigger,
                    from_state=cur,
                    reason=f"blocking guard {guard_name!r} failed: {guard_outcome.evidence}",
                    recovery_flow=guard_outcome.recovery_flow,
                    recovery_quantum=guard_outcome.recovery_quantum,
                    guard=guard_name,
                    guard_outcome=guard_outcome,
                )

        # Guard passed (or none, or non-blocking) → advance.
        self._backend.put_view(FSM_STATE_VIEW, self._view_key(fsm, quantum_id), transition.to_state)
        self._backend.append(
            EventKind.FSM_TRANSITIONED,
            {
                "fsm": fsm,
                "trigger": trigger,
                "quantum_id": quantum_id,
                "from_state": cur,
                "to_state": transition.to_state,
                "guard": guard_name,
                "guard_passed": (guard_outcome.passed if guard_outcome else None),
                "by_role": by_role,
                "invocation_id": invocation_id,
            },
            idempotency_key=idempotency_key,
        )
        return FsmResult(
            status="transitioned",
            fsm=fsm,
            trigger=trigger,
            from_state=cur,
            to_state=transition.to_state,
            guard=guard_name,
            guard_outcome=guard_outcome,
        )
