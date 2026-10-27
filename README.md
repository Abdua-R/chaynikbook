# chaynikbook

A Claude Code skill that explains a topic, a method, a paper or a model to a reader with no background, briefly, as one explorable HTML page. "Chaynik" is Russian slang for a complete beginner. The default output is a short explainer of one to four sections; a whole book with chapters, a computed model and a JavaScript twin is built only when you ask for one.

Every number on the page comes from a script or a cited source. In book mode, a Python kit reproduces the source's published tables and a JavaScript twin of the same model runs in the page, so every slider re-solves the model; numbers that do not reproduce are recorded with their arithmetic in an errata file.

## What a page contains

- One small running example reused in every section, so numbers stay comparable from start to finish.
- Equations shown as three rows: what the equation means in a sentence, the equation with the example's numbers plugged in, and the symbolic form, with a labelled curly brace under every group of symbols that means one thing together.
- Derivations worked one operation per line, with the operation named beside each line.
- A glossary in the right rail with a definition in words for every symbol and term; the build fails an entry without one.
- Interactive panels with fixed axes (the curves move when a control moves, the axes stay put), a table view and a reset, and predict-then-test checks at the end of each section.
- A notes drawer for the reader, with numbered marks in the right margin.

## Install

Copy the skill folder into your Claude Code skills directory:

```bash
git clone https://github.com/Abdua-R/chaynikbook
cp -r chaynikbook/skills/chaynikbook ~/.claude/skills/
```

## Use

In Claude Code, run:

```
/chaynikbook <topic, PDF path or citation> <who the reader is>
```

The skill states the reader, the running example, the sections and the size in a few lines, then builds. `skills/chaynikbook/SKILL.md` has the rules. `skills/chaynikbook/shell/kit/` is the page shell: copy it into a `book/` folder, write the chapters, data and panels, and run `python check.py` to build the page, run the render test and the secret scan. The kit's `README.md` says what each file holds, and `sample/` is a one-chapter page that passes.

## Requirements

Python 3, pandoc, and Chrome or Chromium for the headless render check. The page loads MathJax from a CDN; everything else is inlined. Book mode uses `superpowers:brainstorming` and `superpowers:writing-plans` when the [superpowers](https://github.com/obra/superpowers) plugin is installed, and works without it.

## License

MIT
