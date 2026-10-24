# The page shell

The shell is the part of a chaynikbook that does not depend on the subject: the build, the page behaviour, the chart library, the styles and the checks. Each component below states what it must do.

| Component | What it does |
|---|---|
| `src/02_build.py` | Renders `book/chapters/*.md` with pandoc (with `--citeproc` and the bibliography in a topic book). Expands `[[key]]` into a glossary symbol shown as name and symbol, and marks glossary terms in prose. Turns each equation fence into the three-row block. Keeps collapsed blocks out of the word count and fails when the main path exceeds the budget in `manifest.json`. Lints the source and the rendered HTML (below). Fails on a glossary symbol that is used nowhere or a `[[key]]` that is not in the glossary; in a book with an engine, also fails when no symbol inside an equation is tagged. Inlines the CSS, the scripts that exist, and the data (`models.json` and `cases.json` when present, glossary, terms, manifest, actors) into `src/template.html`, and writes `output/index.html`. |
| `src/template.html` | Three columns on wide screens, stacked on narrow ones: chapter list with time badges and a progress bar on the left, prose in the centre (about 72 characters wide), glossary and terms on the right. One data global, one slot per script, MathJax 3 SVG from a CDN, and the engine badge, hidden when the book has no engine. |
| `src/page.js` | Rail behaviour: progress, current chapter, tabs between glossary and terms, hover on a symbol highlights its glossary row and every other occurrence. Mounts panels through the registry and checks. Runs the engine self-test (re-solve every case, compare `xvec`, set the badge) only when cases exist. Supports reveal-only checks for a book without an engine. |
| `src/viz.js` | The chart library, subject-free: element helpers, number formatting, actor colour slots, tooltips, bars, heatmap, table view behind every chart, a controls row and a reset button. Inline SVG, no chart library. |
| `src/panels.js` | A registry (`register`, `mount`) and the subject's panel types. |
| `src/style.css` | Colour tokens on `:root` with light and dark themes, an actor colour per actor and a tint per symbol type, each with at least 3:1 contrast against both backgrounds, an explicit body background, and the layout. |
| `src/03_verify_render.py` | Opens `output/index.html` in headless Chrome and fails on: clipped equations, symbols that do not respond to hover, chart marks outside their axes, blank panels, checks that do not run, stray markup, and an engine badge other than N/N in a book with an engine. Thresholds (how many symbols, how many charts) come from the manifest. Themes and phone width are a manual look. |
| `src/tests/` | Python tests that reproduce the published numbers; a JavaScript test that the twin matches every case in `cases.json`; a JavaScript test that every check's written reason agrees with what the engine computes. |
| `src/01_export_cases.py` | Solves a spread of cases covering every block and panel with the Python kit and writes `output/models.json` and `output/cases.json`. |

## The engine interface

`page.js` and the checks need one global engine object, which is also passed into `expr:` variables in checks, plus two data files:

- `solve(model)` returns a solution object that carries `xvec`, the vector of unknowns the self-test compares;
- `applyChanges(model, changes)` returns a new model with the changes applied;
- optionally, summary functions for reported variables computed from two solutions (for example a Laspeyres real GDP index);
- `models.json`, the named base models, and `cases.json`, a list of `{id, model, changes, xvec}` solved by the Python kit.

## Lint

On the chapter source and on the rendered HTML: em-dashes, including `---` that pandoc turns into one; "not ... but" and "X, not Y" constructions, also across wrapped lines; unnecessary hyphens between words (hyphens stay in numeric compounds, established terms such as cross-sectional, prefixes such as post-COVID, and participles such as IPF-weighted); bold or italics used for emphasis in prose.

## Saving the shell

The first book built from this file copies its shell (the `src/` components above, with the subject parts removed) into a `shell/` folder next to this file, with a one-chapter demo that builds and passes `03_verify_render.py`. Later books start from that folder.
