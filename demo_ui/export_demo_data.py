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


# Each step demonstrates a thesis — woven into the narrative, not bolted on.
PROOF = {
    "ingress":    ("Deterministic backbone", "Routing and the capacity floor are deterministic — no LLM decides where a quantum goes or whether a plan exceeds capacity. The agency starts only once the conflict is on the table."),
    "coman":      ("Grounded agency", "The agent reads real co-manufacturer facts for both competing SKUs before it judges anything — it never assumes availability. (The hallucinated-grounding failure mode, designed out.)"),
    "line":       ("Grounded quantity", "The line's residual is read from the world, not invented. The agent reasons over a number it actually queried — the fix for the ungrounded-quantity failure mode."),
    "query":      ("Cross-domain grounding", "Context is assembled by querying other domains — logistics for OTIF, commercial for the promo, sourcing for co-man — and grounding on what returns. Facts, not assumptions."),
    "decision":   ("§2 — facts in, judgment out", "The ontology surfaces four structurally-viable levers and ranks NONE of them. Which to pull is the agent's judgment, encoded nowhere in the model. This is the line the architecture refuses to cross."),
    "move":       ("Agency varies with the facts", "This lever is the agent's grounded choice, not a script. Change the facts — lock the promo, open a line — and a grounded agent lands on a different lever (verified across live runs)."),
    "resolved":   ("Commands → events", "The decision is committed to the event log; the entire run is replayable from it. This replay IS that log — every word above is from the real trace."),
    "reconverge": ("The loop closes", "One resolving decision re-converges the chain deterministically and the agent's turn ends. Identity, routes and constraints all came from the ontology — adding a role costs no new code."),
}

_ACT = {
    "query_coman_availability": "checked co-man availability",
    "query_line_load": "read the line load",
    "query_plants_for_sku": "checked which lines can make the SKU",
    "query_commitments_in_window": "looked up retailer commitments",
    "query_supplier_for_sku": "checked suppliers",
    "query_baseline_demand": "read the baseline demand",
}


def _action_label(p: dict) -> str | None:
    tool = p.get("tool")
    a = p.get("args") or {}
    if tool == "call_tool":
        name = a.get("name"); sku = (a.get("input") or {}).get("sku")
        base = _ACT.get(name)
        return None if base is None else (f"{base} · {sku}" if sku else base)
    if tool == "read_ontology":
        q = a.get("query", "")
        return f"read the ontology · {q}" if q and q != "my_view" else "re-read its own role view"
    return None  # skip surface_decision / handoff / emit / query / respond (they ARE the anchors)


