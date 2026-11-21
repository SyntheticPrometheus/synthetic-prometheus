#!/usr/bin/env python3
"""Fresh confirmation on cases the proposer has not inspected (issue #1, finding 4).

The development suite is a regression floor, not proof: it is visible while the arm is written,
and at k=3 a saturated suite accepts on noise. This stage freezes the candidate first, then
generates a confirmation family with an unseen seed, measures BOTH arms on it in alternating
order, and only that family can promote the arm. The independence is stated honestly: the
generator code is public, so this is "seeded post-freeze variants", not a hidden judge.

  confirm.py freeze --arm arms/cand.md
  confirm.py build  --arm arms/cand.md
  confirm.py measure --base arms/base.md --cand arms/cand.md [--reps 3]
  confirm.py decide --dir confirm/<id> --dev-base runs/.../result.json --dev-cand runs/.../result.json

Refusals (exit 1): a candidate already measured before freezing, a second freeze of the same
arm bytes, an arm edited after its freeze, a run older than the freeze, a regenerated suite.
The development pair is required as the floor: a confirmation gain that regresses the dev suite
is not a promotion (gate.py decides the floor; this script refuses to skip it).
Exit codes on decide: 0 confirm, 2 hold, 3 reject, 1 void/refuse.
"""
import argparse
import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIRM = Path(os.environ.get("CONFIRM_DIR", str(HERE / "confirm")))
FIX = HERE / "suite" / "fixtures"
LEDGER = Path(os.environ.get("CONFIRM_LEDGER", str(HERE / "ledger.jsonl")))
POLICY = HERE / "policy.json"
RUNNER = Path(os.environ.get("CONFIRM_RUNNER", str(HERE / "run.py")))
GATE = HERE / "gate.py"
STAMP = re.compile(r"^\d{8}T\d{6}$")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    return sha_bytes(Path(p).read_bytes())


def freeze_path(arm_sha):
    return CONFIRM / f"frozen-{arm_sha[:12]}.json"


def ledger():
    if not LEDGER.exists():
        return []
    return [json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]


def load_json(p):
    return json.loads(Path(p).read_text())


def policy():
    return load_json(POLICY) if POLICY.exists() else {}


def k_default():
    return int(policy().get("gate", {}).get("min_reps", 3))


def alpha_default():
    return float(policy().get("confirmation", {}).get("alpha", 0.1))


def gen_seed(seed, label, i):
    return int(sha_bytes(f"{seed}:{label}:{i}".encode())[:12], 16)


def family(seed):
    """Instantiate the confirmation family. Two seeded variants from generators the dev suite
    already uses (unseen seeds), plus three tasks from a family the dev suite does not contain."""
    sys.path.insert(0, str(FIX))
    import _audit_mix
    import _brief
    import _holdout

    dev = {t["id"]: t for t in load_json(HERE / "suite" / "suite.json")["tasks"]}
    audit_prompt = dev["audit-mix"]["prompt"]
    tasks = []
    for i in (1, 2):
        t = _audit_mix.build(gen_seed(seed, "audit", i))
        tasks.append({"id": f"audit-mix-conf-{i}", "prompt": audit_prompt,
                      "files": t["files"], "verify_files": t["verify_files"],
                      "verify": t["verify"]})
    # the dev suite used version 4.2/5.1; confirmation uses an unseen version and component set.
    for i, (ver, comps) in enumerate((("6.3", "api,auth,billing,search,docs"),
                                      ("6.4", "api,auth,billing,inventory,docs")), 1):
        b = _brief.build(gen_seed(seed, "brief", i), ver, comps.split(","), 26,
                             f"confirmation brief {i}")
        tasks.append({"id": f"release-brief-conf-{i}", "prompt":
                      f"Write RELEASE_NOTES.md and release.json for version {ver}, using "
                      f"changes.csv and following every rule in POLICY.md exactly. The judge "
                      f"checks POLICY.md rule by rule; one violated rule fails the task.",
                      "files": b["files"], "verify_files": b["verify_files"],
                      "verify": b["verify"]})
    for i in (1, 2, 3):
        t = _holdout.build(gen_seed(seed, "settlement", i), i)
        t["id"] = f"settlement-audit-{i}"
        tasks.append(t)
    return tasks


