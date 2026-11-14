# Incidents and their guards

Rule: **every failure gets a guard, not just a fix.** An entry is closed only when the guard is
something that runs (a check, a test, a refusal) or a rule that is loaded every session. A fix
without a guard is a promise, and promises are what failed the first time.

Format: what happened → root cause → guard → where the guard lives.

## 2026-11-14 — auth.json and the memory journal were committed to git

- **What**: the first provenance commit in `~/.pi/agent` tracked `auth.json` (an OpenRouter key) and
  `memory/journal/*.jsonl` (private chat content).
- **Cause**: `git add -A` with a `.gitignore` that listed directories but not secrets.
- **Guard**: history deleted and re-initialised; `.gitignore` now names every secret path; the
  publish path uses an **allowlist** (not a denylist) and greps the snapshot for key shapes and for
  the machine name before any push.
- **Lives in**: `~/.pi/agent/.gitignore`, `bin/pi-publish` (`scan()`), `bin/pi-preflight`.

## 2026-11-14 — global OOM killed the X session

- **What**: concurrent eval runs + Laya resident (2.8 GB) + torch exhausted 7.8 GB; the kernel killed
  dconf/pipewire/gvfs/dbus-broker and the session died.
- **Cause**: no cgroup limit on the eval children, and a 2.8 GB model preloaded for every session.
- **Guard**: `run.py` refuses to start below 1200 MB `MemAvailable` and wraps each `pi` call in
  `systemd-run --user --scope -p MemoryMax=2500M`; Laya is `LAYA_PRELOAD=0`.
- **Lives in**: `selfimprove/run.py`, `mcp.json`.

## 2026-11-14 — three judge defects in the self-improvement suite

- **What**: the verifier expected 1467 (true 1567); it counted only the literal token `5xx` and
  dropped a `500` line; the `spec-10` expected file said `cache: true` where the spec implies false.
  In all three the agent was right and the judge was wrong.
- **Cause**: hand-written expected values, never tested against a known-good answer.
- **Guard**: `selftest.py` must show a known-good answer PASSES and a known-bad answer FAILS for
  every task before any arm runs; the suite hash is pinned in the ledger; `gate.py` voids
  cross-hash comparisons; judge-owned `verify_files` are rewritten after the arm runs.
- **Lives in**: `selfimprove/selftest.py`, `gate.py`, `run.py`.

## 2026-11-14 — GitHub signup blocked as bot activity

- **What**: signup returned "unusual activity" (ID 3b334e10…, IP 96.255.73.39).
- **Cause**: a browser launched from a script (`setsid firefox --new-window …/signup`) plus a burst
  of unauthenticated `api.github.com` calls.
- **Guard**: never automate signup/login, never launch a browser at an auth flow, keep unauthenticated
  API traffic low; signup flows are driven one action at a time with a human available for the
  challenge.
- **Lives in**: `AGENTS.md` (publishing section), `PUBLISHING.md`, `RUNBOOK-accounts.md`.

## 2026-11-14 — xdotool clicks silently missed for 20 minutes

- **What**: pointer clicks did nothing on a page where keyboard worked; the "I agree" button looked
  enabled and was not in the tab order.
- **Cause**: `xdotool mousemove --window` uses the window's **frame** origin while `import -window`
  captures the **client** area — a 28px offset, 12px after `xfwm4 --replace`.
- **Guard**: calibrate the offset with one harmless click before a sequence, or use Tab+Enter; if
  clicks stop working, suspect the offset before clicking harder.
- **Lives in**: `AGENTS.md` (automation note), memory #71.

## 2026-11-14 — publish pushed a duplicate snapshot and failed on a rejected ref

- **What**: the weekly unit rebuilt the tree, counted all 58 files as changed, and the push was
  rejected (`fetch first`).
- **Cause**: no baseline snapshot to diff against, and no rebase path.
- **Guard**: `publish/last` stores the last pushed tree; a rejected push rebases once and retries;
  the unit is gated on `publish/enabled` so an unauthenticated machine produces no failed units.
- **Lives in**: `bin/pi-publish`.

## 2026-11-14 — a harness change was accepted on a single task and then reverted

- **What**: `cand-verify` won +2 on 2 tasks at k=6, then lost 3/3 on `long-reports` at k=3 on the
  full suite.
- **Cause**: one task dominated the aggregate, and the effect was run noise.
- **Guard**: k≥3 with a fresh baseline, no per-task regression, Δ≥2, and a per-task breakdown printed
  by the gate; a change that trades one class for another is a reject.
- **Lives in**: `selfimprove/gate.py`, `policy.json`, `decisions.md`.

## 2026-11-14 — the publish repo silently stopped publishing (three bugs in a row)

- **What**: `pi-publish --push` printed "pushed" while the remote stayed on the old commit; later a
  push failed with "origin does not appear to be a git repository"; the top-level README and
  PUBLISHING.md vanished from the snapshot.
- **Causes**, in the order they were found:
  1. `render()` did `rmtree(DST)`, which deleted the snapshot repo's `.git` — so every run
     re-initialised a repo with no remote, and `git` fell through to the parent repo.
  2. The reject path used `git pull --rebase`, which conflicts on a snapshot repo (every file is
     "added" on both sides) and left the repo stuck mid-rebase; the next push then no-ops.
  3. `README.md`/`LICENSE`/`PUBLISHING.md` were written *after* `render()`, so the reject path's
     re-render wiped them.
- **Guards**: `render()` preserves `.git` and writes README/LICENSE/PUBLISHING itself; a stuck
  rebase is aborted at start; a rejected push does `fetch` + `reset --hard origin/main` + re-render
  + commit (never rebase); the local branch is forced to `main`; `pi-preflight` now checks that the
  snapshot has README/LICENSE/PUBLISHING, that a remote exists, and that no rebase is in progress.
- **Lives in**: `bin/pi-publish`, `bin/pi-preflight`.
