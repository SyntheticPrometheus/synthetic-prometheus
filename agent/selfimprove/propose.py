#!/usr/bin/env python3
"""Weakness mining + proposal: turn observed failures into ONE candidate harness edit.

  propose.py [--base runs/<stamp>-base] [--out arms/cand-auto-<stamp>.md] [--dry]

This is the Self-Harness / RHI step (2606.09498, 2607.15524): mine the failure patterns from the
recorded runs, then ask for a minimal edit tied to those failures. It never evaluates or accepts
anything — `run.py` and `gate.py` own that, and the gate is not editable by the proposal.

Timeout and payload are one decision, not two (task #213). Measured on 2026-11-21 through this
script's own `pi --print` path on `local/qwen2.5-1.5b-instruct-q4_k_m` (warm router, 6 failures),
with the router's `print_timing` lines for the same calls:

    prompt chars   wall secs   prompt eval            generation
    2,713            64.6       1,910 tok @ 12.6 t/s   45 tok @ 6.8 t/s
    4,713            43.0
    6,713            48.6
    12,713          158.9       1,910 tok @ 12.6 t/s   45 tok @ 6.8 t/s

A call costs STARTUP + chars/PREFILL + generated/GEN, and generation is the term that has no
bound of its own: one --timeout 100 run spent 47 s on a 3,900-char prefill and then emitted 919
tokens at 9.5 t/s for another 97 s, timing out with a half-written proposal. The model's
maxTokens is 1,024 (models.json), so the worst case is 20 + 171 + 128 = 319 s for the default
payload — which a 300 s default covered with no margin, and a 100 s one could never cover. Hence:
the payload cap is derived from the timeout, the default timeout is the measured worst case with
margin (600 s, 1.9x), and a local model with a timeout below the floor refuses in a second
instead of burning it and returning nothing.
"""

# Measured 2026-11-21 (router print_timing over the table above): prompt eval 12.6 tok/s at ~6.6
# chars/token = 83 chars/s (70 used, pessimistic); generation 9.5 t/s and 1,024 maxTokens = 128 s
# (8 t/s used); ~20 s of every call is model/slot start-up that no payload change affects.
PREFILL_CHARS_PER_S = 70
GEN_SECONDS = 128
STARTUP_S = 20
MAX_PAYLOAD_CHARS = 12000      # the dump a 6-failure run needs; measured at 158.9 s above
MIN_PAYLOAD_CHARS = 2000
# A local model cannot draft anything in less than this, whatever the payload.
LOCAL_MIN_TIMEOUT_S = STARTUP_S + MIN_PAYLOAD_CHARS // PREFILL_CHARS_PER_S + GEN_SECONDS
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
    ap.add_argument("--timeout", type=int, default=600,
                    help="seconds for the proposer call (default 600 = 1.9x the measured 319 s "
                         "worst case for a local 1.5B at the default payload; bug #213)")
    ap.add_argument("--prompt-chars", type=int, default=0,
                    help="cap on the failure dump handed to the proposer, overriding the default; "
                         "default derives it from --timeout and the measured prefill rate (bug #213)")
    ap.add_argument("--dry-run-proposer", dest="unused", action="store_true", help=__import__("argparse").SUPPRESS)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    run_dir = Path(a.base) if a.base else latest_base()
    fails = failures(run_dir)
    if not fails:
        print(f"no failures in {run_dir.name}; nothing to propose")
        return
    if a.model.startswith("local/") and a.timeout < LOCAL_MIN_TIMEOUT_S:
        raise SystemExit(
            f"propose: --timeout {a.timeout}s cannot draft on {a.model}: a local GGUF needs "
            f">= {LOCAL_MIN_TIMEOUT_S}s (measured 2026-11-21: {MIN_PAYLOAD_CHARS}-char prefill + "
            f"the model's 1024-token generation cap at 8 tok/s). Use --timeout "
            f"{LOCAL_MIN_TIMEOUT_S} or more; a shorter call only burns the budget")

    # A payload the timeout cannot afford is worse than a small one: it drafts nothing.
    affordable = int(PREFILL_CHARS_PER_S * (a.timeout - STARTUP_S - GEN_SECONDS))
    cap = a.prompt_chars or min(MAX_PAYLOAD_CHARS, max(MIN_PAYLOAD_CHARS, affordable))
    prompt = PROMPT.format(failures=json.dumps(fails, indent=1)[:cap])
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
