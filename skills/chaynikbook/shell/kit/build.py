"""Build index.html from chapters/*.md (the chaynikbook kit, generalized from the MarketResearcher explainer).

Usage: python <kit>/build.py [--local], run from the book folder.

The book folder holds book.json, chapters/, data/ and optionally engine.js and panels_*.js; the kit folder (this
file's folder, which may be the book folder itself) holds template.html, style.css, notes.css, viz.js, page.js
and notes.js. book.json: title, subtitle, data_global (default BOOK_DATA), word_limit, currency (suffix of the
sum and sum2 formats, e.g. " сум"), and for verify_render.py checks_per_chapter [min, max] (default [1, 5]). An optional
book.css is appended to the kit's styles.

--local wraps the output in a full html document so it opens from the file system. Without it
the output is the body fragment an Artifact expects.

Markdown conventions:
  {{a.b.c|int}}                   a number from data/: cases.json is the root, any other data/<stem>.json
                                  sits under <stem>, data/extra_<name>.json under x.<name>; formats in FORMATS. An unknown
                                  path, a null value or an unknown format fails the build
  [[key]]                         a symbol from data/glossary.json, rendered as name (symbol)
  ```eq ... ```                   an equation block: id, code, title, meaning, numbers, symbols
  ```steps ... ```                a derivation: title, then one "math // rule" line per operation
  ```panel {json} ```             a panel mounted by viz.js, of a type a panels_*.js registers
  ```check {json} ```             a predict-then-test check mounted by page.js: q, label, why, ref, and either
                                  out + changes + expect (engine.js computes the answer) or answer + reveal
  ```map {json} ```               the bird's-eye map from the manifest's steps: {"full": true} for the
                                  map with what each step computes, {"lit": "ch4"} for a chapter's end
  ::: review ... :::              the "for the review" box at the end of a chapter
"""
import collections
import html
import json
import math
import pathlib
import re
import subprocess
import sys

KIT = pathlib.Path(__file__).parent
ROOT = pathlib.Path.cwd()  # the book folder
BOOK = {"data_global": "BOOK_DATA", "word_limit": 30000, "currency": "", "subtitle": "",
        **json.loads((ROOT / "book.json").read_text(encoding="utf-8"))}
G = json.loads((ROOT / "data/glossary.json").read_text(encoding="utf-8"))
MAN = json.loads((ROOT / "chapters/manifest.json").read_text(encoding="utf-8"))
TERMS = json.loads((ROOT / "data/terms.json").read_text(encoding="utf-8"))
WORD_LIMIT = BOOK["word_limit"]
# longest phrases first, so "negative binomial distribution" wins over "binomial distribution"
TERM_PHRASES = sorted(
    ((k, sorted(v.get("match", [v["name"]]), key=len, reverse=True)) for k, v in TERMS.items()),
    key=lambda kv: -max(len(p) for p in kv[1]))

errors = []
used_symbols = set()
math_hits = collections.Counter()

SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _group(x, nd=0):
    s = f"{abs(x):,.{nd}f}"
    return ("−" if x < 0 and float(s.replace(",", "")) != 0 else "") + s


def _sci2(x, nd=1):
    if x == 0:
        return "0"
    e = math.floor(math.log10(abs(x)))
    m = round(x / 10 ** e, nd)
    if abs(m) >= 10:
        m, e = m / 10, e + 1
    return f"{m:.{nd}f}".replace("-", "−") + " × 10" + str(e).translate(SUPERSCRIPT)


# Fixed rules, so a rate of 6e-8 and a sum of 70 million both stay readable; viz.js prints the same
FORMATS = {
    "int": lambda x: _group(x),
    "sum": lambda x: _group(x) + BOOK["currency"],
    "sum2": lambda x: _group(x, 2) + BOOK["currency"],
    "num2": lambda x: _group(x, 2),
    "pct1": lambda x: f"{100 * x:.1f}".replace("-", "−") + "%",
    "pct0": lambda x: f"{100 * x:.0f}".replace("-", "−") + "%",
    "pct2": lambda x: f"{100 * x:.2f}".replace("-", "−") + "%",
    "sci2": _sci2,
    "sci4": lambda x: _sci2(x, 3),
    "pct3": lambda x: f"{100 * x:.3f}".replace("-", "−") + "%",
    "fix1": lambda x: f"{x:.1f}".replace("-", "−"),
    "fix2": lambda x: f"{x:.2f}".replace("-", "−"),
    "fix4": lambda x: f"{x:.4f}".replace("-", "−"),
    "fix8": lambda x: f"{x:.8f}".replace("-", "−"),
}


def fmt(v, f):
    return FORMATS[f](v)


TOKEN = re.compile(r"\{\{([a-z_]\w*(?:\.[\w-]+)+)(?:\|(\w+))?\}\}")


