#!/usr/bin/env python3
"""Test the judge, not the agent: seed each task, write a known-correct answer (must PASS) and a
known-wrong answer (must FAIL). A suite that cannot fail is not a measurement.

  selftest.py [--task id]
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import fixtures

HERE = Path(__file__).resolve().parent
SUITE = json.loads((HERE / "suite" / "suite.json").read_text())

GOOD = {
    "accounting-sum": {"result.txt": "1567\n"},
    "hash-blob": {"hash.txt": "08ba615a19832273f9ccedb1f322c681dc04f6dca4186b1d9d2837a139bc5a7b\n"},
    "fix-check": {"calc.py": "nums = [4, 9, 17, 22]\nprint(f'{sum(nums)/len(nums):.2f}')\n"},
    "stale-cache": {"answer.txt": "7315\n"},
    "stated-vs-true": {"total.txt": "52550\n"},
    "long-reports": {"count.txt": "10\n", "sum.txt": "9600\n"},
    "log-fanout": None,  # filled from the suite's selftest_good
    "parallel-fix": {f"m/m{i}.py": f"def val(x):\n    return x * {i}\n" for i in range(1, 7)},
    "chain-12": {f"m/m{i}.py": (f"def f(x):\n    return x + {k}\n" if op == "add" else f"def f(x):\n    return x * {k}\n")
                 for i, (op, k) in enumerate([("add",3),("mul",2),("add",7),("mul",3),("add",1),("mul",2),
                                              ("add",5),("mul",2),("add",11),("mul",3),("add",2),("mul",2)], 1)},
    "spec-10": {"config.json": json.dumps({"service": {"name": "api-101", "port": 8080, "replicas": 8, "timeout_s": 101},
                                           "limits": {"cpu": "2000m", "memory": "2048Mi"},
                                           "features": {"beta": True, "cache": False},
                                           "logging": {"level": "debug", "format": "json"}}, indent=2) + "\n"},
}
BAD = {
    "accounting-sum": {"result.txt": "1467\n"},
    "hash-blob": {"hash.txt": "deadbeef\n"},
    "fix-check": {"calc.py": "nums = [4, 9, 17, 22]\nprint(round(sum(nums) / 3, 2))\n"},
    "stale-cache": {"answer.txt": "4600\n"},
    "stated-vs-true": {"total.txt": "48300\n"},
    "long-reports": {"count.txt": "9\n", "sum.txt": "8700\n"},
    "log-fanout": None,  # filled from the suite's selftest_bad
    "parallel-fix": {},  # the seeded broken modules
    "chain-12": {},      # the seeded wrong constants
    "spec-10": {"config.json": json.dumps({"service": {"name": "api", "port": 8080, "replicas": 8},
                                           "limits": {"cpu": "2000m", "memory": "2048Mi"},
                                           "features": {"beta": True, "cache": False},
                                           "logging": {"level": "debug", "format": "json"}}, indent=2) + "\n"},
}


for _t in SUITE["tasks"]:
    if _t["id"] in ("log-fanout", "log-fanout-big", "incident-scan"):
        GOOD[_t["id"]] = _t["selftest_good"]
        BAD[_t["id"]] = _t["selftest_bad"]


def run(task, extra):
    task = fixtures.task(task)
    d = Path(tempfile.mkdtemp(prefix="selftest-"))
    try:
        for name, content in task.get("files", {}).items():
            p = d / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        for name, content in extra.items():
            p = d / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        for name, content in task.get("verify_files", {}).items():
            (d / name).write_text(content)
        r = subprocess.run(["bash", "-c", task["verify"]], cwd=d, capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()[:200]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="")
    a = ap.parse_args()
    bad = 0
    for t in SUITE["tasks"]:
        if a.task and t["id"] != a.task:
            continue
        good_files, bad_files = fixtures.selftest_answers(t)
        good_files = good_files or GOOD.get(t["id"])
        bad_files = bad_files or BAD.get(t["id"])
        if good_files is None or bad_files is None:
            print(f"{t['id']:16s} NO SELFTEST ANSWERS  BROKEN")
            bad += 1
            continue
        ok_pass, err1 = run(t, good_files)
        ok_fail, err2 = run(t, bad_files)
        status = "ok" if (ok_pass and not ok_fail) else "BROKEN"
        if status == "BROKEN":
            bad += 1
        print(f"{t['id']:16s} good->{'PASS' if ok_pass else 'FAIL'} "
              f"bad->{'PASS' if ok_fail else 'FAIL'}  {status}"
              + (f"  {err1 or err2}" if status == "BROKEN" else ""))
    print("judge ok" if not bad else f"{bad} broken task(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
