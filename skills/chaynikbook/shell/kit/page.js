/* page.js: the reading runtime of a chaynikbook (kit).

   Mounts panels, wires the glossary hover, tracks reading progress, toggles the theme and, when the
   book has an engine.js, recomputes every stored case so the badge in the rail states whether the
   engine in this page still agrees with the code that produced the numbers.

   The engine contract (all optional as a whole; a book without engine.js gets no badge and only
   revealed-answer checks):
     window.ENGINE = {
       selfTest(data)                   -> {ok, total, failed: [names]}   the badge
       applyChanges(changes, check, data) -> state                     the inputs of check.case with changes applied
       checkValue(out, state, check)    -> number                       the output a check asks about
       CHECK_BASE: {out: "dotted.path"} where data holds out's base value; "{case}" stands for check.case
     }
   data is the token namespace (data/cases.json at the root, other data files under their stem). */
(function () {
  "use strict";
  const D = window["{{DATA_GLOBAL}}"], E = window.ENGINE;

  (function () {
    const b = document.getElementById("engine-badge");
    if (!E) { b.remove(); return; }
    let res;
    try { res = E.selfTest(D.data); } catch (e) { res = { ok: 0, total: 1, failed: ["engine error: " + e.message] }; }
    b.textContent = `engine: ${res.ok}/${res.total}`;
    b.className = "badge " + (res.ok === res.total ? "ok" : "bad");
    b.title = res.failed.length ? "checks that disagree with the system: " + res.failed.join(", ")
                                : "every worked case recomputes to the value the system computed";
  })();

  // panels
  document.querySelectorAll(".panel[data-panel]").forEach((elm) => {
    try { PANELS.mount(elm, JSON.parse(elm.dataset.panel)); }
    catch (e) { elm.textContent = "panel error: " + e.message; }
  });

  /* Predict then test. A check states a change and asks which way one named output moves. With "out",
     engine.js computes the output before and after the stated change (ENGINE.applyChanges, ENGINE.checkValue),
     so the answer is never typed; with "answer", the code behind the output does not run in the page, and the
     revealed text carries numbers the build read from the data. */
  const checkBase = {};
  const secLabel = (ref) => "Section " + ref.replace(/^#s/, "").replace("-", ".");
  function mountCheck(elm, c) {
    elm.innerHTML = `<div class="q"><span class="ck">Predict.</span> ${c.q}</div>` +
      `<div class="ask">Which way does ${c.label} move?</div>`;
    const ctr = VIZ.div("controls", elm), ans = VIZ.div("answer", elm);
    ans.setAttribute("aria-live", "polite");
    let truth = null, v0, v1;
    function solve() {
      if (truth !== null) return;
      if (!c.out) { truth = c.answer; return; }
      if (!E) throw new Error("this check needs engine.js");
      const key = String(c.case) + "|" + c.out;
      if (!(key in checkBase)) checkBase[key] = E.checkValue(c.out, E.applyChanges({}, c, D.data), c);
      v0 = checkBase[key];
      v1 = E.checkValue(c.out, E.applyChanges(c.changes || {}, c, D.data), c);
      if (!Number.isFinite(v0) || !Number.isFinite(v1)) throw new Error("no number before or after the change");
      truth = Math.abs(v1 - v0) <= 1e-9 * Math.max(Math.abs(v0), Math.abs(v1)) ? "no change" : v1 > v0 ? "up" : "down";
      Object.assign(ans.dataset, { v0, v1 });
    }
    ["up", "down", "no change"].forEach((dir) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = dir;
      b.setAttribute("aria-pressed", "false");
      b.onclick = () => {
        ctr.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        try { solve(); } catch (e) { ans.textContent = "check error: " + e.message; return; }
        const right = dir === truth;
        ans.dataset.truth = truth;
        ans.dataset.kind = c.out ? "engine" : "reveal";
        ans.innerHTML =
          `<span class="${right ? "ok" : "no"}">${right ? "Right" : truth === "no change" ? "Not quite: it does not move" : "Not quite: it goes " + truth}.</span> ` +
          (c.out ? `The engine in this page computes ${c.label}: ${VIZ.fmt(v0, c.fmt || "int")} before the change, ` +
                   `${VIZ.fmt(v1, c.fmt || "int")} after. ` : c.reveal + " ") +
          `${c.why} <a href="${c.ref}">Back to ${secLabel(c.ref)}.</a>`;
      };
      ctr.appendChild(b);
    });
  }
  document.querySelectorAll(".check[data-check]").forEach((elm) => {
    try { mountCheck(elm, JSON.parse(elm.dataset.check)); }
    catch (e) { elm.textContent = "check error: " + e.message; }
  });

  /* The lookup rail.

     Hovering a symbol, term or named idea writes its definition into the card at the top of
     the rail, and clicking pins it so you can read on without keeping the mouse still.

     This replaces an earlier version that called scrollIntoView on the matching glossary row.
     That scrolls every scrollable ancestor including the document, so the page jumped and the
     symbol slid out from under the cursor, which made hovering impossible. Nothing here
     scrolls the document: the card is already in view, and the list is only ever scrolled by
     setting scrollTop on the rail itself. */
  const D2 = D;
  const gl = document.getElementById("glossary");
  const tl = document.getElementById("termlist");
  const card = document.getElementById("defcard");
  const aside = document.querySelector("aside.gloss");
  const emptyCard = card ? card.innerHTML : "";
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  let lit = [];
  let pinned = null;

  const SEC_LABEL = (sec) => (sec || "").replace(/^s/, "Section ").replace("-", ".");

  function highlight(selector) {
    lit.forEach((n) => n.classList.remove("hl"));
    lit = selector ? Array.from(document.querySelectorAll(selector)) : [];
    lit.forEach((n) => n.classList.add("hl"));
  }

  /* Scroll the rail's own list, never the document. */
  function revealRow(row) {
    if (!row || !aside) return;
    const r = row.getBoundingClientRect(), a = aside.getBoundingClientRect();
    if (r.top < a.top + 4) aside.scrollTop -= a.top + 4 - r.top;
    else if (r.bottom > a.bottom - 4) aside.scrollTop += r.bottom - (a.bottom - 4);
  }

  function markRow(list, attr, key) {
    [gl, tl].forEach((l) => l && l.querySelectorAll("li.hl").forEach((n) => n.classList.remove("hl")));
    const row = list && list.querySelector(`li[${attr}="${key}"]`);
    if (row) { row.classList.add("hl"); revealRow(row); }
  }

  function showSymbol(key, pin) {
    const g = D2.glossary[key];
    if (!g || !card) return;
    card.innerHTML =
      `<div class="dc-kind" style="color:var(--t-${g.type})">symbol</div>` +
      `<div class="dc-name">${esc(g.name)}</div>` +
      `<div class="dc-tex">$${g.tex}$</div>` +
      `<div class="dc-body">${esc(g.def)}</div>` +
      `<div class="dc-body dc-note">Every other use of it on screen is highlighted.</div>` +
      (g.sec ? `<a class="dc-link" href="#${g.sec}">Introduced in ${SEC_LABEL(g.sec)}</a>` : "") +
      (pin ? `<button type="button" class="dc-unpin">unpin</button>` : "");
    typeset(card);
    highlight(`[data-sym="${key}"]`);
    markRow(gl, "data-sym", key);
  }

  function showTerm(key, pin) {
    const t = D2.terms[key];
    if (!t || !card) return;
    const see = (t.see || []).filter((s) => D2.terms[s])
      .map((s) => `<button type="button" class="dc-see" data-goterm="${s}">${esc(D2.terms[s].name)}</button>`)
      .join("");
    card.innerHTML =
      `<div class="dc-kind">${t.kind === "concept" ? "named idea" : "term"}</div>` +
      `<div class="dc-name">${esc(t.name)}</div>` +
      `<div class="dc-body">${esc(t.def)}</div>` +
      (t.sec ? `<a class="dc-link" href="#${t.sec}">Introduced in ${SEC_LABEL(t.sec)}</a>` : "") +
      (see ? `<div class="dc-sees"><span>See also</span>${see}</div>` : "") +
      (pin ? `<button type="button" class="dc-unpin">unpin</button>` : "");
    highlight(`[data-term="${key}"]`);
    markRow(tl, "data-term", key);
    if (tl && tl.hidden) showTab("termlist");
  }

  function typeset(node) {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([node]).catch(() => {});
    }
  }

  function lookup(el, pin) {
    if (el.dataset.sym) showSymbol(el.dataset.sym, pin);
    else if (el.dataset.term) showTerm(el.dataset.term, pin);
  }

  const HOVER = ".sym[data-sym], .term[data-term], li[data-sym], li[data-term]";

  document.addEventListener("mouseover", (ev) => {
    if (pinned) return;
    const el = ev.target.closest && ev.target.closest(HOVER);
    if (el) lookup(el, false);
  });

  document.addEventListener("click", (ev) => {
    if (ev.target.closest(".dc-unpin")) {
      pinned = null;
      card.innerHTML = emptyCard;
      highlight(null);
      return;
    }
    const see = ev.target.closest(".dc-see");
    if (see) { pinned = see.dataset.goterm; showTerm(pinned, true); return; }
    const el = ev.target.closest(HOVER);
    if (!el) return;
    if (el.tagName === "A") return;
    pinned = el.dataset.sym || el.dataset.term;
    lookup(el, true);
  });

  // keyboard: the marked spans are focusable, so tabbing through them works the same way
  document.querySelectorAll(".sym[data-sym], .term[data-term]").forEach((el) => {
    el.setAttribute("tabindex", "0");
    el.addEventListener("focus", () => { if (!pinned) lookup(el, false); });
  });

  /* Symbols inside rendered math.

     MathJax turns TeX into an SVG, so a symbol in an equation is a drawing rather than a span
     and there is nothing to press. The build wraps each known symbol in \class{sym-k-<key>};
     this turns that class into the same data-sym a chip in the prose carries, so one set of
     handlers serves both. */
  function tagMath() {
    document.querySelectorAll('g[class*="sym-k-"]').forEach((g) => {
      if (g.dataset.sym) return;
      const mo = /sym-k-([A-Za-z0-9]+)/.exec(g.getAttribute("class") || "");
      const entry = mo && D2.glossary[mo[1]];
      if (!entry) return;
      g.dataset.sym = mo[1];
      g.setAttribute("class", g.getAttribute("class") + " sym sym-" + entry.type);
    });
  }
  (function whenTypeset() {
    if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise.then(tagMath);
      return;
    }
    setTimeout(whenTypeset, 50);      // MathJax loads async, so wait for it to exist
  })();

  function showTab(which) {
    [["glossary", gl], ["termlist", tl]].forEach(([name, list]) => {
      if (list) list.hidden = name !== which;
    });
    document.querySelectorAll(".railtabs button").forEach((b) => {
      b.setAttribute("aria-selected", String(b.dataset.tab === which));
    });
  }
  document.querySelectorAll(".railtabs button").forEach((b) => {
    b.addEventListener("click", () => showTab(b.dataset.tab));
  });

  // reading progress and the current chapter
  const secs = Array.from(document.querySelectorAll("main section"));
  const links = Array.from(document.querySelectorAll("nav.rail a"));
  const bar = document.querySelector("#progress > div");
  function onScroll() {
    const h = document.documentElement;
    const span = h.scrollHeight - h.clientHeight;
    bar.style.width = (span > 0 ? (100 * h.scrollTop / span) : 0).toFixed(1) + "%";
    let cur = 0;
    secs.forEach((s, i) => { if (s.getBoundingClientRect().top < 140) cur = i; });
    links.forEach((a, i) => a.classList.toggle("current", i === cur));
  }
  document.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // theme
  document.getElementById("theme").onclick = () => {
    const r = document.documentElement;
    const dark = r.dataset.theme
      ? r.dataset.theme === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
  };
})();
