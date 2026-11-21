#!/usr/bin/env python3
"""settlement-audit — a task family that does NOT appear in the development suite.

The confirmation stage generates this family with an unseen seed after the candidate arm is
frozen (confirm.py). The generator owns the data, the expected answer and a known-wrong answer:
no expected value is hand-typed, which is the judge-defect class that produced the 2026-11-14
incidents. Independence is only as strong as "the proposer did not see the instantiated cases":
the generator code is public, the seed and its output are not.

  python3 _holdout.py SEED VARIANT   # prints one JSON task payload for confirm.py
"""
import csv
import io
import json
import random
import sys

SERVICES = ["checkout", "payments", "search", "cart", "auth", "shipping"]
STATUSES = ["open", "held", "closed"]
SPEC = """# Settlement audit

`settlements.csv` has one row per settlement: `id,service,status,opening_cents,debits_cents,credits_cents`.

Produce `balances.csv` and `flags.txt`:

1. `closing_cents = opening_cents - debits_cents + credits_cents`.
2. Skip any row whose `id` starts with `X` (voided).
3. Skip any row whose `status` is `held`.
4. `balances.csv`: header `id,closing_cents`, rows sorted by id ascending, one per counted row.
5. `flags.txt`: ids whose absolute movement `|closing_cents - opening_cents|` is >= {threshold}
   cents, ascending, one per line. A skipped row is never flagged.
6. Amounts are integers; never round.
"""


def build(seed, variant=1):
    rnd = random.Random(seed * 1009 + variant)
    threshold = rnd.choice([150000, 200000, 250000, 300000])
    rows = []
    for i in range(1, 17):
        rid = f"A-{i:04d}"
        if rnd.random() < 0.12:
            rid = "X-" + rid[2:]
        status = rnd.choices(STATUSES, weights=[7, 2, 2])[0]
        opening = rnd.randrange(100_000, 9_000_000)
        debits = rnd.randrange(0, 900_000)
        credits = rnd.randrange(0, 900_000)
        rows.append([rid, rnd.choice(SERVICES), status, opening, debits, credits])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "service", "status", "opening_cents", "debits_cents", "credits_cents"])
    w.writerows(rows)
    settlements = buf.getvalue()

    counted = [r for r in rows if not r[0].startswith("X") and r[2] != "held"]
    counted.sort(key=lambda r: r[0])
    expected = [[r[0], r[3] - r[4] + r[5]] for r in counted]
    flags = [r[0] for r in counted if abs((r[3] - r[4] + r[5]) - r[3]) >= threshold]
    good_bal = "id,closing_cents\n" + "".join(f"{i},{c}\n" for i, c in expected)
    good_flags = "".join(f + "\n" for f in flags)
    # known-wrong: one balance off by a cent and one extra flag; both are judge-visible.
    bad = [list(r) for r in expected]
    bad[0][1] += 1
    bad_flags = flags + ["A-9999"]

    exp = {"balances": expected, "flags": flags}
    verify = (
        "import csv, io, json, sys\n"
        f"exp = {exp!r}\n"
        "try:\n"
        "    rows = list(csv.reader(io.StringIO(open('balances.csv').read())))\n"
        "    got = rows[1:]\n"
        "    flags = [l.strip() for l in open('flags.txt') if l.strip()]\n"
        "except Exception as e:\n"
        "    print(f'unreadable: {e}', file=sys.stderr); sys.exit(1)\n"
        "if rows[0] != ['id', 'closing_cents']:\n"
        "    print(f'bad header {rows[0]}', file=sys.stderr); sys.exit(1)\n"
        "if [[r[0], int(r[1])] for r in got] != exp['balances']:\n"
        "    print(f'balances mismatch', file=sys.stderr); sys.exit(1)\n"
        "if flags != exp['flags']:\n"
        "    print(f'flags mismatch {flags} != {exp[\"flags\"]}', file=sys.stderr); sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    prompt = ("settlements.csv lists settlements. Follow SPEC.md exactly and produce balances.csv "
              "and flags.txt. Then reply with the number of flagged settlements.")
    return {
        "id": f"settlement-audit-{variant}",
        "prompt": prompt,
        "files": {"settlements.csv": settlements, "SPEC.md": SPEC.format(threshold=threshold)},
        "verify_files": {"_verify.py": verify},
        "verify": "python3 _verify.py",
        "selftest_good": {"balances.csv": good_bal, "flags.txt": good_flags},
        "selftest_bad": {"balances.csv": good_bal.replace(f"{expected[0][0]},{expected[0][1]}\n",
                                                         f"{bad[0][0]},{bad[0][1]}\n", 1),
                         "flags.txt": "".join(f + "\n" for f in bad_flags)},
    }


def main(argv):
    seed, variant = int(argv[1]), int(argv[2]) if len(argv) > 2 else 1
    print(json.dumps(build(seed, variant)))


if __name__ == "__main__":
    main(sys.argv)
