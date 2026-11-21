#!/usr/bin/env python3
"""audit-mix — the spec-adherence-under-bulk class (cycle 17, agenda #13).

Why this class and not another scriptable fold: the observed base-arm failure on `long-reports`
was not a capability ceiling, it was a *quick* script that missed one stated rule (the literal
`5xx` token). Inputs whose rules are cheap to state but each easy to skip punish the fold-and-report
arm and reward a harness that turns every stated rule into a check before answering. This task
carries six such rules (last-wins retries, alias resolution, literal 5xx, tentative statuses,
exclusions, s->ms units), 4.8k lines across 12 shards, and a near tie for the top service.

Truth is produced here from the same generated rows, never typed by hand. `good` is the truth as
files, `bad` is the truth with one count changed, `tolerant` is the same truth with harmless
whitespace, so selftest.py proves the judge can pass, tolerate, and fail.
"""
import json
import random
import sys

DEFAULT_SEED = 1307
SHARDS = 12
PER_SHARD = 400
CANON = ["auth", "cart", "checkout", "payments", "search", "shipping"]
ALIASES = {
    "pay": "payments",
    "payments_eu": "payments",
    "Payments": "payments",
    "SEARCH": "search",
    "search-svc": "search",
    "auth_svc": "auth",
    "Auth": "auth",
    "cart-svc": "cart",
    "Checkout": "checkout",
    "ship": "shipping",
}
# weights: make payments and search close so the top-service tie rule is load-bearing
WEIGHTS = {"auth": 9, "cart": 7, "checkout": 6, "payments": 30, "search": 27, "shipping": 3}