def tokens(md, data):
    """Replace every {{path|fmt}} with the value at that path in data. Template slots such as
    {{CSS}} have no dot and are left alone."""
    def one(mo):
        path, f = mo.group(1), mo.group(2)
        v = data
        for k in path.split("."):
            if isinstance(v, list) and k.isdigit() and int(k) < len(v):
                v = v[int(k)]
            elif isinstance(v, dict) and k in v:
                v = v[k]
            else:
                errors.append(f"unknown token {{{{{path}}}}}")
                return mo.group(0)
        if v is None:
            errors.append(f"token {{{{{path}}}}} is null")
            return mo.group(0)
        if f is None:
            if isinstance(v, str):
                return v
            errors.append(f"number token {{{{{path}}}}} needs a format")
            return mo.group(0)
        if f not in FORMATS:
            errors.append(f"unknown format {f} in {{{{{path}}}}}")
            return mo.group(0)
        return fmt(v, f)
    return TOKEN.sub(one, md)


def _visible(ch):
    return {k: v for k, v in G.items() if not v.get("in") or ch in v["in"]}


def _math_patterns(ch):
    r"""Which literal pieces of TeX stand for a glossary symbol in chapter ch, so a symbol inside a rendered
    equation can be pressed like one in the prose (see page.js, tagMath). An entry with "in": [chapter ids]
    exists only in those chapters, so one letter can mean two things in two chapters, never in one."""
    pats, dupes = {}, set()
    for k, v in _visible(ch).items():
        forms = {v["tex"], re.sub(r"\(.*\)$", "", v["tex"])}
        for f in (x.strip() for x in forms):
            if not f or f.startswith("-"):
                continue
            if pats.get(f, k) != k:
                dupes.add(f)
            pats[f] = k
    for f in dupes:
        pats.pop(f, None)
        errors.append(f"{ch}: two glossary entries are written ${f}$; give one of them an \"in\" list of chapters")
    family = {}
    for k, v in _visible(ch).items():
        head = re.split(r"[_^(]", v["tex"], maxsplit=1)[0]
        if head and head != v["tex"]:
            family.setdefault(head, set()).add(k)
    family = {h: ks.pop() for h, ks in family.items() if len(ks) == 1}
    return sorted(pats.items(), key=lambda kv: -len(kv[0])), family


PATTERNS = {}
CUR = {"ch": None}  # the chapter being built, so a symbol is matched against that chapter's glossary


def patterns(ch):
    if ch not in PATTERNS:
        PATTERNS[ch] = _math_patterns(ch)
    return PATTERNS[ch]


for _k, _v in G.items():
    if _v.get("nopattern"):
        errors.append(f'glossary {_k} has nopattern, which leaves it unhighlighted; scope it with "in": [chapter ids]')
SUBSCRIPT = re.compile(r"[_^](\{(?:[^{}]|\{[^{}]*\})*\}|\\[A-Za-z]+|.)")
TEXT_MACRO = re.compile(r"\\(?:text|mathrm|operatorname)(?:bf|it|rm|sf|tt)?\{[^{}]*\}")


HIDDEN = re.compile(r"\\(?:text|mathrm|operatorname)(?:bf|it|rm|sf|tt)?\{[^{}]*\}"
                    r"|\\(?:begin|end|hspace|vspace|color|textcolor|phantom)\{[^{}]*\}")


def _hide(s):
    """Text inside \\text{...} and the like keeps its length and content but loses its ASCII letters, so no symbol
    matches inside a label while a glossary symbol written with \\text (\\lambda_{\\text{cat}}) still matches whole."""
    return HIDDEN.sub(lambda mo: mo.group(0)[:mo.group(0).index("{") + 1]
                          + "".join(chr(0xE000 + ord(c)) if c.isascii() and c.isalpha() else c
                                    for c in mo.group(0)[mo.group(0).index("{") + 1:]), s)


def _unhide(s):
    return "".join(chr(ord(c) - 0xE000) if 0xE000 <= ord(c) < 0xE080 else c for c in s)


IN_MACRO = re.compile(r"\\[A-Za-z]*$")


def _mark_chunk(s, pats, family, count=True):
    found = []
    for pat, key in pats:
        hp = _hide(pat)
        bare = "_" not in pat and "^" not in pat
        macro = pat.startswith("\\")
        at = s.find(hp)
        while at >= 0:
            i, n, after = at, len(hp), s[at + len(hp):]
            at = s.find(hp, at + 1)
            # a letter is a symbol unless it is part of a macro name (\frac) or of a longer glossary symbol, which
            # sorts first; a macro symbol (\theta) may follow a letter, as in E\theta
            if not macro and IN_MACRO.search(s[:i]):
                continue
            if i and s[i - 1] == "\\":
                continue
            if macro and after[:1].isalpha():
                continue
            rank, k = 0, key
            if bare and after[:1] in ("_", "^"):
                mo = SUBSCRIPT.match(after)
                if not mo:
                    continue
                n += mo.end()
                rank = 1
                if after[:1] == "_":
                    k = family.get(pat, key)
            found.append((i, -n, rank, k))
    found.sort()
    out, pos = [], 0
    for i, neg, _, key in found:
        if i < pos:
            continue
        out.append(s[pos:i])
        out.append("\\class{sym-k-%s}{%s}" % (key, s[i:i - neg]))
        if count:
            math_hits[key] += 1
        pos = i - neg
    out.append(s[pos:])
    return "".join(out)


