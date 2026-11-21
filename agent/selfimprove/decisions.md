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

## 2026-11-14 — Cycle 15: headroom by input size (falsified) → cost axis in the gate

- hypothesis: heavy context pressure (60 prose records ≈ 110 KB, 40 dependent edits, a 4-file CSV
  reconciliation) would drop base below 1.0 and give the gate something to accept.
- measured: base **9/9** at k=3 (semantic-shards 3/3 at 21–34k tokens_in; chain-40 3/3; join-60 3/3
  in ~5 s). Suite is now 15 tasks and still saturated. Third falsification of "bigger input creates
  discrimination" (cycles 10, 11, 12 were the first two) — the base arm either reads the input or
  writes a script, and a script is a fold.
- kept anyway: the three tasks are a floor for weaker arms and cost ~$0.03/run to keep honest.
- protocol change that follows: at ceiling, `gate.py` now reads `gate.cost_win_frac` (0.10) from
  `policy.json`, so an equal-pass arm that cuts output tokens ≥10% at k≥3 with no regression is
  accepted as **ACCEPT_COST** — explicitly not a capability gain. Without this the loop cannot act
  on anything while the suite is saturated.
- next hypothesis (cycle 16, not yet run): headroom comes from *authored output under many
  simultaneous constraints*, or from probing an opaque oracle — not from larger inputs.

## 2026-11-14 — Review pass: the harness now audits its own relevance weekly

- `bin/pi-review` scores nine signals that metrics alone miss: AGENTS.md size and dangling
  references, suite saturation and evidence age, unverified delegation share and dead roster
  entries, brief budget ratio and consolidation age, preflight + incident guards, timer health,
  skill frontmatter, publish attempt age, stale PDSA cycles. It writes `selfimprove/review.md` and
  exits 1 on a hard failure; `pi-review.timer` runs it weekly and `pi-preflight` fails when the
  review is older than 10 days, so the reflection cannot silently stop.
- First run found two real things: 58% of delegation rows had no verdict, and 12/12 suite
  saturation. Both now have executable signals instead of my memory.
- `pi-delegate expire --days 7` marks dispatches nobody can judge any more as `expired`, so the
  unverified share measures what is still actionable rather than warning forever.

## 2026-11-17 — Second review pass: the gate refuses silences, not just bad numbers

- External review (issue #1, second comment) executed three fabricated pairs against the published
  gate and got ACCEPT on each. All three were real: `--allow-subset` only held when the flag was
  *absent*, balanced row counts accepted duplicate `rep` IDs, and a model change was credited to
  the arm. Fixed in `gate.py`; `selftest_gate.py` is now 19 cases (was 10), all pinned and run by
  `maintain.py --check`.
- Rule that follows from the review, now in code: **a comparison the gate cannot verify is a HOLD,
  never an ACCEPT with a caveat.** Subset pairs print per-task detail and stop (the flag buys
  diagnosis, not a verdict); repetition IDs must be exactly 1..k; a differing or unknown resolved
  model identity cannot promote. `run.py` now records the provider-reported model identity
  (`provider`/`model`/`responseModel`) rather than the `--model` argument, so the gate compares what
  answered, not what was asked for.
- Resource contract is loaded, not hardcoded: `run.py` reads `policy.json`'s `run` section (wall
  bound, memory guard/cap, verifier timeout). The verifier subprocess is bounded and a timeout is
  recorded as `budget_exceeded`, separate from a task failure. `max_cost_per_task_usd` is labelled
  a post-run acceptance limit, not a spending cap.
- Still open (filed, not silently agreed): fresh confirmation variants after a proposal is frozen,
  and a hidden/seeded task family. A saturated suite plus 3 reps is a screening floor, not proof.

## 2026-11-19 — Cycle 16: authored-output headroom (falsified), and two judge defects

Hypothesis (the one cycle 15 left open): headroom comes from *authored output under many
simultaneous constraints*, not from bigger inputs. Class `authored-brief` added as two tasks
(`release-brief`, `upgrade-brief`, suite v5): the arm must author `RELEASE_NOTES.md` +
`release.json` from `changes.csv` under ~20 stated rules at once — word band, banned words,
per-section heading counts, id/ticket/kind cross-references, per-kind summary numbers, section
order, and a self-hash of the body. Inputs, verifier and a known-good answer are generated by
`suite/fixtures/_brief.py`; the bad answer is the good one with a banned word copied verbatim.

