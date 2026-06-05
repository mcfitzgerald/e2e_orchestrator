/* ============================================================================
   WHIPLASH — run replay. Curate the event log into narrative steps and play
   them back, one clear focus at a time. No framework, no build.
   ============================================================================ */
(function () {
  "use strict";
  const D = window.DEMO_DATA;
  if (!D) { console.error("DEMO_DATA missing — run export_demo_data.py"); return; }
  const ev = D.trace.events;
  const boundary = new Set(D.impact.boundary_roles || []);
  const pretty = s => String(s || "").replace(/_/g, " ");
  const money = n => "$" + Number(n).toLocaleString();
  const $ = id => document.getElementById(id);

  /* ---- human labels for flows / queries ----------------------------- */
  const FLOW = {
    submit_promo_plan: "A trade promotion enters the chain",
    submit_supply_request: "Demand planning forwards the supply request",
    request_production: "Supply planning requests production",
    escalate_capacity_conflict: "Escalate the capacity conflict",
    allocate_partial_fill: "Allocate a partial fill — the holding move",
    re_request_production: "Re-request production on a revised plan",
    request_promo_revision: "Hand the promo to trade to reshape",
    negotiate_promo_with_retailer: "Negotiate the revision with the retailer",
    shift_to_coman: "Shift volume to a co-manufacturer",
    plan_fulfillment: "Re-converge the fulfillment plan",
  };
  const QUERY = {
    check_otif_exposure: "What&rsquo;s our OTIF exposure if the order slips?",
    check_promo_flexibility: "Is the promotion still negotiable?",
    check_coman_availability: "Can a co-manufacturer cover the gap?",
  };
  const OPT_TAG = {
    re_request_production: "internal re-plan",
    request_promo_revision: "reshape the promo",
    shift_to_coman: "external capacity",
    allocate_partial_fill: "holding move",
  };

  /* ---- curate events → steps ---------------------------------------- */
  const answers = {};
  ev.forEach(e => { if (e.kind === "query_answered") answers[e.payload.signal.split(":")[1]] = e.payload; });

  const STEPS = [];
  ev.forEach(e => {
    const p = e.payload;
    if (e.kind === "boundary_ingress") {
      STEPS.push({
        type: "enter", scene: "signal in", actor: p.target_role, partner: p.source_role,
        from: p.source_role, to: p.target_role, flow: p.flow, quantum: p.quantum_class,
        title: FLOW[p.flow] || pretty(p.flow),
        body: `A signal crosses the boundary from <code>${p.source_role}</code> into <code>${p.target_role}</code> &mdash; addressed, validated and routed by the deterministic backbone. No model decides where it goes.`,
        meta: [["quantum", p.quantum_class], ["promo", (p.payload && p.payload.promo_id) || "—"]],
      });
    } else if (e.kind === "handoff_executed") {
      STEPS.push({
        type: "handoff", scene: "handoff", actor: p.target_role, partner: p.source_role,
        from: p.source_role, to: p.target_role, flow: p.flow, quantum: p.quantum_class,
        title: FLOW[p.flow] || pretty(p.flow),
        body: `<code>${p.source_role}</code> hands responsibility to <code>${p.target_role}</code>, carrying a <code>${p.quantum_class}</code>. Commands become events &mdash; the handoff is logged, not just performed.`,
        meta: [["carries", p.quantum_class]],
      });
    } else if (e.kind === "handoff_blocked") {
      const ax = (p.failed_axioms && p.failed_axioms[0]) || {};
      STEPS.push({
        type: "block", scene: "the floor holds", actor: null, partner: null,
        flow: p.flow, quantum: p.quantum_class,
        title: "The capacity floor blocks the plan",
        body: `The <code>${ax.name || "capacity"}</code> axiom fails on <code>${p.flow}</code> &mdash; demand exceeds the line&rsquo;s residual. The orchestrator auto-reroutes to <code>${p.rerouted_to}</code>. A deterministic floor catches the over-capacity plan; no LLM is in this decision.`,
        meta: [["severity", ax.severity || "blocking"], ["reroute", p.rerouted_to]],
      });
    } else if (e.kind === "query_requested") {
      const a = answers[p.quantum_id];
      STEPS.push({
        type: "query", scene: "context assembly", actor: p.source_role, partner: p.target_role,
        from: p.source_role, to: p.target_role, flow: p.flow, quantum: p.quantum_class,
        title: QUERY[p.flow] || pretty(p.flow),
        body: `<code>${p.source_role}</code> reads across domains before choosing &mdash; it asks <code>${p.target_role}</code> and grounds on what comes back. Facts, not assumptions.`,
        meta: answerChips(a),
      });
    } else if (e.kind === "decision_surfaced") {
      STEPS.push({
        type: "decision", scene: "the decision", actor: p.role, partner: null,
        to: p.role, flow: p.playbook,
        title: `${p.options.length} viable levers &mdash; <em>ranked by no&nbsp;one</em>`,
        body: `The <code>${p.playbook}</code> playbook surfaces every structurally-viable action. The ontology states what is <em>possible</em>; it never says which to <em>prefer</em>. That weighing is the agent&rsquo;s.`,
        options: p.options, context: p.context, meta: [],
      });
    } else if (e.kind === "event_emitted" && /resolved/.test(p.name)) {
      const res = (p.payload && p.payload.resolution) || "a grounded lever";
      STEPS.push({
        type: "resolved", scene: "re-convergence", actor: p.by_role, partner: null,
        flow: p.name,
        title: `Resolved via <em>${pretty(res)}</em>`,
        body: `<code>${p.by_role}</code> commits one resolving decision; <code>${p.name}</code> is emitted and the chain re-converges. Change the facts &mdash; a locked promo, an open line &mdash; and a grounded agent lands on a different lever. The path isn&rsquo;t scripted.`,
        meta: [["resolution", pretty(res)]],
      });
    }
  });

  function answerChips(a) {
    if (!a) return [];
    const r = a.response || {};
    switch (a.response_class) {
      case "OTIFExposure":
        return [["answer", `${r.retailer} ${r.sku}`], ["late", `${r.delay_days}d`], ["penalty!", money(r.calculated_penalty)]];
      case "PromoFlexibility":
        return [["status", r.commitment_status], ["timing", r.can_shift_timing ? "negotiable" : "locked"]];
      case "ComanAvailability":
        return [["qualified", r.qualified_for_sku ? "yes" : "no"], ["window", String(r.open_window)], ["moq", String(r.moq)], ["verdict!", "gated out"]];
      default:
        return Object.entries(r).slice(0, 3).map(([k, v]) => [k, String(v)]);
    }
  }

  /* ---- actor rail ---------------------------------------------------- */
  const order = [];
  STEPS.forEach(s => [s.partner, s.actor, s.from, s.to].forEach(r => { if (r && !order.includes(r)) order.push(r); }));
  const rail = $("actors");
  const actorEls = {};
  order.forEach(role => {
    const a = document.createElement("div");
    a.className = "actor" + (boundary.has(role) ? " boundary" : "");
    a.innerHTML =
      `<span class="actor-dot"></span>` +
      `<span class="actor-name">${role}</span>` +
      `<span class="actor-tag">${boundary.has(role) ? "boundary" : "internal"}</span>`;
    rail.appendChild(a);
    actorEls[role] = a;
  });

  /* ---- transport state ---------------------------------------------- */
  const N = STEPS.length;
  let i = 0, playing = false, timer = null;
  const SPEEDS = [1, 1.6, 0.6]; let si = 0;
  const baseDelay = 2600;

  $("scenarioName").textContent = D.trace.scenario;
  $("posTotal").textContent = N;
  const _sp = new URLSearchParams(location.search).get("step");
  if (_sp) i = Math.max(0, Math.min(N - 1, parseInt(_sp, 10) - 1));

  // build ticks
  const track = $("track");
  const ticks = STEPS.map((s, idx) => {
    const t = document.createElement("div");
    t.className = "tick"; t.dataset.type = s.type; t.dataset.i = idx;
    t.addEventListener("click", () => { goto(idx); pause(); });
    track.appendChild(t);
    return t;
  });

  function render() {
    const s = STEPS[i];
    const stage = $("stage");
    stage.dataset.type = s.type;
    $("sceneTag").textContent = s.scene;
    $("stepCount").textContent = `step ${i + 1}`;
    $("posNow").textContent = i + 1;

    // flow line
    const showFlow = !!(s.from || s.to) && s.type !== "decision" && s.type !== "resolved";
    $("cfFrom").classList.toggle("hidden", !showFlow || !s.from);
    $("cfArrow").classList.toggle("hidden", !showFlow);
    $("cfTo").classList.toggle("hidden", !showFlow || !s.to);
    if (showFlow) { $("cfFrom").textContent = s.from || ""; $("cfTo").textContent = s.to || ""; }

    $("cardTitle").innerHTML = s.title;
    $("cardBody").innerHTML = s.body;

    const meta = $("cardMeta"); meta.innerHTML = "";
    (s.meta || []).forEach(([k, v]) => {
      const bang = k.endsWith("!");
      const chip = document.createElement("span");
      chip.className = "chip" + (bang ? "" : " teal");
      chip.innerHTML = `<span class="ck">${k.replace("!", "")}</span><b>${v}</b>`;
      meta.appendChild(chip);
    });

    // decision surface
    const surf = $("surface");
    if (s.type === "decision") {
      surf.hidden = false;
      const chosen = lastResolution();
      const opts = $("surfaceOpts"); opts.innerHTML = "";
      s.options.forEach((o, k) => {
        const isC = o === chosen;
        const d = document.createElement("div"); d.className = "opt" + (isC ? " chosen" : "");
        d.innerHTML =
          `<span class="opt-mark">${isC ? "✓" : String.fromCharCode(65 + k)}</span>` +
          `<span class="opt-name">${o}</span>` +
          `<span class="opt-tag">${isC ? "chosen" : (OPT_TAG[o] || "viable")}</span>`;
        opts.appendChild(d);
      });
      const facts = $("surfaceFacts"); facts.innerHTML = "";
      [["shortfall", (s.context && s.context.shortfall_units) || 1500],
       ["at risk", (s.context && s.context.at_risk_commitment) || "—"]].forEach(([k, v]) => {
        const c = document.createElement("span"); c.className = "chip";
        c.innerHTML = `<span class="ck">${k}</span><b>${v}</b>`; facts.appendChild(c);
      });
    } else {
      surf.hidden = true;
    }

    // actors
    Object.entries(actorEls).forEach(([role, el]) => {
      el.classList.remove("active", "partner", "idle");
      if (role === s.actor) el.classList.add("active");
      else if (role === s.partner) el.classList.add("partner");
      else el.classList.add("idle");
    });

    // ticks
    ticks.forEach((t, idx) => {
      t.classList.toggle("past", idx < i);
      t.classList.toggle("cur", idx === i);
    });
  }

  function lastResolution() {
    const re = ev.find(e => e.kind === "event_emitted" && /resolved/.test(e.payload.name));
    return re && re.payload.payload ? re.payload.payload.resolution : null;
  }

  function goto(n) { i = Math.max(0, Math.min(N - 1, n)); render(); }
  function next() { if (i < N - 1) { i++; render(); } else pause(); }
  function prev() { if (i > 0) { i--; render(); } }

  function play() {
    playing = true; $("btnPlay").textContent = "⏸"; $("btnPlay").classList.add("on");
    clearTimeout(timer);
    const tick = () => {
      if (!playing) return;
      if (i >= N - 1) { pause(); return; }
      next();
      timer = setTimeout(tick, baseDelay / SPEEDS[si]);
    };
    if (i >= N - 1) goto(0);
    timer = setTimeout(tick, baseDelay / SPEEDS[si]);
  }
  function pause() { playing = false; $("btnPlay").textContent = "▶"; $("btnPlay").classList.remove("on"); clearTimeout(timer); }
  function toggle() { playing ? pause() : play(); }

  $("btnPlay").addEventListener("click", toggle);
  $("btnNext").addEventListener("click", () => { next(); pause(); });
  $("btnPrev").addEventListener("click", () => { prev(); pause(); });
  $("btnRestart").addEventListener("click", () => { goto(0); pause(); });
  $("btnSpeed").addEventListener("click", () => { si = (si + 1) % SPEEDS.length; $("btnSpeed").textContent = SPEEDS[si] + "×"; });
  document.addEventListener("keydown", e => {
    if (e.code === "Space") { e.preventDefault(); toggle(); }
    else if (e.code === "ArrowRight") { next(); pause(); }
    else if (e.code === "ArrowLeft") { prev(); pause(); }
    else if (e.code === "Home") { goto(0); pause(); }
  });

  render();
})();
