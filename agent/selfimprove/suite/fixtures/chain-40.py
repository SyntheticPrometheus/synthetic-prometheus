#!/usr/bin/env python3
"""chain-40 — 40 dependent modules, each with one wrong constant, plus a table of expected stage
outputs. Long-horizon exactness: one arithmetic slip anywhere in 40 small fixes fails the task.

Why this exists: the suite's hardest long-horizon task is 12 steps (chain-12) and the base arm
solves it 3/3, so the suite has no headroom for gate.py to accept anything (cycle 10, cycle 13).
This is the same class, three times longer, with the expected intermediates published so the task
stays unambiguous.

Truth: the generator knows the intended constants and the resulting stage outputs; the verifier
recomputes the composition by importing the modules the arm wrote.
"""
import json
import random

N = 40
VERIFY = r'''import importlib.util, json, sys
from pathlib import Path
truth = json.load(open("_truth.json"))
mods = []
for i in range(1, truth["n"] + 1):
    p = Path("m") / f"m{i:02d}.py"
    spec = importlib.util.spec_from_file_location(f"m{i:02d}", p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"m{i:02d} does not import: {e!r}", file=sys.stderr)
        sys.exit(1)
    mods.append(mod)
bad = []
for x, expected in truth["expected"].items():
    v = int(x)
    for mod in mods:
        v = mod.f(v)
    if v != expected:
        bad.append(f"x={x}: composed {v}, expected {expected}")
if bad:
    print("; ".join(bad[:6]), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'''


def main():
    rng = random.Random(4020261114)
    files, ops, want = {}, [], []
    v = 2
    for i in range(1, N + 1):
        op = rng.choice(["add", "mul"])
        k = rng.randint(1, 9) if op == "add" else rng.choice([2, 3])
        # keep the pipeline in range: cap multiplication
        while op == "mul" and v * k > 10 ** 7:
            op, k = "add", rng.randint(1, 9)
        v = v + k if op == "add" else v * k
        ops.append((op, k))
        want.append(v)
    # one wrong constant per module: a plausible neighbour
    for i, (op, k) in enumerate(ops, 1):
        wrong = k + (1 if rng.random() < 0.5 else -1)
        wrong = max(1, wrong) if op == "add" else max(2, wrong)
        body = (f'"""Stage {i}: applied in order; the constant is the only thing to fix."""\n'
                f'K = {wrong}\n\n\ndef f(x):\n'
                + ("    return x + K\n" if op == "add" else "    return x * K\n"))
        files[f"m/m{i:02d}.py"] = body

    rows = "\n".join(f"| {i:02d} | {'add' if op == 'add' else 'multiply'} | {out} |"
                     for i, ((op, _), out) in enumerate(zip(ops, want), 1))
    files["ORDER.md"] = (
        "# Pipeline order and expected intermediates\n\n"
        "The modules in `m/` are applied in numeric order to the input value, each feeding the next.\n"
        "For input **2** the table below gives the output expected after each stage. Every module has\n"
        "exactly one constant wrong; the operation itself (add or multiply) is correct. Fix the\n"
        "constants so the composed pipeline reproduces the table for every input, not just 2.\n\n"
        "| stage | operation | expected output |\n|---|---|---|\n" + rows + "\n")

    expected = {}
    for x in (1, 2, 3, 5, 7, 11, 13):
        v = x
        for op, k in ops:
            v = v + k if op == "add" else v * k
        expected[str(x)] = v

    good = {}
    for i, (op, k) in enumerate(ops, 1):
        good[f"m/m{i:02d}.py"] = (f'"""Stage {i}: applied in order; the constant is the only thing to fix."""\n'
                                  f'K = {k}\n\n\ndef f(x):\n'
                                  + ("    return x + K\n" if op == "add" else "    return x * K\n"))
    bad = dict(good)
    bad["m/m33.py"] = files["m/m33.py"]  # leave one stage broken

    print(json.dumps({
        "files": files,
        "verify_files": {"_truth.json": json.dumps({"n": N, "expected": expected}),
                         "_verify.py": VERIFY},
        "verify": "python3 _verify.py",
        "good": good,
        "bad": bad,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