def mark_math(tex):
    pats, family = patterns(CUR["ch"])
    marked = _unhide(_mark_chunk(_hide(tex), pats, family))
    if _unmark(marked) != tex:
        errors.append("marking symbols changed an equation: " + tex[:70])
        return tex
    for tok in leftover_symbols(marked):
        unmarked[(CUR["ch"], tok)] += 1
        unmarked_eg.setdefault((CUR["ch"], tok), tex[:60])
    return marked


GREEK = set(("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta kappa lambda mu nu xi pi rho "
             "sigma tau phi varphi chi psi omega ell Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega").split())
NOT_MATH = re.compile(r"\\(?:text\w*|mathrm|operatorname|begin|end|hspace|vspace|color|textcolor|phantom)\{[^{}]*\}")
unmarked = collections.Counter()
unmarked_eg = {}


def _strip_marks(s):
    out, i = [], 0
    while True:
        mo = CLASS_OPEN.search(s, i)
        if not mo:
            return "".join(out) + s[i:]
        out.append(s[i:mo.start()] + " ")
        depth, j = 1, mo.end()
        while j < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            j += 1
        i = j


def leftover_symbols(marked):
    """Letters and Greek letters left in math once glossary marks, text and macro names are taken out: each is a
    symbol the reader cannot look up, so the build fails on it."""
    s = _strip_marks(marked)
    named = re.findall(r"\\(?:mathrm|operatorname)\{([^{}]*)\}", s)
    s = NOT_MATH.sub(" ", s)
    return named + [mo.group(1) or mo.group(2) for mo in re.finditer(r"\\([A-Za-z]+)|([A-Za-z]+)", s)
            if mo.group(2) or mo.group(1) in GREEK]


def keys_in(tex, ch):
    pats, family = patterns(ch)
    return re.findall(r"\\class\{sym-k-([A-Za-z0-9]+)\}", _mark_chunk(_hide(tex), pats, family, False))


CLASS_OPEN = re.compile(r"\\class\{sym-k-[A-Za-z0-9]+\}\{")


def _unmark(s):
    out, i = [], 0
    while True:
        mo = CLASS_OPEN.search(s, i)
        if not mo:
            out.append(s[i:])
            return "".join(out)
        out.append(s[i:mo.start()])
        depth, j = 1, mo.end()
        while j < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            j += 1
        out.append(s[mo.end():j - 1])
        i = j


used_terms = set()
term_hits = {}
check_refs = set()


def sym(mo):
    key = mo.group(1)
    if key not in G:
        errors.append(f"unknown symbol [[{key}]]")
        return key
    used_symbols.add(key)
    g = G[key]
    return (f'<span class="sym sym-{g["type"]}" data-sym="{key}">'
            f'{g["name"]} (${g["tex"]}$)</span>')


def eq_block(body):
    fields = dict(re.findall(r"^(\w+):[ \t]*(.*)$", body, re.M))
    for k in ("id", "title", "meaning", "numbers", "symbols"):
        if not fields.get(k):
            errors.append(f'equation block missing {k}: {body.strip()[:60]!r}')
    eid = fields.get("id", "")
    # a thousands comma in TeX is punctuation and gets a space after it: 27,495 would read "27, 495"
    for k in ("numbers", "symbols"):
        fields[k] = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "{,}", fields.get(k, ""))
        # a bare % starts a TeX comment and would swallow the rest of the line
        fields[k] = re.sub(r"(?<!\\)%", r"\\%", fields[k])
    lint_numbers(fields.get("numbers", ""), fields.get("symbols", ""), eid)
    if fields.get("code"):
        errors.append(f"eq {eid}: drop the code field; the page never shows where the code lives")
    return (f'<div class="eq" id="eq-{eid.replace(".", "-")}">'
            f'<span class="id">({eid})</span>'
            f'<strong>{fields.get("title", "")}</strong>'
            f'<div class="meaning">{fields.get("meaning", "")}</div>'
            f'<div class="row"><span class="lbl">with numbers</span>'
            f'<span>$${mark_math(fields.get("numbers", ""))}$$</span></div>'
            f'<div class="row"><span class="lbl">in symbols</span>'
            f'<span>$${mark_math(fields.get("symbols", ""))}$$</span></div></div>')


REL = re.compile(r"=|\\approx|\\ge(?:q)?(?![a-z])|\\le(?:q)?(?![a-z])|<|>")
OPS = re.compile(r"[-+/^]|\\times|\\cdot|\\frac|\\sqrt|\\sum|\\prod|\\int|\\min|\\max|\\log|\\ln|\\exp|\\lceil|\\lfloor"
                 r"|\\(?:operatorname|text|mathrm)\{[^{}]*\}\s*\(")
# a brace's label, which may itself hold a symbol (\underbrace{1}_{p_{\text{Farm}}}), and the index range of a sum
BRACE_LABEL = re.compile(r"\}[_^]\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}")
RANGE = re.compile(r"\\(?:sum|prod|int)(?:_\{[^{}]*\}|_.)?(?:\^\{[^{}]*\}|\^.)?")
SUBS = re.compile(r"_\{(?:[^{}]|\{[^{}]*\})*\}|_.")


