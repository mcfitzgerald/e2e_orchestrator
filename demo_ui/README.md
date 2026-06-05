# WHIPLASH — run replay (demo UI)

A focused, self-contained **replay** of the most complex scenario (`full-demo` —
the full promo-whiplash run). Press play and watch one promotion ripple across the
supply chain and the agent resolve the conflict, one clear step at a time.

The 56-event log is curated into **11 narrative steps**:

1. a 3× promo enters → `demand_planning`
2. handoff → `supply_planning` (the supply request)
3. **the capacity floor blocks** the over-capacity plan → auto-reroute
4. escalate the capacity conflict
5–7. context assembly — three cross-domain queries (OTIF $7,200 · promo still
   negotiable · co-man gated out)
8. **the decision** — four structurally-viable levers the ontology ranks *none* of
9. allocate a partial fill (the resolving move)
10. **resolved** — `capacity_resolved` emitted
11. re-converge the fulfillment plan

Each step shows who's acting (the actor rail lights up), what's moving (the flow +
quantum), and the grounded facts. The decision step shows the four levers with the
chosen one marked.

## Run it

No build, no server, no API key — the data is baked into `data.js`:

```
open index.html            # double-click works too (file://)
```

Or serve it:

```
python3 -m http.server --directory demo_ui 8000   # → http://localhost:8000/
```

**Controls:** `space` play/pause · `←` `→` step · `Home` restart · click the
scrubber ticks to jump · the `1×` button cycles speed. `?step=N` jumps to a step.

## Regenerate the data

`data.js` is baked from the real seams — a stub run of `full-demo` (the Scene 1→6
event log). Re-bake after changing the scenario, ontology, or world fixture:

```
uv run python demo_ui/export_demo_data.py
```

Stub mode, no API key. (The export also bakes the 7-O `impact_analysis` closure and
every role's rendered view — available in `window.DEMO_DATA.impact` for future use,
not shown by the current replay.)

## Files

| File | What |
|---|---|
| `index.html` | structure |
| `styles.css` | design system (Fraunces · Hanken Grotesk · IBM Plex Mono; editorial-dark) |
| `app.js` | curates the event log into steps + drives the replay/transport |
| `export_demo_data.py` | bakes the trace (+ 7-O impact) into `data.js` |
| `data.js` | auto-generated; do not hand-edit |

## Note

The resolution shown (`allocate_partial_fill`) is the stub's deterministic path; the
**live** agent's lever varies with the facts (see `briefings/phase-a3-live-report.md`).
The replay says this out loud at the resolution step — the point is that the
ontology ranks nothing.
