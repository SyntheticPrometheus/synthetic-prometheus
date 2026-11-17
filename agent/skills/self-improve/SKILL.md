---
name: self-improve
description: Run and maintain the measured self-improvement loop over this agent's own harness — propose a harness variant, evaluate it against the pinned suite with k repeats, gate it, record the decision and lineage. Use when changing AGENTS.md, skills, prompt templates, tool policy or loop protocol and you want evidence rather than opinion, and when checking that research and memories are still persistent and indexed.
---

# Self-improve — the harness loop

Research base: `~/.pi/agent/research/self-improving-harnesses.md` (mem #32–#40). Design:
`~/.pi/agent/selfimprove/DESIGN.md`.

The genome is the prose harness (AGENTS.md / skills / prompt templates / tool policy). The loop is
`arm → suite → gate → archive → memory`, and the loop's own proposer and thresholds are also
editable — but only through a diff, never silently.

## Run it

```bash
cd ~/.pi/agent/selfimprove
python3 run.py --arm arms/base.md --reps 3 --tag base     # baseline, fresh, same session
python3 run.py --arm arms/cand-x.md --reps 3 --tag cand   # one mechanism changed, nothing else
python3 gate.py runs/<base>/result.json runs/<cand>/result.json
python3 maintain.py --check --research                    # integrity + persistence check
```

Exit codes: 0 accept (archive the arm into `arms/archive/<name>-vN.md`, add the ledger `parent`,
record a `mem` decision), 2 hold (rerun with more reps, or the effect is too small to be worth it),
3 reject (a task regressed — no silent trade-offs).

## Rules that are not negotiable (each has a paper behind it)

- k≥3 per arm and a **fresh baseline rerun** in the same session; a single A/B flips ~13% of tasks
  by noise (2610.04433).
- One mechanism per candidate, no bundled edits (2609.24972); keep every arm with a parent pointer
  (2505.22954, 2609.37834).
- The suite, its verifiers and the gate are outside the editable set; `run.py` records their hash
  and `gate.py` refuses to compare runs across a hash change (2609.12216, 2609.00069).
- Record cost (wall per task, tokens) alongside accuracy — unattended loops die on cost (2609.20519).
- At ceiling the gate may only move on cost: `policy.json → gate.cost_win_frac` accepts an equal-pass
  arm that cuts output tokens ≥10% as `ACCEPT_COST` (never as a capability gain).
- Weekly, and before proposing anything: `bin/pi-review` (writes `selfimprove/review.md`). A FAIL
  there is the first thing to fix; `pi-preflight` refuses an action when the review is >10 days old.
- A run that produced no durable note is incomplete: append the finding to `mem` and to the open
  PDSA cycle (2603.21321: coherence lives in external state, not in a context window).

## Which knob to turn first

1. loop protocol (`verify before claiming`, `write the artifact then re-read it`) — cheapest, RHI 2607.15524;
2. tool policy (`--tools`, MCP on/off, Laya as pre-filter) — SoL-Pi action-execution axis;
3. context/compaction rules (what goes to disk vs context);
4. skills / templates as reusable mechanisms — PluginRSI 2609.32423.

## Known state (2026-11-16)

Suite is 15 tasks. The hard class was added 2026-11-14 (semantic-shards, chain-40, join-60 — long
context, 40-module chain, 60-row join) and base passed all 9 at k=3, so difficulty did not buy
headroom. 12 tasks remain uncovered, which is why `bin/pi-review` no longer prints "saturated" from
a subset run: it reports coverage (`9/9 on 3/15`). `cand-verify` 9/9 at +27% wall → HOLD.

Next in order of proof, not preference: (1) cover the remaining tasks at k≥3 — until then the
ceiling is unproven; (2) if still 1.00, only a cost arm can move the gate (`ACCEPT_COST`, ≥10%
fewer output tokens); (3) a new task class that base *fails* is an owner decision, not a loop edit.
