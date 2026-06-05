# WHIPLASH — run replay (demo UI)

A focused, self-contained **replay of a real `--mode llm` run** (`capacity-resolution`
on gemini-3.5-flash). Press play and watch the agent resolve a capacity conflict one
step at a time — **with its actual reasoning shown**, not a stub.

Why a real run (and why it starts at the conflict): stub mode is scripted and emits
no reasoning, so it can't show "what the agent is thinking." And live `full-demo`
can't be used — a grounded agent sizes the supply request to fit and *dodges* the
conflict (the documented Phase-5 finding). So the conflict is injected, the run is
real, and the replay opens with the deterministic floor handing the conflict to the
agent (one framing line covers the promo origin).

The ~80-event trace is curated (in `export_demo_data.py`) into **10 steps**:

1. **deterministic backbone** — the capacity floor routes a `CapacityConflict` to supply planning
2–3. **agent reasoning** — it reads co-man for both SKUs (flagship gated / secondary viable) and the line load
4–6. **agent reasoning** — three context-assembly queries (promo negotiable · OTIF $7,200 · co-man gated for the flagship)
7. **the decision** — four structurally-viable levers the ontology ranks *none* of
8. **agent reasoning** — shift the secondary SKU's 1,500 units to a co-manufacturer, freeing the line for the flagship
9. **resolved** — `capacity_resolved` committed
10. re-converge the fulfillment plan

Every **agent** step carries a teal *"agent reasoning"* badge, lights up the acting
role in the rail, and shows the agent's **real words**. Every **deterministic
backbone** step (routing, the floor, the event log) is marked *"no LLM in this
step"* — the §2 split, made visible.

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

`data.js` is baked from a captured **real `--mode llm` trace** (`runs/demo-capres.jsonl`
by default). To replay a different real run, capture it and point the export at it:

```
# capture a fresh real run (needs API key / Vertex config):
E2E_MAX_LLM_CALLS=50 E2E_MAX_INVOCATIONS=25 \
  uv run e2e-orchestrator --scenario capacity-resolution --mode llm --log runs/demo-capres.jsonl

# bake it into data.js:
uv run python demo_ui/export_demo_data.py [runs/your-trace.jsonl]
```

The export itself needs no API key — it reads the captured trace.

## Files

| File | What |
|---|---|
| `index.html` | structure |
| `styles.css` | design system (Fraunces · Hanken Grotesk · IBM Plex Mono; editorial-dark) |
| `app.js` | renders the pre-curated steps + drives the replay/transport |
| `export_demo_data.py` | curates a real `--mode llm` trace into `data.js` steps |
| `data.js` | auto-generated; do not hand-edit |

## Note

This run resolved via `shift_to_coman` — the agent's *real* grounded choice (move the
secondary SKU to a co-man, freeing the line for the flagship promo). The lever varies
with the facts across runs (see `briefings/phase-a3-live-report.md`); the replay says
this out loud at the resolution step. The point is that the ontology ranks nothing —
the judgment is the agent's.
