---
name: chaynikbook
description: "Explain a topic, method, paper or model briefly from scratch as one explorable HTML page: worked example, equations with labelled parts and step-by-step derivations, a few live panels. A whole book only when the user asks for one."
argument-hint: "topic, source (PDF path or citation) or model, and who the reader is"
disable-model-invocation: true
---

A chaynikbook explains a subject to a reader with no background, briefly, as one self-contained HTML page: prose, equations, a few interactive panels, and numbers that come from code. The default is a short explainer. A full book, with chapters, a computed model and a JavaScript twin, is built only when the user asks for a book or for a source to be covered whole.

## 1. Size the job first

State in chat, in three to five lines, and then proceed without waiting:

- the reader, and what they can do at the end;
- the running example (one small named case whose numbers every section reuses);
- the sections, each one line;
- the size: an explainer by default, which is one page of 1 to 4 sections, about 800 to 2,500 words on the main path, 1 to 3 panels, a few predict-then-test checks; a book when asked.

Only a book gets the brainstorming, a written spec and a plan (section 5). For an explainer the size line above is the spec. Cover what the subject needs to be understood and used; leave the rest out, naming it in one line at the end.

## 2. Numbers

Every number on the page comes from a script or a cited source, never from memory. For an explainer, one script `src/01_numbers.py` computes the running example and writes `data/cases.json`; the page reads it through `{{tokens}}`. A panel that recomputes live does so in its own JavaScript, checked against the script at two or three points by an assert in the script's output. Build a full kit and twin only in book mode.

## 3. Shell

Copy the files of `~/.claude/skills/chaynikbook/shell/kit/` (not its `sample/`) into a `book/` folder in the project, and say in the README that `book/` holds the page and the code that builds it. `book/data/` holds only what the page shows, since every JSON there is embedded in the published page; raw inputs stay in the project's `data/`. The page writes only `book.json`, `chapters/`, `data/`, its `panels_<name>.js` and, if it recomputes live, `engine.js`; the kit's `README.md` says what each needs and `sample/` is a one-chapter page that passes. Section 4 writes out what to take from the reference books, so do not open or adapt them. From `book/`, run `python check.py`: it builds, runs the render test and the secret scan, and prints only failures.

## 4. Page elements

These hold in both sizes.

- Prose follows the `writing` skill's from-scratch mode. Each section runs in the order things happen: what the step is for in one or two sentences, the running example worked through with its numbers and a visual, the mechanism in plain words, then the method's name and its literature. The page teaches the subject and never reports how it was made: no reruns, fixes, review findings or code locations in prose. Reread each paragraph for the question it leaves open and answer it in place, or cut what raises it.
- The CGE book (`Desktop\CBU\cge_book`) is the model of how a page makes a subject easy, and its patterns hold on every page:
  - The running example is a cast. Its actors have names and one colour each (the Farm, the Factory, the Owner household), and its numbers are small and round enough to check in the head (outputs of 100, incomes of 50 and 25). A real case with large numbers gets a round twin for the explanation, and the real numbers then confirm it.
  - The whole subject is stated first, in two or three plain sentences the reader can hold: "There are only two rules in the whole book. Households spend their income on the bundle they like best. Firms make their output at the lowest cost they can."
  - Each section opens on the question the previous one left open ("Two rules are not a model."), then follows one thing through in the order it happens ("Follow one unit of money.").
  - The reader predicts before the rule is shown ("Before the rules, four questions."), and a new idea is tied to something the reader already knows, such as a curve from an introductory course.
  - The tempting wrong reading is named and corrected where it arises: "It is tempting to say food got 27.7 per cent dearer. That is wrong." A panel comes with a tour of concrete settings, each one showing one such reading ("Set the split to 1 … and read the price of food as 1.277").
  - One idea per paragraph, at most 110 words. Most sentences are under 25 words, and a chapter has at most three over 35. The last chapter reads like the first: `check.py` counts per chapter, because drift starts in the later batches.
  - A symbol is introduced by `[[key]]` (its name with its symbol) before any equation uses it. An equation is never followed by "here $k$ is".
  - What the example leaves out is said once, with where it arrives ("Nobody in this economy is idle, saving, trading abroad, or paying tax. Those arrive in chapters 5, 6 and 7."). A limit of the method is one sentence where it applies, never threaded through the explanation. The page never describes the system's internals (what is logged, what runs nightly, what a report prints, which file computes what), and the build flags the words that do.
