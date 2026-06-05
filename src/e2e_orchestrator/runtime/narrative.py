"""Trace narrative renderer (Phase 6, §6.3).

Turns a JSONL event log into a readable, chronological story of a run — the
promo-whiplash narrative in `demo_narrative.md` told back from what actually
happened. The rich UI is Phase 8; this is the CLI/text rendering that proves
the trace tells the story (DoD: "the narrative document and the trace agree").

The renderer is **generic over the event log**, not hard-coded to the six-scene
promo story: it switches on `EventKind` (the wire contract in
`durability/interface.py`), so it renders any scenario — demand-anomaly, promo,
full-demo — the same way. The "scene" labels are derived from event landmarks
(a boundary ingress opens the story; a blocked axiom is the deterministic floor;
queries + a surfaced decision are context assembly; a resolution handoff +
plan_fulfillment is the resolution and re-convergence), never from scenario or
role names. Lose the genericity and we've re-introduced per-narrative code.

It reads the `model` stamp (on `agent_invocation_started`) and token `usage`
(on `agent_invocation_completed.outcome.usage`) the orchestrator now records, so
the cost story comes straight from the log with zero billing lag.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Estimated Vertex pricing for the cost line, per 1M tokens. gemini-3.5-flash
# (GA) — input billed on the *uncached* prefix; cached input is discounted.
# Update here if rates move; clearly labelled "est." in the output so no one
# mistakes it for a billing figure.
_USD_PER_MTOK_INPUT = 0.30
_USD_PER_MTOK_INPUT_CACHED = 0.075   # cached prefix served at a discount
_USD_PER_MTOK_OUTPUT = 2.50


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_events(path: Path | str) -> list[dict]:
    """Read a JSONL trace into a list of event dicts (seq, ts, kind, payload)."""
    events: list[dict] = []
    with Path(path).open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _as_dicts(events: list[Any]) -> list[dict]:
    """Accept either raw dicts (from JSONL) or LoggedEvent objects (in-memory)."""
    out: list[dict] = []
    for e in events:
        if isinstance(e, dict):
            out.append(e)
        else:  # LoggedEvent
            out.append({"seq": e.seq, "ts": e.ts, "kind": e.kind, "payload": e.payload})
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _fmt_quantum(payload: dict | None) -> str:
    """One-line summary of a quantum payload — the few slots a reader cares
    about, generic across quantum classes."""
    if not payload:
        return ""
    keys = ("sku", "volume", "request_id", "promo_id", "retailer",
            "assigned_plant", "assigned_line", "volume_uplift_factor",
            "shortfall_units", "line_ref")
    bits = [f"{k}={payload[k]}" for k in keys if k in payload and payload[k] is not None]
    return ", ".join(bits)


def _summary_header(events: list[dict]) -> list[str]:
    invocations = [e for e in events if e["kind"] == "agent_invocation_started"]
    roles = sorted({e["payload"]["role"] for e in invocations})
    models = sorted({e["payload"].get("model") for e in invocations if e["payload"].get("model")})
    ingress = next((e for e in events if e["kind"] == "boundary_ingress"), None)

    prompt = cached = candidates = total = 0
    for e in events:
        if e["kind"] == "agent_invocation_completed":
            u = (e["payload"].get("outcome") or {}).get("usage") or {}
            prompt += u.get("prompt_tokens", 0) or 0
            cached += u.get("cached_tokens", 0) or 0
            candidates += u.get("candidates_tokens", 0) or 0
            total += u.get("total_tokens", 0) or 0

    rejected = sum(1 for e in events if e["kind"] == "quantum_rejected")
    blocked = sum(1 for e in events if e["kind"] in ("handoff_blocked", "fsm_blocked"))
    guard = next((e for e in events if e["kind"] == "runaway_guard_tripped"), None)

    lines = ["=" * 72, "SUPPLY CHAIN ORCHESTRATION — TRACE NARRATIVE", "=" * 72]
    if ingress:
        p = ingress["payload"]
        lines.append(f"Seed signal : {p['flow']}  ({p['quantum_class']} → {p['target_role']})")
    lines.append(f"Roles       : {len(invocations)} invocation(s) across {', '.join(roles)}")
    lines.append(f"Model       : {', '.join(models) if models else 'stub (no LLM)'}")
    lines.append(f"Events      : {len(events)}   |   quantum_rejected: {rejected}   |   blocked-by-floor: {blocked}")
    if total:
        uncached = max(prompt - cached, 0)
        cost = (uncached / 1e6) * _USD_PER_MTOK_INPUT \
            + (cached / 1e6) * _USD_PER_MTOK_INPUT_CACHED \
            + (candidates / 1e6) * _USD_PER_MTOK_OUTPUT
        lines.append(
            f"Tokens      : {total:,} total  (prompt {prompt:,}, of which "
            f"{cached:,} cached; output {candidates:,})"
        )
        lines.append(f"Cost (est.) : ${cost:,.2f}  @ ${_USD_PER_MTOK_INPUT}/${_USD_PER_MTOK_OUTPUT} per-MTok in/out")
    if guard:
        gp = guard["payload"]
        lines.append(f"⚠ GUARD TRIP : {gp.get('guard')} (limit {gp.get('limit')}) — run halted")
    lines.append("")
    return lines


def _render_event(e: dict, indent: str = "    ") -> list[str]:
    """Render one event as zero or more annotated lines. Returns [] for events
    that are pure trace bookkeeping (tool-call echoes, completions)."""
    k = e["kind"]
    p = e["payload"]

    if k == "boundary_ingress":
        return [f"▸ SCENE 1 — A signal enters the supply chain (boundary ingress)",
                f"    {p['flow']}: {p['source_role']} → {p['target_role']}  [{p['quantum_class']}]",
                f"    {_fmt_quantum(p.get('payload'))}"]

    if k == "agent_invocation_started":
        via = p.get("incoming_flow")
        model = p.get("model")
        tag = f"  ·  via {via}" if via else ""
        mtag = f"  ·  {model}" if model else ""
        return ["", f"── {p['role']} invoked{tag}{mtag} ──"]

    if k == "agent_reasoning":
        text = (p.get("text") or "").strip().replace("\n", " ")
        if not text:
            return []
        if len(text) > 240:
            text = text[:237] + "…"
        return [f'{indent}💭 "{text}"']

    if k == "event_emitted":
        return [f"{indent}● emitted event: {p['name']}"
                + (f"  {p['payload']}" if p.get("payload") else "")]

    if k == "query_requested":
        return [f"{indent}❓ query {p['flow']}: {p['source_role']} → {p['target_role']}  "
                f"(expects {p.get('returns')})"]

    if k == "query_answered":
        resp = p.get("response") or {}
        bits = ", ".join(f"{kk}={vv}" for kk, vv in list(resp.items())[:5] if not str(kk).startswith("_"))
        return [f"{indent}   ↳ answered: {bits}"]

    if k == "decision_surfaced":
        valid = "validated" if p.get("validated") else "REJECTED (unknown_playbook)"
        opts = ", ".join(p.get("options") or [])
        out = [f"{indent}⚖ SCENE 5/6 — decision surfaced [{p['playbook']}] ({valid})",
               f"{indent}    options (no ranking): {opts}"]
        if p.get("context"):
            out.append(f"{indent}    context: {p['context']}")
        return out

    if k == "wait_all_unsatisfied":
        return [f"{indent}⏳ wait_all gate: decision held — missing evidence from {', '.join(p.get('missing') or [])}"]

    if k == "axiom_evaluated":
        outs = p.get("outcomes") or []
        if not outs:
            return []
        verdict = "✓ pass" if p.get("ok") else "✗ FAIL"
        names = ", ".join(f"{o['name']}={'pass' if o['passed'] else 'FAIL'}" for o in outs)
        return [f"{indent}⚙ axioms on {p['flow']}: {verdict}  ({names})"]

    if k == "handoff_blocked":
        fa = p.get("failed_axioms") or []
        ev = fa[0]["evidence"] if fa else ""
        return [f"{indent}⛔ SCENE 4 — DETERMINISTIC FLOOR: {p['flow']} BLOCKED",
                f"{indent}    {ev}",
                f"{indent}    → auto-reroute to {p.get('rerouted_to')} (no LLM in the routing)"]

    if k == "handoff_executed":
        rec = p.get("recovery_for")
        if rec:
            return [f"{indent}↻ recovery flow {p['flow']}: → {p['target_role']}  "
                    f"(orchestrator followed on_failure_route_to for {rec})"]
        marker = ""
        if p["flow"] == "plan_fulfillment":
            marker = "  ◀ SCENE 6 — re-converge: logistics updates the fulfillment plan"
        return [f"{indent}→ handoff {p['flow']}: → {p['target_role']}  [{p['quantum_class']}]{marker}",
                f"{indent}    {_fmt_quantum(p.get('payload'))}"]

    if k == "fsm_transitioned":
        g = p.get("guard")
        gtxt = f"  guard {g}={'pass' if p.get('guard_passed') else 'n/a'}" if g else ""
        accept = "  ◀ floor ACCEPTS the corrected plan" if p.get("guard_passed") else ""
        return [f"{indent}⤴ lifecycle {p['fsm']}: {p['from_state']} → {p['to_state']} "
                f"(trigger {p['trigger']}){gtxt}{accept}"]

    if k == "fsm_blocked":
        return [f"{indent}⛔ lifecycle {p['fsm']} blocked at {p.get('from_state')}: "
                f"guard {p.get('guard')} — {p.get('evidence')}"]

    if k == "quantum_rejected":
        errs = "; ".join(f"{x.get('slot')}:{x.get('code')}" for x in (p.get("errors") or []))
        return [f"{indent}✗ quantum rejected on {p.get('flow')} ({p.get('quantum_class')}): {errs}"]

    if k == "runaway_guard_tripped":
        return [f"{indent}⚠ runaway guard tripped: {p.get('guard')} (limit {p.get('limit')})"]

    return []


_RESOLUTION_FLOWS = ("shift_to_coman", "re_request_production", "request_promo_revision",
                     "allocate_partial_fill")


def _outcome_footer(events: list[dict]) -> list[str]:
    resolved = next((e for e in events if e["kind"] == "event_emitted"
                     and e["payload"]["name"] == "capacity_resolved"), None)
    # The authoritative resolution is the execution flow that actually fired;
    # the capacity_resolved payload may or may not echo it (the LLM's payload
    # shape is its own), so prefer the executed handoff.
    executed_res = [e["payload"]["flow"] for e in events
                    if e["kind"] == "handoff_executed"
                    and e["payload"]["flow"] in _RESOLUTION_FLOWS]
    fulfillment = any(e["kind"] == "handoff_executed"
                      and e["payload"]["flow"] == "plan_fulfillment" for e in events)
    guard = any(e["kind"] == "runaway_guard_tripped" for e in events)

    lines = ["", "─" * 72]
    if resolved or executed_res:
        res = executed_res[0] if executed_res else \
            (resolved["payload"].get("payload") or {}).get("resolution", "?")
        lines.append(f"OUTCOME: capacity conflict resolved via '{res}'.")
        if fulfillment:
            lines.append("         plan_fulfillment fired → supply chain re-converged on the happy path.")
        lines.append("         One seed → cross-domain assembly → decision → re-convergence. Thesis holds.")
    elif guard:
        lines.append("OUTCOME: run halted by a runaway guard (see ⚠ above).")
    else:
        lines.append("OUTCOME: run reached a clean terminal state.")
    lines.append("─" * 72)
    return lines


def render_narrative(events: list[Any]) -> str:
    """Render an event log (list of dicts or LoggedEvents) into the readable
    Scene 1→6 story. Pure function — no I/O — so tests can assert on the text."""
    ev = _as_dicts(events)
    lines = _summary_header(ev)
    for e in ev:
        lines.extend(_render_event(e))
    lines.extend(_outcome_footer(ev))
    return "\n".join(lines)


def render_trace_file(path: Path | str) -> str:
    """Convenience: load a JSONL trace and render it."""
    return render_narrative(load_events(path))


def cli(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="e2e-narrate",
        description="Render a JSONL orchestration trace into a readable Scene 1→6 narrative.",
    )
    parser.add_argument("trace", type=Path, help="Path to a runs/*.jsonl trace file.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.trace.is_file():
        print(f"no such trace file: {args.trace}", file=sys.stderr)
        return 1
    print(render_trace_file(args.trace))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