def _drop_labels(tex):
    """Keep what a brace groups, drop the brace and its label."""
    out, i = [], 0
    for mo in re.finditer(r"\\(?:underbrace|overbrace)\{", tex):
        if mo.start() < i:
            continue  # a brace inside an outer brace's group is kept with the group and dropped below
        depth, j = 1, mo.end()
        while j < len(tex) and depth:
            depth += {"{": 1, "}": -1}.get(tex[j], 0)
            j += 1
        lab = BRACE_LABEL.match(tex, j - 1)
        out.append(tex[i:mo.start()] + "{" + _drop_labels(tex[mo.end():j - 1]) + "}")
        i = lab.end() if lab else j
    return "".join(out) + tex[i:]


def _clauses(tex):
    """Split a row at commas, quads and line breaks outside brackets, then each clause at its relations outside
    brackets: [[(None, left), (relation, middle), ..., (relation, result)], ...]."""
    out, depth, cur = [], 0, ""
    for piece in re.split(r"(\\qquad|\\quad|\\\\|(?<!\\),(?!\d)|[{}()\[\]]|\\[lr]?[bB]ig[lr]?[\[\]()])", _drop_labels(tex)):
        if piece in ("{", "(", "[") or piece.endswith(("[", "(")) and piece.startswith("\\"):
            depth += 1
        elif piece in ("}", ")", "]") or piece.endswith(("]", ")")) and piece.startswith("\\"):
            depth -= 1
        elif depth == 0 and piece in ("\\qquad", "\\quad", "\\\\", ","):
            out.append(cur)
            cur = ""
            continue
        cur += piece
    out.append(cur)
    res = []
    for c in out:
        parts, rels, depth, last, i = [], [None], 0, 0, 0
        while i < len(c):
            depth += {"{": 1, "(": 1, "[": 1, "}": -1, ")": -1, "]": -1}.get(c[i], 0)
            mo = REL.match(c, i) if depth == 0 else None
            if mo:
                parts.append(c[last:i])
                rels.append(mo.group(0))
                last = i = mo.end()
                continue
            i += 1
        parts.append(c[last:])
        if len(parts) > 1:
            res.append(list(zip(rels, parts)))
    return res


def _symbols(tex, ch):
    """Glossary symbols in a piece of math, operators ($P$, $E$, $e$) and a sum's index range left out."""
    return [k for k in keys_in(RANGE.sub(" ", tex), ch) if G[k].get("type") != "op"]


def _worked(m):
    """Two numbers or more in one piece outside subscripts: they are combined, so arithmetic is shown."""
    return len(re.findall(r"\d+(?:\.\d+)?", SUBS.sub(" ", m).replace("{,}", ""))) >= 2


def lint_numbers(numbers, symbols, eid):
    """Photomath: the numbers row writes the symbolic form with every symbol replaced by its value and works it to
    the result. No symbol may remain right of an "=", no formula of symbols may be set equal to its value in one
    jump, and when the symbolic form computes anything (an operator, or two symbols side by side, as in a product)
    the numbers row combines numbers."""
    ch = CUR["ch"]
    where = f"{ch} eq {eid}"
    clauses = _clauses(numbers)
    if not clauses:
        errors.append(f"{where}: the numbers row has no equation; write the symbolic form with the values in")
        return
    worked = False
    for clause in clauses:
        parts = [m for _, m in clause]
        # a symbol may sit between two inequalities (27,495 <= x_j <= 82,485), never right of an equals sign
        if any(_symbols(m, ch) for r, m in clause[1:] if r in ("=", r"\approx")):
            errors.append(f"{where}: a symbol is left right of '=' in the numbers row; put its value in: {'='.join(parts)[:70]}")
        left = SUBS.sub(" ", parts[0])
        if len(parts) < 3 and _symbols(parts[0], ch) and OPS.search(left):
            errors.append(f"{where}: a formula of symbols jumps to its value; show it with the numbers in first: {'='.join(parts)[:70]}")
        worked = worked or any(_worked(m) for m in parts)
    computes = any(OPS.search(SUBS.sub(" ", m)) or len(_symbols(m, ch)) > 1
                   for clause in _clauses(symbols) for _, m in clause[1:])
    if computes and not worked:
        errors.append(f"{where}: the symbolic form computes something, the numbers row only lists values; work it on numbers")
    if computes and "\\underbrace" not in symbols:
        errors.append(f"{where}: the symbols row combines symbols with no brace naming a group; add \\underbrace labels")


