"""Self-check of the build's math lints, run from a book folder (sample/): python ../test_build.py.
Each case is a numbers row and a symbols row that must pass or must fail, with the reason."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build as b  # noqa: E402

b.G.update({
    "Z": {"name": "labor demand", "tex": "Z", "type": "est", "def": "test entry"},
    "alpha": {"name": "share", "tex": "\\alpha", "type": "param", "def": "test entry"},
    "Y": {"name": "output", "tex": "Y", "type": "data", "def": "test entry"},
    "P": {"name": "probability", "tex": "P", "type": "op", "def": "test entry"},
    "e": {"name": "Euler's number", "tex": "e", "type": "op", "def": "test entry"},
    "D": {"name": "demand", "tex": "D", "type": "est", "def": "test entry"},
    "k": {"name": "count", "tex": "k", "type": "data", "def": "test entry"},
    "mu": {"name": "mean demand", "tex": "\\mu", "type": "est", "def": "test entry"},
    "lam": {"name": "category rate", "tex": "\\lambda_{\\text{cat}}", "type": "est", "def": "test entry"},
    "N": {"name": "net", "tex": "N", "type": "est", "def": "test entry", "in": ["ch1"]},
    "Nb": {"name": "peers", "tex": "N", "type": "data", "def": "test entry", "in": ["ch2"]},
})
b.PATTERNS.clear()
b.CUR["ch"] = "ch1"

CASES = [  # (numbers, symbols, passes, why)
    (r"Z = 0.2 \times 100 + 0.5 \times 100 = 70", r"Z = \underbrace{\alpha Y}_{\text{labor}}", True, "worked to the result"),
    (r"Z = 50", r"Z = \underbrace{\alpha Y}_{\text{labor}}", False, "a product side by side, only the value"),
    (r"x = -0.5", r"x = \underbrace{a - y}_{\text{gap}}", False, "a leading minus is no arithmetic"),
    (r"P(D = 2) = \frac{e^{-0.85}\, 0.85^{2}}{2!} = 0.157",
     r"P(D = k) = \underbrace{\frac{e^{-\mu} \mu^{k}}{k!}}_{\text{Poisson}}", True, "e is an operator, allowed right of ="),
    (r"\underbrace{1}_{p_{\text{x}}} + 2 = 3", r"y = \underbrace{a + x}_{\text{sum}}", True, "a symbol in a brace label"),
    (r"R = 0.10 \, (100) = 10", r"y = \underbrace{a x}_{\text{product}}", True, "a thin space before a bracket"),
    (r"y = \sum_{i=1}^{3} 2 = 6", r"y = \underbrace{\sum a}_{\text{sum}}", True, "a sum's index range"),
    (r"N - a = 3{,}213.35", r"y = \underbrace{N - a}_{\text{margin}}", False, "a formula of symbols jumps to its value"),
    (r"y = a \times 3 = 6", r"y = \underbrace{a x}_{\text{product}}", False, "a symbol left right of ="),
    (r"y = 2 \times 3 = 6", r"y = a x", False, "no brace on a computed group"),
]
bad = 0
for numbers, symbols, passes, why in CASES:
    b.errors.clear()
    b.lint_numbers(numbers, symbols, "t")
    if (not b.errors) != passes:
        bad += 1
        print(f"FAIL ({why}): {numbers}  ->  {b.errors or 'no error'}")

# marking: a symbol written with \text inside highlights, and one letter means different things in two chapters
b.unmarked.clear()
for ch, tex, want in [("ch1", r"\lambda_{\text{cat}} + \theta", {"lam"}), ("ch1", "N", {"N"}), ("ch2", "N", {"Nb"})]:
    b.CUR["ch"] = ch
    got = set(b.keys_in(tex, ch))
    if got != want:
        bad += 1
        print(f"FAIL marking {tex} in {ch}: {got} != {want}")
b.CUR["ch"] = "ch1"
b.mark_math(r"\mathrm{d} t + q")
if {t for (_, t) in b.unmarked} != {"d", "t", "q"}:
    bad += 1
    print("FAIL unmarked letters:", dict(b.unmarked))
print(f"{len(CASES) + 4 - bad} of {len(CASES) + 4} lint cases pass")
sys.exit(1 if bad else 0)
