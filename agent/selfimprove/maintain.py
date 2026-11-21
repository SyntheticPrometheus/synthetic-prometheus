#!/usr/bin/env python3
"""Housekeeping for the self-improvement loop — no LLM calls, cheap enough for a timer.

  maintain.py --check      verify the judge is pinned and the ledger is coherent; exit 1 on drift
  maintain.py --prune N    keep the newest N run directories (default 40)
  maintain.py --report     last 10 ledger entries + open cycles hint

Checks: every ledger record's suite_sha matches the current suite (a changed judge invalidates old
comparisons), every referenced arm file still exists, and the ledger parses line by line.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE / "suite" / "suite.json"
LEDGER = HERE / "ledger.jsonl"
RUNS = HERE / "runs"


def rows():
    if not LEDGER.exists():
        return []
    out = []
    for n, line in enumerate(LEDGER.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"ledger line {n} is not JSON: {e}")
    return out


def check():
    problems = []
    sys.path.insert(0, str(HERE))
    import run as runner  # same fingerprint the runs record: suite.json + every fixture generator
    cur = runner.suite_sha()
    rs = rows()
    if not rs:
        print("ledger empty (no runs yet)")
    stale = [r["stamp"] for r in rs if r.get("suite_sha") != cur]
    if stale:
        # expected after a deliberate judge edit: historical, not a fault
        print(f"WARN: {len(stale)} run(s) predate the current suite hash (latest {stale[-1]}); "
              f"their scores are not comparable to the current judge")
    missing = [r["arm_path"] for r in rs if r.get("arm_path") and not Path(r["arm_path"]).exists()]
    if missing:
        problems.append(f"missing arm files: {sorted(set(missing))}")
    archive = HERE / "arms" / "archive"
    accepted = [p for p in (HERE / "arms").glob("*.md")]
    if accepted and not archive.exists():
        problems.append("arms/archive/ does not exist; accepted arms have no lineage home")
    # The gate is the thing that decides whether the harness may change, so its own rules are a
    # pinned test, not a promise (external review 2026-11-17: an unequal-reps pair read as +3).
    # ... and so is the runner's resource contract (policy loaded, group killed, cost labelled).
    for name, line in (("gate", "selftest_gate.py"), ("runner", "selftest_run.py")):
        st = subprocess.run([sys.executable, str(HERE / line)], capture_output=True, text=True)
        tail = (st.stdout or st.stderr).strip().splitlines()
        if st.returncode != 0:
            problems.append(f"{name} selftest failed: {tail[-1] if tail else 'no output'}")
        else:
            print(f"{name} selftest: {tail[-1] if tail else 'ok'}")
    print(f"suite {cur[:12]}  runs {len(rs)}  arms {len(accepted)}")
    for p in problems:
        print("DRIFT:", p)
    return 1 if problems else 0


RESEARCH = HERE.parent / "research"


def research_check():
    """Every research file must be cited by at least one memory row (persistence across sessions)."""
    import sqlite3
    db = HERE.parent / "memory" / "memory.db"
    files = sorted(RESEARCH.glob("*.md")) if RESEARCH.exists() else []
    if not files:
        return 0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    missing = []
    for f in files:
        hit = con.execute("select 1 from memories where body like ? limit 1",
                          (f"%{f.name}%",)).fetchone()
        if not hit:
            missing.append(f.name)
    con.close()
    print(f"research files {len(files)}, unindexed {len(missing)}")
    for m in missing:
        print("UNINDEXED:", m)
    return 1 if missing else 0


def lineage_check():
    """Every archived arm must name a parent run, and every cand run must have lineage."""
    arch = HERE / "arms" / "archive"
    problems = []
    files = sorted(arch.glob("*.md")) if arch.exists() else []
    for f in files:
        if "parent:" not in f.read_text()[:600]:
            problems.append(f"{f.name} has no parent: header")
    rs = rows()
    orphans = [r["stamp"] for r in rs if r.get("arm", "").startswith("cand") and not r.get("parent")]
    print(f"archived arms {len(files)}, ledger runs without a parent {len(orphans)}")
    for p_ in problems:
        print("LINEAGE:", p_)
    return 1 if problems else 0


def yield_report():
    """Proposal yield: how many auto-proposed arms were measured, and how well they did."""
    props = [r for r in rows() if r["arm"].startswith("cand-auto")]
    print(f"auto-proposals measured: {len(props)}, best pass rate: "
          f"{max((r['pass_rate'] for r in props), default=0):.2f}")
    return 0


def prune(keep):
    dirs = sorted([p for p in RUNS.iterdir() if p.is_dir()]) if RUNS.exists() else []
    for d in dirs[:-keep]:
        shutil.rmtree(d)
        print("pruned", d.name)
    print(f"kept {min(len(dirs), keep)} run dirs")


def report():
    for r in rows()[-10:]:
        print(f"{r['stamp']} {r['arm']:18s} {r['passed']}/{r['n']} {r['wall_s']:7.1f}s  {r.get('tag','')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--prune", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--research", action="store_true")
    ap.add_argument("--lineage", action="store_true")
    ap.add_argument("--yield", dest="yield_", action="store_true")
    a = ap.parse_args()
    rc = 0
    if a.check:
        rc = check()
    if a.lineage:
        rc = max(rc, lineage_check())
    if a.yield_:
        rc = max(rc, yield_report())
    if a.research:
        rc = max(rc, research_check())
    if a.prune is not None:
        prune(a.prune)
    if a.report or not (a.check or a.prune is not None):
        report()
    sys.exit(rc)