- Every displayed equation is an `eq` block of three rows: what it means in one sentence, the equation with the running example's numbers, the symbolic form. The numbers row is the symbolic form with every symbol replaced by its value, worked to the result as Photomath would: $ID_{\text{food}} = \underbrace{0.2 \times 100}_{\text{to the Farm}} + \underbrace{0.5 \times 100}_{\text{to the Factory}} = 70$. No symbol stays right of an "=" (operators such as $e$ and $P$ may), a formula of symbols never jumps to its value (`N - L = 3,213.35` is written `5,000 - 1,786.65 = 3,213.35`), and a row that only lists values fails the build, including for a product written side by side ($Z = \alpha Y$).
- Every group of symbols that means one thing together (a ratio, a product, a difference, a sum, a probability, an exponent) has a curly brace under it with its meaning in about six defined words, `\underbrace{N - \ell L}_{\text{what a late unit brings back}}`: in the symbols row, and in a derivation on the line where the group first appears and on the last line. Inner groups get their own brace, at most two deep. A label says what the group is, checked against the meaning row. A rule that picks among several solutions, or a sum over pieces, states which one is picked and which pieces count, including the case with none.
- A derivation is a `steps` block worked like an old Photomath solution: the first line is the starting equation and where it comes from, each later line the whole equation after exactly one operation, with the operation named on the right in at most 16 words ("divide both sides by $N$"); a longer rule is two operations. No step is skipped; "simplify" and "rearrange" never name a step. A numbers row that needs an intermediate result the reader must hold in mind becomes a `steps` block too. Derivations the point rests on are on the main path; others go into collapsed `<details>`.
- Every symbol and term is in the glossary with a definition in words (`def`): what it is, its unit, what sets it or what it moves, using only words defined by its section. A name alone is no definition. The rail shows it on hover and under each row, any other symbol list is generated from the same files, and the build fails an entry without one. Every letter and Greek letter in math is a glossary entry, so every one highlights, including one written `\mathrm{d}` or `\operatorname{E}`; math in `check` and `panel` JSON is not linted, so keep symbols out of it: indices ($i$, $j$, $k$), dummy variables and operators too (type `op`: $P$ for a probability, $E$ for an expectation, $\Delta$ for a change, $e$, $d$ in an integral). A letter that means two things in two chapters gets an `"in": [chapter ids]` list on each entry; it never means two things in one chapter, and the build fails on an unmarked letter or a clash.
- Each panel has a title, one what-to-watch sentence in defined words, its controls in one row, the chart, a table view and a reset. Axes stay fixed while a control moves, so the curves move: the kit sweeps each panel after load and fixes each chart's range, capped at 2.5 times the base view. A dropdown that changes what the axis measures (another case, horizon, zoom or view) marks itself `data-axes="own"`; a mark pushed past the axes keeps its label at the edge with an arrow, and a chart whose watched mark would leave takes a wider `stretch`.
- A section ends with 1 to 3 predict-then-test checks (3 to 5 per chapter in a book): a change, direction buttons, the answer from the engine or from a script's output, a one-line reason and a link to the section.
- The page carries the notes drawer: notes numbered "1*" in the right margin level with the quoted passage. Publish with `capabilities: {db: {}, user: {}}`; before revising a published page, read the user's notes with `ArtifactData` and treat each as a change request.

## 5. Book mode

When the user asks for a book: brainstorm (`superpowers:brainstorming`), write `docs/spec.md` with the reader, the running example, the chapter map with minutes, panels and checks, the model and the numbers it must reproduce, the bird's-eye map, the word budget and what is out of scope, then a plan (`superpowers:writing-plans`). For a source, extract its text to `output/source_text.txt` so every step can cite page and section, carry the source's section numbers in the headings so coverage is checkable, and record numbers that do not reproduce in `docs/ERRATA.md`. Write the Python kit with tests that reproduce every published number, a JavaScript twin tested against exported cases, and the whole model reduced by substitution to the fewest equations, shown as a `steps` block and plotted. A map near the start shows what comes after what, and each core chapter ends on it with its own step lit. Show chapter 1 to the user as the model of the voice before writing the rest. Work in sessions by phase (spec and plan, kit and twin, chapters in batches of three or four, verify and publish), each ending with `docs/STATE.md` updated.

## 6. Budget

Tokens go mostly to turns times context, so:

- Edit in batches. Write a section in one go, collect the fixes of a round into one script, and run `check.py` once per batch, never after each edit.
- Read code by function with grep or a line range; the kit's README names what each file holds. Never print a whole data file or index.html.
- Look at the page with the render test first. Take a screenshot only for a visual judgement no probe can make, cropped to the element, at most four per round, and never retake one to confirm what a probe already confirms.
- Run the `refuter` once on the finished page (and once per batch of chapters in a book), naming the files that changed; fix what affects correctness in one pass.
- When the context passes about 150K tokens, update `docs/STATE.md` and say that a fresh session would help.

## 7. Verify and publish

Run `check.py` and the number script's asserts. List what the size line (or the spec) promised and confirm each item is on the page. Look at the page once in light and dark and at phone width. Publish as an Artifact and put the link in the README. Done when the check is green and every promised item is on the published page.