def require_freeze(arm):
    arm = Path(arm).resolve()
    if not arm.is_file():
        raise SystemExit(f"REFUSE: arm not found: {arm}")
    cur = sha_file(arm)
    fp = freeze_path(cur)
    if not fp.exists():
        # the arm may have been frozen under its old bytes: say that, not "never frozen"
        for old in sorted(CONFIRM.glob("frozen-*.json")) if CONFIRM.exists() else []:
            try:
                f0 = load_json(old)
            except Exception:
                continue
            if Path(f0.get("arm", "")) == arm:
                raise SystemExit(f"REFUSE: {arm} changed after its freeze ({f0['arm_sha'][:12]}) "
                                 f"— the frozen bytes are the only ones a confirmation may measure")
        raise SystemExit(f"REFUSE: {arm.name} was never frozen (run `confirm.py freeze --arm {arm}` "
                         f"before measuring it on a confirmation family)")
    f = load_json(fp)
    if sha_file(arm) != f["arm_sha"]:
        raise SystemExit(f"REFUSE: {arm} changed after its freeze — the frozen bytes are the only "
                         f"ones a confirmation may measure")
    return arm, f, fp


def cmd_freeze(a):
    arm = Path(a.arm).resolve()
    if not arm.is_file():
        raise SystemExit(f"REFUSE: arm not found: {arm}")
    s = sha_file(arm)
    fp = freeze_path(s)
    if fp.exists():
        raise SystemExit(f"REFUSE: {arm.name} ({s[:12]}) is already frozen ({fp.name}); a second "
                         f"confirmation of the same bytes is fishing, not evidence")
    prior = [r for r in ledger() if r.get("arm_sha") == s]
    if prior:
        raise SystemExit(f"REFUSE: {arm.name} ({s[:12]}) already has {len(prior)} measured run(s) "
                         f"— freeze must happen before the first result exists")
    f = {"arm": str(arm), "arm_sha": s, "frozen_at": time.time(),
         "frozen_stamp": time.strftime("%Y%m%dT%H%M%S", time.gmtime()),
         "seed": sha_bytes((s + secrets.token_hex(16)).encode()),
         "k": k_default(), "alpha": alpha_default()}
    CONFIRM.mkdir(exist_ok=True)
    fp.write_text(json.dumps(f, indent=1))
    print(f"frozen {arm.name} {s[:12]} -> {fp}  seed {f['seed'][:16]}…  k={f['k']}")
    return 0


def cmd_build(a):
    arm, f, fp = require_freeze(a.arm)
    out = CONFIRM / f["arm_sha"][:12]
    if out.exists():
        raise SystemExit(f"REFUSE: {out} already exists — a confirmation family is generated once "
                         f"and never regenerated to fit the results")
    tasks = family(f["seed"])
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"REFUSE: duplicate task ids in generated family: {ids}")
    suite = {"tasks": tasks}
    body = json.dumps(suite, indent=1)
    sys.path.insert(0, str(HERE))
    import run as runner
    out.mkdir(parents=True)
    (out / "suite.json").write_text(body)
    judge_sha = runner.suite_sha(suite_path=out / "suite.json")
    manifest = {**f, "dir": str(out), "suite_path": str(out / "suite.json"),
                "suite_sha": sha_bytes(body.encode()), "judge_sha": judge_sha,
                "created_at": time.time(),
                "created_stamp": time.strftime("%Y%m%dT%H%M%S", time.gmtime()),
                "tasks": ids}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"built {len(ids)} confirmation task(s) in {out}: {', '.join(ids)}")
    print(f"manifest {out / 'manifest.json'}  judge {judge_sha[:12]}")
    return 0


