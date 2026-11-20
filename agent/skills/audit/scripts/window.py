#!/usr/bin/env python3
"""window.py — the evidence pack for a periodic activity audit, in one cheap call.

Why this exists: the 2026-11-16 audit was done by hand — a dozen exploratory shell calls to discover
which instruments were lying (a cadence FAIL that was arithmetic, a brief dropping pinned rules, a
fragility gate flapping on a 0.003 rank tie, a cost ceiling nothing compared to the logs). Every one
of those was mechanical. This script does the mechanical part so the audit session spends its
context on judgement: debate the contested findings, dispatch testers on the fixes, and record the
loop.

    window.py scan                 # the pack (default: since the last recorded run, else 7d)
    window.py scan --since 2026-11-15 --record
    window.py scan --fast          # skip pi-preflight (~60 s) and the session miner
    window.py close --findings 5 --fixed 4 --spend 2.10 --notes "..."
    window.py score                # the self-improving part: yield, repeats, cadence rule

Self-improving rules (applied by `score`, stated in skills/audit/SKILL.md):
  * a suspect that appears in two consecutive runs is a REPEAT: the previous fix did not hold, and
    the next run must spend its first hour on it, not on new ground;
  * cost per fixed finding above $6, or two consecutive runs under one fixed finding, lengthens the
    cadence (the audit is not paying for itself);
  * a lens (tester/boundaries, tester/oracle, redteam/abuse, ...) that reports nothing reproducible
    in two consecutive runs is retired in lenses.json by the auditor, and a lens that finds two or
    more gets a second dispatch next run.

Exit codes: 0 = clean pack, 1 = pack produced but it found suspects (the normal case),
2 = the pack could not be produced honestly (unreadable ledger, bad window) — never confuse the
last two: a crash that exits 1 reads as "found something", which is how an instrument starts lying.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

AGENT = Path(__file__).resolve().parents[3]          # ~/.pi/agent
SKILL = Path(__file__).resolve().parents[1]
LEDGER = SKILL / "ledger.jsonl"
LENSES = SKILL / "lenses.json"
DB = AGENT / "agenda" / "agenda.db"
BURN = AGENT / "burn" / "log.jsonl"
SESSIONS = AGENT / "sessions"
MINE = AGENT / "skills" / "session-review" / "scripts" / "mine.py"
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def run(cmd: list[str], timeout: int = 120, env: dict | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 125, f"{cmd[0]}: {exc}"


ERROR = re.compile(r"^(?:error\b|failed\b|exception\b|traceback\b|timed out\b|"
                   r"command not found\b|no such file\b|permission denied\b|exit code [1-9])", re.I)


def shrink(text: str) -> str:
    """Group error signatures that differ only in numbers, hashes and paths."""
    one = re.sub(r"[0-9a-f]{8,}", "#", " ".join(text.split()))
    return re.sub(r"\d+", "#", one)[:64]


def hum(seconds: float) -> str:
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    if seconds < 172800:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def parse_when(text: str) -> float:
    """Accept `7d`, an ISO-ish local date, or a real epoch. Refuse everything else."""
    text = (text or "").strip()
    if not text:
        raise SystemExit("window.py: empty time")
    m = re.fullmatch(r"(\d+)([smhdw])", text)
    if m:
        return time.time() - int(m.group(1)) * UNITS[m.group(2)]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            val = float(time.mktime(time.strptime(text, fmt)))
        except ValueError:
            continue
        return _sane_time(val, text)
    try:
        val = float(text)
    except ValueError:
        raise SystemExit(f"window.py: cannot read time {text!r} (7d, 2026-11-15, or an epoch)")
    # `2026`, `7` and `0` used to parse as epochs and quietly audit 1969 or a 20,000-day window;
    # NaN/inf used to traceback inside money_section. Both are now refusals.
    if not math.isfinite(val) or val < 1e9:
        raise SystemExit(f"window.py: {text!r} is not a time (a bare number is read as an epoch, "
                         "and 1e9 is 2001 — write 7d or 2026-11-15)")
    return _sane_time(val, text)


def _sane_time(val: float, text: str) -> float:
    if not math.isfinite(val) or not (0 < val <= time.time() + 3600):
        raise SystemExit(f"window.py: {text!r} is not in the past")
    return val


def read_ledger() -> tuple[list[dict], int]:
    """Every reader goes through here: one truncated line must not erase the ledger."""
    if LEDGER.exists() and not LEDGER.is_file():
        raise SystemExit(f"window.py: {LEDGER} is not a file — refusing to guess")
    try:
        raw = LEDGER.read_text(errors="replace")
    except OSError:
        return [], 0
    rows, bad = [], 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            bad += 1
    return rows, bad


def append_ledger(row: dict) -> None:
    """Append one JSON line, never on top of a truncated tail (a half-written row used to swallow
    the next scan's record because the file did not end with a newline)."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if LEDGER.exists() and not LEDGER.is_file():
        raise SystemExit(f"window.py: {LEDGER} is not a file — refusing to write")
    nl = ""
    try:
        with LEDGER.open("rb") as fh:
            fh.seek(-1, 2)
            nl = "" if fh.read(1) == b"\n" else "\n"
    except (OSError, ValueError):
        nl = ""
    with LEDGER.open("a") as fh:
        fh.write(nl + json.dumps(row) + "\n")


def last_window() -> float:
    """Start of this audit = end of the last recorded one (a future end is ignored, not obeyed)."""
    rows, _ = read_ledger()
    now = time.time()
    for row in reversed(rows):
        if row.get("event", "scan") != "scan":
            continue
        try:
            end = float(row.get("window_end"))
        except (TypeError, ValueError):
            continue
        if 0 < end <= now + 60:
            return end
    return now - 7 * 86400


# ------------------------------------------------------------------ evidence sections
def sessions_section(since: float, fast: bool) -> dict:
    """Counts from the session logs + (optionally) the friction miner, composed not duplicated."""
    files = [p for p in SESSIONS.glob("*/*.jsonl") if p.stat().st_mtime >= since]
    total = sum(p.stat().st_size for p in files)
    calls = errors = asks = 0
    sigs: dict[str, int] = {}
    for p in files:
        try:
            fh = p.open(errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if "toolCall" not in line and "toolResult" not in line and '"role":"user"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                msg = row.get("message") or {}
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role") or row.get("role")
                if role == "user":
                    asks += 1
                elif role == "toolResult":
                    # pi stores a tool result as its own row (type toolResult / role toolResult);
                    # the 2026-11-16 audit found this by counting 0 errors across 11k calls, which
                    # no real window produces.
                    is_err = bool(msg.get("isError") or row.get("isError"))
                    text = " ".join(str(c.get("text", "")) for c in msg.get("content") or []
                                    if isinstance(c, dict)) or str(msg.get("content") or "")
                    head = text.lstrip().splitlines()[0] if text.strip() else ""
                    if is_err or ERROR.match(head):
                        errors += 1
                        tool = msg.get("toolName") or row.get("toolName") or "?"
                        sigs[f"{tool}: {shrink(text)}"] = sigs.get(f"{tool}: {shrink(text)}", 0) + 1
                    continue
                for blk in msg.get("content") or []:
                    if isinstance(blk, dict) and blk.get("type") == "toolCall":
                        calls += 1
    out = {"files": len(files), "mb": total / 1e6, "asks": asks, "calls": calls, "errors": errors,
           "top_errors": sorted(sigs.items(), key=lambda kv: -kv[1])[:5]}
    if fast:
        return out
    rc, raw = run(["python3", str(MINE), "--since", time.strftime("%Y-%m-%dT%H:%M",
                                                                time.gmtime(since)), "--json"], 300)
    if rc == 0:
        try:
            mine = json.loads(raw)
        except ValueError:
            mine = {}
        out["repeated_asks"] = [(r["count"], r["text"][:70]) for r in mine.get("repeated_asks", [])[:3]]
        out["corrections"] = len(mine.get("corrections", []))
        out["gaps"] = [g["text"][:90] for g in mine.get("gaps", [])[:2]]
        out["long_chains"] = [(s["id"][:8], s["tool_calls"]) for s in
                              sorted(mine.get("sessions", []), key=lambda s: -s["tool_calls"])[:3]]
    else:
        out["mine"] = f"miner failed: {raw.strip()[:120]}"
    return out


def money_section(days: float) -> dict:
    """Local only: pi-burn --drivers (session logs), --cap (settings vs logs), burn/log.jsonl."""
    out: dict = {}
    rc, text = run([str(AGENT / "bin" / "pi-burn"), "--drivers", str(max(1, round(days)))], 300)
    if rc == 0:
        m = re.search(r"= \$([\d.]+)/day", text)
        out["per_day"] = float(m.group(1)) if m else None
        bands = re.findall(r"^\s*([<>0-9k\-]+)\s+\$?([\d.]+)\s+([\d.]+)%", text, re.M)
        out["bands"] = [(b[0].strip(), float(b[2])) for b in bands][:5]
        top = re.findall(r"^\s*([\d.]+)\s+([\d.]+)% (/.*)$", text, re.M)
        out["top_sessions"] = [(float(t[1]), t[2].split("/")[-1][:44]) for t in top[:3]]
    else:
        out["drivers"] = text.strip()[:140]
    # the decision numbers (recent rate, runway) from the same log, offline: --json would sample
    # the provider, and an audit must not spend money to measure money.
    rc, text = run([str(AGENT / "bin" / "pi-burn"), "--report"], 60)
    if rc == 0:
        try:
            rep = json.loads(text)
            out["per_day_recent"] = rep.get("per_day_recent")
            out["per_day_window"] = rep.get("per_day")
            out["runway_days"] = rep.get("runway_days")
        except ValueError:
            pass
    cap_days = max(1, math.ceil(days))          # one window for the number and for the share
    out["cap_days"] = cap_days
    rc, text = run([str(AGENT / "bin" / "pi-burn"), "--cap", str(cap_days)], 300,
                   env={"PI_BURN_JSON": "1"})
    for line in text.splitlines():
        if line.startswith("JSON "):
            try:
                out["cap"] = json.loads(line[5:])
            except ValueError:
                pass
    if "cap" not in out:
        # a failed instrument is an *error*, never a `fail`: putting the traceback in `fail` made
        # "pi-burn could not run" read as "the ceiling is not in force".
        last = (text.strip().splitlines() or ["no output"])[-1][:140]
        out["cap"] = {"error": last if rc else "no JSON from --cap", "unverified": True,
                      "fail": []}
        out["error"] = f"cap: {out['cap']['error']}"
    try:
        last, bad = None, 0
        for line in BURN.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                float(row.get("remaining") or 0)
            except (ValueError, TypeError):
                bad += 1
                continue
            last = row
        if last:
            out["balance"] = round(float(last.get("remaining") or 0), 2)
            out["credited"] = round(float(last.get("credited") or 0), 2)
            out["today"] = round(float(last.get("daily") or 0), 2)
            out["burn_sample_age_h"] = round(
                (time.time() - when(last.get("ts"))) / 3600, 1)
        out["burn_bad_lines"] = bad
    except OSError:
        out["burn_log"] = "unreadable"
    return out


EMPTY_SCHEDULE = {"fails": [], "dead": [], "badcfg": [], "dense": [], "na": [], "off": [],
                  "artifact": []}


def schedule_section() -> dict:
    rc, text = run([str(AGENT / "bin" / "pi-cadence"), "--json"], 180)
    try:
        data = json.loads(text[text.index("{"):])
    except (ValueError, TypeError):
        # the caller indexes these keys, so an error path that returns only {"error": …} used to
        # traceback — the pack then claimed "suspects found" (rc 1) instead of "could not read".
        return {**EMPTY_SCHEDULE, "error": (text.strip().splitlines() or ["no output"])[-1][:160]}
    rows = data.get("rows", [])
    out = {k: list(v) for k, v in EMPTY_SCHEDULE.items()}
    for r in rows:
        ident = r["id"]
        if r.get("fail"):
            (out["dead"] if r.get("dead") else out["fails"]).append(
                f"{ident} {r.get('cadence')} {r.get('ratio') or 0:.2f}x n={r.get('n')}")
        if r["state"] == "BADCFG":
            out["badcfg"].append(ident)
        if r.get("dense") and r["state"] != "dense":
            out["dense"].append(ident)
        if r["state"] == "n/a":
            out["na"].append(ident)
        if not r.get("enabled"):
            out["off"].append(ident)
        # the 2026-11-16 artefact: a bimodal gap distribution makes the median disagree with the
        # rate. If median/every > 1.3 while mean/every <= 1.2, the row is fine and the *statistic*
        # was the problem — worth knowing before "fixing" a row again.
        if r.get("n") and r.get("ratio") and r["ratio"] <= 1.2 and r.get("med"):
            med_ratio = (r["med"] / r["every"]) if r.get("every") else 0
            if med_ratio > 1.3:
                out["artifact"].append(f"{ident} median {med_ratio:.2f}x vs mean {r['ratio']:.2f}x")
    return out


def guards_section(fast: bool) -> dict:
    if fast:
        return {"skipped": "--fast"}
    rc, text = run([str(AGENT / "bin" / "pi-preflight")], 600)
    return {"rc": rc, "error": (text.strip().splitlines() or ["no output"])[-1][:140]
            if rc not in (0, 1) else None,
            "fails": [l[5:].strip() for l in text.splitlines() if l.startswith("FAIL ")],
            "warns": [l[5:].strip()[:120] for l in text.splitlines() if l.startswith("warn ")]}


def delegation_section() -> dict:
    rc, text = run([str(AGENT / "bin" / "pi-delegate"), "flow"], 120)
    out = {"flow": re.sub(r"\s+", " ", text)[:400] if rc == 0 else text[:160]}
    m = re.search(r"dispatches (\d+) \| verified (\d+).*?unverified (\d+)", text)
    if m:
        out.update(dispatches=int(m.group(1)), verified=int(m.group(2)),
                   unverified=int(m.group(3)))
    roster = {p.stem for p in (AGENT / "agents").glob("*.md")}
    used = set(re.findall(r"^\s*(\w+)\s+n=", text, re.M))
    # on failure `used` is empty and every agent looked never-dispatched, which fired a
    # false suspect — the roster question is only answerable from a flow report that ran.
    out["never_dispatched"] = sorted(roster - used) if rc == 0 else []
    if rc != 0:
        out["error"] = (text.strip().splitlines() or ["no output"])[-1][:140]
    out["$"] = None
    m = re.search(r"cost \$([\d.]+)", text)
    if m:
        out["$"] = float(m.group(1))
    return out


def tasks_section(since: float) -> dict:
    out: dict = {}
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        q = lambda sql, *a: c.execute(sql, a).fetchone()[0]
        out.update(created=q("select count(*) from tasks where created>=?", since),
                   done=q("select count(*) from tasks where status='done' and updated>=?", since),
                   open=q("select count(*) from tasks where status in ('open','doing')"),
                   p1_open=q("select count(*) from tasks where status in ('open','doing') and priority=1"),
                   stale_p1=[f"#{r[0]} {r[1][:70]}" for r in c.execute(
                       "select id,title from tasks where status in ('open','doing') and priority=1"
                       " and created<=? order by created", (time.time() - 3 * 86400,))])
        out["top_open"] = [f"#{r[0]} p{r[1]} {r[2][:64]}" for r in c.execute(
            "select id,priority,title from tasks where status in ('open','doing')"
            " order by priority,created desc limit 6")]
    except sqlite3.Error as exc:
        out["error"] = f"agenda.db: {exc}"
    return out


def when(ts) -> float:
    """Parse a log timestamp with its offset; `mktime` on a trailing-Z string was an hour off
    under DST and five hours off in a fixture TZ."""
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        try:
            return float(time.mktime(time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S")))
        except (ValueError, TypeError):
            return 0.0


def memory_section() -> dict:
    rc, text = run([str(AGENT / "bin" / "mem"), "brief"], 120)
    m = re.search(r"budget ~(\d+)/(\d+)", text)
    drops = re.findall(r"^## (.+?) (\d+)/(\d+)$", text, re.M)
    pinned = re.search(r"budget too small for (\d+) pinned", text)
    return {"used": int(m.group(1)) if m else None, "budget": int(m.group(2)) if m else None,
            "drops": [f"{n} {k}/{t}" for n, k, t in drops],
            "pinned_dropped": int(pinned.group(1)) if pinned else 0}


def repo_section(since: float) -> dict:
    rc, text = run(["git", "-C", str(AGENT), "status", "--short"], 60)
    lines = [l for l in text.splitlines() if l.strip()]
    gen = ("agenda/schedule.json", "self-funding/", "selfimprove/review.md", "percolation/")
    # prefix, not substring: `my-percolation/real.py` is not a generated path
    real = [l for l in lines if not any(l[3:].lstrip().startswith(g) for g in gen)]
    size = sum(p.stat().st_size for p in SESSIONS.glob("*/*.jsonl"))
    return {"modified": len(real), "examples": [l[:70] for l in real[:6]], "sessions_gb": size / 1e9}


def suite_section() -> dict:
    """How much of the eval suite is actually covered at k>=3 (the ceiling question)."""
    path = AGENT / "selfimprove" / "ledger.jsonl"
    try:
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return {"error": "no selfimprove ledger"}
    tasks = set()
    for r in rows:
        for t in r.get("tasks") or []:
            tasks.add(t)
        if r.get("n") and r.get("reps") and r["reps"] >= 3:
            tasks.add(r.get("tag") or r.get("arm"))
    total, covered, last_base = 0, set(), None
    last_model = last_k = None
    try:
        spec = json.loads((AGENT / "selfimprove" / "suite" / "suite.json").read_text())
        ids = [t["id"] for t in spec.get("tasks") or []]
        total = len(ids)
        # coverage is what the last base run actually executed (pi-review's rule: a subset run must
        # not be scored against today's suite size)
        # A local-model run is a batch-target measurement, not this harness's baseline: the ledger's
        # last row on 2026-11-19 was qwen2.5-1.5b 0/6 (by design) and the report read "last base
        # 0.0" — the same class as #239, a number read off the wrong run.
        base = [r for r in rows if r.get("arm") == "base"]
        hosted = [r for r in base if (r.get("model_provider") or "") != "local"]
        if hosted or base:
            last = (hosted or base)[-1]
            last_base = last.get("pass_rate")
            last_model = (last.get("model_resolved") or "?").split("/")[-1][:28]
            last_k = last.get("reps")
            rp = (AGENT / "selfimprove" / "runs" / f"{last['stamp']}-{last['arm']}"
                  / "result.json")
            covered = {r["id"] for r in json.loads(rp.read_text()).get("results", [])}
            covered &= set(ids)
    except Exception:
        pass
    return {"suite_tasks": total, "covered_tags": len(covered) or len(tasks),
            "last_base": last_base, "last_model": last_model, "last_k": last_k}


# ------------------------------------------------------------------ the pack
def scan(args) -> int:
    since = last_window() if args.since in (None, "last", "auto") else parse_when(args.since)
    now = time.time()
    days = max((now - since) / 86400, 0.1)
    s = sessions_section(since, args.fast)
    money = money_section(days)
    sched = schedule_section()
    guards = guards_section(args.fast)
    deleg = delegation_section()
    tasks = tasks_section(since)
    mem = memory_section()
    repo = repo_section(since)
    suite = suite_section()

    suspects: list[str] = []
    # an unreadable instrument is a suspect of its own: silence must never look like health
    for name, sec in (("cadence", sched), ("delegation", deleg), ("tasks", tasks),
                      ("money", money)):
        if sec.get("error"):
            suspects.append(f"instrument:{name}-unreadable")
    if guards.get("rc") not in (0, 1, None):
        suspects.append("instrument:guard-unrun")
    if money.get("burn_bad_lines"):
        suspects.append("instrument:burn-log")
    for ident in sched["fails"] + sched["dead"] + sched["badcfg"]:
        suspects.append(f"cadence:{ident.split()[0]}")
    if sched["artifact"]:
        suspects.append("cadence:statistic-artifact")
    cap = money.get("cap") or {}
    if cap.get("fail"):
        suspects.append("cost:ceiling-not-in-force")
    if cap.get("above_cost") and money.get("per_day"):
        share = cap["above_cost"] / money.get("cap_days", days or 1)
        if share > 0.5 * money["per_day"]:
            suspects.append("cost:band-above-ceiling")
    if guards.get("fails"):
        suspects.extend(f"guard:{f.split()[0]}" for f in guards["fails"])
    # Only a *pinned* rule that did not fit is a defect: `mem brief` exits 1 for it and preflight
    # gates publish. Ordinary section trimming at a fixed budget is the allocator doing its job —
    # treating "4 of 10 lessons shown" as a suspect made every audit re-open it (2026-11-20).
    if mem.get("pinned_dropped"):
        suspects.append("memory:pinned-dropped")
    if deleg.get("unverified"):
        suspects.append("delegation:unverified")
    if deleg.get("never_dispatched"):
        suspects.append("delegation:unused-roster")
    if repo.get("modified"):
        suspects.append("repo:dirty")
    if suite.get("suite_tasks") and suite.get("covered_tags", 0) < suite["suite_tasks"]:
        suspects.append("suite:coverage")
    if s.get("top_errors") and s["top_errors"][0][1] >= 3:
        suspects.append(f"friction:{s['top_errors'][0][0].split(':')[0]}")
    if s.get("repeated_asks"):
        suspects.append("friction:repeated-ask")

    print(f"# Audit evidence pack — window {hum(now - since)} "
          f"({time.strftime('%Y-%m-%d %H:%M', time.localtime(since))} → now)")
    print(f"# generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))} · days {days:.1f}")
    print(f"\n## SESSIONS {s['files']} file(s), {s['mb']:.0f} MB, {s['asks']} asks, "
          f"{s['calls']} tool calls, {s['errors']} errors")
    for sig, n in s.get("top_errors") or []:
        print(f"  {n:>4}x {sig[:100]}")
    for n, text in s.get("repeated_asks") or []:
        print(f"  repeated ask {n}x: {text}")
    if s.get("corrections"):
        print(f"  corrections: {s['corrections']} · gaps: {len(s.get('gaps') or [])}")
    for cid, calls in s.get("long_chains") or []:
        print(f"  long chain {cid}: {calls} calls")
    fmt = lambda v: f"{v:.2f}" if isinstance(v, (int, float)) else "?"
    print(f"\n## MONEY  ${fmt(money.get('per_day_recent') or money.get('per_day'))}/day recent"
          f" · ${fmt(money.get('per_day'))}/day window"
          f" · balance ${money.get('balance', '?')}/${money.get('credited', '?')}"
          f" · today ${money.get('today', '?')}"
          f" · runway {money.get('runway_days', '?')}d"
          f" · sample {money.get('burn_sample_age_h', '?')}h old")
    for band, share in money.get("bands") or []:
        print(f"  context band {band:<10} {share:5.1f}% of spend")
    for share, name in money.get("top_sessions") or []:
        print(f"  top session {share:5.1f}% {name}")
    if cap:
        print(f"  ceiling {cap.get('ceiling', 0):,} · above {cap.get('above_calls', 0)} call(s) "
              f"${cap.get('above_cost', 0):.2f} · compactions {cap.get('compactions', 0)}"
              + (" · UNVERIFIED" if cap.get("unverified") else ""))
        for f in cap.get("fail") or []:
            print(f"  CAP FAIL {f}")
    print(f"\n## SCHEDULE  {len(sched.get('fails', []))} fail · {len(sched.get('dead', []))} dead"
          f" · {len(sched.get('na', []))} n/a · {len(sched.get('dense', []))} dense"
          f" · {len(sched.get('off', []))} off")
    for k in ("fails", "dead", "badcfg", "artifact", "dense", "na", "off"):
        if sched.get(k):
            print(f"  {k}: {', '.join(sched[k])}")
    print(f"\n## GUARDS  preflight rc={guards.get('rc', '-')}"
          + (f" ({guards['skipped']})" if guards.get("skipped") else ""))
    for f in guards.get("fails") or []:
        print(f"  FAIL {f}")
    for w in (guards.get("warns") or [])[:4]:
        print(f"  warn {w}")
    print(f"\n## DELEGATION  dispatches {deleg.get('dispatches', '?')} · verified "
          f"{deleg.get('verified', '?')} · unverified {deleg.get('unverified', '?')} · "
          f"${deleg.get('$', '?')}")
    if deleg.get("never_dispatched"):
        print(f"  never dispatched: {', '.join(deleg['never_dispatched'])}")
    print(f"\n## TASKS  created {tasks.get('created', '?')} · done {tasks.get('done', '?')} · "
          f"open {tasks.get('open', '?')} (p1 {tasks.get('p1_open', '?')})"
          + (f"  UNREADABLE: {tasks['error']}" if tasks.get("error") else ""))
    for t in (tasks.get("stale_p1") or [])[:3]:
        print(f"  stale p1 {t}")
    for t in (tasks.get("top_open") or [])[:4]:
        print(f"  open {t}")
    if sched.get("error"):
        print(f"\n  SCHEDULE UNREADABLE: {sched['error']}")
    if deleg.get("error"):
        print(f"  DELEGATION UNREADABLE: {deleg['error']}")
    if money.get("burn_bad_lines"):
        print(f"  MONEY: {money['burn_bad_lines']} unparsable line(s) in burn/log.jsonl")
    print(f"\n## MEMORY  brief {mem.get('used', '?')}/{mem.get('budget', '?')} tok"
          + (f" · pinned dropped {mem['pinned_dropped']}" if mem.get("pinned_dropped") else "")
          + (f" · cut: {', '.join(mem.get('drops') or [])}" if mem.get("drops") else ""))
    print(f"\n## REPO  {repo.get('modified', '?')} uncommitted path(s) outside generated files · "
          f"sessions {repo.get('sessions_gb', 0):.2f} GB")
    for e in repo.get("examples") or []:
        print(f"  {e}")
    print(f"\n## SUITE  {suite.get('covered_tags', '?')}/{suite.get('suite_tasks', '?')} tasks "
          f"covered at k>=3 · last base {suite.get('last_base', '?')}"
          + (f" ({suite['last_model']}, k={suite['last_k']})"
             if suite.get("last_model") else ""))
    print(f"\n## SUSPECTS ({len(suspects)})")
    for x in suspects:
        print(f"  - {x}")
    print("\n## NEXT (the audit itself)")
    print("  1. for each suspect: is the instrument wrong or the system? name the command that")
    print("     decides it, then run that command, not a hunch")
    print("  2. rank findings by money first; the default-if-silent cost of the top one is the")
    print("     audit's justification")
    print("  3. debate the contested ones (agents/debator, FOR and AGAINST on two model families),")
    print("     dispatch a tester per fix (disjoint lenses from lenses.json), then close the loop")
    print("     with: window.py close --findings N --fixed N --spend USD --notes \"...\"")

    if args.record:
        append_ledger({"event": "scan", "ts": now, "window_start": since, "window_end": now,
                       "hours": round((now - since) / 3600, 1), "suspects": suspects,
                       "sessions": s["files"], "spend_per_day": money.get("per_day"),
                       "balance": money.get("balance")})
        print(f"\n(recorded: {LEDGER.relative_to(AGENT)})")
    return 1 if suspects else 0


def close(args) -> int:
    """Close the loop: the Study step. Without this the ledger cannot improve anything."""
    rows, bad = read_ledger()
    if bad:
        print(f"window.py: {bad} unparsable ledger line(s) skipped", file=sys.stderr)
    if not any(r.get("event", "scan") == "scan" for r in rows):
        print("window.py: no scan recorded — run `scan --record` first", file=sys.stderr)
        return 2
    if args.fixed > args.findings:
        print(f"window.py: --fixed {args.fixed} > --findings {args.findings} is not a measurement",
              file=sys.stderr)
        return 2
    lenses = {}
    for item in args.lens or []:
        for part in item.split(","):
            if not part.strip():
                continue
            if "=" not in part:
                print(f"window.py: --lens {part!r} needs name=count", file=sys.stderr)
                return 2
            name, n = part.rsplit("=", 1)
            try:
                lenses[name.strip()] = int(n)
            except ValueError:
                print(f"window.py: --lens {part!r}: {n!r} is not a count", file=sys.stderr)
                return 2
    append_ledger({"event": "close", "ts": time.time(), "findings": args.findings,
                   "fixed": args.fixed, "spend": args.spend, "lenses": lenses,
                   "notes": args.notes or ""})
    print(f"closed: {args.findings} finding(s), {args.fixed} fixed, ${args.spend:.2f}"
          + (f", lenses {lenses}" if lenses else ""))
    return 0


def score(args) -> int:
    """Yield per run, repeat suspects, and the cadence/lens rules — the self-improving part."""
    rows, bad = read_ledger()
    if not rows:
        print("window.py: no ledger yet — the first `scan --record` starts it")
        return 0
    if bad:
        print(f"window.py: {bad} unparsable ledger line(s) skipped", file=sys.stderr)
    scans = [r for r in rows if r.get("event", "scan") == "scan"]
    closes = [r for r in rows if r.get("event") == "close"]
    lens_yield: dict[str, list[int]] = {}
    for c in closes:
        for name, n in (c.get("lenses") or {}).items():
            lens_yield.setdefault(name, []).append(n)
    print(f"runs {len(scans)} · closed {len(closes)}")
    # A repeat is a suspect that survives *two scans*, whether or not the first was closed —
    # pairing only closed scans made the rule unobservable on the (common) run that ships nothing.
    prev_scan: set[str] | None = None
    for s in scans:
        cur = set(s.get("suspects") or [])
        rep = sorted(cur & prev_scan) if prev_scan is not None else []
        mark = f" · REPEAT {', '.join(rep)}" if rep else ""
        print(f"  scan {time.strftime('%m-%d %H:%M', time.localtime(s.get('ts') or 0))} "
              f"window {s.get('hours', 0):5.1f}h · suspects {len(cur):2d}{mark}")
        prev_scan = cur
    pairs, last_scan = [], None
    for r in rows:
        if r.get("event", "scan") == "scan":
            last_scan = r
        elif r.get("event") == "close" and last_scan:
            pairs.append((last_scan, r))
    for s, c in pairs:
        per = (c.get("spend") or 0) / (c.get("fixed") or 1)
        print(f"  close {time.strftime('%m-%d %H:%M', time.localtime(c.get('ts') or 0))} "
              f"findings {c.get('findings', 0)} · fixed {c.get('fixed', 0)} · "
              f"${c.get('spend', 0):.2f} · ${per:.2f}/fix")
    if pairs:
        cost = sum(c.get("spend") or 0 for _, c in pairs)
        fixed = sum(c.get("fixed") or 0 for _, c in pairs)
        per = cost / fixed if fixed else float("inf")
        print(f"\nyield ${per:.2f}/fixed finding over {int(fixed)} fix(es)")
        # the cadence rule reads the last two runs, not the lifetime average: an audit that paid
        # for itself three runs ago does not justify a fourth run that ships nothing.
        last_two = pairs[-2:]
        if len(last_two) == 2 and not any(c.get("fixed") for _, c in last_two):
            print("cadence rule: two consecutive runs with no fixed finding — lengthen the row to "
                  "14d or widen the window")
        elif len(last_two) == 2:
            recent = sum(c.get("fixed") or 0 for _, c in last_two) / 2
            spend = sum(c.get("spend") or 0 for _, c in last_two) / 2
            rper = spend / recent if recent else float("inf")
            print(f"cadence rule: last two runs averaged {recent:.1f} fix(es) at ${rper:.2f}/fix — "
                  + ("lengthen to 14d" if rper > 6 else "keep 7d"))
        else:
            print(f"cadence rule: one run so far (${per:.2f}/fix) — the rule needs two")
    if lens_yield:
        print("\nlens yield (findings per dispatch)")
        retired, promote = [], []
        path = LENSES
        if path.exists() and not path.is_file():
            print(f"window.py: {path} is not a file — not writing lens state", file=sys.stderr)
            return 2
        try:
            state = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(state, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            # overwriting a corrupt roster with {"retire":…} silently deleted the lens list
            print(f"window.py: {path} is unreadable ({exc}) — fix it, not the score", file=sys.stderr)
            return 2
        for name, vals in sorted(lens_yield.items()):
            print(f"  {name:<22} {vals}")
            if len(vals) >= 2 and sum(vals[-2:]) == 0:
                retired.append(name)
            elif vals and vals[-1] >= 2:
                promote.append(name)
        state["retire"] = sorted(set(state.get("retire") or []) | set(retired))
        state["double"] = promote
        tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(state, indent=1) + "\n")
        os.replace(tmp, path)
        if retired:
            print(f"retire (0 findings twice): {', '.join(retired)}")
        if promote:
            print(f"dispatch twice next run: {', '.join(promote)}")
    return 0


def selftest() -> int:
    """Prove the boundary cases that the 2026-11-16 tester panel found — in-process, no network.

    Each case is a defect that shipped once: a crash that exited 1 (indistinguishable from
    "suspects found"), a truncated ledger that erased itself, a failed instrument that read as a
    real finding, and a lens roster that a corrupt read silently replaced.
    """
    import tempfile
    global LEDGER, LENSES, run, AGENT
    real = (LEDGER, LENSES, run, AGENT)
    fails: list[str] = []
    ran: list[str] = []

    def check(name: str, got, want) -> None:
        ran.append(name)
        ok = got == want if not callable(want) else want(got)
        print(f"selftest {name}: {got!r}" + ("" if ok else f" (want {want!r})") + ("" if ok else " FAIL"))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "bin").mkdir()
        for b in ("pi-burn", "pi-cadence", "pi-preflight", "pi-delegate"):
            (t / "bin" / b).write_text("#!/bin/sh\n")
        (t / "mem").symlink_to(AGENT / "bin" / "mem")
        AGENT, LEDGER = t, t / "ledger.jsonl"
        LENSES = t / "lenses.json"
        global SESSIONS, BURN, DB
        real_paths = (SESSIONS, BURN, DB)
        SESSIONS = t / "sessions"
        SESSIONS.mkdir()
        BURN, DB = t / "burn.jsonl", t / "agenda.db"

        # 1. a truncated tail does not erase the ledger, and the next record does not join it
        LEDGER.write_text('{"event":"scan","ts":1,"window_end":1}\n{"event":"scan","ts":17')
        rows, bad = read_ledger()
        check("truncated-line-is-counted", (len(rows), bad), (1, 1))
        append_ledger({"event": "scan", "ts": 2})
        rows, bad = read_ledger()
        check("append-after-truncation", (len(rows), bad), (2, 1))

        # 2. a future window_end cannot swallow the next window
        LEDGER.write_text(json.dumps({"event": "scan", "ts": 1, "window_end": time.time() + 1e9}) + "\n")
        check("future-window-ignored", last_window() < time.time() - 3600, True)

        # 3. time parsing refuses what used to traceback or lie
        for bad_t in ("2026", "7", "0", "NaN", "inf", "1e400", "2099-01-01"):
            try:
                parse_when(bad_t)
                check(f"refuse-{bad_t}", "accepted", "refused")
            except SystemExit:
                check(f"refuse-{bad_t}", "refused", "refused")
        check("accept-7d", abs(parse_when("7d") - (time.time() - 604800)) < 5, True)

        # 4. a stubbed instrument that cannot answer must not crash the pack or look healthy
        outputs = {"pi-cadence": (125, "cadence: locked"),
                   "pi-burn": (1, "burn: no settings"),
                   "pi-delegate": (125, "timeout"),
                   "pi-preflight": (125, "timed out")}

        def fake_run(cmd, timeout=0, env=None):
            name = os.path.basename(str(cmd[0]))
            if name == "mem":
                return 0, "## CORE 1/1\nSTATS 1 memories (0 archived), budget ~10/100 tok"
            return outputs.get(name, (0, ""))

        run = fake_run
        sched = schedule_section()
        check("schedule-error-has-keys", sorted(sched), sorted([*EMPTY_SCHEDULE, "error"]))
        deleg = delegation_section()
        check("delegation-failure-no-roster-claim", (deleg["never_dispatched"], bool(deleg["error"])),
              ([], True))
        money = money_section(1.0)
        check("cap-failure-is-error-not-fail", (money["cap"]["fail"], money["cap"].get("error")),
              ([], "burn: no settings"))
        check("guards-timeout-not-green",
              (guards_section(False)["rc"], guards_section(False)["error"]), (125, "timed out"))

        # 5. scan itself survives all four, and says which instrument it could not read
        # run the real scan() with four unreadable instruments: it must not crash, must exit 1
        # (suspects, not a crash), and must name each instrument it could not read
        import io
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = scan(argparse.Namespace(since="1h", fast=True, record=False, json=False))
        except Exception as exc:  # a crash here is the defect the tester found
            rc, buf = f"crash {type(exc).__name__}: {exc}", io.StringIO()
        finally:
            sys.stdout = old
        pack = buf.getvalue()
        check("scan-exit-1-on-suspects", rc, 1)
        check("scan-names-unreadable",
              sorted(x for x in ("instrument:cadence-unreadable",
                                 "instrument:delegation-unreadable",
                                 "instrument:money-unreadable",
                                 "instrument:tasks-unreadable") if x in pack),
              ["instrument:cadence-unreadable", "instrument:delegation-unreadable",
               "instrument:money-unreadable", "instrument:tasks-unreadable"])
        # a guard that cannot run is a suspect too — but only the non-fast path calls it
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            scan(argparse.Namespace(since="1h", fast=False, record=False, json=False))
        finally:
            sys.stdout = old
        check("scan-flags-a-guard-that-cannot-run", "instrument:guard-unrun" in buf.getvalue(), True)

        # 6. score: REPEAT across two unclosed scans; cadence rule needs two runs
        LEDGER.write_text("".join(json.dumps(r) + "\n" for r in [
            {"event": "scan", "ts": 50, "hours": 24, "suspects": ["suite:coverage"]},
            {"event": "scan", "ts": 60, "hours": 24, "suspects": ["suite:coverage"]},
            {"event": "scan", "ts": 100, "hours": 24, "suspects": ["repo:dirty"]},
            {"event": "scan", "ts": 200, "hours": 24, "suspects": ["repo:dirty", "cost:x"]},
            {"event": "close", "ts": 210, "findings": 1, "fixed": 0, "spend": 1.0,
             "lenses": {"tester/x": 1}},
            {"event": "scan", "ts": 300, "hours": 24, "suspects": ["repo:dirty"]},
            {"event": "close", "ts": 310, "findings": 0, "fixed": 0, "spend": 1.0, "lenses": {}},
        ]))
        import io
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = score(None)
        finally:
            sys.stdout = old
        text = buf.getvalue()
        # the verifier's point: the fixture used to close every scan, so the REPEAT string could
        # come from any pair. Assert the line that must carry it (two adjacent, unclosed scans).
        line60 = next((l for l in text.splitlines() if "scan " in l and "06-30" not in l
                       and "suite:coverage" not in l), "")
        check("score-repeat-on-second-unclosed-scan",
              any("REPEAT suite:coverage" in l for l in text.splitlines()), True)
        check("score-repeat-fires", "REPEAT repo:dirty" in text, True)
        check("score-two-run-rule", "two consecutive runs with no fixed finding" in text, True)
        check("score-rc", rc, 0)

        # 7. a corrupt lens roster is refused, not overwritten
        LENSES.write_text('{"lenses": {"tester/x": "y"}, broken')
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = score(None)
        finally:
            sys.stdout = old
        check("corrupt-lenses-refused", (rc, LENSES.read_text().endswith("broken")), (2, True))
        LENSES.write_text(json.dumps({"note": "n", "lenses": {"tester/x": "y"}}))
        sys.stdout = io.StringIO()
        try:
            score(None)
        finally:
            sys.stdout = old
        state = json.loads(LENSES.read_text())
        check("lenses-preserved", state.get("note") == "n" and "tester/x" in state.get("lenses", {}),
              True)

        # 8. close refuses an orphan close and an impossible measurement
        LEDGER.write_text(json.dumps({"event": "close", "ts": 1}) + "\n")
        check("close-needs-scan", close(argparse.Namespace(findings=1, fixed=0, spend=0.0,
                                                          lens=None, notes="")), 2)
        LEDGER.write_text(json.dumps({"event": "scan", "ts": 1, "window_end": time.time()}) + "\n")
        check("close-refuses-fixed-gt-findings",
              close(argparse.Namespace(findings=1, fixed=2, spend=0.0, lens=None, notes="")), 2)
        check("close-refuses-bad-lens",
              close(argparse.Namespace(findings=1, fixed=0, spend=0.0, lens=["x=abc"], notes="")), 2)

    LEDGER, LENSES, run, AGENT = real
    SESSIONS, BURN, DB = real_paths
    # a file that lost its cases would otherwise pass trivially (the verifier found this)
    if len(ran) < 22:
        fails.append(f"only {len(ran)} cases ran")
    print(f"selftest: {len(ran)} case(s) " + ("FAIL " + ", ".join(fails) if fails else "ok"))
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="window.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="the evidence pack")
    s.add_argument("--since", default=None, help="last (default), 7d, 2026-11-15[THH:MM], epoch")
    s.add_argument("--fast", action="store_true", help="skip pi-preflight and the session miner")
    s.add_argument("--record", action="store_true", help="append this run to the ledger")
    c = sub.add_parser("close", help="record what the audit found and did")
    c.add_argument("--findings", type=int, required=True)
    c.add_argument("--fixed", type=int, default=0)
    c.add_argument("--spend", type=float, default=0.0, help="this audit's own cost in USD")
    c.add_argument("--lens", action="append", help="name=findings, e.g. tester/boundaries=2")
    c.add_argument("--notes", default="")
    sub.add_parser("score", help="yield, repeats and the cadence/lens rules")
    sub.add_parser("selftest", help="re-prove the boundary cases a tester panel found")
    a = p.parse_args(argv)
    try:
        if a.cmd == "close":
            return close(a)
        if a.cmd == "score":
            return score(a)
        if a.cmd == "selftest":
            return selftest()
        return scan(a)
    except SystemExit:
        raise
    except Exception as exc:  # never exit 1 on a crash: 1 means "suspects found"
        print(f"window.py: could not produce an honest answer: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