def steps_block(body):
    """A derivation, Photomath style: one line per operation, the whole equation after it on the left and
    the operation in plain words on the right ("math // rule"); the first line's rule says where it starts."""
    head = dict(re.findall(r"^(id|title):[ \t]*(.*)$", body, re.M))
    lines = [ln for ln in body.splitlines() if ln.strip() and not re.match(r"^(id|title):", ln)]
    if not head.get("title") or len(lines) < 2:
        errors.append(f"steps block needs a title and at least two lines: {body.strip()[:60]!r}")
    rows = []
    for ln in lines:
        tex, _, rule = ln.partition("//")
        if not rule.strip():
            errors.append(f"steps line without a rule after //: {ln.strip()[:60]!r}")
        if re.search(r"(simplif|rearrang|tidy|clean up)", rule, re.I):
            errors.append(f"{CUR['ch']}: a step named 'simplify' or 'rearrange' hides its operation: {rule.strip()[:70]!r}")
        cap = 25 if not rows else 16  # the author's judgement: an operation fits in a short instruction
        if len(re.sub(r"\$[^$]*\$", "X", rule).split()) > cap:
            errors.append(f"{CUR['ch']}: a step's rule over {cap} words is more than one operation: {rule.strip()[:70]!r}")
        tex = re.sub(r"(?<!\\)%", r"\\%", re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "{,}", tex.strip()))
        rows.append(f'<li><span class="st-math">$${mark_math(tex)}$$</span><span class="st-rule">{rule.strip()}</span></li>')
    sid = head.get("id", "")
    return (f'<div class="steps"{f' id="steps-{sid.replace(".", "-")}"' if sid else ""}>'
            f'<strong>{head.get("title", "")}</strong><ol>{"".join(rows)}</ol></div>')


def map_block(obj):
    """The order of the computation as one line of numbered stops, each linked to its chapter. The
    steps are the manifest entries that carry a "step"; one marked "aside" sits off the line. One
    line of html, so pandoc passes it through untouched."""
    lit, full = obj.get("lit"), obj.get("full", False)
    steps = [c for c in MAN if c.get("step")]
    if lit and lit not in {c["id"] for c in steps}:
        errors.append(f"map lights {lit}, which is not a step")

    def code(s):
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(s))
    items = []
    for k, c in enumerate((c for c in steps if not c.get("aside")), 1):
        on = c["id"] == lit
        items.append(f'<li{' class="lit"' if on else ""}><a href="#{c["id"]}"{' aria-current="step"' if on else ""}>'
                     f'<span class="mstep">{k}</span><span class="mname">{html.escape(c["step"])}</span>'
                     f'<span class="mch">Chapter {c["id"][2:]}{", this chapter" if on else ""}</span></a>'
                     + (f'<span class="mdoes">{code(c["does"])}</span>' if full else "") + "</li>")
    side = "".join(f'<p class="maside">Off the line: <a href="#{c["id"]}">Chapter {c["id"][2:]}, {html.escape(c["step"])}</a>: '
                   f'{code(c["does"])}.</p>' for c in steps if c.get("aside"))
    cap = "The steps, in the order this book explains them" if full else "Where this chapter sits among the steps"
    return (f'<figure class="map" data-lit="{lit or ""}"><figcaption>{cap}</figcaption>'
            f'<ol>{"".join(items)}</ol>{side}</figure>')


def fence(mo):
    kind, body = mo.group(1), mo.group(2)
    if kind == "eq":
        return eq_block(body)
    if kind == "steps":
        return steps_block(body)
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        errors.append(f"bad json in a {kind} block: {exc}")
        return ""
    if kind == "map":
        return map_block(obj)
    if kind == "check":
        miss = [k for k in ("id", "q", "label", "why", "ref") if not obj.get(k)]
        if not (obj.get("out") or obj.get("reveal") and obj.get("answer") in ("up", "down", "no change")):
            miss.append("out, or reveal with an answer of up, down or no change")
        if obj.get("out") and obj.get("expect") not in ("up", "down", "no change"):
            miss.append("expect (the direction the why text explains, which verify_render.py confirms)")
        if miss:
            errors.append(f'check {obj.get("id", "?")} missing {", ".join(miss)}')
        if obj.get("out") and not (ROOT / "engine.js").exists():
            errors.append(f'check {obj.get("id", "?")} has "out" but the book has no engine.js')
        check_refs.add(obj.get("ref", "").lstrip("#"))
    attr = html.escape(json.dumps(obj), quote=True)
    return f'<div class="{kind}" data-{kind}="{attr}"></div>'


def term_span(key, shown):
    t = TERMS[key]
    used_terms.add(key)
    return f'<span class="term term-{t["kind"]}" data-term="{key}">{shown}</span>'


def mark_terms(md, chapter_id):
    """Link every use of each term. Fenced blocks, headings and details summaries are left
    alone: a match inside a panel's JSON or inside TeX would corrupt it."""
    parts = re.split(r"(```.*?```|^#[^\n]*$|^:::[^\n]*$|<details>|</details>|\$\$[^$]*\$\$|\$[^$\n]+\$)",
                     md, flags=re.S | re.M)
    out = []
    for part in parts:
        if part is None:
            continue
        if part.startswith(("```", "#", "<details", ":::", "$")):
            out.append(part)
            continue
        for key, phrases in TERM_PHRASES:
            for phrase in phrases:
                body_pat = r"\s+".join(re.escape(w) for w in phrase.split())
                pat = re.compile(r'(?<![\w\[/>"{.-])(' + body_pat + r's?)(?![\w\]"}-])',
                                 re.IGNORECASE)
                n = len(pat.findall(part))
                if not n:
                    continue
                part = pat.sub(lambda mo: term_span(key, mo.group(1)), part)
                term_hits[chapter_id] = term_hits.get(chapter_id, 0) + n
        out.append(part)
    marked = "".join(out)
    if _unmark_terms(marked) != md:
        errors.append(f"linking terms changed the prose of {chapter_id}")
        return md
    return marked