def cmd_measure(a):
    arm, f, fp = require_freeze(a.cand)
    out = CONFIRM / f["arm_sha"][:12]
    man = load_json(out / "manifest.json")
    if sha_file(a.cand) != man["arm_sha"]:
        raise SystemExit("REFUSE: candidate changed after the family was built")
    k = a.reps or man["k"]
    if k < man["k"]:
        raise SystemExit(f"REFUSE: --reps {k} is below the frozen k={man['k']}")
    tasks = ",".join(man["tasks"])
    runs = {"base": [], "cand": []}
    for rep in range(1, k + 1):
        # alternate order every rep: a provider drift or a warm/cold cache cannot favour one arm.
        order = [("base", a.base), ("cand", a.cand)] if rep % 2 else [("cand", a.cand),
                                                                     ("base", a.base)]
        for name, arm_path in order:
            cmd = [sys.executable, str(RUNNER), "--arm", arm_path, "--suite", man["suite_path"],
                   "--tasks", tasks, "--reps", "1", "--tag", f"confirm-r{rep}",
                   "--variant-seed", man["seed"], "--confirm-sha", man["judge_sha"]]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode != 0:
                print(p.stdout[-1200:] + p.stderr[-1200:])
                raise SystemExit(f"REFUSE: {name} rep {rep} failed — no result to confirm with")
            line = [x for x in p.stdout.splitlines() if " → " in x][-1]
            runs[name].append(Path(line.rsplit(" → ", 1)[1].strip()) / "result.json")
            print(f"r{rep} {name} -> {runs[name][-1]}")
    for name in ("base", "cand"):
        merged = merge(runs[name], k)
        (out / f"{name}.json").write_text(json.dumps(merged, indent=1))
        print(f"{name}: {out / (name + '.json')}")
    print(f"decide: confirm.py decide --dir {out} --dev-base <run> --dev-cand <run>")
    return 0


def merge(paths, k):
    recs = [load_json(p) for p in paths]
    first = dict(recs[0])
    results = []
    for rep, r in enumerate(recs, 1):
        if sha_file(r["arm_path"]) != r["arm_sha"]:
            raise SystemExit(f"REFUSE: {r['arm_path']} changed during measurement")
        for x in r["results"]:
            x = dict(x)
            x["rep"] = rep
            results.append(x)
    first.update({"results": results, "reps": k, "n": len(results),
                  "passed": sum(1 for x in results if x["pass"]),
                  "wall_s": round(sum(r.get("wall_s", 0) for r in recs), 1),
                  "tokens_in": sum(r.get("tokens_in", 0) for r in recs),
                  "tokens_out": sum(r.get("tokens_out", 0) for r in recs),
                  "cost_usd": round(sum(r.get("cost_usd", 0) for r in recs), 6)})
    first["pass_rate"] = round(first["passed"] / first["n"], 4) if first["n"] else 0.0
    return first


def parse_stamp(s):
    try:
        return time.mktime(time.strptime(s, "%Y%m%dT%H%M%S"))
    except Exception:
        return None


def by_task(d):
    out = {}
    for r in d["results"]:
        out.setdefault(r["id"], []).append(bool(r["pass"]))
    return out


def sign_p(w, l):
    """One-sided exact sign test: P(at least w wins among w+l discordant tasks | p=0.5).
    Pre-registered direction (the candidate is the proposal), so doubling it would be the wrong
    correction; no scipy on this host."""
    n = w + l
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(w, n + 1)) / (2 ** n)
    return min(1.0, tail)


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def provenance(man, base, cand):
    """Every confirmation check that decides whether these numbers may be looked at at all."""
    for name, d in (("base", base), ("cand", cand)):
        if d.get("variant_seed") != man["seed"]:
            return f"VOID: {name} run is not from the frozen family (variant_seed " \
                   f"{str(d.get('variant_seed'))[:16]} != {man['seed'][:16]})"
        if d.get("confirm_sha") != man["judge_sha"]:
            return f"VOID: {name} run was scored by a different generated suite"
        if Path(d.get("suite_path") or "") != Path(man["suite_path"]):
            return f"VOID: {name} run used {d.get('suite_path')}, not the frozen family"
        if d.get("suite_sha") != man["judge_sha"]:
            return f"VOID: {name} run's judge hash changed under the frozen family"
        st = parse_stamp(str(d.get("stamp", "")))
        if not st or not STAMP.match(str(d.get("stamp", ""))):
            return f"VOID: {name} run has no readable stamp"
        if st <= man["frozen_at"]:
            return f"VOID: {name} run predates the freeze — that is development, not fresh " \
                   f"confirmation"
    if base.get("arm_sha") == cand.get("arm_sha"):
        return "VOID: identical arms"
    if cand.get("arm_sha") != man["arm_sha"]:
        return "VOID: candidate arm bytes differ from the frozen candidate"
    if sha_file(cand.get("arm_path") or "") != man["arm_sha"]:
        return "VOID: candidate arm file no longer matches the frozen sha"
    if sum(1 for r in ledger() if r.get("arm_sha") == man["arm_sha"]
           and r.get("variant_seed") == man["seed"]) > 2 * man["k"]:
        return "VOID: more confirmation runs than frozen for this (arm, seed) — reseeded fishing"
    return None


