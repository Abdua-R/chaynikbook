/* viz.js: the chart and panel library of a chaynikbook (kit), generalized from the MarketResearcher explainer.

   A book's own panel types live in panels_<name>.js files, which build.py concatenates after this one; each calls
   PANELS.register(name, (host, o) => { ... }, "what to watch when the controls move") and draws with window.VIZ.
   Charts are plain SVG with every mark inside a clipped group, which verify_render.py checks; axes stay fixed while
   the controls move (fixedAxes). Colour carries one meaning everywhere (style.css chart roles: main, alt, ref, and
   the book colours at the end of style.css). Labels sit on the marks they name. */
(function () {
  "use strict";
  const D = window["{{DATA_GLOBAL}}"], CUR = (D.book && D.book.currency) || "";
  const NS = "http://www.w3.org/2000/svg";
  window.__axesReady = true;  // false while a sweep is queued (sweepAxes), so a page whose panels all opt out still reads ready
  const PAD = { l: 56, r: 18, t: 34, b: 40 };
  let clipId = 0;

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function div(cls, parent, html) {
    const d = document.createElement("div");
    if (cls) d.className = cls;
    if (html !== undefined) d.innerHTML = html;
    if (parent) parent.appendChild(d);
    return d;
  }

  // the build's number formats (build.py FORMATS), so a panel and the prose print alike
  const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
  function group(x, nd) {
    const s = Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: nd || 0, maximumFractionDigits: nd || 0 });
    return (x < 0 && Number(s.replace(/,/g, "")) !== 0 ? "−" : "") + s;
  }
  function sci2(x, nd) {
    if (x === 0) return "0";
    nd = nd || 1;
    let e = Math.floor(Math.log10(Math.abs(x))), m = Math.round(x / 10 ** e * 10 ** nd) / 10 ** nd;
    if (Math.abs(m) >= 10) { m /= 10; e += 1; }
    return m.toFixed(nd).replace("-", "−") + " × 10" + String(e).split("").map((c) => SUP[c]).join("");
  }
  const F = {
    int: (x) => group(x), sum: (x) => group(x) + CUR, sum2: (x) => group(x, 2) + CUR, num2: (x) => group(x, 2), pct1: (x) => (100 * x).toFixed(1).replace("-", "−") + "%", pct0: (x) => (100 * x).toFixed(0).replace("-", "−") + "%", pct2: (x) => (100 * x).toFixed(2).replace("-", "−") + "%",
    sci2, sci4: (x) => sci2(x, 3), fix1: (x) => x.toFixed(1), fix2: (x) => x.toFixed(2), fix3: (x) => x.toFixed(3).replace("-", "−"), fix4: (x) => x.toFixed(4), fix8: (x) => x.toFixed(8).replace("-", "−"), pct3: (x) => (100 * x).toFixed(3).replace("-", "−") + "%",
    sig3: (x) => String(+x.toPrecision(3)),
  };
  function fmt(x, f) {
    if (x === null || x === undefined || Number.isNaN(x)) return "none";
    if (!Number.isFinite(x)) return x > 0 ? "unbounded" : "unbounded below";
    return F[f](x);
  }
  const signed = (x, f) => (x > 0 ? "+" : "") + fmt(x, f);
  /* The table view of a panel: a drawing hands its numbers, already printed the way its labels print
     them, to the panel frame (mount), one section per drawing. */
  function tableOf(host, cap, head, rows) {
    const p = host.closest(".panel");
    if (p && p._table) p._table(cap, head, rows);
  }
  const kfmt = (v) => (v === 0 ? "0" : group(v / 1000) + "k");
  const kfmt1 = (v) => (Math.abs(v) < 1000 ? group(v) : (v / 1000).toFixed(Math.abs(v) < 10000 ? 1 : 0).replace("-", "−") + "k");

  function niceStep(span, n) {
    const raw = span / Math.max(1, n), p = 10 ** Math.floor(Math.log10(raw)), m = raw / p;
    return (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p;
  }
  function autoTicks(a, b, n) {
    const s = niceStep(b - a, n), out = [];
    for (let v = Math.ceil(a / s - 1e-9) * s; v <= b + Math.abs(s) * 1e-9; v += s) out.push(Math.abs(v) < Math.abs(s) * 1e-9 ? 0 : v);
    return out;
  }
  function logTicks(a, b) {
    const out = [];
    for (let e = Math.floor(Math.log10(a)); e <= Math.ceil(Math.log10(b)); e++) {
      for (const m of [1, 2, 5]) { const v = m * 10 ** e; if (v >= a * 0.999 && v <= b * 1.001) out.push(v); }
    }
    return out;
  }
  const plainTick = (v) => { const a = Math.abs(v); return a >= 1000 ? group(v) : String(+v.toPrecision(4)).replace("-", "−"); };
  const textW = (s, px) => String(s).length * (px || 12) * 0.58;

  /* One chart frame: axes, gridlines, axis titles and a clipped group to draw into. The y title sits
     above the axis, horizontal, so it reads without turning the head. */
  function frame(host, o) {
    const box = div("chart", host);
    o = fixedAxes(host, box, o);
    const W = Math.max(320, Math.round(box.clientWidth || 600)), H = o.height || 270;
    const pad = Object.assign({}, PAD, o.pad || {});
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.label || "" }, box);
    const x0 = pad.l, x1 = W - pad.r, y0 = H - pad.b, y1 = pad.t;
    const L = o.xlog ? (v) => Math.log10(Math.max(v, o.xmin)) : (v) => v;
    const sx = (v) => x0 + (L(v) - L(o.xmin)) / ((L(o.xmax) - L(o.xmin)) || 1) * (x1 - x0);
    const sy = (v) => y0 - (v - o.ymin) / ((o.ymax - o.ymin) || 1) * (y0 - y1);
    const id = "clip" + (++clipId);
    const cp = el("clipPath", { id }, el("defs", {}, svg));
    el("rect", { x: x0, y: y1 - 1, width: x1 - x0, height: y0 - y1 + 2 }, cp);
    const yf = o.yfmt || plainTick, xf = o.xfmt || plainTick;
    for (const v of o.yticks || autoTicks(o.ymin, o.ymax, o.ny || 5)) {
      el("line", { x1: x0, x2: x1, y1: sy(v), y2: sy(v), class: "gridline" }, svg);
      el("text", { x: x0 - 7, y: sy(v) + 4, "text-anchor": "end", class: "tick" }, svg).textContent = yf(v);
    }
    for (const t of o.xticks || (o.xlog ? logTicks(o.xmin, o.xmax) : autoTicks(o.xmin, o.xmax, o.nx || 6))) {
      const [v, s] = Array.isArray(t) ? t : [t, xf(t)];
      el("text", { x: sx(v), y: y0 + 17, "text-anchor": "middle", class: "tick" }, svg).textContent = s;
    }
    el("line", { x1: x0, x2: x1, y1: y0, y2: y0, class: "baseline" }, svg);
    if (o.xlabel) el("text", { x: (x0 + x1) / 2, y: H - 4, "text-anchor": "middle", class: "axtitle" }, svg).textContent = o.xlabel;
    if (o.ylabel) el("text", { x: 4, y: y1 - 18, class: "axtitle" }, svg).textContent = o.ylabel;
    const g = el("g", { "clip-path": `url(#${id})` }, svg);
    const fr = { svg, g, sx, sy, x0, x1, y0, y1, W, H, o, tags: [] };
    if (o.ymin < 0 && o.ymax > 0 && o.zero !== false) el("line", { x1: x0, x2: x1, y1: sy(0), y2: sy(0), class: "zeroline" }, g);
    return fr;
  }

  /* Axes that stay put while the controls move, so the curves move instead. When a panel mounts, sweepAxes
     draws it at the ends and quarter points of every slider, every option of its dropdowns and, with up to four
     sliders, every corner, and keeps for each chart the widest range any of those drawings asked for, within
     the cap AX_STRETCH sets around the base view. Later
     drawings use that range, widened only if a drawing needs more (a button that adds draws, say). A chart is
     known by its place among the panel's charts; a dropdown marked data-axes="own" (another
     candidate, a horizon, a zoom, another view) keeps a range per option, swept when the reader first picks
     it; frame({stretch: k}) changes the cap for one chart and frame({free: true}) opts it out. */
  // ponytail: a slider can widen an axis to at most the base view's span plus this share of it on each side
  // (2.5 times in all), so a curve pushed further runs off the chart instead of flattening the base view
  const AX_STRETCH = 0.75;
  function fixedAxes(host, box, o) {
    const elm = host.closest && host.closest("[data-axes]"), ax = elm && elm._axes;
    if (!ax || o.free) return o;
    const own = [...elm.querySelectorAll('select[data-axes="own"]')].map((s) => s.value).join(",");
    const k = [own, [...elm.querySelectorAll(".chart")].indexOf(box), o.xlog ? 1 : 0].join("|");
    const want = [o.xmin, o.xmax, o.ymin, o.ymax];
    if (!want.every(Number.isFinite)) return o;
    const grow = (r) => r ? [Math.min(r[0], want[0]), Math.max(r[1], want[1]), Math.min(r[2], want[2]), Math.max(r[3], want[3])] : want;
    // the base view: the drawings with every slider at its base value (any dropdown option)
    const rb = elm._rangeBase, atBase = !rb || [...rb].every(([c, v]) => !c.isConnected || c.value === v);
    if (!elm._axesBase.has(k) || (elm._sweeping && atBase)) elm._axesBase.set(k, grow(elm._axesBase.get(k)));
    const u = grow(ax.get(k)), b = elm._axesBase.get(k);
    const st = o.stretch === undefined ? AX_STRETCH : o.stretch;
    const sx = (b[1] - b[0]) * st, sy = (b[3] - b[2]) * st;
    const c = [Math.max(u[0], b[0] - sx), Math.min(u[1], b[1] + sx), Math.max(u[2], b[2] - sy), Math.min(u[3], b[3] + sy)];
    ax.set(k, c);
    return elm._sweeping ? o : Object.assign({}, o, { xmin: c[0], xmax: c[1], ymin: c[2], ymax: c[3] });
  }
  // The sweep runs after load in slices of about 30 ms, panel by panel in page order, so it never holds up
  // the page. If the reader touches a panel before its sweep is done, the sweep finishes at once, puts the
  // controls back to their base values, and the reader's change then lands on the fixed axes.
  const AXQ = [];
  let axTimer = 0;
  function fireCtl(elm, c, v, reset) {
    elm._firing = true;
    try {
      c.value = v;
      c.dispatchEvent(c.tagName === "SELECT" ? new Event("change", { bubbles: true })
        : new CustomEvent("input", { bubbles: true, detail: { reset: !!reset } }));
    } finally { elm._firing = false; }
  }
  function* sweepSteps(elm) {
    const ownSel = () => elm.querySelectorAll('select[data-axes="own"]');
    const shared = () => [...elm.querySelectorAll('input[type="range"], select:not([data-axes="own"])')];
    if (!shared().length) return;  // a panel whose only control picks its own axes has nothing to sweep
    const ownBase = [...ownSel()].map((s) => s.value);
    const combos = [ownBase];
    elm._sweptOwn.add(ownBase.join(","));
    const few = (xs, n) => xs.length <= n ? xs : [...Array(n).keys()].map((i) => xs[Math.round(i * (xs.length - 1) / (n - 1))]);
    elm._sweeping = true;
    try {
      for (const combo of few(combos, 12)) {
        combo.forEach((v, i) => { const s = ownSel()[i]; if (s && s.value !== v) fireCtl(elm, s, v); });
        // a dropdown may rebuild the controls, so look them up after it
        const ctl = shared(), base = ctl.map((c) => c.value);
        elm._rangeBase = new Map(ctl.filter((c) => c.tagName === "INPUT").map((c) => [c, c.value]));
        const ranges = ctl.filter((c) => c.tagName === "INPUT"), sels = ctl.filter((c) => c.tagName === "SELECT");
        const opts = (c) => few([...c.options].map((op) => op.value), 8);
        const at = (c, t) => String(+c.min + t * (c.max - c.min));
        // the ends of each control first, then the corners of up to four sliders, then the quarter points
        const settings = [];
        ctl.forEach((c, i) => (c.tagName === "SELECT" ? opts(c) : [c.min, c.max]).forEach((v) => settings.push({ [i]: v })));
        if (ranges.length && ranges.length <= 4) {
          for (let m = 0; m < 1 << ranges.length; m++) {
            const s = {};
            ranges.forEach((c, j) => { s[ctl.indexOf(c)] = (m >> j) & 1 ? c.max : c.min; });
            settings.push(s);
            sels.forEach((sc) => opts(sc).forEach((v) => settings.push(Object.assign({}, s, { [ctl.indexOf(sc)]: v }))));
          }
        }
        ranges.forEach((c) => [0.25, 0.5, 0.75].forEach((q) => settings.push({ [ctl.indexOf(c)]: at(c, q) })));
        for (const s of settings) {
          ctl.forEach((c, i) => { const v = String(i in s ? s[i] : base[i]); if (c.isConnected && c.value !== v) fireCtl(elm, c, v); });
          yield;
        }
        ctl.forEach((c, i) => { if (c.isConnected && c.value !== base[i]) fireCtl(elm, c, base[i], true); });
      }
    } finally {
      elm._sweeping = false;
      ownBase.forEach((v, i) => { const s = ownSel()[i]; if (s && s.value !== v) fireCtl(elm, s, v); });
      // draw the base once more, now on the fixed axes
      shared().forEach((c) => fireCtl(elm, c, c.value, true));
    }
  }
  function finishSweep(elm) {
    const it = elm._sweep;
    if (!it) return;
    elm._sweep = null;
    const k = AXQ.indexOf(elm);
    if (k >= 0) AXQ.splice(k, 1);
    try { while (!it.next().done); } catch (e) { /* the ranges gathered so far stand */ }
    if (!AXQ.length) window.__axesReady = true;
  }
  function pumpAxes() {
    const t0 = performance.now();
    while (AXQ.length && performance.now() - t0 < 30) {
      const elm = AXQ[0];
      let r;
      try { r = elm._sweep.next(); } catch (e) { r = { done: true }; }
      if (r.done) { elm._sweep = null; AXQ.shift(); }
    }
    axTimer = AXQ.length ? setTimeout(pumpAxes, 0) : 0;
    if (!AXQ.length) window.__axesReady = true;
  }
  function sweepAxes(elm) {
    elm._sweep = sweepSteps(elm);
    AXQ.push(elm);
    window.__axesReady = false;
    // a reader's touch, or any change the sweep did not make itself, first finishes the sweep
    const guard = (ev) => {
      if (!elm._sweep || elm._firing) return;
      const c = ev.target, keep = (ev.type === "input" || ev.type === "change") && "value" in c ? c.value : null;
      finishSweep(elm);
      if (keep !== null && c.isConnected) c.value = keep;
    };
    for (const ev of ["pointerdown", "keydown", "focusin", "input", "change", "click"]) elm.addEventListener(ev, guard, true);
    elm._sweptOwn = new Set();
    // after the panel has drawn a newly picked candidate, horizon or view, sweep it at once, before the next paint
    elm.addEventListener("change", (ev) => {
      if (elm._firing || !ev.target.matches('select[data-axes="own"]')) return;
      const key = [...elm.querySelectorAll('select[data-axes="own"]')].map((s) => s.value).join(",");
      if (elm._sweptOwn.has(key)) return;
      const it = sweepSteps(elm);
      try { while (!it.next().done); } catch (e) { /* the ranges gathered so far stand */ }
    });
    if (!axTimer) axTimer = setTimeout(pumpAxes, 0);
  }

  // a label on the chart, moved down until it clears the labels already placed
  function tag(fr, x, y, text, cls, anchor) {
    // a mark pushed past the fixed axes keeps its label at the edge, with an arrow toward the mark
    const off = x > fr.x1 + 12 ? " →" : x < fr.x0 - 12 ? "← " : "";
    if (off) { text = off === " →" ? text + off : off + text; cls = (cls || "") + " offchart"; }
    const w = textW(text), h = 15;
    let left = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
    left = Math.max(2, Math.min(left, fr.W - 2 - w));
    let top = y - 11;
    for (let k = 0; k < 10; k++) {
      const hit = fr.tags.find((b) => left < b[0] + b[2] && left + w > b[0] && top < b[1] + b[3] && top + h > b[1]);
      if (!hit) break;
      top = hit[1] + hit[3] + 1;
    }
    fr.tags.push([left, top, w, h]);
    const t = el("text", { x: left, y: top + 11, class: "tag " + (cls || "") }, fr.svg);
    t.textContent = text;
    return t;
  }
  function vref(fr, x, label, cls, ylab) {
    const X = fr.sx(x);
    el("line", { x1: X, x2: X, y1: fr.y1, y2: fr.y0, class: "ref " + (cls || "") }, fr.g);
    if (label) {
      const right = X + textW(label) + 6 > fr.x1;
      tag(fr, right ? X - 5 : X + 5, ylab === undefined ? fr.y1 + 12 : ylab, label, cls || "ref", right ? "end" : "start");
    }
  }
  function href(fr, y, label, cls, at) {
    const Y = fr.sy(y);
    el("line", { x1: fr.x0, x2: fr.x1, y1: Y, y2: Y, class: "ref " + (cls || "") }, fr.g);
    if (label) {
      if (at === "left") tag(fr, fr.x0 + 6, Y - 5, label, cls || "ref", "start");
      else tag(fr, fr.x1 - 4, Y - 5, label, cls || "ref", "end");
    }
  }
  function bars(fr, xs, ys, cls, base) {
    const b = base || 0, w = Math.max(1, (fr.sx(xs[1] ?? xs[0] + 1) - fr.sx(xs[0])) * 0.86);
    return xs.map((x, i) => el("rect", { x: fr.sx(x) - w / 2, y: Math.min(fr.sy(ys[i]), fr.sy(b)), width: w,
      height: Math.abs(fr.sy(b) - fr.sy(ys[i])), class: "bar " + (typeof cls === "function" ? cls(i) : (cls || "")) }, fr.g));
  }
  function line(fr, xs, ys, cls) {
    const d = xs.map((x, i) => (i ? "L" : "M") + fr.sx(x).toFixed(1) + "," + fr.sy(ys[i]).toFixed(1)).join("");
    return el("path", { d, class: "series " + (cls || "") }, fr.g);
  }
  function area(fr, xs, lo, hi, cls) {
    const lo_ = (i) => (Array.isArray(lo) ? lo[i] : lo), hi_ = (i) => (Array.isArray(hi) ? hi[i] : hi);
    let d = xs.map((x, i) => (i ? "L" : "M") + fr.sx(x).toFixed(1) + "," + fr.sy(hi_(i)).toFixed(1)).join("");
    for (let i = xs.length - 1; i >= 0; i--) d += "L" + fr.sx(xs[i]).toFixed(1) + "," + fr.sy(lo_(i)).toFixed(1);
    return el("path", { d: d + "Z", class: "area " + (cls || "") }, fr.g);
  }
  function span(fr, xa, xb, cls, label, style) {
    const a = fr.sx(xa), b = fr.sx(xb);
    el("rect", { x: Math.min(a, b), y: fr.y1, width: Math.abs(b - a), height: fr.y0 - fr.y1, class: "area " + (cls || ""), style: style || "" }, fr.g);
    if (label) tag(fr, Math.min(a, b) + 5, fr.y1 + 12, label, "quiet");
  }
  function hzone(fr, ya, yb, cls, label, style) {
    const a = fr.sy(ya), b = fr.sy(yb);
    el("rect", { x: fr.x0, y: Math.min(a, b), width: fr.x1 - fr.x0, height: Math.abs(b - a), class: "area " + (cls || ""), style: style || "" }, fr.g);
    if (label) tag(fr, fr.x0 + 6, Math.min(a, b) + 14, label, "quiet");
  }
  function dot(fr, x, y, r, cls) { return el("circle", { cx: fr.sx(x), cy: fr.sy(y), r, class: "dot " + (cls || "") }, fr.g); }

  // an HTML legend whose swatches draw the mark they stand for
  function legend(host, items) {
    const sw = (k, c) => {
      const col = `var(--v-${c || "main"})`;
      const inner = k === "line" ? `<line x1="1" x2="21" y1="6" y2="6" style="stroke:${col};stroke-width:2.4"/>`
        : k === "dash" ? `<line x1="1" x2="21" y1="6" y2="6" style="stroke:${col};stroke-width:2;stroke-dasharray:5 3"/>`
        : k === "area" ? `<rect x="1" y="1" width="20" height="10" rx="2" style="fill:${col};opacity:.3"/>`
        : k === "dot" ? `<circle cx="11" cy="6" r="4" style="fill:${col}"/>`
        : k === "hollow" ? `<circle cx="11" cy="6" r="4" style="fill:none;stroke:${col};stroke-width:1.8"/>`
        : `<rect x="5" y="1" width="12" height="10" rx="1.5" style="fill:${col}"/>`;
      return `<svg viewBox="0 0 22 12" aria-hidden="true">${inner}</svg>`;
    };
    const d = div("legend", host);
    d.innerHTML = items.map(([t, k, c]) => `<span>${sw(k, c)}${t}</span>`).join("");
    return d;
  }
  const kvHtml = (rows) => `<dl class="kv">${rows.map(([a, b, c]) => `<div><dt>${a}</dt><dd class="${c || ""}">${b}</dd></div>`).join("")}</dl>`;
  // a short status word in a rounded outline; cls picks its colour (style.css .pill.<cls>)
  const pill = (text, cls) => `<span class="pill ${cls || "none"}">${esc(text || "none")}</span>`;

  function slider(host, o, onInput) {
    const row = host.querySelector(":scope > .controls") || (host.classList.contains("controls") ? host : div("controls", host));
    const lab = document.createElement("label");
    lab.textContent = o.label;
    const inp = document.createElement("input");
    Object.assign(inp, { type: "range", min: o.min, max: o.max, step: o.step, value: o.value });
    const val = document.createElement("span");
    val.className = "val";
    lab.append(inp, val);
    row.appendChild(lab);
    const show = () => { val.textContent = o.show ? o.show(+inp.value) : inp.value; };
    // a base value off the slider's step (a candidate's own rate, say) is kept exactly, so Reset
    // (mount) can hand it back unrounded: the browser snaps inp.value to the step
    inp._base = o.value;
    inp._drawn = o.value;
    inp.addEventListener("input", (ev) => {
      show();
      inp._drawn = ev.detail && ev.detail.reset ? o.value : +inp.value;
      onInput(inp._drawn);
    });
    show();
    return inp;
  }
  function choice(host, label, opts, value, onChange) {
    const lab = document.createElement("label");
    lab.textContent = label;
    const sel = document.createElement("select");
    opts.forEach(([v, t]) => { const op = document.createElement("option"); op.value = v; op.textContent = t; sel.appendChild(op); });
    sel.value = String(value);
    sel.addEventListener("change", () => onChange(sel.value));
    lab.appendChild(sel);
    host.appendChild(lab);
    return sel;
  }

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  /* ---------------- the Sankey ---------------- */

  /* Columns of nodes joined by bands whose width is the money that flows. A node's height is the larger of
     what flows in and out; nodes stack in the order given, and bands leave and enter in the order of their
     far ends, so they do not cross inside a column. */
  function sankey(host, spec) {
    const box = div("sankey", host);
    const W = Math.max(330, Math.round(box.clientWidth || 640)), H = spec.height || 330;
    const nodes = spec.nodes.map((n) => Object.assign({ inV: 0, outV: 0 }, n)), by = {};
    nodes.forEach((n) => { by[n.id] = n; });
    const links = spec.links.filter((l) => l.v > 1e-9);
    links.forEach((l) => { by[l.s].outV += l.v; by[l.t].inV += l.v; });
    nodes.forEach((n) => { n.v = Math.max(n.inV, n.outV, n.fixed || 0); });
    const shown = nodes.filter((n) => n.v > 1e-9), cols = Math.max(...shown.map((n) => n.col)) + 1;
    const NW = 11, GAP = 22, top = 8, labelW = 150;
    const colX = (c) => 4 + c * (W - 8 - labelW - NW) / Math.max(1, cols - 1);
    let k = Infinity;
    for (let c = 0; c < cols; c++) {
      const col = shown.filter((n) => n.col === c), tot = col.reduce((a, n) => a + n.v, 0);
      if (tot > 0) k = Math.min(k, (H - top - 6 - GAP * (col.length - 1)) / tot);
    }
    for (let c = 0; c < cols; c++) {
      let y = top;
      shown.filter((n) => n.col === c).forEach((n) => { n.x = colX(c); n.y = y; n.h = Math.max(2, n.v * k); y += n.h + GAP; n.o = 0; n.i = 0; });
    }
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.label || "flows" }, box);
    const lg = el("g", {}, svg), ng = el("g", {}, svg), tg = el("g", {}, svg);
    const order = (n) => shown.indexOf(n);
    const outs = (n) => links.filter((l) => by[l.s] === n).sort((a, b) => order(by[a.t]) - order(by[b.t]));
    const ins = (n) => links.filter((l) => by[l.t] === n).sort((a, b) => order(by[a.s]) - order(by[b.s]));
    shown.forEach((n) => { outs(n).forEach((l) => { l.sy = n.y + n.o; n.o += l.v * k; }); ins(n).forEach((l) => { l.ty = n.y + n.i; n.i += l.v * k; }); });
    const val = spec.fmt || ((v) => fmt(v, "sum"));  // spec.unit names the value column of the table view
    links.forEach((l) => {
      const s = by[l.s], t = by[l.t], w = Math.max(1, l.v * k), xa = s.x + NW, xb = t.x, m = (xa + xb) / 2;
      const d = `M${xa},${l.sy}C${m},${l.sy} ${m},${l.ty} ${xb},${l.ty}L${xb},${l.ty + w}C${m},${l.ty + w} ${m},${l.sy + w} ${xa},${l.sy + w}Z`;
      const p = el("path", { d, class: "link " + (l.cls || "flow") }, lg);
      el("title", {}, p).textContent = `${s.label} → ${t.label}: ${val(l.v)}`;
    });
    // two-line labels right of each node, pushed apart within a column so small neighbours stay readable
    for (let c = 0; c < cols; c++) {
      let floor = -Infinity;
      shown.filter((n) => n.col === c).forEach((n) => { n.ly = Math.max(n.y + n.h / 2 - 7, floor); floor = n.ly + 30; });
    }
    svg.setAttribute("viewBox", `0 0 ${W} ${Math.max(H, ...shown.map((n) => n.ly + 22))}`);
    shown.forEach((n) => {
      el("rect", { x: n.x, y: n.y, width: NW, height: n.h, rx: 2, class: "node " + (n.cls || "flow") }, ng);
      const t = el("text", { x: n.x + NW + 6, y: n.ly + 4 }, tg);
      el("tspan", { class: "n" }, t).textContent = n.label;
      el("tspan", { class: "v", x: n.x + NW + 6, dy: 14 }, t).textContent = val(n.v) + (spec.total ? " · " + fmt(n.v / spec.total, n.v / spec.total < 0.01 ? "pct1" : "pct0") : "");
    });
    tableOf(host, spec.label || "flows", ["flow", spec.unit || CUR.trim() || "value"].concat(spec.total ? ["share of the total"] : []),
      shown.map((n) => [n.label, val(n.v)].concat(spec.total ? [fmt(n.v / spec.total, n.v / spec.total < 0.01 ? "pct1" : "pct0")] : [])));
    return box;
  }

  // fill sinks in order from sources in order: every link is a piece of one source paying one sink
  function pour(sources, sinks, linkCls) {
    const src = sources.map(([id, v, cls]) => ({ id, v, cls })), out = [];
    let i = 0;
    for (const [id, need] of sinks) {
      let left = need;
      while (left > 1e-9 && i < src.length) {
        const take = Math.min(left, src[i].v);
        if (take > 1e-9) out.push({ s: src[i].id, t: id, v: take, cls: src[i].cls || linkCls });
        src[i].v -= take; left -= take;
        if (src[i].v <= 1e-9) i++;
      }
    }
    return out;
  }

  /* ---------------- panel types ---------------- */

  const TYPES = {};
  function register(name, fn, watch) { TYPES[name] = fn; if (watch) WATCH[name] = watch; }

  const logFactorial = (k) => { let s = 0; for (let j = 2; j <= k; j++) s += Math.log(j); return s; };
  function poissonPmf(mu, kmax) {
    const out = [], lm = Math.log(mu);
    let lf = 0;
    for (let k = 0; k <= kmax; k++) { if (k) lf += Math.log(k); out.push(Math.exp(-mu + k * lm - lf)); }
    return out;
  }

  const normCdf = (z) => {  // Abramowitz and Stegun 7.1.26, |error| < 1.5e-7
    const t = 1 / (1 + 0.3275911 * Math.abs(z) / Math.SQRT2);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z / 2);
    return z >= 0 ? (1 + y) / 2 : (1 - y) / 2;
  };

  // Lanczos log-gamma, enough for drawing a density
  function lgamma(x) {
    const g = [676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
      12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1;
    let a = 0.99999999999980993;
    const t = x + 7.5;
    for (let i = 0; i < 8; i++) a += g[i] / (x + i + 1);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  }

  // one sentence per panel type, under the title: what to watch when the controls move (register's third argument)
  const WATCH = {};

  const isNum = (s) => /^[−+\-¥]?\d/.test(s);
  function tableHtml(tabs) {
    // numbers align right, words left; a column's header follows its first cell
    const cell = (tag, s, num) => `<${tag}${num ? "" : ' class="l"'}>${esc(s)}</${tag}>`;
    const secs = Object.entries(tabs);
    if (!secs.length) return `<p class="pnote">Nothing is drawn for this choice.</p>`;
    return secs.map(([cap, [head, rows]]) => `<p class="pnote">${esc(cap)}</p><div class="tablewrap twrap"><table class="tv">` +
      `<thead><tr>${head.map((h, i) => cell("th", h, rows.length && isNum(rows[0][i]))).join("")}</tr></thead>` +
      `<tbody>${rows.map((r) => "<tr>" + r.map((x) => cell("td", x, isNum(x))).join("") + "</tr>").join("")}</tbody></table></div>`).join("");
  }

  /* The frame every panel shares: title, the line on what to watch, Reset and Table. Reset puts each
     control back to the value it had when the panel was drawn (the candidate's base values) and fires
     the control's own event, so the panel redraws itself; controls are looked up again after each step,
     because a candidate switch rebuilds the controls below it. Table hides the drawings and shows the
     numbers each drawing handed to tableOf, refreshed after every change while it is shown. */
  function mount(elm, o) {
    const fn = TYPES[o.type];
    if (!fn) { elm.textContent = "unknown panel type " + o.type; return; }
    const head = div("phead", elm);
    if (o.title) head.innerHTML = "<h4>" + o.title + "</h4>";
    const tools = div("ptools", head);
    const watch = o.watch || WATCH[o.type];
    if (watch) { const p = document.createElement("p"); p.className = "watch"; p.textContent = watch; elm.appendChild(p); }
    let tabs = {}, showing = false;
    elm._table = (cap, h, rows) => { tabs[cap] = [h, rows]; };
    elm.dataset.axes = "1";
    elm._axes = new Map();
    elm._axesBase = new Map();
    fn(elm, o);
    const tv = div("ptable", elm);
    tv.hidden = true;
    const render = () => { if (showing) tv.innerHTML = tableHtml(tabs); };
    const controls = () => [...elm.querySelectorAll("input, select")];
    // a change replaces every drawing's numbers, so start the sections afresh before the panel redraws
    for (const ev of ["input", "change"]) {
      elm.addEventListener(ev, () => { tabs = {}; }, true);
      elm.addEventListener(ev, render);
    }
    elm.addEventListener("click", (e) => { if (!e.target.closest(".ptools")) render(); });
    const base = controls().map((c) => c.value);
    if (base.length) {
      const reset = document.createElement("button");
      Object.assign(reset, { type: "button", textContent: "Reset", className: "preset", title: "back to the base values" });
      reset.addEventListener("click", () => {
        base.forEach((v, k) => {
          const c = controls()[k];
          if (!c || (c.value === v && c._drawn === c._base)) return;
          c.value = v;
          c.dispatchEvent(c.tagName === "SELECT" ? new Event("change", { bubbles: true })
            : new CustomEvent("input", { bubbles: true, detail: { reset: true } }));
        });
      });
      tools.appendChild(reset);
    }
    const tb = document.createElement("button");
    Object.assign(tb, { type: "button", textContent: "Table", className: "ptoggle", title: "the plotted numbers as a table" });
    tb.setAttribute("aria-pressed", "false");
    tb.addEventListener("click", () => {
      showing = !showing;
      elm.classList.toggle("tableview", showing);
      tv.hidden = !showing;
      tb.setAttribute("aria-pressed", String(showing));
      render();
    });
    tools.appendChild(tb);
    if (o.axes !== "free") sweepAxes(elm);
  }

  window.VIZ = { el, div, fmt, signed, frame, bars, line, area, span, hzone, vref, href, tag, dot, legend, sankey, pour, slider, choice,
                 niceStep, autoTicks, logTicks, group, sci2, kfmt, kfmt1, tableOf, tableHtml, kvHtml, pill, esc,
                 poissonPmf, logFactorial, normCdf, lgamma, fixedAxes, AX_STRETCH };
  window.PANELS = { register, mount, types: TYPES, watch: WATCH };
})();