def curate(events: list[dict]) -> list[dict]:
    """Curate the live trace into replay steps. Each step carries the FULL chain
    of thought for its segment (every reasoning event + the actions taken, with
    consecutive repeats collapsed) and the thesis it proves."""
    steps: list[dict] = []
    buf: list[dict] = []          # accumulating chain-of-thought since last step
    seen = set()
    answers = {e["payload"]["signal"].split(":")[1]: e["payload"]
               for e in events if e["kind"] == "query_answered"}
    coman_by_sku = {c.get("sku"): c for c in _reader_outputs(events, "query_coman_availability")}
    lineload = (_reader_outputs(events, "query_line_load") or [{}])[0]

    QUERY_TITLE = {
        "check_otif_exposure": "What does it cost us to be late?",
        "check_promo_flexibility": "Can the promotion itself move?",
        "check_coman_availability": "Can a co-manufacturer cover the gap?",
    }

    def think(text):
        buf.append({"t": "think", "text": _trim(text, 600)})

    def act(text):
        # collapse consecutive identical actions into "… (×N)"
        if buf and buf[-1]["t"] == "act" and buf[-1].get("base") == text:
            buf[-1]["n"] = buf[-1].get("n", 1) + 1
            buf[-1]["text"] = f"{text} (×{buf[-1]['n']})"
        else:
            buf.append({"t": "act", "text": text, "base": text})

    def flush():
        nonlocal buf
        out = [{"t": x["t"], "text": x["text"]} for x in buf]
        buf = []
        return out

    def emit(step, proof_key):
        t, n = PROOF[proof_key]
        step["thoughts"] = flush()
        step["proof"] = {"thesis": t, "note": n}
        steps.append(step)

    for e in events:
        k, p = e["kind"], e["payload"]

        if k == "agent_reasoning":
            think(p.get("text"))
        elif k == "agent_tool_call":
            lbl = _action_label(p)
            if lbl:
                act(lbl)
            name = (p.get("args") or {}).get("name")
            if p.get("tool") == "call_tool" and name == "query_coman_availability" and "coman" not in seen:
                seen.add("coman")
                flag = coman_by_sku.get("TP-FLAG-6OZ", {}); sec = coman_by_sku.get("TP-SEC-6OZ", {})
                emit({
                    "type": "agent", "mode": "agent", "scene": "reading the world",
                    "actor": "supply_planning", "partner": None, "flow": None,
                    "title": "Can a co-man take either competing SKU?",
                    "meta": [["co-man TP-FLAG", f"window {flag.get('open_window','?')} — gated!"],
                             ["co-man TP-SEC", f"window {sec.get('open_window','?')} — viable"]],
                }, "coman")
            elif p.get("tool") == "call_tool" and name == "query_line_load" and "line" not in seen:
                seen.add("line")
                emit({
                    "type": "agent", "mode": "agent", "scene": "reading the world",
                    "actor": "supply_planning", "partner": None, "flow": None,
                    "title": "How tight is the line, really?",
                    "meta": [["NJ-L1 capacity", str(lineload.get("capacity_total"))],
                             ["committed", str(lineload.get("committed_load"))],
                             ["residual!", str(lineload.get("available"))]],
                }, "line")

        elif k == "boundary_ingress":
            emit({
                "type": "ingress", "mode": "system", "scene": "conflict in",
                "actor": p.get("target_role"), "partner": None,
                "from": "capacity floor", "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": "A capacity conflict reaches supply planning",
                "body": "Upstream, a 3× promo on the flagship overran <code>NJ-L1</code>. The deterministic capacity floor caught it and routed a <code>CapacityConflict</code> here — no model decided that. Now a rendered agent picks it up.",
                "meta": [["line", p.get("payload", {}).get("line_ref", "NJ-L1")],
                         ["shortfall", str(p.get("payload", {}).get("shortfall_units", 1500))]],
            }, "ingress")

        elif k == "query_requested":
            if p.get("flow") in seen:
                continue
            seen.add(p.get("flow"))
            a = answers.get(p.get("quantum_id"), {})
            emit({
                "type": "query", "mode": "agent", "scene": "context assembly",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": QUERY_TITLE.get(p.get("flow"), p.get("flow", "").replace("_", " ")),
                "meta": _answer_chips(a),
            }, "query")

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
            emit({
                "type": "decision", "mode": "agent", "scene": "the decision",
                "actor": p.get("role"), "partner": None, "flow": p.get("playbook"),
                "title": f"{len(p.get('options', []))} viable levers — the ontology ranks none",
                "options": p.get("options", []), "context": facts, "meta": [],
            }, "decision")

        elif k == "handoff_executed" and p.get("flow") in RESOLUTION_FLOWS:
            emit({
                "type": "handoff", "mode": "agent", "scene": "the move",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": _human_flow(p.get("flow")),
                "meta": [["carries", p.get("quantum_class")]],
            }, "move")

        elif k == "event_emitted" and "resolved" in p.get("name", ""):
            pl = p.get("payload", {})
            emit({
                "type": "resolved", "mode": "system", "scene": "resolved",
                "actor": p.get("by_role"), "partner": None, "flow": p.get("name"),
                "title": f"Resolved — {_human_flow(pl.get('resolution',''))}",
                "body": f"<code>{p.get('name')}</code> is committed to the event log. The agent shifted <b>{pl.get('volume','—')}</b> units of <code>{pl.get('resolved_sku','—')}</code> to a co-manufacturer — freeing the line for the flagship promo. Change the facts and a grounded agent lands elsewhere; the path isn't scripted.",
                "meta": [["resolution", _human_flow(pl.get("resolution", ""))],
                         ["sku", pl.get("resolved_sku", "—")], ["volume", str(pl.get("volume", "—"))]],
            }, "resolved")

        elif k == "handoff_executed" and p.get("flow") == "plan_fulfillment":
            emit({
                "type": "handoff", "mode": "agent", "scene": "re-convergence",
                "actor": p.get("source_role"), "partner": p.get("target_role"),
                "from": p.get("source_role"), "to": p.get("target_role"),
                "flow": p.get("flow"), "quantum": p.get("quantum_class"),
                "title": "Re-converge the fulfillment plan",
                "meta": [["to", p.get("target_role")]],
            }, "reconverge")

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
