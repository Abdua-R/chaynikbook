/* Reader notes for a chaynikbook: a drawer that slides in from the left edge.
   A note keeps the section it was written in and, if text was selected, the quoted passage. Each note is numbered
   in the order it was written, and its number ("1*") sits in the right margin level with the passage it quotes.
   Storage: in a published Artifact that declares {db: {}, user: {}}, notes are private to the viewer at
   data/users/<id>/<book>/notes (Claude reads them back with ArtifactData); everywhere else, and as a cache,
   localStorage under "chaynikbook-notes:<book title>". No dependency on the rest of the page. */
(function () {
  const KEY = "chaynikbook-notes:" + (document.title || location.pathname);
  let notes = [], remote = null, quote = "";

  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
  const cache = () => { try { localStorage.setItem(KEY, JSON.stringify(notes)); return true; } catch (e) { return false; } };
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const h = (tag, attrs, parent, text) => {
    const e = document.createElement(tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  };

  // the heading the reader is in: the last heading with an id above the top fifth of the window
  function here() {
    const hs = [...document.querySelectorAll("main h1[id], main h2[id], main h3[id], section h1[id], section h2[id], [id] > h1, [id] > h2")];
    let best = null;
    for (const x of hs) { if (x.getBoundingClientRect().top < innerHeight * 0.2) best = x; else break; }
    best = best || hs[0];
    if (!best) return { id: "", title: document.title };
    const id = best.id || (best.parentElement && best.parentElement.id) || "";
    return { id, title: best.textContent.replace(/\s+/g, " ").trim() };
  }

  async function save(n) {
    cache();
    if (remote) { try { await remote.col.doc(n.id).set(n); } catch (e) { status("could not save to your account; kept in this browser"); } }
  }
  async function drop(id) {
    notes = notes.filter((n) => n.id !== id); cache();
    if (remote) { try { await remote.col.doc(id).delete(); } catch (e) { status("could not delete it from your account; it may come back on reload"); } }
  }

  // ---- drawer
  const tab = h("button", { class: "nt-tab", type: "button", "aria-expanded": "false", title: "Notes (Alt+N)" }, document.body, "Notes");
  const box = h("aside", { class: "nt-box", "aria-label": "Your notes", hidden: "" }, document.body);
  const head = h("div", { class: "nt-head" }, box);
  h("b", {}, head, "Your notes");
  const close = h("button", { class: "nt-x", type: "button", "aria-label": "close notes" }, head, "×");
  const where = h("div", { class: "nt-where" }, box);
  const q = h("blockquote", { class: "nt-quote", hidden: "" }, box);
  const ta = h("textarea", { class: "nt-new", rows: "4", placeholder: "Write a note about this section" }, box);
  const row = h("div", { class: "nt-row" }, box);
  const add = h("button", { type: "button", class: "nt-add" }, row, "Save note");
  const exp = h("button", { type: "button" }, row, "Export .md");
  const st = h("div", { class: "nt-status" }, box);
  const list = h("div", { class: "nt-list" }, box);
  const status = (t) => { st.textContent = t; };

  function open(on) {
    box.hidden = !on; tab.setAttribute("aria-expanded", String(on)); document.body.classList.toggle("nt-open", on);
    if (on) { refreshWhere(); ta.focus(); }
  }
  function refreshWhere() {
    const p = here(); where.textContent = "Section: " + p.title;
    q.hidden = !quote; q.textContent = quote;
  }
  tab.addEventListener("click", () => open(box.hidden));
  close.addEventListener("click", () => open(false));
  addEventListener("keydown", (e) => { if (e.altKey && (e.key === "n" || e.key === "N")) { e.preventDefault(); open(box.hidden); } });
  addEventListener("scroll", () => { if (!box.hidden) refreshWhere(); }, { passive: true });
  // keep the last text the reader selected in the book, so a note can quote it
  document.addEventListener("selectionchange", () => {
    const s = String(getSelection() || "").trim();
    if (s && !box.contains(getSelection().anchorNode)) { quote = s.slice(0, 400); if (!box.hidden) refreshWhere(); }
  });

  add.addEventListener("click", async () => {
    const text = ta.value.trim(); if (!text) return;
    const p = here(), t = new Date().toISOString();
    const n = { id: uid(), section: p.id, sectionTitle: p.title, quote, text, created: t, updated: t };
    notes.push(n); ta.value = ""; quote = ""; refreshWhere(); render(); await save(n);
  });

  const ordered = () => [...notes].sort((a, b) => a.created < b.created ? -1 : 1);

  function render() {
    list.textContent = "";
    marks();
    if (!notes.length) { h("p", { class: "nt-empty" }, list, "No notes yet. Select a passage, write a note, save."); return; }
    const by = {}, num = new Map(ordered().map((n, i) => [n.id, i + 1]));
    ordered().forEach((n) => (by[n.sectionTitle] = by[n.sectionTitle] || []).push(n));
    for (const sec in by) {
      const g = h("div", { class: "nt-group" }, list);
      const a = h("a", { href: "#" + (by[sec][0].section || ""), class: "nt-sec" }, g, sec);
      a.addEventListener("click", () => { if (innerWidth < 900) open(false); });
      for (const n of by[sec]) {
        const c = h("div", { class: "nt-card", "data-note": n.id }, g);
        h("span", { class: "nt-num" }, c, num.get(n.id) + "*");
        if (n.quote) h("blockquote", { class: "nt-quote" }, c, n.quote);
        const body = h("div", { class: "nt-text" }, c, n.text);
        const bar = h("div", { class: "nt-bar" }, c);
        h("span", { class: "nt-date" }, bar, n.updated.slice(0, 10));
        const ed = h("button", { type: "button" }, bar, "Edit");
        const del = h("button", { type: "button" }, bar, "Delete");
        ed.addEventListener("click", async () => {
          if (ed.textContent === "Edit") {
            const t = h("textarea", { class: "nt-new", rows: "4" }); t.value = n.text; body.replaceWith(t); t.focus(); ed.textContent = "Done";
            ed._t = t;
          } else { n.text = ed._t.value.trim() || n.text; n.updated = new Date().toISOString(); render(); await save(n); }
        });
        // confirm() is blocked in a sandboxed Artifact frame and returns false, so the button asks in place instead
        del.addEventListener("click", async () => {
          if (del.textContent === "Delete") { del.textContent = "Delete? Yes"; setTimeout(() => { del.textContent = "Delete"; }, 4000); return; }
          await drop(n.id); render();
        });
      }
    }
  }

  // ---- numbers in the right margin, level with the quoted passage (or the section heading when there is no quote)
  const layer = h("div", { class: "nt-marks" }, document.body);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function anchor(n) {
    const sec = n.section ? document.getElementById(n.section) : null;
    let node = null, rect = null;
    const key = (n.quote || "").replace(/\s+/g, " ").trim().slice(0, 32);
    if (key) {
      const re = new RegExp(esc(key).replace(/ /g, "\\s+"));
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      if (sec) w.currentNode = sec;
      for (let t = w.nextNode(); t; t = w.nextNode()) {
        if (box.contains(t) || layer.contains(t)) continue;
        const m = re.exec(t.nodeValue);
        if (!m) continue;
        const r = document.createRange(); r.setStart(t, m.index); r.setEnd(t, m.index + 1);
        node = t.parentElement; rect = r.getClientRects()[0] || null; break;
      }
    }
    if (!node) { node = sec; rect = sec ? sec.getBoundingClientRect() : null; }
    if (!node) return null;
    const shut = node.closest("details:not([open])");  // inside a closed block: point at its summary
    if (shut) { node = shut.querySelector("summary") || shut; rect = node.getBoundingClientRect(); }
    if (!rect || (!rect.height && !rect.width)) return null;
    const col = node.closest("p, li, blockquote, td, th, figure, h1, h2, h3, h4, .eq, .steps, div") || node;
    return { top: rect.top, right: col.getBoundingClientRect().right };
  }
  function marks() {
    layer.textContent = "";
    document.body.classList.toggle("nt-has", notes.length > 0);  // narrow screens keep a right margin for the marks
    const used = [];
    ordered().forEach((n, i) => {
      const a = anchor(n); if (!a) return;
      let top = a.top + scrollY;
      const left = Math.min(a.right + 8, innerWidth - 30) + scrollX;
      while (used.some((u) => Math.abs(u - top) < 18)) top += 18;  // two notes on one line stack
      used.push(top);
      const m = h("button", { class: "nt-mark", type: "button", title: "Note " + (i + 1) + ": " + n.text.slice(0, 80) }, layer, (i + 1) + "*");
      m.style.top = top + "px"; m.style.left = left + "px";
      m.addEventListener("click", () => {
        open(true);
        const c = list.querySelector('[data-note="' + n.id + '"]');
        if (c) { c.scrollIntoView({ block: "center" }); c.classList.add("nt-flash"); setTimeout(() => c.classList.remove("nt-flash"), 1200); }
      });
    });
  }
  let pending = 0;
  const later = () => { cancelAnimationFrame(pending); pending = requestAnimationFrame(marks); };
  addEventListener("resize", later);
  document.addEventListener("toggle", later, true);  // a <details> opened or closed
  if (window.ResizeObserver) new ResizeObserver(later).observe(document.body);  // fonts, MathJax and panels settling

  exp.addEventListener("click", () => {
    const lines = ["# Notes on " + document.title, ""];
    let last = null;
    ordered().forEach((n, i) => {
      if (n.sectionTitle !== last) { lines.push("## " + n.sectionTitle, ""); last = n.sectionTitle; }
      if (n.quote) lines.push("> " + n.quote.replace(/\n/g, " "), "");
      lines.push((i + 1) + "* " + n.text, "");
    });
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const a = h("a", { href: URL.createObjectURL(blob), download: "notes.md" }); a.click();
  });

  // ---- start: local notes at once, then the viewer's account notes if the page runs as an Artifact with db
  notes = load(); render();
  status(cache() ? "Saved in this browser." : "This browser does not keep notes; export them before closing.");
  (async () => {
    if (!window.claude || !window.claude.use) return;
    const [db, user] = await Promise.all([window.claude.use("db"), window.claude.use("user")]);
    if (!db || !user) return;
    try {
      const id = await user.id();
      // data/users/<id> is the viewer's private collection; the book's notes sit one level down, keyed by book
      const col = db.collection("data/users/" + id).doc(KEY.replace(/[^A-Za-z0-9_\-.~:@+]/g, "-").slice(0, 190)).collection("notes");
      remote = { col };
      const snap = await col.get();
      const got = snap.docs.filter((d) => d.exists).map((d) => Object.assign({}, d.data()));
      const seen = new Set(got.map((n) => n.id));
      const local = notes.filter((n) => !seen.has(n.id));  // notes written before the account was reachable
      notes = got.concat(local); cache(); render();
      for (const n of local) await save(n);
      status("Saved to your account; private to you.");
    } catch (e) { remote = null; status("Saved in this browser."); }
  })();
})();
