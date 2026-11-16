#!/usr/bin/env python3
"""Run one harness arm over the pinned suite and record the result.

  run.py --arm arms/base.md [--tasks accounting-sum,hash-blob] [--reps 3] [--tag smoke]
         [--timeout 240] [--dry]

Each task gets a fresh directory under runs/<stamp>/<arm>/<task>-r<N>/, seeded with the suite's
files, then `pi --print` runs the prompt there with the arm appended to the system prompt and
every other harness layer disabled (no extensions, skills, context files, templates, MCP), so the
arm is the only variable. The verifier command then decides pass/fail.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import fixtures

HERE = Path(__file__).resolve().parent
SUITE = HERE / "suite" / "suite.json"
LEDGER = HERE / "ledger.jsonl"
RUNS = HERE / "runs"
PI = shutil.which("pi") or "/usr/bin/pi"
AGENT_DIR = Path(os.environ.get("PI_AGENT_DIR", str(Path.home() / ".pi" / "agent")))
SUBAGENT_EXT = AGENT_DIR / "extensions" / "subagent" / "index.ts"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_rev(path):
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def parse_json_stream(out):
    """Extract the last assistant text and summed usage from `pi --mode json` records."""
    text, usage = [], {"input": 0, "output": 0, "cost": 0.0, "turns": 0}
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") != "message_end":
            continue
        msg = ev.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        for blk in msg.get("content") or []:
            if blk.get("type") == "text":
                text.append(blk.get("text", ""))
        u = msg.get("usage") or {}
        usage["input"] += u.get("input") or 0
        usage["output"] += u.get("output") or 0
        usage["cost"] += ((u.get("cost") or {}).get("total") or 0)
        usage["turns"] += 1
    return "\n".join(t for t in text if t).strip(), usage


def mem_available_mb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 10_000


def run_task(task, workdir, arm_text, timeout, subagent=False, usage_mode=False):
    workdir.mkdir(parents=True, exist_ok=True)
    task = fixtures.task(task)          # expand large generated inputs, judge files, verifier
    for name, content in task.get("files", {}).items():
        (workdir / name).parent.mkdir(parents=True, exist_ok=True)
        (workdir / name).write_text(content)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PI_")}
    tools = "read,bash,edit,write"
    cmd = [PI, "--no-session", "-ne", "-ns", "-nc", "-np", "--no-mcp"]
    if subagent:
        # delegation arm: the only enabled extension is the subagent tool + the agents/ roster
        tools += ",subagent"
        cmd += ["-e", str(SUBAGENT_EXT)]
    cmd += ["--tools", tools, "--mode", "json" if usage_mode else "text",
            "--append-system-prompt", arm_text, task["prompt"]]
    # memory guard: a global OOM on this 7.8 GB box killed the X session once (2026-11-14).
    # Refuse to start a run that cannot fit, and cap the child's cgroup when systemd-run exists.
    if mem_available_mb() < 1200:
        return {"id": task["id"], "pass": False, "verify_rc": -1,
                "verify_err": f"skipped: only {mem_available_mb()} MB available",
                "agent_rc": -1, "wall_s": 0.0, "reply": "", "usage": {}, "files": []}
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=2500M",
               "-p", "MemorySwapMax=1G", "--"] + cmd
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                           timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", 124
    wall = round(time.time() - t0, 1)
    tum, tusage = parse_json_stream(out) if usage_mode else (out.strip(), {"input": 0, "output": 0, "cost": 0.0, "turns": 0})
    # judge-owned verifier files are (re)written AFTER the arm runs, so an arm cannot tamper with them
    for name, content in task.get("verify_files", {}).items():
        (workdir / name).parent.mkdir(parents=True, exist_ok=True)
        (workdir / name).write_text(content)
    verify = subprocess.run(["bash", "-c", task["verify"]], cwd=workdir, capture_output=True, text=True)
    return {
        "id": task["id"],
        "pass": verify.returncode == 0,
        "verify_rc": verify.returncode,
        "verify_err": verify.stderr.strip()[:300],
        "agent_rc": rc,
        "wall_s": wall,
        "reply": tum[:400],
        "usage": tusage,
        "files": sorted(p.name for p in workdir.iterdir()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--tag", default="")
    ap.add_argument("--parent", default="",
                    help="arm name or run stamp this candidate descends from (lineage)")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--subagent", action="store_true",
                    help="enable the subagent tool + agents/ roster (delegation arms)")
    ap.add_argument("--usage", action="store_true", default=True,
                    help="capture token/cost usage via --mode json (default on)")
    ap.add_argument("--no-usage", dest="usage", action="store_false")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    suite = json.loads(SUITE.read_text())
    arm = Path(a.arm).resolve()
    arm_text = arm.read_text()
    ids = [t for t in a.tasks.split(",") if t]
    tasks = [t for t in suite["tasks"] if not ids or t["id"] in ids]
    suite_sha_start = sha(SUITE)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    arm_name = arm.stem
    outdir = RUNS / f"{stamp}-{arm_name}"
    if a.dry:
        print(json.dumps({"arm": str(arm), "tasks": [t["id"] for t in tasks],
                          "reps": a.reps, "outdir": str(outdir)}, indent=1))
        return

    results = []
    for rep in range(a.reps):
        for t in tasks:
            r = run_task(t, outdir / f"{t['id']}-r{rep+1}", arm_text, a.timeout,
                         subagent=a.subagent, usage_mode=a.usage)
            r["rep"] = rep + 1
            print(f"{arm_name:16s} {t['id']:16s} r{rep+1} {'PASS' if r['pass'] else 'FAIL'} "
                  f"{r['wall_s']:6.1f}s", flush=True)
            results.append(r)

    passed = sum(r["pass"] for r in results)
    record = {
        "stamp": stamp,
        "policy_sha": sha(HERE / "policy.json") if (HERE / "policy.json").exists() else None,
        "tag": a.tag,
        "arm": arm_name,
        "arm_path": str(arm),
        "arm_sha": sha(arm),
        "parent": a.parent or None,
        "harness_rev": git_rev(HERE.parent),
        "suite_sha": suite_sha_start,
        "suite_sha_at_end": sha(SUITE),
        "reps": a.reps,
        "n": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "wall_s": round(sum(r["wall_s"] for r in results), 1),
        "tokens_in": sum((r.get("usage") or {}).get("input", 0) for r in results),
        "tokens_out": sum((r.get("usage") or {}).get("output", 0) for r in results),
        "cost_usd": round(sum((r.get("usage") or {}).get("cost", 0.0) for r in results), 6),
        "results": results,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "result.json").write_text(json.dumps(record, indent=1))
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({k: record[k] for k in
                             ("stamp", "tag", "arm", "arm_sha", "parent", "harness_rev",
                              "suite_sha", "policy_sha", "reps", "n", "passed", "pass_rate",
                              "wall_s", "tokens_in", "tokens_out", "cost_usd")}) + "\n")
    print(f"\n{arm_name}: {passed}/{len(results)} pass, {record['wall_s']}s, "
          f"tokens {record['tokens_in']}→{record['tokens_out']}, ${record['cost_usd']:.4f} → {outdir}")


if __name__ == "__main__":
    main()
