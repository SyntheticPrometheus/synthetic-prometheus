#!/usr/bin/env python3
"""Fixture loader for suite tasks whose inputs are too big to inline in suite.json.

A task may name a generator under suite/fixtures/<name>.py instead of carrying its files. The
generator is deterministic (fixed seed) and prints one JSON object:

    {"files": {...},               # seeded before the arm runs
     "verify_files": {...},        # written AFTER the arm runs (judge-owned, untamperable)
     "good": {...}, "bad": {...},  # selftest answers: a known-good and a known-wrong submission
     "verify": "shell command"}    # optional verifier override

Truth is produced by the generator, never typed by hand — the 2026-11-14 judge incidents came from
hand-written expected values that no known-good answer had ever been run against.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "suite" / "fixtures"
_cache = {}


def _data(task, timeout=60):
    name = task.get("fixture")
    if not name:
        return {}
    if name in _cache:
        return _cache[name]
    script = FIX / name
    if not script.exists():
        raise SystemExit(f"fixture missing: {script}")
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise SystemExit(f"fixture {name} failed: {out.stderr.strip()[:400]}")
    _cache[name] = json.loads(out.stdout)
    return _cache[name]


def task(t):
    """Return the task with fixture files, judge files and verifier merged in."""
    d = _data(t)
    if not d:
        return t
    out = dict(t)
    out["files"] = {**(t.get("files") or {}), **(d.get("files") or {})}
    out["verify_files"] = {**(t.get("verify_files") or {}), **(d.get("verify_files") or {})}
    if d.get("verify"):
        out["verify"] = d["verify"]
    return out


def selftest_answers(t):
    d = _data(t)
    return d.get("good") or t.get("selftest_good") or {}, d.get("bad") or t.get("selftest_bad") or {}
