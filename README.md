# chaynikbook

A Claude Code skill that turns a textbook, a paper or a topic into an explorable book for dummies: one interactive HTML page that takes a reader with no background to the point where they can use the subject on a question of their own. "Chaynik" is Russian slang for a complete beginner.

Every number in the book is recomputed by a model rather than copied. A Python kit reproduces the source's published tables, and a JavaScript twin of the same model runs in the page, so every slider re-solves the model and every check asks the reader to predict a result before the model shows it. When the recomputation disagrees with the source, the book records the arithmetic in an errata file instead of repeating the error.

## What a book contains

- Chapters reordered for learning, covering everything in the source, with depth added where the source states an assumption without showing what it costs.
- One small running example reused in every chapter, so numbers stay comparable from start to finish.
- Equations shown as three rows: what the equation means in a sentence, the equation with the example's numbers plugged in, and the symbolic form, with a readable name beside every symbol.
- A glossary in the right rail that lights up when the reader hovers a symbol or term.
- Interactive panels with a table view and a reset to the base values, and three to five predict-then-test checks at the end of each chapter.
- Derivations, code and deeper material collapsed, outside the stated reading time.
- A self-test badge that re-solves, in the browser, every case the Python kit solved.

## Install

Copy the skill folder into your Claude Code skills directory:

```bash
git clone https://github.com/Abdua-R/chaynikbook
cp -r chaynikbook/skills/chaynikbook ~/.claude/skills/
```

## Use

In Claude Code, run:

```
/chaynikbook <PDF path, citation or topic> <who the reader is>
```

The skill works in five steps, each with a condition that ends it: a spec and plan agreed with you, the model and its tests before any prose, the page shell, the chapters, and a final round of tests, render checks and review before publishing. `skills/chaynikbook/SKILL.md` has the details and `skills/chaynikbook/shell.md` specifies the subject-independent page components. The first book you build saves its shell next to the skill, so later books start from it.

## Requirements

Python 3 with the libraries the model needs, pandoc, Node.js for the JavaScript tests, and Chrome or Chromium for the headless render check. The page loads MathJax from a CDN; everything else is inlined. The skill uses `superpowers:brainstorming` and `superpowers:writing-plans` when the [superpowers](https://github.com/obra/superpowers) plugin is installed, and works without it.

## License

MIT
