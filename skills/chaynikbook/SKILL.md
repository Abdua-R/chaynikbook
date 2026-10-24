---
name: chaynikbook
description: "Build an explorable book for dummies: a textbook, paper or topic turned into one interactive HTML page with a live model behind every number, readable from scratch."
argument-hint: "source (PDF path or citation) or topic, and who the reader is"
disable-model-invocation: true
---

A chaynikbook takes a reader with no background to the point where they can use the subject on a question of their own, over a stated main-path time (a full textbook: about one day). It is one self-contained HTML page: prose, equations, interactive panels, and a model that recomputes every number the reader sees.

It starts from one of two inputs, named in the arguments:

- a source (textbook, paper, course): the book covers everything in it, reordered for learning, adds depth where the source states an assumption without showing what it costs, and recomputes every number the source prints;
- a topic: the book is assembled from the literature, and every number comes from code or a cited source, never from memory.

## 1. Spec and plan

For a source, keep the file out of version control and extract its text with a script to `output/source_text.txt`, so that every later step can cite page and section. For a topic, search the literature, record each source and what it provides in `docs/REFERENCES.md`, and keep a `references.bib`.

Settle the design with the user (with `superpowers:brainstorming` if installed) and write `docs/spec.md` with a decisions table that fixes:

- the reader and what they can do at the end;
- the running example: one small named economy, system or case that every chapter reuses, with its base values (for a general equilibrium book: a Farm, a Factory, an Owner household and a Worker household);
- the chapter map: for each chapter the source sections or references it covers, minutes on the main path, its panels and its checks; core chapters first, then application chapters, then a last chapter that is the recipe from a research question to a result;
- the model the book computes with and the numbers it must reproduce (a source's printed tables, or a topic's published results), or, for a subject with no computable model, the data the panels show;
- notation: a readable name beside each symbol;
- the main-path time and word budget, collapsed material excluded;
- the visual system: one fixed colour per actor, a tint per symbol type, chart rules (one axis per chart, a legend for two or more series, a tooltip on every mark, a table view behind every chart);
- whether the book applies the method to the reader's own country or data, timeboxed, with a template of named blank cells as the fallback;
- what is out of scope.

Then write the implementation plan (with `superpowers:writing-plans` if installed). Done when the user approves the spec and the plan.

## 2. Model before prose

Write the reference model as a Python kit, one module shared by every chapter, and tests that reproduce every number the spec lists to the precision it was published at. Every parameter has a source: calibrated from data where the method allows (a general equilibrium model reads all of them off its social accounting matrix), otherwise cited. Keep every cited parameter and every reproduced published number in one registry file that the code writes and the text reads. When a recomputation disagrees with a source, find which side is wrong and record it in `docs/ERRATA.md` with the arithmetic that shows it; never copy a number that does not reproduce. If the source prints code, transcribe it and plan it beside its Python twin with a translation table.

Then write the JavaScript twin to the engine interface in `shell.md`, export solved cases from the kit, and test that the twin matches each. A subject with no computable model has no kit and no twin: its checks reveal a written answer, and its panels draw from the cited data. Done when the kit's tests pass and the twin matches every exported case, or, without a model, when a test reproduces every number a panel draws from the cited data.

## 3. Shell

Build the page shell to the component list in `shell.md`; if a `shell/` folder exists next to this file, start from it instead. The project layout is: `data/` raw inputs only, `src/` all code (kit, engine, panels, tests, and the scripts numbered in run order: `01_export_cases.py`, `02_build.py`, `03_verify_render.py`), `book/` the hand-written content (`chapters/*.md`, `manifest.json`, `glossary.json`, `terms.json`), `output/` everything generated (`index.html`, `models.json`, `cases.json`), `docs/` the spec, plan, references and errata. The README opens with this map. Done when chapter 1 builds and `03_verify_render.py` reports no problems, with the engine badge at N/N when there is an engine.

## 4. Chapters

Each chapter follows one anatomy:

- Prose written for a reader new to the subject, as described below.
- Headings carry the source's section number, or in a topic book the citation key of the main reference, so coverage is checkable.
- Every displayed equation is one block of three rows: what it means in one plain sentence, the equation with the running example's numbers plugged in, then the symbolic form with dual notation.
- Every symbol and term is in the glossary, which lights up on hover in the right rail.
- Derivations, code listings and deeper panels sit in collapsed `<details>` and do not count toward the budget.
- Each panel has a title, one sentence saying what to watch, its controls in one row, the chart, a table view and a reset to the base values.
- The chapter ends with 3 to 5 predict-then-test checks: a change, direction buttons for one variable, the engine's answer (or the revealed answer), a one-line reason and a link to the section that explains it.

The prose explains directly, the way a colleague would, rather than staging the material like a lecturer: no aphorisms, no "two things surprise people", no announcing what the reader is about to learn. It keeps the field's real terms and defines each one inside the sentence that first needs it. For a mechanism it shows the worked example first, then the mechanism in plain words, then the name of the theory. It states the final result only, never how the author got there; it makes each point once; it uses no em-dashes, no "not X but Y", no unnecessary hyphens between words, no bold for emphasis, and lists only for items that really are parallel.

Done for a chapter when it builds without lint errors, its words and minutes are within the manifest's numbers, every panel and check in the spec's map for it works in the page, and a reread as the reader finds no sentence to cut.

## 5. Verify and publish

Run the kit's tests, the JavaScript tests, `02_build.py` and `03_verify_render.py`. Open the page and look at every chapter in light and dark themes and at phone width. List everything in the spec (every chapter, panel, check, reproduced number) and confirm each is in the rendered page. Give a fresh reviewer agent the user's request and the spec, and fix what it finds. Publish the page, and put the link in the README with how to run the model, what the book leaves out, and the errata. If this book built its shell from `shell.md`, save the shell as `shell.md` describes. Done when every check above passes and every spec item is in the published page.
