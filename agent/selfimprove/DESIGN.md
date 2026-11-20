# Self-improving harness — design v0

Goal: make this agent's *harness* (the prose+code layer around the frozen model: `AGENTS.md`,
skills, prompt templates, tool policies, loop protocol) improve on a measured, auditable schedule —
without the loop being able to fake its own score.

Research basis: `~/.pi/agent/research/self-improving-harnesses.md` (mem #32–#40).

## Genome

A harness arm is a directory of files that pi can load: a system-prompt fragment (`arm.md`),
optionally skills/prompt templates/tool allowlist. `arm.md` is the NL harness spec of the loop
(2603.25723), so an edit is a readable diff, not a code review of a controller.

Mutation axes, in order of evidence:
1. loop protocol in `arm.md` (plan → act → **verify** → report) — RHI 2607.15524.
2. tool policy (`--tools` set, MCP on/off, Laya as a pre-filter) — SoL-Pi's action execution.
3. context/compaction rules (what gets written to disk vs held in context) — SoL-Pi, Engram 2603.21321.
4. skills / prompt templates (reusable mechanisms) — PluginRSI 2609.32423.
5. the proposer + gate thresholds themselves — Hyperagents 2603.19461 (meta-level is editable).

## Loop

```
suite (pinned)  ──run──▶  arm A (k reps)  ──▶ pass rate, tokens, wall
                        arm B (k reps)  ──▶ pass rate, tokens, wall
                                              │
                          gate.py (k-aware) ──┤ accept → arms/archive/A-vN.md + ledger + mem
                                              └ hold/reject → ledger, reason
```

Rules taken from the literature, enforced in code:
- **k≥3 per arm** before any accept; compare against a *fresh baseline rerun* in the same session
  (2610.04433: harness swaps flip ~13% of tasks, same as reruns).
- **One mechanism per candidate**, annealed budget: no bundled edits (RRSI 2609.24972).
- **Archive everything** with parent pointers, never delete an arm (DGM 2505.22954, branches 2609.37834).
- **Pinned judge**: the suite, verifiers and gate are hash-recorded in the ledger and are *outside*
  the editable set; any arm whose diff touches them is rejected automatically (2609.12216,
  2609.00069). Budget caps: max wall per task, max reps.
- **Cost is a metric**, not a footnote (SoL-Pi 2609.20519): record wall + output size per task.
- **Persistence**: every run appends to `ledger.jsonl` and to `mem`, and a run that produced no
  durable note is flagged (Engram 2603.21321: coherence lives in external state).

## Implemented protocol (v1, 2026-11-14)

| step | file | state |
|---|---|---|
| propose one mechanism (weakness mining) | `propose.py` | done — mines failures from a run, asks for <= 6 lines |
| audit before measuring (tamper check) | `audit.py` + `policy.json` | done — refuses judge-mentioning text, base-line removal, and over-budget diffs (annealed per net-accepted arm) |
| measure with k reps + cost | `run.py` | done — default `--mode json` usage capture, memory guard, cgroup cap, `--parent` lineage, `harness_rev` |
| decide | `gate.py` | done — audit first, then policy thresholds (k>=3, delta>=2, no regression); voids unequal reps, missing/duplicate rep IDs, suite drift, policy/task-selection mismatch and differing or unknown model identities; `selftest_gate.py` pins 19 cases |
| archive | `arms/archive/` + `decisions.md` | done — header names parent; DECISIONS entries are append-only |
| provenance | `git` in `~/.pi/agent` | done — harness commits, `harness_rev` recorded per run |
| maintain | `maintain.py` + weekly timer | done — integrity, research index, lineage, proposal yield, prune |
| persist | `mem` + PDSA cycles | done by hand every cycle (not automated; see open item) |

Still open (deliberately): branching/dev-subset evolution (2609.37834), a judge-based screening
layer for expensive evaluation (2609.19526), and automated run-end memory capture.

## The free half runs offline (v1.1, 2026-11-17)

Owner, 2026-11-16: "more of the self-improvement work done in the background by local models
without using cloud tokens, even if it's really slow." Measured what that can and cannot cover:

| half of the loop | who runs it | measured |
|---|---|---|
| mine failures → draft one candidate | local GGUF, `propose.py --model local/...` | 1m43s, **$0**, produced a readable 1-line edit from a 3-failure run |
| measure an arm against the suite | cloud (`pi --print`, default model) | a local run is possible (`run.py --model`) but the 1.5B scored **0/3** on accounting-sum, fix-check, stated-vs-true at 59-116 s/task — it cannot do the tasks, so a local pass rate is not a capability measurement |
| gate (k≥3, δ≥2) | cloud | unchanged; a weak model's pass rate says nothing about the harness |

So the split is **local = breadth (mining, drafting, screening), cloud = the one decision worth
paying for**. `bin/pi-selfimprove-local` is the job: it checks the router is up and the model is
loaded (a refusal, not 30 minutes of timeouts), runs the base arm on a cheap 6-task subset with
`--model local/...`, drafts a candidate from the failures, writes `local-<stamp>.md`, and exits 0
at cost $0. Agenda row `local-selfimprove` (1d, priority 3) runs it detached via `pi-done run`, so
it needs no session and no clock of mine. Pins: `tests/pi-selfimprove-local.sh` (`pi-tool check`).

Refusals are the point: the tool exits 1 with one line if the router is down, the model is not
loaded, or `run.py` fails — an offline loop that silently does nothing would look like progress.

## Full-stack safe replay (roadmap P0, 2026-11-20)

`run.py` is the mechanism experiment and stays that way: `-ne -ns -nc -np --no-mcp` deliberately
removes every layer around the arm. The deployment experiment is `replay.py`, a second family that
keeps the stack and fakes everything outside it:

| real | faked |
|---|---|
| extensions, skills, prompts, AGENTS.md, memory boot | fresh sandbox DB + a pinned canary, fake `auth.json`, scripted provider |
| tool and shell execution | disposable HOME/agent dir; `pass`, `notify-send`, `paplay`, `curl`, `wget`, `gh`, `ssh`, `pi-text`, `pi-mail`, `pi-publish` are logging refusals |
| network | `unshare -rn`, loopback plus one private address for the scripted provider; no route out |

A run is deterministic and costs $0: the provider returns a fixed answer, and the judge reads the
request the provider actually received (`prompt_contains`), the reply, the effects log, and the
canary files. `--selftest` is the acceptance test from the roadmap, measured three ways: healthy
full-stack **PASS**, the same harness with `memory-boot.ts` dropped **FAIL (missing memory canary)**,
and the arm-only invocation on that broken harness **PASS** — the blind spot reproduced. `pi-review`
now runs that selftest as its `replay` signal.

Scope, stated honestly: this family measures **harness wiring and safety contracts** (context,
skills, memory, headless notify, credential/side-effect boundaries), not model capability. A
model-driven production replay needs held-out, sanitized traces and remains agenda #308 / #267;
this is the safe substrate those tasks can run on, not a substitute for them.

## Files

- `suite/suite.json` — tasks: prompt, seeded files, verifier shell command (exit 0 = pass).
- `arms/base.md`, `arms/*.md` — harness specs.
- `run.py` — runs an arm over the suite; writes `runs/<stamp>-<arm>.json`; appends the ledger;
  `--model local/<gguf>` for a $0 run (screening only, see above).
- `bin/pi-selfimprove-local` (in `bin/`) — the offline pass: local measure + local draft, weekly/daily row.
- `replay.py` — full-stack safe replay family; `--selftest` proves it catches a dropped layer.
- `gate.py` — compares two run files under the k-aware rule; prints accept/hold/reject + reasons.
  `--min-delta`/`--k`/`--cost-win-frac` are floors (an override may tighten, never loosen), and
  `--skip-audit` needs `--diagnose`: a verdict without the tamper audit is a diagnostic, not a
  promotion (2026-11-20, roadmap G08/G09).
- `ledger.jsonl` — append-only: arm hash, parent, suite hash, reps, per-task results, decision.
- `maintain.py` — housekeeping: prune `runs/` beyond N, verify ledger chain, report drift.

## At ceiling: the cost axis (cycle 15)

Three cycles (10, 11, 12, 15) failed to find a task class where the base arm drops below 1.0; input
size, dependency depth and prose volume all collapse into "the model scripts it". A saturated suite
makes the gate unable to accept anything, so `policy.json` now carries `gate.cost_win_frac` (0.10):
when accuracy is tied at k≥3 with no regression, an arm that cuts **output** tokens by ≥10% is
accepted as `ACCEPT_COST`. It is labelled as cost, never as capability, and is re-measured next
cycle. Capability headroom must come from somewhere else — bigger inputs are not it.

## Cycle 16: authored output under many constraints (falsified, 2026-11-19)

The class was added (`release-brief`, `upgrade-brief`, suite v5): author a release brief under ~20
simultaneous stated rules — word band, banned words, section counts, id/ticket/kind
cross-references, per-kind summary numbers, self-hash. With a *fair* judge the base arm passes
6/6 at k=3; the two earlier "failures" (0/6, then 4/6) were judge defects — a quoted YAML scalar
and a trailing period the POLICY prose never showed. Replaying the saved artifacts against the
fixed judge is what proved it, and `selftest.py` now pins a third answer per fixture (`tolerant`,
an equivalent representation) that must pass, so over-strictness is caught before a run is blamed
on the arm.

Consequence: a fully specified deterministic task does not discriminate for this base model,
however many constraints it carries. Headroom has to come from a different axis — judged quality
with its own calibration, an interactive/adversarial oracle, or cost (which the gate already
accepts as ACCEPT_COST) — and a failure manufactured by tightening unstated prose is a judge
defect, not headroom.

## Review (the part that keeps it relevant)

`bin/pi-review` walks the setup, not the metrics: AGENTS.md size/dangling refs, suite saturation and
evidence age, unverified delegation share and dead roster entries, brief budget ratio, guard/timer
health, skill frontmatter, publish attempt age, stale PDSA cycles. It writes `review.md`, exits 1 on
a hard failure, runs weekly (`pi-review.timer`) and `pi-preflight` fails when the review is >10 days
old. Metrics catch a system that degrades; the review catches one that stopped mattering.

## Snapshot boundaries (what a reader can and cannot reproduce)

Published: `agent/selfimprove/` (suite, fixtures, runner, gate, proposal + audit, maintain, the
design and decision log) and the allowlisted harness around it. The snapshot is a working personal
harness, not an installer.

- **Environment tested:** Arch Linux, Python ≥ 3.11 (the gate and tests are stdlib-only), Pi ≥ 1.5.
  The external review ran `selftest_gate.py` and `maintain.py --check` on Python 3.13/Windows and
  both passed; model runs were not exercised there.
- **Minimal checks that need no model:**
  `python3 agent/selfimprove/selftest_gate.py` (19 gate cases) and
  `python3 agent/selfimprove/maintain.py --check` (suite hash, ledger chain, archive completeness).
- **Needs a model:** `run.py --arm arms/base.md --tasks <id> --reps 3` (spends tokens; `--model
  local/<gguf>` makes it $0 when a local router is configured).
- **Deliberately unpublished:** session logs, memory DB/journal, delegation ledger, research caches,
  `auth.json`, the local-model router and Laya weights. The runner loads only what the suite names,
  so their absence affects the arms, not the gate's arithmetic.
- **A pair to inspect the gate with:** fabricate two result files (the helper in `selftest_gate.py`
  shows every required field) and run `gate.py base.json cand.json --diagnose --skip-audit`; a
  perfect-vs-perfect unequal-rep pair must print `VOID`, not `ACCEPT`.

At a saturated suite the order is deliberate: an equal-pass pair with a reproducible output-token
win prints `ACCEPT_COST` (efficiency only, never capability); the `UNINFORMATIVE` hold applies only
when there is no cost win. Before 2026-11-20 the ceiling check ran first and made `ACCEPT_COST`
unreachable there, contradicting this file and `policy.json` v2.

## Maintenance (the part that keeps it alive)

- `maintain.py --check` after every session that mutates the genome; exits non-zero if the suite
  hash drifted, the ledger chain is broken, or an accepted arm is missing from `arms/archive/`.
- Weekly: `mem consolidate --digest`, and re-read this design's PDSA cycle. Scheduled by a
  systemd --user timer (`selfimprove-maintain.timer`), no LLM calls, so it costs nothing.
- Any accepted arm must land in `AGENTS.md`/`skills/` only via a human-visible diff in git. The
  agent dir is a git repo (that is the harness history this snapshot is cut from); `harness_rev`
  records its HEAD per run, so a ledger row can always be traced to the tree that produced it.