def cmd_decide(a):
    out = Path(a.dir)
    man = load_json(out / "manifest.json")
    base, cand = load_json(out / "base.json"), load_json(out / "cand.json")
    bad = provenance(man, base, cand)
    if bad:
        print(bad)
        return 1
    # The development suite is the floor: a candidate that regresses it cannot be promoted on a
    # confirmation family, however good that family looks.
    if not a.dev_base or not a.dev_cand:
        print("REFUSE: --dev-base and --dev-cand are required — the pinned dev suite is the "
              "regression floor; confirmation alone is not a promotion")
        return 1
    floor = subprocess.run([sys.executable, str(GATE), a.dev_base, a.dev_cand],
                           capture_output=True, text=True)
    floor_out = (floor.stdout + floor.stderr).strip()
    if floor.returncode != 0:
        print("DEV FLOOR:")
        print(floor_out[-900:])
        if floor.returncode == 3:
            print("REJECT: the candidate regresses the pinned development suite")
        else:
            print("HOLD: the development floor did not accept this pair")
        return 3 if floor.returncode == 3 else 2
    print("DEV FLOOR: accepted — confirmation is now allowed to decide")
    gate = subprocess.run([sys.executable, str(GATE), str(out / "base.json"),
                           str(out / "cand.json")], capture_output=True, text=True)
    gout = (gate.stdout + gate.stderr).strip()
    bt, ct = by_task(base), by_task(cand)
    common = sorted(set(bt) & set(ct))
    if not common:
        print("VOID: the two confirmation runs share no task")
        return 1
    won = [t for t in common if sum(ct[t]) > sum(bt[t])]
    lost = [t for t in common if sum(ct[t]) < sum(bt[t])]
    ties = [t for t in common if sum(ct[t]) == sum(bt[t])]
    pb = sum(sum(bt[t]) for t in common) / (len(common) * base["reps"])
    pc = sum(sum(ct[t]) for t in common) / (len(common) * cand["reps"])
    p = sign_p(len(won), len(lost))
    lb, lc = wilson(pb, len(common) * base["reps"]), wilson(pc, len(common) * cand["reps"])
    print(f"confirmation: {len(common)} unseen task(s), k={base['reps']}")
    print(f"  base {pb:.0%} [{lb[0]:.0%},{lb[1]:.0%}]   cand {pc:.0%} [{lc[0]:.0%},{lc[1]:.0%}]")
    print(f"  tasks won {len(won)}, lost {len(lost)}, tied {len(ties)}   sign-test p={p:.3f} "
          f"(alpha {man['alpha']})")
    for t in common:
        mark = "WON " if t in won else ("LOST" if t in lost else "tie ")
        print(f"    {mark} {t:20s} {sum(bt[t])}/{len(bt[t])} -> {sum(ct[t])}/{len(ct[t])}")
    print("GATE:", gout.splitlines()[0] if gout else "(no output)")
    if gate.returncode == 3:
        print("REJECT: confirmation regression — no promotion")
        return 3
    if gate.returncode == 2:
        print("HOLD: confirmation is not sufficient evidence")
        return 2
    if p > man["alpha"]:
        print(f"HOLD: {len(won)} won / {len(lost)} lost is not distinguishable from noise "
              f"(sign p={p:.3f} > {man['alpha']})")
        return 2
    if "ACCEPT_COST" in gout:
        print("CONFIRM_COST: equal pass with fewer output tokens on unseen cases — an efficiency "
              "win, not a capability gain")
        return 0
    print("CONFIRM: improvement reproduced on cases frozen before the candidate existed")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--arm", required=True)
    b = sub.add_parser("build")
    b.add_argument("--arm", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--base", required=True)
    m.add_argument("--cand", required=True)
    m.add_argument("--reps", type=int, default=0)
    d = sub.add_parser("decide")
    d.add_argument("--dir", required=True)
    d.add_argument("--dev-base", default="")
    d.add_argument("--dev-cand", default="")
    a = ap.parse_args()
    return {"freeze": cmd_freeze, "build": cmd_build, "measure": cmd_measure,
            "decide": cmd_decide}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