TERM_OPEN = re.compile(r'<span class="term term-(?:term|concept)" data-term="[\w-]+">')


def _unmark_terms(marked):
    back = TERM_OPEN.sub("", marked)
    for _ in range(len(TERM_OPEN.findall(marked))):
        back = back.replace("</span>", "", 1)
    return back


def mark_prose_math(md):
    def one(mo):
        return mo.group(1) + mark_math(mo.group(2)) + mo.group(1)

    out = []
    for part in re.split(r"(```.*?```)", md, flags=re.S):
        if not part.startswith("```"):
            part = re.sub(r"(\$\$)([^$\n]+)\1", one, part)
            part = re.sub(r"(?<!\$)(\$)([^$\n]+)\1(?!\$)", one, part)
        out.append(part)
    return "".join(out)


INTRODUCED = set()  # symbols the text has introduced with [[key]] so far, in reading order across chapters


def lint_order(md, ch):
    """A symbol appears in math only after the text has introduced it in words with [[key]], earlier in this
    chapter or in an earlier one (an eq block's meaning row counts, as it is read before the equation)."""
    def steps(mo):
        return "\n" + "\n".join("" if re.match(r"^(id|title):", ln) else
                                "$" + ln.partition("//")[0] + "$ " + ln.partition("//")[2]
                                for ln in mo.group(1).splitlines()) + "\n"
    scan = re.sub(r"```steps\n(.*?)```", steps, md, flags=re.S)
    scan = re.sub(r"```(?:panel|check|map)\n.*?```", lambda mo: "\n" * mo.group(0).count("\n"), scan, flags=re.S)
    scan = re.sub(r"^(?:numbers|symbols):(.*)$", lambda mo: "$" + mo.group(1) + "$", scan, flags=re.M)
    late = {}
    for mo in re.finditer(r"\[\[([\w:-]+)\]\]|\$\$?([^$]+?)\$\$?", scan):
        if mo.group(1):
            INTRODUCED.add(mo.group(1))
            continue
        for key in keys_in(mo.group(2), ch):
            if key not in INTRODUCED and key not in late:
                late[key] = scan.count("\n", 0, mo.start()) + 1
    for key, line in late.items():
        errors.append(f"{ch}:{line} {G[key]['name']} (${G[key]['tex']}$) is in math before the text introduces it as [[{key}]]")


NARRATION = re.compile(r"\b(each night|every night|nightly|logs? (?:a|the|every|each)|is logged|the script|the code"
                       r"|prints?|in the file|the database)\b", re.I)


def lint_prose(md, ch):
    """The CGE book's measure (its longest paragraph is 102 words, and no chapter has more than three sentences
    over 35 words): no paragraph or list item over 110 words, at most three sentences over 35 words a chapter.
    And the page teaches the subject, so it never narrates the system's internals."""
    t = re.sub(r"```.*?```|<details>.*?</details>", lambda mo: "\n" * mo.group(0).count("\n"), md, flags=re.S)
    long_s, line = [], 1
    for para in re.split(r"(\n\s*\n|\n(?=\s*(?:[-*]|\d+\.) ))", t):
        body = re.sub(r"^\s*(?:[-*]|\d+\.|:::\s*\w*)\s+", "", para)
        if para.strip() and not para.lstrip().startswith(("#", "|", "<")) and body.strip():
            flat = re.sub(r"\$[^$]*\$", "X", body)
            n = len(flat.split())
            if n > 110:
                errors.append(f"{ch}:{line} a paragraph of {n} words; split it at its second idea (cap 110)")
            long_s += [line for s in re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\[\$\"(Ѐ-ӿ])", flat) if len(s.split()) > 35]
            for mo in NARRATION.finditer(flat):
                errors.append(f"{ch}:{line} '{mo.group(0)}' narrates the system; say what the method does instead")
        line += para.count("\n")
    if len(long_s) > 3:
        errors.append(f"{ch}: {len(long_s)} sentences over 35 words (cap 3), at lines {', '.join(map(str, long_s[:8]))}")


def preprocess(md, chapter_id, data):
    CUR["ch"] = chapter_id
    md = tokens(md, data)
    lint_order(md, chapter_id)
    lint_prose(md, chapter_id)

    def anchor(mo):
        return f"{mo.group(0)} {{#s{mo.group(1).replace('.', '-')}}}"
    md = re.sub(r"^## (\d+\.\d+)[^\n]*$", anchor, md, flags=re.M)
    md = mark_terms(md, chapter_id)
    md = mark_prose_math(md)
    md = re.sub(r"```(eq|steps|panel|check|map)\n(.*?)```", fence, md, flags=re.S)
    return re.sub(r"\[\[([\w:-]+)\]\]", sym, md)


