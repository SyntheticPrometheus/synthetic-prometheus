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
import hashlib
import json
import math
import sys
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    d = json.loads(Path(p).read_text())
    d["by_task"], d["rep_ids"] = {}, {}
    for r in d["results"]:
        d["by_task"].setdefault(r["id"], []).append(r["pass"])
        d["rep_ids"].setdefault(r["id"], []).append(r.get("rep"))
    return d


def model_ident(d):
    """The identity that determines which model produced a run. Newer runners record the
    resolved pair (provider, model, responseModel); older ones only the --model argument. An
    empty identity is unknown, not a match (2026-11-17 review, finding 3)."""
    parts = [d.get("model_provider"), d.get("model_resolved"), d.get("model_response")]
    if any(p for p in parts):
        return "|".join("" if p is None else str(p) for p in parts)
    return (d.get("model") or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("cand")
    ap.add_argument("--min-delta", type=int, default=None)
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--skip-audit", action="store_true")
    ap.add_argument("--allow-subset", action="store_true",
                    help="accepted for compatibility: a subset pair prints per-task detail and always HOLDs")
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
    # --k may raise the evidence bar for one comparison, never lower it: `--k 1` accepted a
    # single observation (forged-result probe, 2026-11-18).
    floor_k = pol.get("min_reps", 3)
    if a.k < floor_k:
        print(f"NOTE: --k {a.k} is below the policy floor {floor_k}; using {floor_k}")
        a.k = floor_k
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

    # Provenance: the compared runs must describe the same measurement contract. A run whose
    # suite changed underneath it, or that was taken under a different gate policy, is not a
    # comparable observation — score it as a diagnostic, never promote on it (2026-11-17 review).
    for name, d in (("base", b), ("cand", c)):
        if d.get("suite_sha_at_end") and d.get("suite_sha_at_end") != d.get("suite_sha"):
            print(f"VOID: {name} run saw the suite change mid-run "
                  f"(start {str(d.get('suite_sha'))[:12]} -> end {str(d['suite_sha_at_end'])[:12]})")
            return 1
    if b.get("policy_sha") != c.get("policy_sha"):
        print("VOID: different policy_sha — gate thresholds changed between runs, re-measure both")
        return 1
    # Provenance of the model itself: a harness change credited to a stronger model is not a
    # harness improvement, and two unknown identities do not prove the same model ran.
    ib, ic = model_ident(b), model_ident(c)
    model_unknown = not ib or not ic
    if ib != ic and not model_unknown:
        print(f"VOID: model identities differ (base {ib} vs cand {ic}) — rerun both arms on the "
              f"same model; a model change is not a harness effect")
        return 1
    # The audit above read arm_path now; bind it to the bytes that were actually evaluated.
    # A missing file is not "nothing to check": it is an unverifiable claim, so it voids the
    # pair instead of silently skipping the check (forged-result probe, 2026-11-17).
    for name, d in (("base", b), ("cand", c)):
        p = Path(d.get("arm_path") or "")
        if not d.get("arm_sha"):
            print(f"VOID: {name} records no arm_sha — the arm that ran is not identified")
            return 1
        if not p.is_file():
            print(f"VOID: {name} arm file is missing ({p or 'no path'}) — the bytes behind "
                  f"arm_sha cannot be checked, so this pair is unverifiable")
            return 1
        if sha(p) != d["arm_sha"]:
            print(f"VOID: {name} arm file changed after it was evaluated ({p}) — re-run it, "
                  f"an edited arm is not the arm that produced these results")
            return 1

    # Balanced matrix: scoring unequally repeated arms lets raw pass counts stand in for a rate
    # (base 3/3 vs cand 6/6 read as "+3 tasks"). Require one repetition count and exactly that
    # many recorded results per task, or the comparison is not a comparison.
    if b["reps"] != c["reps"]:
        print(f"VOID: reps differ (base {b['reps']} vs cand {c['reps']}) — rerun both with the "
              f"same --reps; unequal counts are not comparable")
        return 1
    k = b["reps"]
    for name, d in (("base", b), ("cand", c)):
        # A pass is a boolean observation. Anything else (5, "yes", NaN, a float) is a forged or
        # corrupt row whose sum would inflate a score, so it is void rather than coerced.
        for task_id, vals in d["by_task"].items():
            if any(not (isinstance(x, int) and x in (0, 1)) for x in vals):
                print(f"VOID: {name}/{task_id} pass values must be 0 or 1, got {vals}")
                return 1
        to = d.get("tokens_out")
        if to is not None and (isinstance(to, bool) or not isinstance(to, (int, float))
                               or not math.isfinite(to) or to < 0):
            print(f"VOID: {name} tokens_out {to!r} is not a finite non-negative number — "
                  f"a cost comparison against it is meaningless")
            return 1
        bad = {t: len(v) for t, v in d["by_task"].items() if len(v) != k}
        if bad:
            print(f"VOID: {name} is not a balanced matrix — reps={k} but per-task counts {bad}")
            return 1
        if len(d["results"]) != len(d["by_task"]) * k:
            print(f"VOID: {name} declares {len(d['results'])} results for "
                  f"{len(d['by_task'])} tasks x {k} reps")
            return 1
        # Balanced counts do not prove independent repetitions: rows carrying rep=1 three times
        # are one observation copied, not three samples.
        for task_id, ids in d["rep_ids"].items():
            if (any(type(x) is not int for x in ids)
                    or sorted(ids) != list(range(1, k + 1))):
                print(f"VOID: {name}/{task_id} repetition IDs must be exactly 1..{k}, got {ids} "
                      f"— repeated or missing IDs are not independent reps")
                return 1

    common = sorted(set(b["by_task"]) & set(c["by_task"]))
    only_b = sorted(set(b["by_task"]) - set(c["by_task"]))
    only_c = sorted(set(c["by_task"]) - set(b["by_task"]))
    nb = sum(sum(b["by_task"][x]) for x in common)
    nc = sum(sum(c["by_task"][x]) for x in common)
    # min_delta is a count of *tasks* ("wins by at least min_delta tasks"). Summing pass counts
    # let one task improve 0/3 -> 3/3 and read as +3, which accepted a single-task change. Score
    # tasks: won if the candidate passes it more often, lost if less often.
    won = [t for t in common if sum(c["by_task"][t]) > sum(b["by_task"][t])]
    lost = [t for t in common if sum(c["by_task"][t]) < sum(b["by_task"][t])]
    delta = len(won) - len(lost)
    if only_b or only_c:
        # A shared-subset delta and a whole-run cost total are different observations. Report them
        # for diagnosis and never promote from them: --allow-subset buys the detail, not a verdict.
        print(f"NOTE: comparing the {len(common)} shared task(s); "
              f"not in cand: {only_b or '-'}; not in base: {only_c or '-'}")
    regressed = [t for t, v in c["by_task"].items()
                 if sum(v) < sum(b["by_task"].get(t, []))]
    detail = {t: (f"{sum(b['by_task'].get(t, []))}/{len(b['by_task'].get(t, []))}",
                  f"{sum(v)}/{len(v)}") for t, v in c["by_task"].items()}
    print(f"lineage: cand parent={c.get('parent') or '-'} harness_rev={c.get('harness_rev') or '-'}")
    print(f"base {b['arm']}: {nb}/{len(common) * k}   cand {c['arm']}: {nc}/{len(common) * k}   "
          f"tasks +{len(won)}/-{len(lost)} (delta {delta:+d})   reps {k}   "
          f"wall {b['wall_s']}s -> {c['wall_s']}s")
    for t, (x, y) in detail.items():
        print(f"  {t:18s} {x} -> {y}{'  REGRESSED' if t in regressed else ''}")

    if only_b or only_c:
        print(f"HOLD: task selections differ ({len(common)} shared) — subset accuracy and "
              f"whole-run cost totals are diagnostics only; rerun both arms on the same suite")
        return 2
    if model_unknown:
        print(f"HOLD: model identity unknown (base '{ib or '-'}', cand '{ic or '-'}') — record the "
              f"resolved provider/model before promoting; equal blanks prove nothing")
        return 2
    if k < a.k:
        print(f"HOLD: k={k} < {a.k}; rerun both arms with --reps {a.k} before deciding")
        return 2
    if regressed:
        print(f"REJECT: regression on {', '.join(regressed)}")
        return 3
    # A suite the base already passes completely cannot show a capability gain (delta <= 0 by
    # arithmetic), so a cost difference there is uninformative, not an improvement. Report it as
    # such instead of promoting on a ceiling (agenda #13, #112; review finding 4).
    if delta == 0 and nb == len(common) * k:
        print(f"HOLD: UNINFORMATIVE — base passes all {len(common)} task(s) on this suite at k={k}; "
              f"a pass-rate or token difference here is not evidence about capability. Widen the "
              f"suite (agenda #112) before promoting.")
        return 2

    # Cost-only win: delegated recon can leave pass rate unchanged while cutting the parent's
    # output tokens (the expensive ones). Accepted only at equal per-task pass, k>=3, and with a
    # margin, and reported as its own verdict so it is never confused with a capability gain.
    if delta == 0 and a.cost_win_frac > 0:
        tb, tc = b.get("tokens_out", 0), c.get("tokens_out", 0)
        if tb and tc is not None:
            frac = 1 - tc / tb
            print(f"cost: out-tokens {tb} -> {tc} (-{frac:.1%})  wall {b.get('wall_s')}s -> {c.get('wall_s')}s")
            if frac >= a.cost_win_frac:
                print(f"ACCEPT_COST: equal pass, {frac:.0%} fewer output tokens "
                      f"(threshold {a.cost_win_frac:.0%}) — measure again next cycle before trusting it")
                return 0
    if delta >= a.min_delta:
        print(f"ACCEPT: {delta:+d} tasks, no regression — archive the arm and record the decision")
        return 0
    print(f"HOLD: delta {delta:+d} below min-delta {a.min_delta}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
