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


def suite_sha(root=None):
    """Fingerprint of the judge, not just its index. suite.json names the tasks, but
    suite/fixtures/*.py builds their inputs and verifiers: regenerating a fixture changes what the
    arm is scored on while suite.json stays byte-identical. Hash both, sorted, file name included
    (2026-11-17 review, finding 2 — verified: an edited fixture left suite_sha unchanged)."""
    base = Path(root) if root else HERE
    h = hashlib.sha256()
    files = sorted([base / "suite" / "suite.json"] + list((base / "suite" / "fixtures").glob("*.py")))
    for p in files:
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


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
    """Extract the last assistant text, summed usage, and the resolved model identity from
    `pi --mode json` records. The identity is what the provider actually answered with — a
    drifting default model must not be credited to the arm (2026-11-17 review, finding 3)."""
    text, usage = [], {"input": 0, "output": 0, "cost": 0.0, "turns": 0}
    ident = {}
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
        if not ident and msg.get("provider"):
            ident = {"model_provider": msg.get("provider"),
                     "model_resolved": msg.get("model"),
                     "model_response": msg.get("responseModel")}
    return "\n".join(t for t in text if t).strip(), usage, ident


def mem_available_mb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 10_000


def run_task(task, workdir, arm_text, timeout, subagent=False, usage_mode=False, model=None,
             mem_guard_mb=1200, mem_cap_mb=2500, verify_timeout=60):
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
    if model:                      # --model local/<gguf> runs the suite offline ($0)
        cmd += ["--model", model]
    cmd += ["--tools", tools, "--mode", "json" if usage_mode else "text",
            "--append-system-prompt", arm_text, task["prompt"]]
    # memory guard: a global OOM on this 7.8 GB box killed the X session once (2026-11-14).
    # Refuse to start a run that cannot fit, and cap the child's cgroup when systemd-run exists.
    if mem_available_mb() < mem_guard_mb:
        return {"id": task["id"], "pass": False, "verify_rc": -1,
                "verify_err": f"skipped: only {mem_available_mb()} MB available "
                              f"(guard {mem_guard_mb} MB)",
                "agent_rc": -1, "wall_s": 0.0, "reply": "", "usage": {}, "files": [],
                "budget_exceeded": True, "timed_out": False}
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryMax={mem_cap_mb}M",
               "-p", "MemorySwapMax=1G", "--"] + cmd
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                           timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", 124
    wall = round(time.time() - t0, 1)
    if usage_mode:
        tum, tusage, tident = parse_json_stream(out)
    else:
        tum, tusage, tident = out.strip(), {"input": 0, "output": 0, "cost": 0.0, "turns": 0}, {}
    # judge-owned verifier files are (re)written AFTER the arm runs, so an arm cannot tamper with them
    for name, content in task.get("verify_files", {}).items():
        (workdir / name).parent.mkdir(parents=True, exist_ok=True)
        (workdir / name).write_text(content)
    # A verifier is a subprocess like any other: it gets a bound, and a hung one is a budget
    # outcome, not a task failure (it tells us nothing about the arm).
    try:
        verify = subprocess.run(["bash", "-c", task["verify"]], cwd=workdir,
                                capture_output=True, text=True, timeout=verify_timeout)
        vrc, verr, vto = verify.returncode, verify.stderr.strip(), False
    except subprocess.TimeoutExpired:
        vrc, verr, vto = 124, f"verifier timed out after {verify_timeout}s", True
    timed_out = rc == 124
    return {
        "id": task["id"],
        "pass": vrc == 0 and not timed_out,
        "verify_rc": vrc,
        "verify_err": verr[:300],
        "agent_rc": rc,
        "wall_s": wall,
        "reply": tum[:400],
        "usage": tusage,
        "model_ident": tident,
        "timed_out": timed_out,
        "verify_timed_out": vto,
        "budget_exceeded": timed_out or vto,
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
    ap.add_argument("--timeout", type=int, default=None,
                    help="wall bound per task; default is policy.json run.max_wall_per_task_s")
    ap.add_argument("--subagent", action="store_true",
                    help="enable the subagent tool + agents/ roster (delegation arms)")
    ap.add_argument("--usage", action="store_true", default=True,
                    help="capture token/cost usage via --mode json (default on)")
    ap.add_argument("--no-usage", dest="usage", action="store_false")
    ap.add_argument("--model", default="",
                    help="model pattern passed to pi (e.g. local/qwen2.5-1.5b-instruct-q4_k_m) "
                         "— a loopback model makes a run cost $0; default = pi's own default")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    # The declared resource contract lives in policy.json; the runner used to hardcode it.
    pol = json.loads((HERE / "policy.json").read_text()).get("run", {}) \
        if (HERE / "policy.json").exists() else {}
    if a.timeout is None:
        a.timeout = int(pol.get("max_wall_per_task_s", 240))
    mem_guard_mb = int(pol.get("memory_guard_mb", 1200))
    mem_cap_mb = int(pol.get("memory_cap_mb", 2500))
    verify_timeout = int(pol.get("verifier_timeout_s", 60))
    cost_limit = pol.get("max_cost_per_task_usd")

    suite = json.loads(SUITE.read_text())
    arm = Path(a.arm).resolve()
    arm_text = arm.read_text()
    ids = [t for t in a.tasks.split(",") if t]
    tasks = [t for t in suite["tasks"] if not ids or t["id"] in ids]
    suite_sha_start = suite_sha()
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
                         subagent=a.subagent, usage_mode=a.usage, model=a.model or None,
                         mem_guard_mb=mem_guard_mb, mem_cap_mb=mem_cap_mb,
                         verify_timeout=verify_timeout)
            r["rep"] = rep + 1
            print(f"{arm_name:16s} {t['id']:16s} r{rep+1} {'PASS' if r['pass'] else 'FAIL'} "
                  f"{r['wall_s']:6.1f}s", flush=True)
            results.append(r)

    passed = sum(r["pass"] for r in results)
    # Resolved identity, not the requested pattern: if the provider answered with a different
    # model than requested, the gate must see that, not the argument we passed.
    seen = {}
    for r in results:
        mi = r.get("model_ident") or {}
        if mi.get("model_provider"):
            seen[(mi.get("model_provider"), mi.get("model_resolved"),
                  mi.get("model_response"))] = mi
    ident = next(iter(seen.values()), {})
    ident_all = [f"{p}/{m}" for p, m, _ in sorted(seen)]
    over_budget = [r["id"] for r in results if r.get("budget_exceeded")]
    record = {
        "stamp": stamp,
        "policy_sha": sha(HERE / "policy.json") if (HERE / "policy.json").exists() else None,
        "tag": a.tag,
        "model": a.model or None,
        "model_provider": ident.get("model_provider"),
        "model_resolved": ident.get("model_resolved"),
        "model_response": ident.get("model_response"),
        "model_identities": ident_all,      # >1 entry means the run itself drifted models
        "arm": arm_name,
        "arm_path": str(arm),
        "arm_sha": sha(arm),
        "parent": a.parent or None,
        "harness_rev": git_rev(HERE.parent),
        "suite_sha": suite_sha_start,
        "suite_sha_at_end": suite_sha(),
        "reps": a.reps,
        "n": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "wall_s": round(sum(r["wall_s"] for r in results), 1),
        "tokens_in": sum((r.get("usage") or {}).get("input", 0) for r in results),
        "tokens_out": sum((r.get("usage") or {}).get("output", 0) for r in results),
        "cost_usd": round(sum((r.get("usage") or {}).get("cost", 0.0) for r in results), 6),
        "budget_exceeded": over_budget,
        "budget_limits": {"wall_per_task_s": a.timeout, "verifier_s": verify_timeout,
                          "memory_guard_mb": mem_guard_mb,
                          "cost_per_task_usd": cost_limit,
                          "cost_note": "post-run acceptance limit, not a spending cap"},
        "results": results,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "result.json").write_text(json.dumps(record, indent=1))
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({k: record[k] for k in
                             ("stamp", "tag", "model", "model_provider", "model_resolved",
                              "model_response", "arm", "arm_sha", "parent", "harness_rev",
                              "suite_sha", "policy_sha", "reps", "n", "passed", "pass_rate",
                              "wall_s", "tokens_in", "tokens_out", "cost_usd",
                              "budget_exceeded")}) + "\n")
    print(f"\n{arm_name}: {passed}/{len(results)} pass, {record['wall_s']}s, "
          f"tokens {record['tokens_in']}→{record['tokens_out']}, ${record['cost_usd']:.4f} → {outdir}")


if __name__ == "__main__":
    main()