def pandoc(md):
    # --wrap=none: a newline inside a TeX text macro makes MathJax swallow the space
    out = subprocess.run(["pandoc", "-f", "markdown+bracketed_spans+fenced_divs", "-t", "html5",
                          "--mathjax", "--wrap=none"],
                         input=md, capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        errors.append(f"pandoc failed: {out.stderr.strip()[:300]}")
        return ""
    return out.stdout


def main_path_words(rendered):
    stripped = re.sub(r"<details.*?</details>", " ", rendered, flags=re.S)
    stripped = re.sub(r'<div class="(panel|check)"[^>]*></div>', " ", stripped)
    stripped = re.sub(r'<figure class="map".*?</figure>', " ", stripped, flags=re.S)
    stripped = re.sub(r'<span class="math display">.*?</span>', " ", stripped, flags=re.S)  # TeX source is not reading text
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return len(stripped.split())


def lint_source(md, name):
    for i, line in enumerate(md.splitlines(), 1):
        if re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", line.strip()):
            continue  # a table's header rule, which pandoc never renders as a dash
        if "—" in line or re.search(r"(?<![-`])---(?!-)", line):
            errors.append(f"{name}:{i} em-dash")
        if re.search(r"\bnot\b[^.;:]{0,70}?\bbut\b", line):
            errors.append(f"{name}:{i} 'not ... but' construction")


def build():
    # data/cases.json is the root of the token namespace; every other data/<stem>.json is read as {{<stem>.…}}
    cases = ROOT / "data/cases.json"
    data = json.loads(cases.read_text(encoding="utf-8")) if cases.exists() else {}
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.stem in ("cases", "glossary", "terms") or f.stem.startswith("extra_"):
            continue
        if f.stem in data or f.stem == "x":
            errors.append(f"data/{f.name} clashes with the key {f.stem} in data/cases.json")
        data[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    # extra numbers for single chapters, one file per export script: data/extra_<name>.json read as {{x.<name>.…}}
    if "x" in data:
        errors.append("the key x in data/cases.json clashes with the extra_*.json namespace")
    data["x"] = {f.stem[6:]: json.loads(f.read_text(encoding="utf-8")) for f in sorted((ROOT / "data").glob("extra_*.json"))}
    body, nav, total = [], [], 0
    for ch in MAN:
        miss = [k for k in ("file", "id", "title", "min", "words") if k not in ch] + (["does"] if ch.get("step") and "does" not in ch else [])
        if miss:
            errors.append(f'manifest entry {ch.get("id", ch.get("file", "?"))} missing {", ".join(miss)}')
        elif not re.fullmatch(r"ch\w+", ch["id"]):
            errors.append(f'chapter id {ch["id"]} must be ch<number>: the maps print it as "Chapter <number>"')
    if errors:
        for e in errors:
            print("  LINT " + e)
        sys.exit(1)
    all_source = "\n".join((ROOT / "chapters" / ch["file"]).read_text(encoding="utf-8")
                            for ch in MAN if (ROOT / "chapters" / ch["file"]).exists())
    for ch in MAN:
        path = ROOT / "chapters" / ch["file"]
        if not path.exists():
            errors.append(f'missing chapter file {ch["file"]}')
            continue
        md = path.read_text(encoding="utf-8")
        lint_source(md, ch["file"])
        rendered = pandoc(preprocess(md, ch["id"], data))
        n = main_path_words(rendered)
        total += n
        flag = "" if n <= ch["words"] * 1.15 else "  over target"
        print(f'  {ch["id"]:5} {n:6} words   target {ch["words"]:5}{flag}')
        body.append(f'<section id="{ch["id"]}" data-min="{ch["min"]}">{rendered}</section>')
        nav.append(f'<a href="#{ch["id"]}"><span>{ch["title"]}</span>'
                   f'<span class="min">{ch["min"]}m</span></a>')
    print(f"  total {total} words   limit {WORD_LIMIT}")
    if total > WORD_LIMIT:
        errors.append(f"main path {total} words is over the {WORD_LIMIT} limit")

    def core(tex):
        return tex.split("_")[0].split("(")[0].split("^")[0].strip()

    orphans = [k for k, v in G.items() if k not in used_symbols and k not in math_hits
               and not ((len(core(v["tex"])) > 1 and core(v["tex"]) in all_source)
                        or (len(core(v["tex"])) == 1 and re.search(re.escape(core(v["tex"])) + r"[_^(]", all_source)))]
    if orphans:
        errors.append("glossary entries that appear nowhere: " + ", ".join(sorted(orphans)))

    page = "".join(body)
    for snippet in re.findall(r"\\text\{[^}]*\n[^}]*\}", page):
        errors.append("a line break inside a TeX text macro: " + snippet[:60].replace("\n", " / "))
    have = set(re.findall(r'id="([^"]+)"', page)) | {ch["id"] for ch in MAN}
    wanted = {v["sec"] for v in list(TERMS.values()) + list(G.values()) if v.get("sec")}
    wanted |= set(re.findall(r'href="#([^"]+)"', page)) | check_refs
    dead = sorted(w for w in wanted if w not in have)
    if dead:
        errors.append(f"{len(dead)} internal links point at ids that do not exist: " + ", ".join(dead[:12]))
    # every symbol and term says what it is in words, not only its name
    for k, v in list(G.items()) + list(TERMS.items()):
        if len(v.get("def", "").split()) < 8:
            errors.append(f"{k} has no definition of at least eight words")
    orphan_terms = sorted(set(TERMS) - used_terms)
    if orphan_terms:
        errors.append("terms defined but never used in the prose: " + ", ".join(orphan_terms))
    for k, v in TERMS.items():
        if v.get("kind") not in ("term", "concept"):
            errors.append(f"term {k} has kind {v.get('kind')!r}, not term or concept")
        for other in v.get("see", []):
            if other not in TERMS:
                errors.append(f"term {k} points at unknown related term {other}")
    if unmarked:
        by_ch = collections.defaultdict(list)
        for (ch, tok), n in unmarked.most_common():
            by_ch[ch].append(f"{tok} ({n}, e.g. ${unmarked_eg[(ch, tok)]}$)")
        for ch, toks in by_ch.items():
            errors.append(f"{ch}: symbols in math with no glossary entry for this chapter: " + "; ".join(toks[:8]))
    print(f"  terms: {len(TERMS)} defined, {sum(term_hits.values())} links; "
          f"math: {sum(math_hits.values())} symbols tagged, {len(math_hits)} distinct")

    groups = [("data", "Data"), ("est", "Estimates"), ("param", "Settings"), ("decision", "Decisions"),
              ("op", "Operations")]
    for k, v in G.items():
        if v.get("type") not in {g for g, _ in groups}:
            errors.append(f"glossary {k} has type {v.get('type')!r}, not one of data, est, param, decision, op")
    gloss = ""
    for kind, label in groups:
        gloss += f'<li class="ghead"><span>{label}</span><span></span></li>'
        gloss += "".join(
            f'<li data-sym="{k}"><span><i class="gtype" style="background:var(--t-{kind})"></i>'
            f'{v["name"]}</span><span class="tex">${v["tex"]}$</span><span class="gdef">{html.escape(v["def"])}</span></li>'
            for k, v in G.items() if v["type"] == kind)

    def sec_order(item):
        mo = re.match(r"s(\d+)-(\d+)", item[1].get("sec", "s99-99"))
        return (int(mo.group(1)), int(mo.group(2))) if mo else (99, 99)

    termlist = ""
    for kind, label in (("term", "Terms, as introduced"), ("concept", "Named methods")):
        rows = sorted(((k, v) for k, v in TERMS.items() if v["kind"] == kind), key=sec_order)
        termlist += f'<li class="ghead"><span>{label}</span><span></span></li>'
        termlist += "".join(
            f'<li data-term="{k}"><span>{v["name"]}</span>'
            f'<span class="tex">{v.get("sec", "").replace("s", "").replace("-", ".")}</span>'
            f'<span class="gdef">{html.escape(v["def"])}</span></li>'
            for k, v in rows)

    blob = {"data": data, "glossary": G, "terms": TERMS, "manifest": MAN, "book": BOOK}
    out = (KIT / "template.html").read_text(encoding="utf-8")
    eng = ROOT / "engine.js"
    parts = {"TITLE": html.escape(BOOK["title"]), "SUBTITLE": BOOK["subtitle"],
             # a book's own colours and styles go in an optional book.css, read last
             "CSS": "".join(f.read_text(encoding="utf-8") for f in (KIT / "style.css", KIT / "notes.css", ROOT / "book.css") if f.exists()),
             "NAV": "".join(nav), "BODY": page, "GLOSS": gloss, "TERMLIST": termlist,
             # "</" inside the JSON would close the script tag early
             "DATA": json.dumps(blob, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
             # optional: a book whose numbers the page can recompute sets window.ENGINE (see page.js)
             "ENGINE": eng.read_text(encoding="utf-8") if eng.exists() else "",
             # the book's own panel types (panels_<name>.js), registered after the library viz.js
             "PANELS": "\n".join(f.read_text(encoding="utf-8") for f in [KIT / "viz.js"] + sorted(ROOT.glob("panels_*.js"))),
             "PAGE": (KIT / "page.js").read_text(encoding="utf-8"),
             "NOTES": (KIT / "notes.js").read_text(encoding="utf-8"),
             # last, so the scripts inserted above can name the data global as "{{DATA_GLOBAL}}"
             "DATA_GLOBAL": BOOK["data_global"]}
    for k, val in parts.items():
        out = out.replace("{{" + k + "}}", val)
    if "--local" in sys.argv:
        out = ('<!doctype html><html><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1">'
               '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
               "</head><body>" + out + "</body></html>")
    (ROOT / "index.html").write_text(out, encoding="utf-8")

    if errors:
        print()
        for e in errors:
            print("  LINT " + e)
        sys.exit(1)
    print(f"  built index.html  {len(out) // 1024} KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
