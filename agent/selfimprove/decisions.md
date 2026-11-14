# Decisions (append-only)

## 2026-11-14 — ACCEPT `cand-verify` (verification-before-claiming)

- parent arm: `base`; candidate: `arms/archive/cand-verify-v1.md`
- suite: 6 tasks, k=3, judge hash pinned; judge itself was fixed twice before this run (see below)
- base 16/18 (99.6 s) → cand 18/18 (118.1 s), Δ+2, no task regressed → gate exit 0
- the whole delta is `long-reports` 1/3 → 3/3: aggregation over 5 files where the base arm
  miscounted a `500` status as not-5xx and skipped a file
- cost: +18% wall on this suite; accepted because the failure it removes is silent-wrong-answer,
  not slow-answer
- landed as the "Verify before claiming" section of `AGENTS.md`

### Judge defects found while measuring (both fixed, both recorded)

1. `accounting-sum` verifier expected 1467; the true sum is 1567. The agent was right, the judge
   was wrong.
2. `long-reports` verifier counted only the literal token `5xx`, so a `500` status line was
   excluded — the agent's 10/9600 was semantically correct. Fixed to accept 500–599.

Both are why `suite_sha` is in the ledger, `gate.py` voids cross-hash comparisons, and
`selftest.py` (good answer must pass, bad answer must fail) runs before any arm.

## 2026-11-14 — REVERT `cand-verify` (the +2 did not replicate)

- v4, k=6, 2 tasks: base 9/12 → cand 11/12 (long-reports 3/6 → 5/6) → gate ACCEPT
- v5, k=3, 8 tasks (suite extended to log-fanout + parallel-fix): base 24/24 → cand 21/24,
  long-reports 3/3 → 0/3 → gate REJECT (regression), wall 154.8 s → 288.9 s
- diagnosis: with the verification rule the arm reads "5xx" as a literal token and drops the
  `500` status line (9/8700 instead of 10/9600); without it, it reads the term semantically.
  The rule did not make the agent more correct, it made it more literal.
- action: section removed from `AGENTS.md`; arm kept in `arms/archive/` with this trail.
- lesson: one task can dominate an 8-task aggregate, and a k=6 result on 2 tasks did not survive
  a k=3 run on 8. Effects must be measured per task class, and a change that trades one class
  for another is a reject, not a win.

## 2026-11-14 — Judge hardening (no arm involved)

- `parallel-fix` verifier only checked `run_all.py` exited 0, so an arm could edit the checks it
  was told not to touch. The runner and the six `m/tN.py` checks are now `verify_files`
  (judge-owned, rewritten after the arm runs); `selftest.py` covers all 8 tasks.
- `run.py` now snapshots the suite hash at run start (`suite_sha_at_end` records a mid-run edit),
  and `gate.py` compares on the intersection of tasks when a run covers a subset.

## 2026-11-14 — Third judge defect, and the long-horizon class is saturated too

- added `chain-12` (12 modules, 3 wrong constants, spec-driven) and `spec-10` (ten dependent edits
  to one config). First base run: chain-12 3/3, spec-10 0/3 — looked like a discriminating class.
- it was the judge again: edit 9 says `cache = false if timeout_s > 100`, timeout_s is 101, so
  `false` is correct; my expected file said `true`. All three "failures" were the agent being right.
- after the fix: spec-10 3/3. The class is saturated as authored.
- tally for the day: three judge defects (arithmetic, 5xx semantics, dependent-edit logic), zero
  genuine agent failures on the final judge. The loop's most reliable output so far is judge
  hardening, not harness improvement — which is the honest reading of 2610.04433 (harness deltas
  are small) plus 2609.00069 (the judge is the attack surface).

## 2026-11-14 — Delegation is not a token win (cycle 12)

- `incident-scan` (20 narrative shards, 6 data-loss reports): base 2/2, 16090 tokens_in, 15.5 s,
  $0.0027; `deleg` 2/2, 13772 tokens_in (−14.4%), 58.1 s, $0.0069.
- `log-fanout-big` (30 shards, 90k chars): base 2/2 with 5776 tokens_in — it writes a grep/awk
  script, and a script is already a fold, so delegation has nothing to save.
- conclusion: subagent delegation is a context-window tool, not a cost tool. Keep the arms, stop
  proposing delegation as an optimisation.

## 2026-11-14 — Machine incident (not a harness change)

- 17:40:25 global OOM killed the X session (dconf/pipewire/gvfs/dbus-broker). Cause: concurrent
  eval runs + Laya resident (2.8 GB) + torch on a 7.8 GB box.
- fixes: `LAYA_PRELOAD=0`; `run.py` refuses to start below 1200 MB available and caps each pi call
  with `systemd-run --user --scope -p MemoryMax=2500M -p MemorySwapMax=1G`; autologin + tmux
  `pi-attach` so an unattended machine resumes the session.

## 2026-11-14 — Protocol v1 closed (architecture complete, evolution continues)

Done: propose → audit+policy → run (k reps, lineage, cost, memory guard) → gate (audit first,
policy thresholds) → archive+decisions → maintain (integrity, research index, lineage, yield,
prune, weekly timer) → git provenance for the whole agent dir.

Validated this session: audit refuses a judge-touching arm and a >budget arm; gate invokes the
audit before comparing; a run records parent/harness_rev/policy_sha/suite_sha/cost; maintain
passes all checks; the weekly unit runs green.

Not done on purpose (each needs a reason, not a checkbox):
- branching + evolving dev subsets (2609.37834) — premature while the suite is saturated and no
  arm has a demonstrated gain;
- judge-based screening of expensive evaluations (2609.19526) — the suite costs < $0.01/run, so a
  judge would add error, not save money;
- automatic run-end memory capture (Engram 2603.21321) — the cycle note is written by hand into
  `decisions.md` and `mem`; automating it means an LLM call per run, which the cost data does not
  justify yet.
