"""The one command a book runs after each batch of edits: python <kit>/check.py, from the book folder.

Builds the page for the file system (build.py --local) and renders it in headless Chrome (verify_render.py), then
builds the artifact form that gets published and scans it for secrets. Prints a short summary and the failures
only; exits 1 on any failure. index.html is left in the artifact form.
"""
import pathlib
import re
import subprocess
import sys

KIT = pathlib.Path(__file__).parent
# what each pattern looks for is printed on a hit, never the matched text itself
SECRETS = {"sk- key": r"sk-[A-Za-z0-9_-]{16,}", "AIza key": r"AIza[0-9A-Za-z_-]{20,}", "ghp_ token": r"ghp_[A-Za-z0-9]{20,}",
           "postgres URL": r"postgres(?:ql)?://", "sb_secret": r"sb_secret", "PRIVATE KEY": r"PRIVATE KEY",
           "api_key=": r"(?i)api_key=", "nvapi- key": r"nvapi-[A-Za-z0-9_-]{20,}", "AKIA key": r"AKIA[0-9A-Z]{16}",
           "Telegram bot token": r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "JWT": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."}


def run(script, *args):
    out = subprocess.run([sys.executable, str(KIT / script), *args], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return out.returncode, out.stdout + out.stderr


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fails = []
    code, log = run("build.py", "--local")
    words = re.search(r"total (\d+) words\s+limit (\d+)", log)
    lint = [ln.strip() for ln in log.splitlines() if ln.strip().startswith("LINT")]
    print(f"build: {'ok' if code == 0 else 'FAILED'}" + (f", {words.group(1)} of {words.group(2)} words" if words else ""))
    fails += lint or ([] if code == 0 else [log.strip()[-600:]])
    if code == 0:
        code, log = run("verify_render.py")
        bad = [ln.strip() for ln in log.splitlines() if ln.strip().startswith("RENDER")]
        skips = [ln.strip()[5:] for ln in log.splitlines() if ln.strip().startswith("skip ")]
        print(f"render: {'ok' if code == 0 else 'FAILED'}" + (f" (skipped: {'; '.join(skips)})" if skips else ""))
        fails += bad or ([] if code == 0 else [log.strip()[-600:]])
        code, log = run("build.py")
        if code:
            fails.append("artifact build failed: " + log.strip()[-300:])
        page = (pathlib.Path.cwd() / "index.html").read_text(encoding="utf-8")
        hits = [k for k, pat in SECRETS.items() if re.search(pat, page)]
        kb = re.search(r"built index.html\s+(\d+) KB", log)
        print(f"secrets: {'none' if not hits else 'FOUND'}" + (f" in index.html ({kb.group(1)} KB, artifact form)" if kb else ""))
        fails += [f"index.html contains a {h} pattern" for h in hits]
    print(f"{len(fails)} problems")
    for f in fails:
        print("  " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
