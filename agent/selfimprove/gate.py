#!/usr/bin/env python3
"""Decide whether a candidate arm is accepted, held, or rejected.

  gate.py runs/<base>/result.json runs/<cand>/result.json [--min-delta 2] [--k 3]

Rules (all traceable to the research digest):
- same suite hash required, else the comparison is void (pinned judge, 2609.12216);
- fewer than k reps per arm => HOLD, because a single harness A/B flips ~13% of tasks by run
  noise alone (2610.04433);
- any task that regressed => REJECT regardless of the total (no silent trade);
- otherwise accept only if the candidate wins by at least min_delta tasks (default 2), else HOLD.
Exit code: 0 accept, 2 hold, 3 reject, 1 usage/void.
"""
import argparse
import json
import sys
from pathlib import Path


def load(p):
    d = json.loads(Path(p).read_text())
    d["by_task"] = {}
    for r in d["results"]:
        d["by_task"].setdefault(r["id"], []).append(r["pass"])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("cand")
    ap.add_argument("--min-delta", type=int, default=None)
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--skip-audit", action="store_true")
    ap.add_argument("--cost-win-frac", type=float, default=None,
                    help="accept an equal-pass candidate that cuts output tokens by at least this "
                         "fraction; default comes from policy.json gate.cost_win_frac, 0 = off")
    a = ap.parse_args()
    import json as _json
    pol_path = Path(__file__).resolve().parent / "policy.json"
    pol = _json.loads(pol_path.read_text())["gate"] if pol_path.exists() else {}
    if a.min_delta is None:
        a.min_delta = pol.get("min_delta", 2)
    if a.k is None:
        a.k = pol.get("min_reps", 3)
    if a.cost_win_frac is None:
        a.cost_win_frac = pol.get("cost_win_frac", 0.0)
    b, c = load(a.base), load(a.cand)
    if not a.skip_audit:
        import subprocess as _sp
        aud = _sp.run([sys.executable, str(Path(__file__).resolve().parent / "audit.py"),
                       "--arm", c["arm_path"]], capture_output=True, text=True)
        if aud.returncode != 0:
            print(aud.stdout.strip()[-800:])
            print("REFUSE: candidate failed the tamper audit (see audit.py output above)")
            return 3

    if b["suite_sha"] != c["suite_sha"]:
        print("VOID: suite hash differs — the judge changed between runs")
        return 1
    if b["arm_sha"] == c["arm_sha"]:
        print("VOID: identical arms")
        return 1
    k = min(b["reps"], c["reps"])
    common = sorted(set(b["by_task"]) & set(c["by_task"]))
    only_b = sorted(set(b["by_task"]) - set(c["by_task"]))
    only_c = sorted(set(c["by_task"]) - set(b["by_task"]))
    nb = sum(sum(b["by_task"][x]) for x in common)
    nc = sum(sum(c["by_task"][x]) for x in common)
    delta = nc - nb
    if only_b or only_c:
        print(f"NOTE: comparing the {len(common)} shared task(s); "
              f"not in cand: {only_b or '-'}; not in base: {only_c or '-'}")
    regressed = [t for t, v in c["by_task"].items()
                 if sum(v) < sum(b["by_task"].get(t, []))]
    detail = {t: (f"{sum(b['by_task'].get(t, []))}/{len(b['by_task'].get(t, []))}",
                  f"{sum(v)}/{len(v)}") for t, v in c["by_task"].items()}
    print(f"lineage: cand parent={c.get('parent') or '-'} harness_rev={c.get('harness_rev') or '-'}")
    print(f"base {b['arm']}: {nb}/{len(common)*k}   cand {c['arm']}: {nc}/{len(common)*k}   "
          f"delta {delta:+d}   reps {k}   wall {b['wall_s']}s -> {c['wall_s']}s")
    for t, (x, y) in detail.items():
        print(f"  {t:18s} {x} -> {y}{'  REGRESSED' if t in regressed else ''}")

    if k < a.k:
        print(f"HOLD: k={k} < {a.k}; rerun both arms with --reps {a.k} before deciding")
        return 2
    if regressed:
        print(f"REJECT: regression on {', '.join(regressed)}")
        return 3

    # Cost-only win: delegated recon can leave pass rate unchanged while cutting the parent's
    # output tokens (the expensive ones). Accepted only at equal per-task pass, k>=3, and with a
    # margin, and reported as its own verdict so it is never confused with a capability gain.
    if delta == 0 and a.cost_win_frac > 0:
        tb, tc = b.get("tokens_out", 0), c.get("tokens_out", 0)
        if tb and tc:
            frac = 1 - tc / tb
            print(f"cost: out-tokens {tb} -> {tc} (-{frac:.1%})  wall {b.get('wall_s')}s -> {c.get('wall_s')}s")
            if frac >= a.cost_win_frac:
                print(f"ACCEPT_COST: equal pass, {frac:.0%} fewer output tokens "
                      f"(threshold {a.cost_win_frac:.0%}) — measure again next cycle before trusting it")
                return 0
    if delta >= a.min_delta:
        print(f"ACCEPT: +{delta} tasks, no regression — archive the arm and record the decision")
        return 0
    print(f"HOLD: delta {delta:+d} below min-delta {a.min_delta}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
