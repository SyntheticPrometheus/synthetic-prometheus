#!/usr/bin/env python3
"""Audit a candidate arm before it is allowed to be measured — the tamper check.

  audit.py --arm arms/cand-x.md [--base arms/base.md] [--json]

Refuses (exit 3) when the candidate:
  - adds more lines than the annealed proposal budget (policy.json, one mechanism at a time);
  - mentions the evaluation machinery (verifier, expected values, suite/gate/ledger/policy),
    which is what harness tampering looks like in prose (arXiv 2609.00069);
  - drops or rewrites a line of the base spec instead of extending it (policy must not weaken);
  - changes a judge-owned file (suite, gate, policy, run) — the arm is a single .md file, so any
    such edit would have to appear in its text; the pattern check above covers the prose version.
Cost ceiling per task is checked by run.py, not here.

Exit 0 = pass, 3 = refuse, 1 = usage.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICY = HERE / "policy.json"


def added_lines(base_text, cand_text):
    b = [l.rstrip() for l in base_text.splitlines() if l.strip()]
    c = [l.rstrip() for l in cand_text.splitlines() if l.strip()]
    i = 0
    while i < min(len(b), len(c)) and b[i] == c[i]:
        i += 1
    return [l for l in c[i:] if l not in b]


def accepted_count():
    p = HERE / "decisions.md"
    if not p.exists():
        return 0
    acc = rev = 0
    for l in p.read_text().splitlines():
        if l.startswith("## ") and "ACCEPT" in l:
            acc += 1
        elif l.startswith("## ") and "REVERT" in l:
            rev += 1
    return max(0, acc - rev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--base", default=str(HERE / "arms" / "base.md"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    pol = json.loads(POLICY.read_text())["proposal"]
    base_text = Path(a.base).read_text()
    cand_text = Path(a.arm).read_text()
    added = added_lines(base_text, cand_text)

    budget = max(pol["min_added_lines"],
                 pol["max_added_lines"] - pol["anneal_per_accepted_arm"] * accepted_count())
    problems = []
    if not added:
        problems.append("no change relative to the base arm")
    if len(added) > budget:
        problems.append(f"{len(added)} added lines > budget {budget} "
                        f"(annealed after {accepted_count()} accepted arm(s))")
    low = " \n".join(added).lower()
    for pat in pol["forbidden_patterns"]:
        if pat.lower() in low:
            problems.append(f"added text mentions the evaluation machinery: {pat!r}")
    if pol.get("must_extend_base"):
        removed = [l for l in base_text.splitlines() if l.strip() and l not in cand_text.splitlines()]
        if removed:
            problems.append(f"removes {len(removed)} base line(s): {removed[0][:60]!r}")
    out = {"arm": a.arm, "added_lines": len(added), "budget": budget,
           "accepted_so_far": accepted_count(), "added": added, "problems": problems}
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"{Path(a.arm).name}: {len(added)} added line(s), budget {budget}, "
              f"{accepted_count()} accepted so far")
        for l in added:
            print("  +", l)
        for p in problems:
            print("REFUSE:", p)
    return 3 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