def build(seed=DEFAULT_SEED):
    rnd = random.Random(seed)
    rows = []          # (eid, status, service_raw, duration_raw, retry)
    nxt = 1
    aliases = list(ALIASES.items())
    alias_names = [a for a, _ in aliases]

    def service():
        if rnd.random() < 0.35:
            return rnd.choice(alias_names)
        return rnd.choice(CANON).upper() if rnd.random() < 0.10 else rnd.choice(CANON)

    def status():
        r = rnd.random()
        if r < 0.55:
            return rnd.choice(["200", "200", "302", "404"])
        if r < 0.88:
            s = str(rnd.choice([500, 500, 502, 503, 503, 504]))
        else:
            s = rnd.choice(["5xx", "5xx", "5XX"])
        return s + "*" if rnd.random() < 0.05 else s          # tentative

    def duration():
        r = rnd.random()
        if r < 0.03:
            return f"{rnd.randint(1, 5)}m"
        if r < 0.33:
            return f"{rnd.randint(1, 9)}s"
        return str(rnd.randint(1, 9000))

    # a retry repeats an earlier id and its line is what counts (last wins)
    retry_pool = []
    for i in range(SHARDS * PER_SHARD):
        eid = f"evt-{nxt:06d}"
        nxt += 1
        if retry_pool and rnd.random() < 0.04:
            eid = retry_pool.pop(rnd.randrange(len(retry_pool)))
            rows.append((eid, status(), service(), duration(), True))
            continue
        if rnd.random() < 0.05:
            retry_pool.append(eid)      # this id will be re-issued later; earlier line is a draft
        rows.append((eid, status(), service(), duration(), False))
    # any id whose retry never arrived is still just one event
    shards = [[] for _ in range(SHARDS)]
    for i, row in enumerate(rows):
        shards[i % SHARDS].append(row)

    def canon(svc):
        low = svc.lower()
        for a, c in aliases:
            if a.lower() == low:
                return c
        return low

    # truth: last line per id wins, then aliases, exclude, 5xx/tentative/units
    last = {}
    for row in rows:
        last[row[0]] = row
    excl = set()
    while len(excl) < 14:
        excl.add(f"evt-{rnd.randint(1, len(rows)):06d}")
    n = ms = 0
    per = {c: 0 for c in CANON}
    for eid, st, svc, dur, _ in last.values():
        if eid in excl:
            continue
        base = st.rstrip("*")
        tentative = st.endswith("*")
        is5 = base.lower() == "5xx" or (len(base) == 3 and base.isdigit() and base[0] == "5")
        if not is5:
            continue
        c = canon(svc)
        n += 1
        per[c] = per.get(c, 0) + 1
        if tentative:
            continue
        if dur.endswith("m"):
            ms += int(dur[:-1]) * 60000
        elif dur.endswith("s"):
            ms += int(dur[:-1]) * 1000
        else:
            ms += int(dur)
    top = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    files = {}
    for si, shard in enumerate(shards, 1):
        lines = [f"# shard {si:02d} — one event per line: id time status service duration"]
        for eid, st, svc, dur, retry in shard:
            t = f"2026-03-{2 + si % 3:02d}T{(si * 7 + int(eid[-3:]) % 60) % 24:02d}:{int(eid[-3:]) % 60:02d}:00Z"
            line = f"{eid} {t} {st} {svc} {dur}"
            if retry:
                line += " retry=1"
            if rnd.random() < 0.03:
                line += ' note="seen on the edge node, paged at 3am"'
            lines.append(line)
        files[f"logs/shard{si:02d}.txt"] = "\n".join(lines) + "\n"

    files["aliases.csv"] = "alias,canonical\n" + "".join(f"{a},{c}\n" for a, c in aliases)
    files["exclude.txt"] = "\n".join(sorted(excl)) + "\n"
    files["SPEC.md"] = f"""# Audit spec — counted 5xx events

`logs/` holds {SHARDS} shards of request events, one per line:
`<event-id> <timestamp> <status> <service> <duration>` followed by zero or more
`retry=1` / `note="..."` fields in any order. `note` values are quoted and may contain spaces; they
never affect the count. Lines beginning with `#` are headers, not events.

A line with `retry=1` re-issues an event id that appeared before it. Only the **last** line for an
event id is the event; every earlier line with the same id is a draft and is ignored.

An event id listed in `exclude.txt` is dropped after the last-wins step (none of its lines count).

Resolve each service through `aliases.csv` (`alias,canonical`); matching is case-insensitive on the
alias. A service not listed there is used as-is in lowercase (so `PAYMENTS` is `payments`).

A **5xx event** is a status that, ignoring a trailing `*`, is either the literal token `5xx`
(case-insensitive) or a three-digit code beginning with `5`. A trailing `*` marks the status **tentative**.

Counting:
- `n.txt`: the number of 5xx events. Tentative events are included.
- `ms.txt`: the sum of the durations of the non-tentative 5xx events, in milliseconds. A bare
  integer duration is already milliseconds; a duration ending in `s` is seconds (multiply by
  1000); one ending in `m` is minutes (multiply by 60000).
- `top.txt`: the canonical service with the most 5xx events counted above (tentative included);
  break ties alphabetically. If none, write `none`.

Write just the number in `n.txt` and `ms.txt`, and just the service name in `top.txt`,\nin this directory (the judge also accepts them under `logs/`).
"""

    good = {"n.txt": f"{n}\n", "ms.txt": f"{ms}\n", "top.txt": f"{top}\n"}
    bad = {"n.txt": f"{n + 1}\n", "ms.txt": f"{ms}\n", "top.txt": f"{top}\n"}
    tolerant = {"n.txt": f" {n} \n", "ms.txt": f"{ms}\n\n", "top.txt": f"{top}  \n"}
    verify = ("python3 _verify.py")
    verify_files = {
        "_truth.json": json.dumps({"n": n, "ms": ms, "top": top}) + "\n",
        "_verify.py": (
            "import json, os, sys\n"
            "t = json.load(open('_truth.json'))\n"
            "def rd(p):\n"
            "    q = p if os.path.exists(p) else os.path.join('logs', p)\n"
            "    return open(q).read().strip()\n"
            "try:\n"
            "    n = int(rd('n.txt'))\n"
            "    ms = int(rd('ms.txt'))\n"
            "    top = rd('top.txt').lower()\n"
            "except Exception as e:\n"
            "    print(f'answer unreadable: {e}', file=sys.stderr); sys.exit(1)\n"
            "if n != t['n']:\n"
            "    print(f\"n: expected {t['n']}; got {n}\", file=sys.stderr); sys.exit(1)\n"
            "if ms != t['ms']:\n"
            "    print(f\"ms: expected {t['ms']}; got {ms}\", file=sys.stderr); sys.exit(1)\n"
            "if top != t['top']:\n"
            "    print(f\"top: expected {t['top']}; got {top}\", file=sys.stderr); sys.exit(1)\n"
        ),
    }
    return {"files": files, "verify": verify, "verify_files": verify_files,
            "good": good, "bad": bad, "tolerant": tolerant}


if __name__ == "__main__":
    json.dump(build(), sys.stdout)
