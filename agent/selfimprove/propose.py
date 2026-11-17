#!/usr/bin/env python3
"""Weakness mining + proposal: turn observed failures into ONE candidate harness edit.

  propose.py [--base runs/<stamp>-base] [--out arms/cand-auto-<stamp>.md] [--dry]

This is the Self-Harness / RHI step (2606.09498, 2607.15524): mine the failure patterns from the
recorded runs, then ask for a minimal edit tied to those failures. It never evaluates or accepts
anything — `run.py` and `gate.py` own that, and the gate is not editable by the proposal.
"""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PI = shutil.which("pi") or "/usr/bin/pi"

PROMPT = """You are improving the harness (the prose protocol around a frozen model) of a coding agent.

Below are recorded failures of the current harness on a fixed task suite. Each failure shows the
task, what the agent replied, what files it produced, and why the verifier rejected the result.

Write ONE minimal addition to the harness spec that would prevent this class of failure. Rules:
- at most 6 lines of markdown, imperative, no headings;
- one mechanism only, tied to the observed failures, not general advice;
- it must be checkable by the agent itself (no "be careful", no "think harder");
- do not mention the task names, the suite, or the verifier.

Output only the markdown lines, nothing else.

FAILURES:
{failures}
"""


def latest_base():
    cands = sorted(RUNS.glob("*-base/result.json"))
    if not cands:
        raise SystemExit("no base runs found; run run.py --arm arms/base.md first")
    return cands[-1].parent


def failures(run_dir):
    rec = json.loads((run_dir / "result.json").read_text())
    out = []
    for r in rec["results"]:
        if r["pass"]:
            continue
        d = run_dir / f"{r['id']}-r{r['rep']}"
        produced = {}
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.name not in ("_verify.py",) and f.stat().st_size < 2000:
                produced[str(f.relative_to(d))] = f.read_text(errors="replace")[:600]
        out.append({
            "task": r["id"],
            "agent_reply": r["reply"],
            "verifier_stderr": r["verify_err"],
            "produced_files": produced,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--model", default="",
                    help="pi --model pattern for the proposer (e.g. a local GGUF: costs $0 "
                         "and can run unattended overnight; default = pi's own model")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=int, default=300,
                    help="seconds for the proposer call; a local GGUF needs more (default 300)")
    ap.add_argument("--prompt-chars", type=int, default=12000,
                    help="cap on the failure dump handed to the proposer; a 1.5B GGUF on this "
                         "host prefills ~12000 chars in the time a short call allows (bug #149)")
    ap.add_argument("--dry-run-proposer", dest="unused", action="store_true", help=__import__("argparse").SUPPRESS)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    run_dir = Path(a.base) if a.base else latest_base()
    fails = failures(run_dir)
    if not fails:
        print(f"no failures in {run_dir.name}; nothing to propose")
        return
    prompt = PROMPT.format(failures=json.dumps(fails, indent=1)[:max(2000, a.prompt_chars)])
    if a.dry:
        print(prompt[:2000])
        return

    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("PI_")}
    cmd = [PI, "--print", "--no-session", "-ne", "-ns", "-nc", "-np", "--no-mcp"]
    if a.model:
        cmd += ["--model", a.model]
    cmd += ["--tools", "read", prompt]
    try:
        p = subprocess.run(cmd,
                           capture_output=True, text=True, timeout=a.timeout, env=env,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        # A traceback here reached the caller as "candidate: none drafted" with no reason at all
        # (bug #149, a 6-failure run at 100s on a local 1.5B model). The message names the knobs.
        raise SystemExit(
            f"propose: proposer timed out after {a.timeout}s "
            f"(model {a.model or 'default'}, prompt {len(prompt)} chars, "
            f"{len(fails)} failure(s)); raise --timeout or lower --prompt-chars")
    proposal = p.stdout.strip()
    if not proposal:
        raise SystemExit(f"proposal failed: {p.stderr[-500:]}")

    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = Path(a.out) if a.out else HERE / "arms" / f"cand-auto-{stamp}.md"
    base_text = (HERE / "arms" / "base.md").read_text().rstrip() + "\n"
    out.write_text(base_text + "\n" + proposal + "\n")
    (out.with_suffix(".rationale.md")).write_text(
        f"# Proposal {stamp}\n\nmodel: {a.model or 'default'}\nmined from: {run_dir.name}\nfailures: "
        f"{', '.join(f['task'] for f in fails)}\n\n## Edit\n\n{proposal}\n")
    print(f"wrote {out}\n\n--- proposed edit ---\n{proposal}")


if __name__ == "__main__":
    main()
