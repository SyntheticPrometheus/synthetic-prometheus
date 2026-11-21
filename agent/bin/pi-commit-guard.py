#!/usr/bin/env python3
"""pi-commit-guard — refuse a commit that stages a secret-shaped string.

Guard for the 2026-11-14 incident (auth.json + memory journal committed with `git add -A`).
That guard lived only at publish time, so a new secret file with a different name would still
be committed. This runs at the earliest point instead: `git commit` via .git/hooks/pre-commit.

  pi-commit-guard            scan `git diff --cached` (added lines only), exit 1 on a hit
  pi-commit-guard --install  write the pre-commit hook (idempotent)

Also refuses: merge-conflict markers in any staged file, and a staged `vendor/` tree that
`bin/pi-skills verify` rejects. Guard for the 2026-11-14 incident in which a parallel session's
`git add -A` committed another session's half-finished skill edits and a protocol draft.

Shapes are imported from bin/pi-publish (SECRETS), so there is one list, not two.
Bypass deliberately, never habitually: `git commit --no-verify`.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
HOOK = AGENT / ".git" / "hooks" / "pre-commit"
HOOK_BODY = """#!/bin/sh
# managed by bin/pi-commit-guard.py --install (secret-shaped string => refuse commit)
exec python3 "$(dirname "$0")/../../bin/pi-commit-guard.py"
"""

# fallback if pi-publish cannot be imported (kept in sync by hand; preflight compares them)
FALLBACK = [
    (r"sk-[A-Za-z0-9_-]{20,}", "openai-style key"),
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "github token"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "github fine-grained token"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "slack token"),
    (r"AKIA[0-9A-Z]{16}", "aws key id"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][A-Za-z0-9/+=_-]{12,}['\"]", "inline credential"),
    # a leaked ntfy topic = a public publish right for the text channel (#117, task #220)
    (r"ntfy\.sh/[A-Za-z0-9_-]{12,}", "ntfy topic URL"),
    (r"\bpi-[0-9a-f]{24}\b", "ntfy topic name"),
]

# paths that must never be staged at all, whatever their contents
FORBIDDEN = ["auth.json", "models-store.json", "memory/journal/", "memory/memory.db", "sessions/",
             "delegation/ledger.jsonl", ".pi-claim", "claims/", "claim-log.jsonl"]


def secrets():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("pipublish", AGENT / "bin" / "pi-publish")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SECRETS
    except Exception:
        return FALLBACK


def staged():
    """(path, added-line) pairs for everything in the index."""
    out = subprocess.run(["git", "-C", str(AGENT), "diff", "--cached", "--unified=0",
                          "--no-color", "--no-ext-diff", "--diff-filter=ACMR"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None, out.stderr.strip() or "git diff failed"
    path, pairs = None, []
    for line in out.stdout.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if path:
                pairs.append((path, line[1:]))
    return pairs, None


CONFLICT_MARK = re.compile(r"^(<{7} |={7}$|>{7} )", re.M)

# `TOPIC_SECRET = "pi/text-topic"` is a *pass entry name*, not a secret: the value it names is
# retrieved by pi-secret at run time. The generic inline-credential pattern cannot tell the two
# apart, so the name form gets an exemption (measured 2026-11-15: it refused bin/pi-text for
# defining TOPIC_SECRET/TG_SECRET). A real credential never looks like a `pi/` path.
PASS_ENTRY = re.compile(r"""(?i)(api[_-]?key|secret|password)\s*[:=]\s*['"]pi/[a-z0-9._/-]{2,}['"]""")


def names_a_pass_entry(line: str) -> bool:
    return bool(PASS_ENTRY.search(line))
VENDOR_TOOL = AGENT / "bin" / "pi-skills"


def staged_files():
    out = subprocess.run(["git", "-C", str(AGENT), "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                         capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l.strip()] if out.returncode == 0 else []


def content_problems(paths):
    problems = []
    for rel in paths:
        f = AGENT / rel
        if not f.is_file() or f.stat().st_size > 2_000_000:
            continue
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        if CONFLICT_MARK.search(text):
            problems.append(f"{rel}: staged with merge-conflict markers (half-resolved merge)")
    if any(p.startswith("vendor/") for p in paths) and VENDOR_TOOL.exists():
        # one implementation, not two: the vendored pack's own verifier decides
        r = subprocess.run([str(VENDOR_TOOL), "verify"], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            first = next((l for l in (r.stdout or "").splitlines() if l.startswith("FAIL")), "verify failed")
            problems.append(f"vendor/: pi-skills verify says {first.strip()}")
    return problems


def claims(root: Path):
    """Refuse when a staged path is owned by another live session, or edited by one right now.

    Guests for two failures: `git add -A` swept a parallel session's half-finished files into an
    unrelated commit, and two sessions edited the same file. Leases (`bin/pi-claim`) cover sessions
    that cooperate; the session-log check covers the ones that do not, because every session writes
    its own edit/write calls to disk.
    """
    tool = AGENT / "bin" / "pi-claim"
    if not tool.exists():
        return []
    r = subprocess.run([str(tool), "guard", "--staged"], cwd=str(root),
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        return []
    lines = [l.strip() for l in (r.stderr or "").splitlines() if l.strip()]
    return lines[:6] or ["another session owns or is editing a staged path"]


def main():
    if "--install" in sys.argv:
        HOOK.parent.mkdir(parents=True, exist_ok=True)
        HOOK.write_text(HOOK_BODY)
        HOOK.chmod(0o755)
        print(f"installed {HOOK}")
        return 0
    pairs, err = staged()
    if pairs is None:
        print(f"pi-commit-guard: skipped ({err})", file=sys.stderr)
        return 0
    problems = content_problems(staged_files())
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                               text=True).stdout.strip() or str(AGENT))
    problems.extend(claims(root))
    for path, line in pairs:
        if any(path == f or path.startswith(f) for f in FORBIDDEN):
            problems.append(f"{path}: path is never committable (see .gitignore)")
        if names_a_pass_entry(line):
            continue        # the line names a pass entry; the secret itself lives in `pass`
        for pat, label in secrets():
            if re.search(pat, line):
                problems.append(f"{path}: added line looks like a {label}")
    if problems:
        print("pi-commit-guard: REFUSING this commit\n", file=sys.stderr)
        for p in dict.fromkeys(problems):
            print(f"  - {p}", file=sys.stderr)
        hints = []
        if any("pi-secret" in p or "looks like" in p or "never committable" in p for p in problems):
            hints.append("move the value into pi-secret and unstage the file")
        if any("conflict markers" in p for p in problems):
            hints.append("resolve the markers (pi-skills resolve) or unstage the file")
        if any("pi-skills verify" in p for p in problems):
            hints.append("run bin/pi-skills verify, register the edit in upstream/LOCAL-CHANGES.md")
        if any("REFUSED" in p or "owns" in p for p in problems):
            hints.append("unstage the other session's paths (git restore --staged PATH) and commit "
                         "only yours; see CONCURRENCY.md")
        print("\nFix: " + ("; ".join(hints) or "unstage the offending files") +
              ". Deliberate override: git commit --no-verify", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
