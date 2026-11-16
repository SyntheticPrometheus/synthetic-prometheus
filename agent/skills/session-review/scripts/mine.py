#!/usr/bin/env python3
"""mine.py — extract friction signals from pi session logs.

Reads ~/.pi/agent/sessions/*/*.jsonl and prints a compact markdown report:
sessions, repeated asks, user corrections, assistant capability gaps, tool
errors, and long tool chains. It is a *finder*, not a judge: the model reading
the report decides which signal is a missing skill, a protocol, a memory row,
or nothing.

Usage:
  mine.py [--since 24h|YYYY-MM-DD|all] [--cwd SUBSTR] [--out FILE] [--json]
          [--max-text N] [--max-items N]

Exit codes: 0 ok, 2 no sessions found / bad argument.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SESSIONS = Path.home() / ".pi" / "agent" / "sessions"
MAX_TEXT = 280
MAX_ITEMS = 12

# Phrases that usually precede a correction or a capability gap. Curated, not
# learned: false positives are cheap because the model reads the context.
CORRECTION = re.compile(
    r"\b(?:please continue|i can'?t|i cant|did you|why did you|you didn'?t|"
    r"that'?s not|not what|i meant|i said|actually|hold on|stop|wait|"
    r"no,|wrong|instead|you pushed|you forgot|you missed|again)\b",
    re.I,
)
GAP = re.compile(
    r"\b(?:i can'?t|i cannot|i don'?t have|i do not have|no access|not able|"
    r"unable to|cannot browse|can'?t browse|no browser|no api|"
    r"bot[- ]?wall|credential[- ]?wall|last resort|blocked by|"
    r"requires? (?:a )?(?:browser|human)|not available here)\b",
    re.I,
)
ERROR = re.compile(
    r"^(?:error\b|failed\b|exception\b|traceback\b|timed out\b|"
    r"permission denied\b|no such file\b|not found\b|exit code [1-9]\b|"
    r"command not found\b|connection refused\b|status 4\d\d\b|status 5\d\d\b)",
    re.I,
)


def text_of(content) -> str:
    """Flatten a message content value to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    out.append(str(b.get("text", "")))
                elif b.get("type") == "thinking":
                    continue
                elif b.get("text"):
                    out.append(str(b.get("text", "")))
            elif isinstance(b, str):
                out.append(b)
        return "\n".join(out)
    return ""


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> set[str]:
    return {t for t in norm(s).split() if len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cutoff(since: str) -> float:
    now = dt.datetime.now().timestamp()
    if since == "all":
        return 0.0
    m = re.fullmatch(r"(\d+)([hd])", since)
    if m:
        n = int(m.group(1))
        return now - n * (3600 if m.group(2) == "h" else 86400)
    try:
        d = dt.date.fromisoformat(since)
        return dt.datetime.combine(d, dt.time.min).timestamp()
    except ValueError:
        raise SystemExit(f"mine.py: bad --since {since!r} (use 24h, 7d, YYYY-MM-DD or all)")


def clip(s: str, n: int = MAX_TEXT) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def read_session(path: Path) -> dict:
    meta = {"id": path.stem, "cwd": "?", "started": None, "path": str(path)}
    users, assistant, tools, errors = [], [], [], []
    for line in path.open(errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") == "session":
            meta["id"] = o.get("id") or meta["id"]
            meta["cwd"] = o.get("cwd") or meta["cwd"]
            meta["started"] = o.get("timestamp") or meta["started"]
            continue
        if o.get("type") not in ("message", "toolResult"):
            continue
        m = o.get("message") or {}
        role = m.get("role") or o.get("role")
        if role == "user":
            t = text_of(m.get("content") if "content" in m else o.get("content"))
            if t.strip():
                users.append(clip(t))
        elif role == "assistant":
            c = m.get("content") or []
            if isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text"):
                        assistant.append(clip(str(b["text"])))
                    elif b.get("type") == "toolCall":
                        tools.append({"name": b.get("name", "?"), "args": b.get("arguments") or {}})
        elif role == "toolResult":
            t = text_of(m.get("content") if "content" in m else o.get("content"))
            is_err = bool(m.get("isError") or o.get("isError"))
            head = t.lstrip().splitlines()[0] if t.strip() else ""
            if is_err or ERROR.match(head):
                errors.append({"tool": m.get("toolName") or o.get("toolName") or "?", "text": clip(t)})
    return {
        "meta": meta,
        "users": users,
        "assistant": assistant,
        "tools": tools,
        "errors": errors,
    }


def find_sessions(since: str, cwd_filter: str | None) -> list[dict]:
    if not SESSIONS.exists():
        return []
    cut = cutoff(since)
    rows = []
    for p in sorted(SESSIONS.glob("*/*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if mtime < cut:
            continue
        row = read_session(p)
        row["mtime"] = mtime
        if cwd_filter and cwd_filter not in row["meta"]["cwd"]:
            continue
        rows.append(row)
    return rows


def repeated_asks(rows: list[dict]) -> list[dict]:
    """Group user asks by exact normalized text, then by token Jaccard >= 0.75."""
    items = []
    for r in rows:
        for u in r["users"]:
            items.append({"text": u, "norm": norm(u), "tokens": tokens(u), "session": r["meta"]["id"]})
    groups: list[dict] = []
    for it in items:
        placed = False
        for g in groups:
            if g["norm"] == it["norm"] or jaccard(g["tokens"], it["tokens"]) >= 0.75:
                g["items"].append(it)
                g["sessions"].add(it["session"])
                placed = True
                break
        if not placed:
            groups.append({"norm": it["norm"], "tokens": it["tokens"], "items": [it], "sessions": {it["session"]}})
    out = []
    for g in groups:
        if len(g["items"]) >= 2:
            out.append({
                "count": len(g["items"]),
                "sessions": len(g["sessions"]),
                "text": g["items"][0]["text"],
                "all": [i["text"] for i in g["items"]],
            })
    out.sort(key=lambda g: (-g["sessions"], -g["count"]))
    return out


def main() -> int:
    global MAX_TEXT, MAX_ITEMS
    ap = argparse.ArgumentParser(description="mine pi session logs for friction signals")
    ap.add_argument("--since", default="24h", help="24h, 7d, YYYY-MM-DD or all (default 24h)")
    ap.add_argument("--cwd", default=None, help="only sessions whose cwd contains this substring")
    ap.add_argument("--out", default=None, help="write the report here instead of stdout")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    ap.add_argument("--max-text", type=int, default=MAX_TEXT)
    ap.add_argument("--max-items", type=int, default=MAX_ITEMS)
    args = ap.parse_args()

    MAX_TEXT, MAX_ITEMS = args.max_text, args.max_items

    rows = find_sessions(args.since, args.cwd)
    if not rows:
        print("mine.py: no sessions matched", file=sys.stderr)
        return 2

    rep = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "since": args.since,
        "sessions": [],
        "repeated_asks": repeated_asks(rows),
        "corrections": [],
        "gaps": [],
        "errors": [],
        "long_chains": [],
    }

    for r in rows:
        meta = r["meta"]
        rep["sessions"].append({
            "id": meta["id"],
            "cwd": meta["cwd"],
            "started": meta["started"],
            "mtime": dt.datetime.fromtimestamp(r["mtime"]).isoformat(timespec="seconds"),
            "user_asks": len(r["users"]),
            "tool_calls": len(r["tools"]),
            "errors": len(r["errors"]),
            "last": r["assistant"][-1] if r["assistant"] else "",
        })
        for u in r["users"]:
            if CORRECTION.search(u):
                rep["corrections"].append({"session": meta["id"], "text": u})
        for a in r["assistant"]:
            if GAP.search(a):
                rep["gaps"].append({"session": meta["id"], "text": a})
        for e in r["errors"]:
            rep["errors"].append({"session": meta["id"], **e})
        if len(r["tools"]) >= 25:
            c = Counter(t["name"] for t in r["tools"])
            rep["long_chains"].append({
                "session": meta["id"],
                "tool_calls": len(r["tools"]),
                "top": c.most_common(5),
            })

    # keep the report readable
    for k in ("corrections", "gaps", "errors"):
        rep[k] = rep[k][: args.max_items]
    rep["long_chains"].sort(key=lambda x: -x["tool_calls"])

    if args.json:
        out = json.dumps(rep, indent=2)
    else:
        L = []
        L.append(f"# Session friction report — {rep['generated']} (since {args.since})")
        L.append("")
        L.append("## Sessions scanned")
        for s in rep["sessions"]:
            L.append(f"- `{s['id']}` — {s['cwd']} — {s['user_asks']} asks, {s['tool_calls']} tool calls, {s['errors']} errors")
            if s["last"]:
                L.append(f"  - last: {clip(s['last'], 180)}")
        L.append("")
        L.append("## Repeated asks (>=2 occurrences)")
        if not rep["repeated_asks"]:
            L.append("- none")
        for g in rep["repeated_asks"]:
            L.append(f"- **{g['count']}× / {g['sessions']} sessions**: {clip(g['text'])}")
            for t in g["all"][1:]:
                L.append(f"  - variant: {clip(t, 180)}")
        L.append("")
        L.append("## User corrections / friction markers")
        if not rep["corrections"]:
            L.append("- none")
        for c in rep["corrections"]:
            L.append(f"- `{c['session']}`: {c['text']}")
        L.append("")
        L.append("## Assistant capability-gap phrases")
        if not rep["gaps"]:
            L.append("- none")
        for g in rep["gaps"]:
            L.append(f"- `{g['session']}`: {g['text']}")
        L.append("")
        L.append("## Tool errors")
        if not rep["errors"]:
            L.append("- none")
        for e in rep["errors"]:
            L.append(f"- `{e['session']}` {e['tool']}: {e['text']}")
        L.append("")
        L.append("## Long tool chains (>=25 calls)")
        if not rep["long_chains"]:
            L.append("- none")
        for c in rep["long_chains"]:
            L.append(f"- `{c['session']}` — {c['tool_calls']} calls; top: {', '.join(f'{n} {k}' for n, k in c['top'])}")
        L.append("")
        L.append("## Next")
        L.append("For each signal, decide: skill / protocol / memory row / prompt / extension / nothing. A skill")
        L.append("is justified only when the workflow repeats and is not already covered by a doc or a bin tool.")
        out = "\n".join(L)

    if args.out:
        Path(args.out).write_text(out + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
