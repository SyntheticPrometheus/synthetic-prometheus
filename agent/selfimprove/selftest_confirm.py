#!/usr/bin/env python3
"""Pin confirm.py the way selftest_gate.py pins gate.py.

The confirmation stage exists because a visible suite at k=3 can accept noise, so the tests are
about refusals as much as verdicts: a stale run, a reseeded family, an arm edited after its freeze,
a second freeze of the same bytes, and a confirmation win that regresses the development floor
must each fail to promote. Uses a temp CONFIRM_DIR/LEDGER; no network, no model, no cost.

  selftest_confirm.py
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIRM = HERE / "confirm.py"
GATE = HERE / "gate.py"
TMP = None
ENV = None
CASES = []


def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


BASE_ARM = (HERE / "arms" / "base.md").read_text()


def arm(name, text=None):
    p = TMP / f"{name}.md"
    # a real arm extends the pinned base (audit.py refuses a candidate that removes its lines)
    p.write_text(text or BASE_ARM + f"\nVerify the {name} result before replying.\n")
    return p


def run_record(arm_path, suite_sha, stamp, reps, by_task, seed, arm_field=None):
    arm_path = Path(arm_path)
    results = [{"id": t, "pass": p, "rep": i + 1}
               for t, v in by_task.items() for i, p in enumerate(v)]
    return {
        "stamp": stamp, "policy_sha": "policy-fixed", "tag": "confirm",
        "model": "m", "model_provider": "p", "model_resolved": "m", "model_response": "m",
        "arm": arm_field or arm_path.stem, "arm_path": str(arm_path),
        "arm_sha": h(arm_path), "parent": None, "harness_rev": "h",
        "suite_path": str(TMP / "confirm-suite.json"),
        "variant_seed": seed, "confirm_sha": suite_sha,
        "suite_sha": suite_sha, "suite_sha_at_end": suite_sha,
        "reps": reps, "n": len(results), "passed": sum(r["pass"] for r in results),
        "pass_rate": 0.0, "wall_s": 1.0, "tokens_in": 10, "tokens_out": 100,
        "cost_usd": 0.0, "results": results,
    }


def write(d, name):
    p = TMP / name
    p.write_text(json.dumps(d))
    return p


def call(*args):
    p = subprocess.run([sys.executable, str(CONFIRM), *args], capture_output=True, text=True,
                       env=ENV)
    return p.returncode, (p.stdout + p.stderr).strip()


def gate_call(base, cand):
    p = subprocess.run([sys.executable, str(GATE), str(base), str(cand)],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def case(name, want_rc, want_text=None):
    def deco(fn):
        CASES.append((name, want_rc, want_text, fn))
        return fn
    return deco


def fresh_arm_and_freeze():
    a = arm("cand")
    rc, out = call("freeze", "--arm", str(a))
    assert rc == 0, out
    return a, json.loads(next((TMP / "confirm").glob("frozen-*.json")).read_text())


@case("second freeze of the same arm bytes is refused", 1, "already frozen")
def _c1():
    a, _ = fresh_arm_and_freeze()
    return call("freeze", "--arm", str(a))


@case("arm already measured before freeze is refused", 1, "already has")
def _c2():
    a = arm("measured")
    (TMP / "ledger.jsonl").write_text(json.dumps({"arm_sha": h(a)}) + "\n")
    return call("freeze", "--arm", str(a))


@case("arm edited after its freeze cannot build a family", 1, "changed after its freeze")
def _c3():
    a, _ = fresh_arm_and_freeze()
    a.write_text("# edited after freeze\n")
    return call("build", "--arm", str(a))


@case("a confirmation run older than the freeze is void", 1, "predates the freeze")
def _c4():
    a, f = fresh_arm_and_freeze()
    d = TMP / f["arm_sha"][:12]
    d.mkdir(parents=True)
    man = {**f, "dir": str(d), "suite_path": str(TMP / "confirm-suite.json"),
           "judge_sha": "judge-x", "suite_sha": "suite-x", "created_at": time.time(),
           "tasks": ["t1"]}
    (d / "manifest.json").write_text(json.dumps(man))
    b = arm("base")
    rec = run_record(b, "judge-x", "20200101T000000", 3, {"t1": [False] * 3}, f["seed"])
    c = run_record(a, "judge-x", "20200101T000000", 3, {"t1": [True] * 3}, f["seed"])
    write(rec, "b.json")
    write(c, "c.json")
    (d / "base.json").write_text(json.dumps(rec))
    (d / "cand.json").write_text(json.dumps(c))
    return call("decide", "--dir", str(d))


@case("a run from a different seed is void", 1, "not from the frozen family")
def _c5():
    a, f = fresh_arm_and_freeze()
    d = TMP / f["arm_sha"][:12]
    d.mkdir(parents=True)
    man = {**f, "dir": str(d), "suite_path": str(TMP / "confirm-suite.json"),
           "judge_sha": "judge-x", "suite_sha": "suite-x", "created_at": time.time(),
           "tasks": ["t1"]}
    (d / "manifest.json").write_text(json.dumps(man))
    b = arm("base2")
    later = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() + 60))
    (d / "base.json").write_text(json.dumps(
        run_record(b, "judge-x", later, 3, {"t1": [False] * 3}, "other-seed")))
    (d / "cand.json").write_text(json.dumps(
        run_record(a, "judge-x", later, 3, {"t1": [True] * 3}, f["seed"])))
    return call("decide", "--dir", str(d))


def full_pair(conf_base, conf_cand, dev_gain=True):
    """A valid frozen candidate + confirmation runs + a development floor pair."""
    a, f = fresh_arm_and_freeze()
    d = TMP / f["arm_sha"][:12]
    d.mkdir(parents=True)
    later = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() + 60))
    man = {**f, "dir": str(d), "suite_path": str(TMP / "confirm-suite.json"),
           "judge_sha": "judge-x", "suite_sha": "suite-x", "created_at": time.time(),
           "tasks": list(conf_base)}
    (d / "manifest.json").write_text(json.dumps(man))
    b = arm("floor-base")
    cb = arm("floor-cand")
    (d / "base.json").write_text(json.dumps(
        run_record(b, "judge-x", later, 3, conf_base, f["seed"])))
    (d / "cand.json").write_text(json.dumps(
        run_record(a, "judge-x", later, 3, conf_cand, f["seed"], arm_field="cand")))
    dev_base = ({"d1": [False] * 3, "d2": [False] * 3, "d3": [True] * 3} if dev_gain
                else {"d1": [True] * 3, "d2": [True] * 3})
    dev_cand = ({"d1": [True] * 3, "d2": [True] * 3, "d3": [True] * 3} if dev_gain
                else {"d1": [True, True, False], "d2": [True] * 3})
    db = write(run_record(b, "dev-suite", "20260101T000000", 3, dev_base, "dev"),
               "dev-base.json")
    dc = write(run_record(cb, "dev-suite", "20260101T000000", 3, dev_cand, "dev-cand"),
               "dev-cand.json")
    return call("decide", "--dir", str(d), "--dev-base", str(db), "--dev-cand", str(dc))


@case("confirmation gain with an accepted dev floor promotes", 0, "CONFIRM:")
def _c6():
    return full_pair({"t1": [False] * 3, "t2": [False] * 3, "t3": [False] * 3,
                      "t4": [True] * 3},
                     {"t1": [True] * 3, "t2": [True] * 3, "t3": [True] * 3,
                      "t4": [True] * 3})


@case("2 won / 0 lost is a screening result, not confirmation (p=0.5)", 2, "noise")
def _c7():
    """Only two discordant tasks: gate's delta=2 accepts, the sign test says p=0.50."""
    a, f = fresh_arm_and_freeze()
    d = TMP / f["arm_sha"][:12]
    d.mkdir(parents=True)
    later = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() + 60))
    man = {**f, "dir": str(d), "suite_path": str(TMP / "confirm-suite.json"),
           "judge_sha": "judge-x", "suite_sha": "suite-x", "created_at": time.time(),
           "tasks": ["t1", "t2"]}
    (d / "manifest.json").write_text(json.dumps(man))
    b, cb = arm("floor-b2"), arm("floor-c2")
    (d / "base.json").write_text(json.dumps(
        run_record(b, "judge-x", later, 3, {"t1": [False] * 3, "t2": [False] * 3}, f["seed"])))
    (d / "cand.json").write_text(json.dumps(
        run_record(a, "judge-x", later, 3, {"t1": [True] * 3, "t2": [True] * 3}, f["seed"],
                   arm_field="cand")))
    db = write(run_record(b, "dev-suite", "20260101T000000", 3,
                          {"d1": [False] * 3, "d2": [False] * 3}, "dev"), "dev-b2.json")
    dc = write(run_record(cb, "dev-suite", "20260101T000000", 3,
                          {"d1": [True] * 3, "d2": [True] * 3}, "dev-c2"), "dev-c2.json")
    return call("decide", "--dir", str(d), "--dev-base", str(db), "--dev-cand", str(dc))


@case("confirmation gain that regresses the dev floor is rejected", 3, "regresses the pinned")
def _c8():
    return full_pair({"t1": [False] * 3, "t2": [False] * 3},
                     {"t1": [True] * 3, "t2": [True] * 3}, dev_gain=False)


@case("confirmation regression is rejected", 3, "REJECT")
def _c9():
    return full_pair({"t1": [True] * 3, "t2": [True] * 3},
                     {"t1": [True, True, False], "t2": [True] * 3})


def main():
    global TMP, ENV
    fails = 0
    for name, want_rc, want_text, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            TMP = Path(td)
            ENV = {**os.environ, "CONFIRM_DIR": str(TMP / "confirm"),
                   "CONFIRM_LEDGER": str(TMP / "ledger.jsonl")}
            (TMP / "ledger.jsonl").write_text("")
            rc, out = fn()
        ok = rc == want_rc and (want_text is None or want_text in out)
        print(f"{'ok  ' if ok else 'FAIL'} [{rc}/{want_rc}] {name}")
        if not ok:
            fails += 1
            print("\n".join("      " + ln for ln in out.splitlines()[-8:]))
    print(f"\n{len(CASES) - fails}/{len(CASES)} confirmation cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