Measured, in three passes (base arm, k=3 on both tasks, $0.032 / $0.030 / $0.068):

1. 4/6 — the two failures were `version: "4.2"` vs `version: 4.2`. YAML quoting is the same
   string. **Judge defect**, not an arm failure.
2. 0/6 — every run failed the summary line on a trailing period that POLICY's prose template
   never showed. **Judge defect**, same class (the arm was right, the judge was literal).
3. After fixing both — replaying the *same saved artifacts* against the final judge: **6/6 PASS**.
   A fresh k=3 run under the final suite hash confirms it in the ledger.

Verdict: the class saturates too, with a fair judge. This is the fourth falsification of
"more/denser work creates discrimination" (cycles 10, 11, 12, 15, now 16). The base model is
compliant enough to satisfy ~20 simultaneous explicit constraints in one pass, so any
deterministic, fully-specified task can be scripted or simply followed. Manufacturing a failure
here would mean tightening prose the judge does not state — which is the judge-defect factory
this log already names three times.

Kept anyway: the two tasks are a floor for weaker arms and a real authored-compliance test; they
cost ~$0.07/run, the most expensive pair in the suite.

Guards added, both executable:
- POLICY now prints the literal expected summary line, produced by the same expression the
  verifier uses, and carries no punctuation trap; `selftest.py` pins the two together.
- `selftest.py` now runs a **third** answer per fixture: `tolerant` — an equivalent
  representation of the correct answer (quoted YAML scalars here). It must PASS. A judge that
  fails an equivalent answer is over-strict by definition, and this is the exact defect that
  produced two spurious "base failures" today. `fixtures.selftest_answers` returns it.

## 2026-11-20 — gate hardening: override floors, audit on the release path, cost win at ceiling

Input: external roadmap (`Synthetic_Prometheus_Self_Improvement_Engineering_Roadmap.md`, 2026-11-19,
reviewed against `main` d0ac58a). Phase 0 of that document: fix release-safety failures in the
existing Python gate before any Rust rewrite. Three of its P0 findings reproduced on this host:

1. `--min-delta 0` accepted a +1-task arm (`ACCEPT: +1 tasks`) against a policy floor of 2.
2. `--skip-audit` let a candidate verdict skip `audit.py`; nothing separated that from promotion.
3. base 3/3 vs cand 3/3 with output tokens 100 -> 10 printed `HOLD: UNINFORMATIVE` — the ceiling
   branch returned before `ACCEPT_COST`, so the cost axis `policy.json` v2 describes was unreachable
   exactly where it was meant to apply.

Fixed in `gate.py` (no policy change, so `policy_sha` is unchanged: 21b2705c563bea5b):
- `--min-delta` and `--cost-win-frac` are floored at `policy.json` values: an override may raise the
  bar for one comparison, never lower it (same rule `--k` already had).
- `--skip-audit` now requires `--diagnose`; without it the gate prints `REFUSE` and exits 1. The
  release path therefore always runs the tamper audit.
- the cost-only branch runs before the ceiling hold: equal pass + reproducible output-token win =>
  `ACCEPT_COST` (efficiency, never capability); `UNINFORMATIVE` only when there is no cost win.

Evidence: `selftest_gate.py` 25/25 before, **29/29 after** (4 new cases: min-delta floor, skip-audit
without diagnose, cost-frac floor, default-path audit refusal; case 25 flipped from HOLD to
ACCEPT_COST). `selftest.py` judge suite unchanged (17 tasks, good/tolerant/bad all classified).
Still open from the roadmap and filed as agenda tasks: full-stack replay (arm-only runs are not a
production measurement), a frozen evaluation contract with held-out post-freeze tasks, execution
isolation, and the Rust validator/pure gate. None of those is claimed as done here.

## 2026-11-20 — Full-stack safe replay: the arm-only blind spot is now measured

Roadmap P0 said `run.py` is not a production-harness measurement. Built `replay.py` +
`suite/replay.json`: the real extensions/skills/prompts/AGENTS.md/memory boot, a fresh sandbox DB,
fake credentials, logging refusals for pass/notify-send/curl/gh/pi-text, a scripted non-loopback
provider (so local-slim does not strip the stack), and `unshare -rn` with only loopback plus one
private address. Judge reads the provider request, reply, effects log and canary files.

