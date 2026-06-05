"""Bake a REAL LLM run into `data.js` the replay loads as `window.DEMO_DATA`.

The replay plays back an actual `--mode llm` `capacity-resolution` run (real
agent reasoning, real grounded decision) — NOT a stub. Stub mode is scripted and
emits no reasoning, so it can't answer "what is the agent thinking"; this reads a
captured live trace and curates its 80-odd events into a clean, ordered list of
narrative steps, each carrying the agent's *actual* words.

The live run starts at the injected `CapacityConflict` (a grounded agent on the
full `submit_promo_plan` path sizes the request to fit and dodges the conflict —
the documented Phase-5 finding — so the conflict is injected to make the agency
visible). One framing line covers the promo origin.

Run:  uv run python demo_ui/export_demo_data.py [path/to/trace.jsonl]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp_server.core import OntologyKnowledgeService

HERE = Path(__file__).resolve().parent
DEFAULT_TRACE = HERE.parent / "runs" / "demo-capres.jsonl"


def _load(trace_path: Path) -> list[dict]:
    return [json.loads(l) for l in trace_path.read_text().splitlines() if l.strip()]


def _trim(text: str, n: int = 320) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip(" ,.;:") + "…"


def _reader_outputs(events: list[dict], tool: str) -> list[dict]:
    """All `output` dicts a reader tool returned, in order."""
    out = []
    for e in events:
        if e["kind"] != "agent_tool_call":
            continue
        a = e["payload"].get("args") or {}
        if a.get("name") == tool:
            res = e["payload"].get("result") or {}
            if isinstance(res, dict) and res.get("output"):
                out.append(res["output"])
    return out


def curate(events: list[dict]) -> list[dict]:
    """Curate the live trace into clean replay steps with the agent's REAL words.
    Anchors on the structural beats; attaches the nearest preceding reasoning."""
    steps: list[dict] = []
    last_reason = None
    seen_tool = set()
    answers = {e["payload"]["signal"].split(":")[1]: e["payload"]
               for e in events if e["kind"] == "query_answered"}

    coman = _reader_outputs(events, "query_coman_availability")
    coman_by_sku = {c.get("sku"): c for c in coman}
    lineload = (_reader_outputs(events, "query_line_load") or [{}])[0]

    QUERY_TITLE = {
        "check_otif_exposure": "What does it cost us to be late?",
        "check_promo_flexibility": "Can the promotion itself move?",
        "check_coman_availability": "Can a co-manufacturer cover the gap?",
    }

    for e in events:
        k, p = e["kind"], e["payload"]

        if k == "agent_reasoning":
            last_reason = p.get("text")
            continue

        if k == "boundary_ingress":
            steps.append({
                "type": "ingress", "mode": "system", "scene": "conflict in",
                "actor": p.get("target_role"), "partner": None,
                "from": "capacity floor", "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": "A capacity conflict reaches supply planning",
                "body": "Upstream, a 3× promo on the flagship overran <code>NJ-L1</code>. The deterministic capacity floor caught it and routed a <code>CapacityConflict</code> here — no model decided that. Now a rendered agent picks it up.",
                "meta": [["line", p.get("payload", {}).get("line_ref", "NJ-L1")],
                         ["shortfall", str(p.get("payload", {}).get("shortfall_units", 1500))]],
            })

        elif k == "agent_tool_call":
            a = p.get("args") or {}
            tool = a.get("name")
            # one context-gathering beat per key reader tool (first time only)
            if tool == "query_coman_availability" and "coman" not in seen_tool:
                seen_tool.add("coman")
                flag = coman_by_sku.get("TP-FLAG-6OZ", {})
                sec = coman_by_sku.get("TP-SEC-6OZ", {})
                steps.append({
                    "type": "agent", "mode": "agent", "scene": "reading the world",
                    "actor": "supply_planning", "partner": None, "flow": None,
                    "title": "Can a co-man take either competing SKU?",
                    "reasoning": _trim(last_reason),
                    "meta": [
                        [f"co-man TP-FLAG", f"window {flag.get('open_window','?')} < 1500 — gated!"],
                        [f"co-man TP-SEC", f"window {sec.get('open_window','?')} ≥ 1500 — viable"],
                    ],
                })
                last_reason = None
            elif tool == "query_line_load" and "line" not in seen_tool:
                seen_tool.add("line")
                avail = lineload.get("available"); comm = lineload.get("committed_load"); cap = lineload.get("capacity_total")
                steps.append({
                    "type": "agent", "mode": "agent", "scene": "reading the world",
                    "actor": "supply_planning", "partner": None, "flow": None,
                    "title": "How tight is the line, really?",
                    "reasoning": _trim(last_reason),
                    "meta": [["NJ-L1 capacity", str(cap)], ["committed", str(comm)], ["residual!", str(avail)]],
                })
                last_reason = None

        elif k == "query_requested":
            if p.get("flow") in seen_tool:   # one step per distinct query flow
                last_reason = None
                continue
            seen_tool.add(p.get("flow"))
            a = answers.get(p.get("quantum_id"), {})
            steps.append({
                "type": "query", "mode": "agent", "scene": "context assembly",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": QUERY_TITLE.get(p.get("flow"), p.get("flow", "").replace("_", " ")),
                "reasoning": _trim(last_reason),
                "meta": _answer_chips(a),
            })
            last_reason = None

        elif k == "decision_surfaced":
            ctx = p.get("context", {})
            otif = ctx.get("otif_exposure", {}) or {}
            promo = ctx.get("promo_flexibility", {}) or {}
            cm = ctx.get("coman_availability", {}) or {}
            facts = {}
            if otif.get("calculated_penalty") is not None:
                facts["OTIF penalty"] = "$" + format(int(otif["calculated_penalty"]), ",")
            if promo.get("commitment_status"):
                facts["promo"] = promo["commitment_status"]
            if cm.get("open_window") is not None:
                facts["co-man window"] = str(cm["open_window"])
            steps.append({
                "type": "decision", "mode": "agent", "scene": "the decision",
                "actor": p.get("role"), "partner": None, "flow": p.get("playbook"),
                "title": f"{len(p.get('options', []))} viable levers — the ontology ranks none",
                "reasoning": _trim(last_reason, 440),
                "options": p.get("options", []),
                "context": facts,
                "meta": [],
            })
            last_reason = None

        elif k == "handoff_executed" and p.get("flow") in RESOLUTION_FLOWS:
            steps.append({
                "type": "handoff", "mode": "agent", "scene": "the move",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": _human_flow(p.get("flow")),
                "reasoning": _trim(last_reason, 380),
                "meta": [["carries", p.get("quantum_class")]],
            })
            last_reason = None

        elif k == "event_emitted" and "resolved" in p.get("name", ""):
            pl = p.get("payload", {})
            steps.append({
                "type": "resolved", "mode": "system", "scene": "resolved",
                "actor": p.get("by_role"), "partner": None, "flow": p.get("name"),
                "title": f"Resolved — {_human_flow(pl.get('resolution',''))}",
                "body": f"<code>{p.get('name')}</code> is committed to the event log. The agent shifted <b>{pl.get('volume','—')}</b> units of <code>{pl.get('resolved_sku','—')}</code> to a co-manufacturer — freeing the line for the flagship promo. Change the facts and a grounded agent lands elsewhere; the path isn't scripted.",
                "meta": [["resolution", _human_flow(pl.get("resolution", ""))],
                         ["sku", pl.get("resolved_sku", "—")], ["volume", str(pl.get("volume", "—"))]],
            })

        elif k == "handoff_executed" and p.get("flow") == "plan_fulfillment":
            steps.append({
                "type": "handoff", "mode": "agent", "scene": "re-convergence",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": "Re-converge the fulfillment plan",
                "reasoning": _trim(last_reason, 320),
                "meta": [["to", p.get("target_role")]],
            })
            last_reason = None

    return steps


RESOLUTION_FLOWS = {"shift_to_coman", "re_request_production", "request_promo_revision", "allocate_partial_fill"}


def _human_flow(f: str) -> str:
    return {
        "shift_to_coman": "shift to a co-manufacturer",
        "request_promo_revision": "reshape the promo",
        "re_request_production": "re-plan internally",
        "allocate_partial_fill": "allocate a partial fill",
    }.get(f, str(f or "").replace("_", " "))


def _answer_chips(a: dict) -> list[list[str]]:
    if not a:
        return []
    r = a.get("response", {})
    cls = a.get("response_class")
    if cls == "OTIFExposure":
        return [["answer", f"{r.get('retailer')} {r.get('sku')}"], ["late", f"{r.get('delay_days')}d"],
                ["penalty!", "$" + format(int(r.get("calculated_penalty", 0)), ",")]]
    if cls == "PromoFlexibility":
        return [["status", r.get("commitment_status", "?")],
                ["timing", "negotiable" if r.get("can_shift_timing") else "locked"]]
    if cls == "ComanAvailability":
        return [["sku", r.get("sku", "?")], ["window", str(r.get("open_window", "?"))],
                ["moq", str(r.get("moq", "?"))], ["verdict!", "gated for flagship"]]
    return [[k, str(v)] for k, v in list(r.items())[:3]]


def main() -> None:
    trace_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TRACE
    events = _load(trace_path)
    steps = curate(events)

    # the model overview (counts) for the header chip — from the 7-O service
    k = OntologyKnowledgeService()
    summary = k.model_summary()

    roles_in_run = sorted({e["payload"].get("role") for e in events
                           if e["kind"] == "agent_invocation_started" and e["payload"].get("role")})

    data = {
        "scenario": "capacity-resolution",
        "mode": "llm",
        "model": next((e["payload"].get("model") for e in events
                       if e["kind"] == "agent_invocation_started" and e["payload"].get("model")), "gemini"),
        "roles": roles_in_run,
        "boundary_roles": summary["boundary_roles"],
        "counts": summary["counts"],
        "steps": steps,
    }
    payload = json.dumps(data, indent=2, default=str)
    out = HERE / "data.js"
    out.write_text(
        "// AUTO-GENERATED by export_demo_data.py — do not edit by hand.\n"
        f"// Baked from a REAL --mode llm run: {trace_path.name}\n"
        f"window.DEMO_DATA = {payload};\n",
        encoding="utf-8",
    )
    print(f"wrote {out.relative_to(HERE.parent)} from {trace_path.name}")
    print(f"  {len(steps)} replay steps · roles={roles_in_run}")
    for i, s in enumerate(steps, 1):
        print(f"   {i:>2} [{s['mode']:6}] {s['type']:9} {s['title'][:54]}")


if __name__ == "__main__":
    main()
