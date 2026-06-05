# WHIPLASH — the demo console (Phase C / Phase 8)

A single-page, self-contained demo that answers the CSCO's two questions by
*showing* them — built on the real ontology + orchestrator, not slideware.

- **Q1 — "what is an ontology, and is it legible?"** An impact **blast radius**:
  *"if Megalomart's promo slips a week, who's affected?"* answered by traversing
  the model with the 7-O `impact_analysis` — the whole resolution cast lights up
  from one `TradePromotion`. Hover any node to trace *why* it's reachable; click a
  role to read the exact ontology-rendered prompt the agent runs on.
- **Q2 — "what is the agentic strategy?"** The run: one promotion enters, the
  deterministic capacity floor blocks an over-capacity plan, the agent assembles
  cross-domain facts, and a **decision surface** presents four structurally-viable
  levers the ontology *ranks none of* — grounded judgment on rails.

## Run it

The data is baked into `data.js` (`window.DEMO_DATA`), so there's **no build and
no server required** — just open the file:

```
open index.html            # macOS — double-click also works (file://)
```

Or serve it (identical result; avoids any browser file:// quirks):

```
python3 -m http.server --directory demo_ui 8000
# → http://localhost:8000/index.html
```

No Node, no npm, no API key. Fonts load from Google Fonts (online); everything
else is local.

## Regenerate the data

`data.js` is produced from the **real seams** — a stub run of the full
promo-whiplash narrative (the Scene 1→6 event log) and the 7-O knowledge service
(`impact_analysis` + model summary + the resolution playbook + every affected
role's rendered view). Re-bake it after changing the scenario, the ontology, or
the world fixture:

```
uv run python demo_ui/export_demo_data.py
```

Stub mode, no API key. It writes `demo_ui/data.js`.

## Files

| File | What |
|---|---|
| `index.html` | structure + framing copy |
| `styles.css` | the design system (Fraunces · Hanken Grotesk · IBM Plex Mono; editorial-dark) |
| `app.js` | renders `window.DEMO_DATA` — the blast-radius SVG, the run timeline, the decision surface |
| `export_demo_data.py` | bakes the trace + 7-O impact into `data.js` |
| `data.js` | auto-generated; do not hand-edit |

## Notes

- The resolution shown (`allocate_partial_fill`) is the stub's deterministic path;
  the **live** agent's lever varies with the facts (see the balanced/locked
  scenarios and `briefings/phase-a3-live-report.md`). The decision-surface copy
  says this out loud — the point is that the ontology ranks nothing.
- Everything on screen traces to something real: the 61-element closure is the
  actual `impact_analysis` output; the facts in the decision surface are the
  actual cross-domain query responses from the run.
