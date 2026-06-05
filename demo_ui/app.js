/* ============================================================================
   WHIPLASH — run replay. Plays back a REAL --mode llm run, step by step, with
   the agent's actual reasoning. Steps are pre-curated in export_demo_data.py;
   this just renders them + drives the transport. No framework, no build.
   ============================================================================ */
(function () {
  "use strict";
  const D = window.DEMO_DATA;
  if (!D || !D.steps) { console.error("DEMO_DATA.steps missing — run export_demo_data.py"); return; }
  const STEPS = D.steps;
  const N = STEPS.length;
  const boundary = new Set(D.boundary_roles || []);
  const $ = id => document.getElementById(id);
  const pretty = s => String(s || "").replace(/_/g, " ");
  const escapeHtml = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  const OPT_TAG = {
    re_request_production: "internal re-plan",
    request_promo_revision: "reshape the promo",
    shift_to_coman: "external capacity",
    allocate_partial_fill: "holding move",
  };
  const chosen = (() => {
    const r = STEPS.find(s => s.type === "resolved");
    if (!r) return null;
    const m = (r.title.match(/—\s*(.+)$/) || [])[1];
    // map back the resolution to its flow name from the handoff step
    const h = STEPS.find(s => s.type === "handoff" && s.scene === "the move");
    return h ? h.flow : null;
  })();

  /* ---- header ------------------------------------------------------- */
  $("scenarioName").textContent = `${D.scenario} · ${D.mode} · ${D.model}`;
  $("posTotal").textContent = N;

  /* ---- actor rail --------------------------------------------------- */
  const order = [];
  STEPS.forEach(s => [s.partner, s.actor, s.from, s.to].forEach(r => {
    if (r && !order.includes(r) && r !== "capacity floor") order.push(r);
  }));
  const rail = $("actors");
  const actorEls = {};
  order.forEach(role => {
    const a = document.createElement("div");
    a.className = "actor" + (boundary.has(role) ? " boundary" : "");
    a.innerHTML =
      `<span class="actor-dot"></span>` +
      `<span class="actor-name">${role}</span>` +
      `<span class="actor-tag" data-role="${role}">${boundary.has(role) ? "boundary" : "internal"}</span>`;
    rail.appendChild(a);
    actorEls[role] = a;
  });

  /* ---- transport state ---------------------------------------------- */
  let i = 0, playing = false, timer = null;
  const SPEEDS = [1, 1.6, 0.6]; let si = 0;
  const baseDelay = 3200;

  const track = $("track");
  const ticks = STEPS.map((s, idx) => {
    const t = document.createElement("div");
    t.className = "tick"; t.dataset.type = s.type; t.dataset.i = idx;
    t.title = s.title;
    t.addEventListener("click", () => { goto(idx); pause(); });
    track.appendChild(t);
    return t;
  });

  const _sp = new URLSearchParams(location.search).get("step");
  if (_sp) i = Math.max(0, Math.min(N - 1, parseInt(_sp, 10) - 1));

  function render() {
    const s = STEPS[i];
    const stage = $("stage");
    stage.dataset.type = s.type;
    stage.dataset.mode = s.mode;
    $("sceneTag").textContent = s.scene;
    $("stepCount").textContent = `step ${i + 1}`;
    $("posNow").textContent = i + 1;

    // mode badge — the load-bearing distinction: agent reasoning vs deterministic backbone
    const badge = $("modeBadge");
    if (s.mode === "agent") {
      badge.className = "mode-badge agent";
      badge.innerHTML = `<span class="mb-dot"></span><span class="mb-label">agent reasoning</span><span class="mb-role">${s.actor}</span>`;
    } else {
      badge.className = "mode-badge system";
      badge.innerHTML = `<span class="mb-dot"></span><span class="mb-label">deterministic backbone</span><span class="mb-role">no LLM in this step</span>`;
    }

    // flow line
    const showFlow = !!(s.from || s.to);
    $("cfFrom").classList.toggle("hidden", !showFlow || !s.from);
    $("cfArrow").classList.toggle("hidden", !showFlow);
    $("cfTo").classList.toggle("hidden", !showFlow || !s.to);
    if (showFlow) { $("cfFrom").textContent = s.from || ""; $("cfTo").textContent = s.to || ""; }

    $("cardTitle").innerHTML = s.title;

    // body: system steps carry a descriptive body; agent steps carry the CoT
    const body = $("cardBody");
    if (s.body) { body.hidden = false; body.innerHTML = s.body; } else { body.hidden = true; }

    // chain of thought (the agent's FULL real reasoning + actions, scrollable)
    const cot = $("cot");
    const thoughts = s.thoughts || [];
    if (thoughts.length) {
      cot.hidden = false;
      $("cotWho").textContent = s.actor;
      const thread = $("cotThread"); thread.innerHTML = "";
      thoughts.forEach(t => {
        const row = document.createElement("div");
        row.className = "cot-row " + (t.t === "think" ? "think" : "act");
        row.innerHTML = t.t === "think"
          ? `<span class="cot-q">“</span>${escapeHtml(t.text)}<span class="cot-q">”</span>`
          : `<span class="cot-arrow">→</span>${escapeHtml(t.text)}`;
        thread.appendChild(row);
      });
      thread.scrollTop = 0;
    } else {
      cot.hidden = true;
    }

    // the thesis this step proves
    const proof = $("proof");
    if (s.proof) {
      proof.hidden = false;
      $("proofThesis").textContent = s.proof.thesis;
      $("proofNote").textContent = s.proof.note;
    } else {
      proof.hidden = true;
    }

    // meta chips
    const meta = $("cardMeta"); meta.innerHTML = "";
    (s.meta || []).forEach(([k, v]) => {
      const bang = k.endsWith("!");
      const chip = document.createElement("span");
      chip.className = "chip" + (bang ? " hot" : "");
      chip.innerHTML = `<span class="ck">${k.replace("!", "")}</span><b>${v}</b>`;
      meta.appendChild(chip);
    });

    // decision surface
    const surf = $("surface");
    if (s.type === "decision" && s.options) {
      surf.hidden = false;
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
      Object.entries(s.context || {}).forEach(([k, v]) => {
        const c = document.createElement("span"); c.className = "chip";
        c.innerHTML = `<span class="ck">${pretty(k)}</span><b>${v}</b>`; facts.appendChild(c);
      });
    } else {
      surf.hidden = true;
    }

    // actors
    Object.entries(actorEls).forEach(([role, el]) => {
      el.classList.remove("active", "partner", "idle", "reasoning");
      const tag = el.querySelector(".actor-tag");
      tag.textContent = boundary.has(role) ? "boundary" : "internal";
      if (role === s.actor) {
        el.classList.add("active");
        if (s.mode === "agent") { el.classList.add("reasoning"); tag.textContent = "reasoning…"; }
      } else if (role === s.partner) {
        el.classList.add("partner");
      } else {
        el.classList.add("idle");
      }
    });

    // ticks
    ticks.forEach((t, idx) => {
      t.classList.toggle("past", idx < i);
      t.classList.toggle("cur", idx === i);
    });
  }

  function goto(n) { i = Math.max(0, Math.min(N - 1, n)); render(); }
  function next() { if (i < N - 1) { i++; render(); } else pause(); }
  function prev() { if (i > 0) { i--; render(); } }

  function play() {
    if (i >= N - 1) goto(0);
    playing = true; $("btnPlay").textContent = "⏸";
    clearTimeout(timer);
    const tick = () => {
      if (!playing) return;
      if (i >= N - 1) { pause(); return; }
      next();
      timer = setTimeout(tick, baseDelay / SPEEDS[si]);
    };
    timer = setTimeout(tick, baseDelay / SPEEDS[si]);
  }
  function pause() { playing = false; $("btnPlay").textContent = "▶"; clearTimeout(timer); }
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