Measured, `python3 selfimprove/replay.py --selftest`:
- healthy full-stack **PASS**;
- same harness with `memory-boot.ts` dropped **FAIL: missing context REPLAY_CANARY_MEMORY_7f3c**;
- arm-only invocation (`-ne -ns -nc -np --no-mcp`) on that broken harness **PASS** — the regression
  is invisible to the current suite, which is exactly the roadmap's completion evidence.

`replay.py` full family: 2/2 PASS (~0.9 s/task). `pi-review` runs the selftest as the `replay`
signal; `tests/pi-selfimprove-replay.sh` pins the three observations and is byte-identical across
two runs. Scope: wiring/safety contracts, not model capability; model-driven replay stays #308/#267.

## 2026-11-21 — Issue #1 finding 3 closed for real: group kill, per-task cost label, pinned

The 2026-11-17 commit loaded `policy.json`'s `run` section and bounded the verifier by timeout, but
two halves of the finding were still prose: `subprocess.run(timeout=)` kills only the pid it started,
so pi's bash-tool grandchildren and the verifier's children outlived the run; and
`max_cost_per_task_usd` appeared only in the record header, so no task was ever labelled.

What changed: both the agent and the verifier now run through `run_bounded()` — own session
(`start_new_session=True`), and on timeout `os.killpg(SIGKILL)` then a reap, so nothing survives.
Every task carries `budget` (any of wall/verifier/memory/cost), `cost_usd`, `cost_over_limit`;
`budget_exceeded` keeps its old meaning (the run did not finish), and a cost overrun is the separate
post-run label the policy calls for. `run_policy()` is a function, not an inline read, so a test can
point it at an edited file.

Measured: `selftest_run.py` 5/5 (policy loaded, edited policy changes enforcement, output/exit code
preserved, a timed-out grandchild is gone, cost labelled not capped); `maintain.py --check` runs it
next to the 29 gate cases and exits 0. End-to-end with a stub `pi`: a 0.05 USD reply under a 0.02
limit is recorded `budget:["cost"]`, `budget_exceeded:false`, `cost_over_limit:true`; a stub that
spawns `sleep 300` is recorded `budget:["wall"]` at 3.0 s and its grandchild pid answers `kill -0`
with no such process. Stub rows were removed from the ledger — a stub is not a measurement.

## 2026-11-21 — Cycle 17 (agenda #13): spec-adherence-under-bulk measured at k=3 → saturated

Class `audit-mix` + `audit-mix-2` (suite v6, added by the previous session) asks for three
numbers folded from 4.8k sparse log lines across 12 shards under seven simultaneous rules
(last-wins retries, alias resolution, literal `5xx`, tentative statuses, exclusions, s/m→ms units,
alphabetical top tie). Truth is generated from the rows, never typed.

Judge fairness, run first (`python3 selftest.py --task audit-mix{, -2}`): good→PASS,
tolerant→PASS, bad→FAIL, 0.25 s each. So a failure is the arm's, not the judge's.

Measured, base arm, k=3 on the pair, tag `cycle17-confirm`, suite_sha 2ec10874…, harness_rev
72330a2, model deepseek/deepseek-v4.1-flash-1017:

| run | pass | wall | cost |
|---|---|---|---|
| 20261120T232218 (n=3) | 1/3 | 133 s | $0.032 |
| 20261120T232453 (n=6) | 5/6 | 529 s | $0.078 |
| 20261120T233358 (n=6) | 6/6 | 349 s | $0.084 |
| **20261121T122130 (n=6)** | **6/6** | **364 s** | **$0.092** |

Per-task: audit-mix 3/3 (110/59/52 s), audit-mix-2 3/3 (36/21/85 s). The early 1/3 was the
class's only apparent headroom and it did not reproduce under a fair, unchanged judge.

Verdict: **saturated**. Fifth falsification of "denser/more-ruled work creates discrimination"
(cycles 10, 11, 12, 15, 16, now 17). The base arm scripts the fold or follows every stated rule;
the 4.8k-line, 7-rule input is not a capability edge. Kept anyway: it is the best floor in the
suite for a weaker arm and it costs $0.09/6 runs.

Agenda #13 therefore stays unmet in substance: the gate still has no capability headroom on any
of the 19 tasks. Filed as its own task (#379) the one axis that is qualitatively different from
every failed class so far: **counterfactual rule attribution** — the arm must also report what
each named rule contributes (`impact.txt`: n/ms recomputed with each of four rules disabled).
A one-pass fold answers the numbers; attribution requires re-deriving the fold four times, which
is exactly the plan→act→verify→report behaviour the loop is trying to buy.
