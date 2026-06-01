"""Replay + determinism (Phase 6, §6.3).

What "replay" guarantees here, stated precisely (the seed asks us to be explicit,
and §12.5 of `agent_system_design.md` flags this as an open question):

  • DETERMINISTIC ORCHESTRATION REPLAY — guaranteed.
    The backbone is commands→events (CQRS): agents emit commands, the
    orchestrator validates and writes events, downstream effects fire off events.
    Routing is pure ontology lookup; axiom/FSM evaluation is deterministic code;
    every flow firing carries a stable idempotency key. So for a *fixed sequence
    of agent decisions* (which a stub scenario pins, and the event log records),
    re-running the same seed reproduces the identical **structural** event
    sequence — same event kinds, same flows, same routing, same axiom verdicts —
    and re-applying the recorded idempotency keys never double-fires a downstream
    effect. `structural_signature` is that replay-invariant projection.

  • LLM REPLAY — NOT guaranteed, by design.
    The agent's resolution choice is irreducibly stochastic (that's the agency —
    Scene 6 *should* differ across runs). Vertex/Gemini through ADK exposes no
    seed that makes a tool-using agent's output bit-reproducible, so we do not
    claim LLM-level replay. What stays invariant even across different LLM seeds
    is the *deterministic frame*: the context-assembly query set, the axiom
    floor, and the routing — which is exactly what `structural_signature`
    captures and what the Phase 5 DoD ("same queries, different resolution")
    rests on.

Runtime handles (quantum_id, invocation_id) are random UUIDs and timestamps are
wall-clock, so two runs are never byte-identical; the structural signature
deliberately excludes them. Determinism lives in the routing/verdict structure,
not the surface bytes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .narrative import _as_dicts, load_events

# Event kinds whose presence/order is part of the deterministic orchestration
# structure. Pure trace bookkeeping (reasoning text, tool-call echoes, agent
# completions) and anything carrying random ids/usage is excluded.
_STRUCTURAL_KINDS = {
    "boundary_ingress",
    "handoff_executed",
    "handoff_blocked",
    "query_requested",
    "query_answered",
    "axiom_evaluated",
    "fsm_transitioned",
    "fsm_blocked",
    "event_emitted",
    "decision_surfaced",
    "wait_all_unsatisfied",
    "quantum_rejected",
    "runaway_guard_tripped",
}


def structural_signature(events: list[Any]) -> list[tuple]:
    """The replay-invariant projection of a trace: the routing/verdict structure
    with all random handles (quantum_id, invocation_id, ts) and token usage
    stripped out. Two runs of the same seed + same agent decisions produce equal
    signatures; that equality is the deterministic-orchestration-replay claim."""
    sig: list[tuple] = []
    for e in _as_dicts(events):
        k = e["kind"]
        if k not in _STRUCTURAL_KINDS:
            continue
        p = e["payload"]
        if k == "boundary_ingress":
            sig.append((k, p["flow"], p["source_role"], p["target_role"], p["quantum_class"]))
        elif k in ("handoff_executed", "handoff_blocked"):
            sig.append((k, p["flow"], p.get("target_role"), p.get("rerouted_to")))
        elif k == "query_requested":
            sig.append((k, p["flow"], p["source_role"], p["target_role"]))
        elif k == "query_answered":
            sig.append((k, p.get("response_class")))
        elif k == "axiom_evaluated":
            sig.append((k, p["flow"], bool(p["ok"]),
                        tuple((o["name"], bool(o["passed"])) for o in p.get("outcomes", []))))
        elif k == "fsm_transitioned":
            sig.append((k, p["fsm"], p["from_state"], p["to_state"], p["trigger"],
                        p.get("guard"), p.get("guard_passed")))
        elif k == "fsm_blocked":
            sig.append((k, p["fsm"], p.get("from_state"), p.get("guard")))
        elif k == "event_emitted":
            sig.append((k, p["name"]))
        elif k == "decision_surfaced":
            sig.append((k, p["playbook"], bool(p.get("validated")), tuple(p.get("options") or ())))
        elif k == "wait_all_unsatisfied":
            sig.append((k, p["playbook"], tuple(p.get("missing") or ())))
        elif k == "quantum_rejected":
            sig.append((k, p.get("flow"), p.get("quantum_class")))
        elif k == "runaway_guard_tripped":
            sig.append((k, p.get("guard")))
    return sig


def signatures_match(events_a: list[Any], events_b: list[Any]) -> bool:
    """True iff two traces share the same deterministic orchestration structure."""
    return structural_signature(events_a) == structural_signature(events_b)


def diff_signatures(events_a: list[Any], events_b: list[Any]) -> list[str]:
    """Human-readable structural diff (empty list ⇒ identical orchestration)."""
    a, b = structural_signature(events_a), structural_signature(events_b)
    out: list[str] = []
    for i in range(max(len(a), len(b))):
        ea = a[i] if i < len(a) else None
        eb = b[i] if i < len(b) else None
        if ea != eb:
            out.append(f"[{i}] A={ea!r}  !=  B={eb!r}")
    return out


def cli(argv: list[str] | None = None) -> int:
    """Compare two JSONL traces for deterministic-orchestration equivalence."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="e2e-replay",
        description="Compare two orchestration traces for deterministic-replay equivalence "
        "(structural signature: routing + axiom verdicts + FSM, ignoring random ids/usage).",
    )
    parser.add_argument("trace_a", type=Path)
    parser.add_argument("trace_b", type=Path)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    a, b = load_events(args.trace_a), load_events(args.trace_b)
    diff = diff_signatures(a, b)
    if not diff:
        print("✓ deterministic orchestration replay: structural signatures are IDENTICAL")
        print(f"  ({len(structural_signature(a))} structural events matched)")
        return 0
    print("✗ structural signatures DIFFER:")
    for line in diff:
        print("  " + line)
    return 1


if __name__ == "__main__":
    raise SystemExit(cli())
