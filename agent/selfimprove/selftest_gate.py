#!/usr/bin/env python3
"""Pin gate.py's promotion rules with fabricated run pairs — the gate decides whether the harness
is allowed to change, so a gate that accepts a perfect-vs-perfect pair is a measurement bug, not a
style issue (external review, 2026-11-17, issue #1 findings 1-2; second pass findings 1-4).

  selftest_gate.py            # every case, prints ok/FAIL per case, exit 1 on any failure

Cases 1-2 are the ones that fired: base 3/3 vs cand 6/6 both read as "+3 tasks" before the fix.
Cases 11-18 pin the second review: --allow-subset never promotes, repetition IDs must be 1..k,
and a model change (or an unknown one) cannot be credited to the arm.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"
SUITE = "suite-a"
TMP = None  # set to a per-case TemporaryDirectory by main(), so no fixture outlives its case


def run(by_task, reps, arm="cand", arm_sha="bbb", policy="pol-a", suite=SUITE,
        suite_at_end=None, arm_path="/nonexistent/arm.md", model="m", model_ident=None,
        rep_ids=None, extra_args=()):
    results = [{"id": t, "pass": p, "rep": i + 1}
               for t, v in by_task.items() for i, p in enumerate(v)]
    if rep_ids is not None:
        for r, rid in zip(results, rep_ids):
            r["rep"] = rid
    d = {"stamp": "t", "policy_sha": policy, "tag": "t", "model": model, "arm": arm,
         "arm_path": arm_path, "arm_sha": arm_sha, "parent": None, "harness_rev": "h",
         "suite_sha": suite, "suite_sha_at_end": suite_at_end or suite,
         "reps": reps, "n": len(results), "passed": sum(1 for r in results if r["pass"]),
         "pass_rate": 0.0, "wall_s": 1.0, "tokens_in": 10, "tokens_out": 100, "cost_usd": 0.0,
         "results": results}
    if model_ident:
        d.update(model_ident)
    tmp = TMP if TMP is not None else Path(tempfile.mkdtemp())
    f = tmp / f"{arm}-{'cand' if arm_sha != 'aaa' else 'base'}-{len(list(tmp.iterdir()))}.json"
    f.write_text(json.dumps(d))
    return f


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
    arm = TMP / "arm.md"
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


@case("--allow-subset: subset accuracy cannot promote", 2, "HOLD: task selections differ")
def _c11():
    return gate(run({"shared": [False, False, True], "omitted": [True] * 3}, 3, "base", "aaa"),
                run({"shared": [True, True, True]}, 3), "--allow-subset")


@case("--allow-subset: subset cost cannot promote", 2, "HOLD: task selections differ")
def _c12():
    return gate(run({"shared": [True] * 3, "omitted": [True] * 3}, 3, "base", "aaa"),
                run({"shared": [True] * 3}, 3), "--allow-subset")


@case("duplicate repetition IDs (rep=1 three times)", 1, "repetition IDs must be exactly")
def _c13():
    return gate(run({"task1": [False, False, True]}, 3, "base", "aaa"),
                run({"task1": [True, True, True]}, 3, rep_ids=[1, 1, 1]))


@case("missing repetition IDs (historical rows)", 1, "repetition IDs must be exactly")
def _c14():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3, rep_ids=[None, None, None]))


@case("out-of-range repetition IDs (1,2,4)", 1, "repetition IDs must be exactly")
def _c15():
    return gate(run({"task1": [True] * 3}, 3, "base", "aaa"),
                run({"task1": [True] * 3}, 3, rep_ids=[1, 2, 4]))


@case("model identity differs between arms", 1, "model identities differ")
def _c16():
    return gate(run({"task1": [False, False, True]}, 3, "base", "aaa",
                    model_ident={"model_provider": "p", "model_resolved": "weak"}),
                run({"task1": [True, True, True]}, 3,
                    model_ident={"model_provider": "p", "model_resolved": "strong"}))


@case("model identity unknown on both sides", 2, "model identity unknown")
def _c17():
    return gate(run({"task1": [False, False, True]}, 3, "base", "aaa", model=""),
                run({"task1": [True, True, True]}, 3, model=""))


@case("model identity recorded on one side only", 2, "model identity unknown")
def _c19():
    return gate(run({"task1": [False, False, True]}, 3, "base", "aaa",
                    model_ident={"model_provider": "p", "model_resolved": "m1"}),
                run({"task1": [True, True, True]}, 3, model=""))


@case("equal resolved model, genuine gain", 0, "ACCEPT")
def _c18():
    ident = {"model_provider": "p", "model_resolved": "m1", "model_response": "m1-2026"}
    return gate(run({"task1": [False, False, True], "task2": [False, False, True]}, 3,
                    "base", "aaa", model_ident=ident),
                run({"task1": [True] * 3, "task2": [True] * 3}, 3, model_ident=ident))


def main():
    global TMP
    fails = 0
    for name, want_rc, want_text, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            TMP = Path(td)
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
