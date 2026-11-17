#!/usr/bin/env python3
"""Pin gate.py's promotion rules with fabricated run pairs — the gate decides whether the harness
is allowed to change, so a gate that accepts a perfect-vs-perfect pair is a measurement bug, not a
style issue (external review, 2026-11-17, issue #1 findings 1-2).

  selftest_gate.py            # every case, prints ok/FAIL per case, exit 1 on any failure

Cases 1-2 are the ones that fired: base 3/3 vs cand 6/6 both read as "+3 tasks" before the fix.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"
SUITE = "suite-a"


def run(by_task, reps, arm="cand", arm_sha="bbb", policy="pol-a", suite=SUITE,
        suite_at_end=None, arm_path="/nonexistent/arm.md", extra_args=()):
    results = [{"id": t, "pass": p} for t, v in by_task.items() for p in v]
    d = {"stamp": "t", "policy_sha": policy, "tag": "t", "model": "m", "arm": arm,
         "arm_path": arm_path, "arm_sha": arm_sha, "parent": None, "harness_rev": "h",
         "suite_sha": suite, "suite_sha_at_end": suite_at_end or suite,
         "reps": reps, "n": len(results), "passed": sum(1 for r in results if r["pass"]),
         "pass_rate": 0.0, "wall_s": 1.0, "tokens_in": 10, "tokens_out": 100, "cost_usd": 0.0,
         "results": results}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(d, f)
    f.close()
    return Path(f.name)


def gate(base, cand, *extra):
    p = subprocess.run([sys.executable, str(GATE), str(base), str(cand), "--skip-audit", *extra],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


CASES = []


def case(name, want_rc, want_text=None):
    def deco(fn):
        CASES.append((name, want_rc, want_text, fn))
        return fn
    return deco


@case("unequal reps, both perfect (3/3 vs 6/6)", 1, "reps differ")
def _c1():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 6}, 6))


@case("unequal reps, real gain hidden in raw counts", 1, "reps differ")
def _c2():
    return gate(run({"task1": [False, True, True]}, 3, "base", "aaa"),
                run({"task1": [True] * 5 + [False]}, 6))


@case("genuine gain at equal reps", 0, "ACCEPT")
def _c3():
    return gate(run({"task1": [False, True, True], "task2": [False, False, True]}, 3, "base", "aaa"),
                run({"task1": [True, True, True], "task2": [True, True, True]}, 3))


@case("regression at equal reps", 3, "REJECT")
def _c4():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True, True, False]}, 3))


@case("suite changed mid-run", 1, "change mid-run")
def _c5():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3, suite_at_end="suite-b"))


@case("policy_sha differs between runs", 1, "policy_sha")
def _c6():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3, policy="pol-b"))


@case("task selections differ => diagnostic HOLD", 2, "task selections differ")
def _c7():
    return gate(run({"task1": [True] * 3, "task2": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3))


@case("arm edited after evaluation", 1, "changed after it was evaluated")
def _c8():
    arm = Path(tempfile.mkdtemp()) / "arm.md"
    arm.write_text("edited\n")
    import hashlib
    good = hashlib.sha256(arm.read_bytes()).hexdigest()
    arm.write_text("edited again\n")
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3, arm_sha=good, arm_path=str(arm)))


@case("unbalanced matrix (reps 3, two results)", 1, "not a balanced matrix")
def _c9():
    b = run({"task1": [True] * 3}, 3, "base", "aaa")
    c = run({"task1": [True] * 2}, 3)
    return gate(b, c)


@case("identical arms", 1, "identical arms")
def _c10():
    return gate(run({"task1": [True] * 3}, 3, "base", "same"),
                run({"task1": [True] * 3}, 3, arm_sha="same"))


def main():
    fails = 0
    for name, want_rc, want_text, fn in CASES:
        rc, out = fn()
        ok = rc == want_rc and (want_text is None or want_text in out)
        print(f"{'ok  ' if ok else 'FAIL'} [{rc}/{want_rc}] {name}")
        if not ok:
            fails += 1
            print("\n".join("      " + ln for ln in out.splitlines()[-6:]))
    print(f"\n{len(CASES) - fails}/{len(CASES)} gate cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
