# chaynikbook kit

The subject-free shell of an explorable book, generalized from the MarketResearcher explainer. Every script runs from the book folder and finds the kit files next to itself, so the kit can be copied into the book folder (`python check.py`) or kept one level up (`python ../check.py`, as `sample/` does).

- **Kit files, never edited per book:** `build.py`, `template.html`, `style.css` (its closing "book colours" block holds the MarketResearcher roles; a book overrides or adds its own in `book.css`), `viz.js`, `page.js`, `notes.js`, `notes.css`, `verify_render.py`, `check.py`.
- **Files a book writes itself:** `book.json` (title, subtitle, data_global, word_limit, currency, checks_per_chapter), `chapters/manifest.json` and `chapters/*.md`, `data/` (`glossary.json` and `terms.json` are required; `cases.json` is the token root; every other `<stem>.json` is read as `{{<stem>.…}}` and `extra_<name>.json` as `{{x.<name>.…}}`), an optional `book.css`, `panels_<name>.js` (each calls `PANELS.register(type, draw, watchText)` and draws with `window.VIZ`), and `engine.js` if the page should recompute numbers (contract at the top of `page.js`).
- **Without `engine.js`:** no engine badge, and only `answer` plus `reveal` checks.
- **Without `step` entries in the manifest:** no maps are required.

The one command, after each batch of edits, run from the book folder:

    python <kit>/check.py

It builds the page (`--local`), renders it in headless Chrome through every probe, rebuilds the artifact form and scans that form for secrets. It prints a summary and the failures only, and exits 1 on any failure. `sample/` is a one-chapter book that passes it.
