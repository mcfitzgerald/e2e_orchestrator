/* ============================================================================
   WHIPLASH — render the baked demo data (window.DEMO_DATA) into the console.
   No framework, no build. Two acts: Q1 impact blast-radius, Q2 the run.
   ============================================================================ */
(function () {
  "use strict";
  const D = window.DEMO_DATA;
  if (!D) { console.error("DEMO_DATA missing — run export_demo_data.py"); return; }

  const SVGNS = "http://www.w3.org/2000/svg";
  const KIND = {
    role:     getCss("--k-role"),
    flow:     getCss("--k-flow"),
    entity:   getCss("--k-entity"),
    event:    getCss("--k-event"),
    tool:     getCss("--k-tool"),
    playbook: getCss("--k-playbook"),
  };
  const KIND_LABEL = { role: "roles", flow: "flows", entity: "quanta", event: "events", tool: "reader tools", playbook: "playbooks" };
  function getCss(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function el(tag, cls, txt) { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function svg(tag, attrs) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }

  /* ---------------------------------------------------------------- masthead */
  const c = D.impact.counts;
  document.getElementById("mastMeta").textContent =
    `${c.roles} roles · ${c.flows} flows · ${c.entities} quanta · ${c.playbooks} playbook`;
  document.getElementById("colMid").textContent =
    `${D.impact.affected_count} elements reachable from one TradePromotion`;

  /* ============================================================ Q1 — BLAST */
  const CX = 360, CY = 360;
  const RING = { 1: 108, 2: 177, 3: 246, 4: 314 };
  const OFFSET = { 1: -0.4, 2: 0.25, 3: -0.15, 4: 0.5 };
  const svgEl = document.getElementById("blastSvg");
  const nodes = D.impact.graph.nodes.filter(n => n.depth > 0);
  const center = D.impact.graph.nodes.find(n => n.depth === 0);
  const pos = {}; // id -> {x,y,kind,depth}
  pos[center.id] = { x: CX, y: CY, kind: center.kind, depth: 0 };

  // ring guide circles
  for (const d of [1, 2, 3, 4]) svgEl.appendChild(svg("circle", { class: "ring-line", cx: CX, cy: CY, r: RING[d] }));

  // place nodes: group by depth, cluster by kind, distribute by angle
  const byDepth = { 1: [], 2: [], 3: [], 4: [] };
  nodes.forEach(n => (byDepth[n.depth] || byDepth[4]).push(n));
  for (const d of [1, 2, 3, 4]) {
    const ring = byDepth[d].sort((a, b) => (a.kind + a.id).localeCompare(b.kind + b.id));
    const N = ring.length;
    ring.forEach((n, i) => {
      const ang = (i / N) * Math.PI * 2 + OFFSET[d];
      pos[n.id] = { x: CX + Math.cos(ang) * RING[d], y: CY + Math.sin(ang) * RING[d], kind: n.kind, depth: d, ang };
    });
  }

  // edges (drawn first, under nodes)
  const edgeEls = {};
  const gEdges = svg("g", {});
  svgEl.appendChild(gEdges);
  D.impact.graph.edges.forEach(e => {
    const a = pos[e.source], b = pos[e.target];
    if (!a || !b) return;
    const line = svg("path", { class: "edge", d: `M${a.x.toFixed(1)} ${a.y.toFixed(1)} L${b.x.toFixed(1)} ${b.y.toFixed(1)}` });
    gEdges.appendChild(line);
    edgeEls[e.source + "__" + e.target] = line;
  });

  // core glyph
  const gCore = svg("g", {});
  gCore.appendChild(svg("circle", { class: "core-ring", cx: CX, cy: CY, r: 30 }));
  gCore.appendChild(svg("circle", { class: "core-ring", cx: CX, cy: CY, r: 21 }));
  gCore.appendChild(svg("circle", { class: "core-glyph", cx: CX, cy: CY, r: 7 }));
  svgEl.appendChild(gCore);

  // nodes
  const nodeEls = {};
  const tip = document.getElementById("blastTip");
  const stage = document.querySelector(".blast-stage");
  nodes.forEach(n => {
    const p = pos[n.id];
    const g = svg("g", { class: `node ${n.kind}`, style: `color:${KIND[n.kind]}` });
    g.dataset.id = n.id; g.dataset.kind = n.kind;
    const r = n.kind === "role" ? 6.2 : n.kind === "playbook" ? 6 : 4;
    g.appendChild(svg("circle", { cx: p.x, cy: p.y, r, fill: KIND[n.kind] }));
    if (n.kind === "role" || n.kind === "playbook") {
      const right = Math.cos(p.ang) >= 0;
      const lbl = svg("text", {
        class: "node-label", x: (p.x + (right ? 10 : -10)).toFixed(1), y: (p.y + 3.5).toFixed(1),
        "text-anchor": right ? "start" : "end",
      });
      lbl.textContent = n.id;
      g.appendChild(lbl);
    }
    svgEl.appendChild(g);
    nodeEls[n.id] = g;

    g.addEventListener("mouseenter", () => hoverNode(n, p));
    g.addEventListener("mouseleave", clearHover);
    if (n.kind === "role") g.addEventListener("click", () => inspectRole(n.id));
  });

  function hoverNode(n, p) {
    const path = D.impact.paths[n.id] || [];
    const chain = [center.id, ...path.map(e => e.id)];
    const chainSet = new Set(chain);
    Object.entries(nodeEls).forEach(([id, e]) => e.classList.toggle("dim", !chainSet.has(id)));
    path.forEach(e => { const le = edgeEls[e.from + "__" + e.id]; if (le) le.classList.add("lit"); });
    nodeEls[n.id].classList.add("hot");
    // tooltip
    const rels = path.map(e => `<b>${e.relation.replace(/_/g, " ")}</b> ${e.id}`).join(" → ");
    tip.innerHTML =
      `<span class="tt-kind" style="color:${KIND[n.kind]}">${KIND_LABEL[n.kind] || n.kind}</span><br>` +
      `<span class="tt-name">${n.id}</span>` +
      `<div class="tt-path">${center.id} → ${rels}</div>`;
    tip.style.left = (p.x / 720 * 100) + "%";
    tip.style.top = (p.y / 720 * 100) + "%";
    tip.hidden = false;
  }
  function clearHover() {
    Object.values(nodeEls).forEach(e => e.classList.remove("dim", "hot"));
    Object.values(edgeEls).forEach(e => e.classList.remove("lit"));
    tip.hidden = true;
  }

  // staggered reveal, ring by ring
  function revealBlast() {
    for (const d of [1, 2, 3, 4]) {
      byDepth[d].forEach((n, i) => {
        const e = nodeEls[n.id];
        setTimeout(() => e.classList.add("in"), (d - 1) * 260 + i * 16);
      });
    }
  }

  /* legend + count */
  document.getElementById("impactCount").textContent = D.impact.affected_count;
  document.getElementById("impactNote").textContent = D.impact.note;
  const legend = document.getElementById("blastLegend");
  ["role", "flow", "entity", "event", "tool", "playbook"].forEach(k => {
    const arr = D.impact.affected[k] || [];
    if (!arr.length) return;
    const li = el("li"); li.dataset.kind = k;
    const dot = el("span", "lg-dot"); dot.style.background = KIND[k]; dot.style.color = KIND[k];
    const name = el("span", "lg-name", KIND_LABEL[k]);
    const cnt = el("span", "lg-count", String(arr.length));
    li.append(dot, name, cnt);
    li.addEventListener("mouseenter", () => {
      Object.entries(nodeEls).forEach(([id, e]) => e.classList.toggle("dim", e.dataset.kind !== k));
      li.classList.add("active");
    });
    li.addEventListener("mouseleave", () => { clearHover(); li.classList.remove("active"); });
    legend.appendChild(li);
  });

  /* role inspect */
  const insp = document.getElementById("roleInspect");
  function inspectRole(role) {
    const rv = D.impact.roleviews[role];
    document.getElementById("riName").textContent = role;
    document.getElementById("riBody").textContent = rv ? rv.trim() : "(role view not exported)";
    insp.hidden = false;
    insp.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /* ============================================================ Q2 — RUN */
  const ev = D.trace.events;
  const find = (kind, pred) => ev.find(e => e.kind === kind && (!pred || pred(e)));
  const findAll = (kind, pred) => ev.filter(e => e.kind === kind && (!pred || pred(e)));
  const resp = cls => { const e = ev.find(x => x.kind === "query_answered" && x.payload.response_class === cls); return e ? e.payload.response : null; };

  const otif = resp("OTIFExposure") || {};
  const flex = resp("PromoFlexibility") || {};
  const coman = resp("ComanAvailability") || {};
  const decision = find("decision_surfaced");
  const options = (decision && decision.payload.options) || [];
  const resolvedEv = ev.find(e => e.kind === "event_emitted" && /resolved/.test(JSON.stringify(e.payload)));
  const resolution = resolvedEv ? (resolvedEv.payload.payload && resolvedEv.payload.payload.resolution) || resolvedEv.payload.resolution : null;
  const chosen = resolution || (findAll("handoff_executed").map(e => e.payload.flow).find(f => options.includes(f)));
  const money = n => "$" + Number(n).toLocaleString();

  /* timeline beats — distilled from the 56-event log */
  const beats = [
    {
      tone: "signal", scene: "Scene 1 · ingress",
      title: "A 3× promotion enters the chain",
      body: `Sales aligns the Megalomart promo on <code>TP-FLAG-6OZ</code> through S&OP. One signal crosses the boundary into <code>demand_planning</code> — addressed, validated, routed by the deterministic backbone.`,
    },
    {
      tone: "block", scene: "Scene 4 · the floor holds",
      title: "The capacity floor blocks the plan",
      body: `Full uplift assigned to <code>NJ-L1</code> overruns its residual. The <code>line_capacity_not_exceeded</code> axiom fires and the orchestrator auto-reroutes to escalate — no LLM in that decision.`,
      fact: `<span class="tf">residual <b>5,000</b>/wk</span><span class="tf">demand <b>6,500</b>/wk</span><span class="tf">shortfall <b>1,500</b></span>`,
    },
    {
      tone: "signal", scene: "Scene 5 · context assembly",
      title: "The agent reads across domains",
      body: `Before choosing, <code>supply_planning</code> fans out three queries and grounds on what comes back — penalties, promo terms, external capacity. Facts, not assumptions.`,
      fact:
        `<span class="tf">OTIF risk <b>${otif.calculated_penalty ? money(otif.calculated_penalty) : "—"}</b></span>` +
        `<span class="tf">promo <b>${flex.commitment_status || "—"}</b></span>` +
        `<span class="tf">co-man window <b>${coman.open_window != null ? coman.open_window.toLocaleString() : "—"}</b> &lt; 1,500</span>`,
    },
    {
      tone: "signal", scene: "Scene 5 · decision",
      title: "Four levers surface — ranked by no one",
      body: `The playbook offers <code>${options.length}</code> structurally-viable actions. The ontology states which are <em>possible</em>; it never says which to <em>prefer</em>. That weighing is the agent's. →`,
    },
    {
      tone: "resolved", scene: "Scene 6 · re-convergence",
      title: chosen ? `Resolved via ${pretty(chosen)}` : "Resolved",
      body: `A single resolving decision fires, <code>capacity_resolved</code> is emitted, and <code>plan_fulfillment</code> re-converges the chain on the happy path. One seed → assembly → judgment → resolution.`,
    },
  ];

  const tl = document.getElementById("timeline");
  beats.forEach(b => {
    const li = el("li", "tl-step"); li.dataset.tone = b.tone;
    li.appendChild(el("span", "tl-node"));
    li.appendChild(el("div", "tl-scene", b.scene));
    li.appendChild(el("h3", "tl-title", b.title));
    const body = el("div", "tl-body"); body.innerHTML = b.body; li.appendChild(body);
    if (b.fact) { const f = el("div", "tl-fact"); f.innerHTML = b.fact; li.appendChild(f); }
    tl.appendChild(li);
  });

  /* decision surface */
  const OPT_TAG = {
    re_request_production: "internal re-plan",
    request_promo_revision: "reshape the promo",
    shift_to_coman: "external capacity",
    allocate_partial_fill: "holding move",
  };
  const decOpts = document.getElementById("decOptions");
  options.forEach((o, i) => {
    const isChosen = o === chosen;
    const d = el("div", "opt" + (isChosen ? " chosen" : ""));
    const mark = el("span", "opt-mark", isChosen ? "✓" : String.fromCharCode(65 + i));
    const name = el("span", "opt-name", o);
    const tag = el("span", "opt-tag", isChosen ? "chosen" : (OPT_TAG[o] || "viable"));
    d.append(mark, name, tag);
    decOpts.appendChild(d);
  });

  const ctx = [
    { k: "OTIF exposure", v: otif.retailer ? `<b>${money(otif.calculated_penalty)}</b> — ${otif.retailer} ${otif.sku}, ${otif.delay_days}d late` : "—" },
    { k: "Promo flexibility", v: flex.commitment_status ? `<b>${flex.commitment_status}</b> — ${flex.can_shift_timing ? "timing negotiable" : "locked"}` : "—" },
    { k: "Co-man (flagship)", v: coman.open_window != null ? `window <b>${coman.open_window.toLocaleString()}</b> / MOQ ${coman.moq != null ? coman.moq.toLocaleString() : "—"} — gated out` : "—" },
    { k: "The shortfall", v: `<b>1,500</b>/wk on NJ-L1` },
  ];
  const dc = document.getElementById("decContext");
  ctx.forEach(it => {
    const d = el("div", "dc-item");
    d.appendChild(el("div", "dc-k", it.k));
    const v = el("div", "dc-v"); v.innerHTML = it.v; d.appendChild(v);
    dc.appendChild(d);
  });
  const out = document.getElementById("decOutcome");
  out.innerHTML =
    `<div class="do-eyebrow">outcome — varies with the facts, not a script</div>` +
    `<div class="do-text">This world resolves to <b>${chosen ? pretty(chosen) : "a grounded lever"}</b> — change the facts and a grounded agent moves to a different lever.</div>`;

  /* ---------------------------------------------------------------- close */
  const TENETS = [
    { n: "1", h: "Facts in, judgment out", p: "The ontology declares what is true, legal and possible. The trade-off — which lever, how to split — is the agent's, never a field in the model. (§2: world vs. policy.)" },
    { n: "2", h: "Identity is rendered, not authored", p: "Every role runs on <code>render_role_view(role)</code> — the same structure you can read in the graph above is the agent's prompt. No hand-written per-role logic." },
    { n: "3", h: "Role N+1 costs no code", p: "<code>plant_scheduler</code> and <code>trade</code> dropped in with zero edits to the agent template or its tools. Generality holds — the proof, not the promise." },
    { n: "4", h: "Deterministic where it must be", p: "Routing, validation, the capacity floor — all deterministic. The LLM reasons; it never decides where a quantum goes. Grounded agency on rails." },
  ];
  const tn = document.getElementById("tenets");
  TENETS.forEach(t => {
    const li = el("li", "tenet");
    li.appendChild(el("span", "tenet-n", t.n));
    const b = el("div", "tenet-b");
    b.appendChild(el("h4", null, t.h));
    const p = el("p"); p.innerHTML = t.p; b.appendChild(p);
    li.appendChild(b);
    tn.appendChild(li);
  });

  function pretty(s) { return String(s).replace(/_/g, " "); }

  /* ---------------------------------------------------- scroll observers */
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      if (e.target === svgEl.parentElement) revealBlast();
      if (e.target.classList.contains("timeline")) {
        [...e.target.children].forEach((li, i) => setTimeout(() => li.classList.add("in"), i * 140));
      }
      e.target.classList.add("seen");
      obs.unobserve(e.target);
    });
  }, { threshold: 0.25 });
  io.observe(svgEl.parentElement);
  io.observe(tl);
  document.querySelectorAll(".sec-head, .decision, .close-grid").forEach(n => { n.classList.add("io"); io.observe(n); });
})();
