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
| decide | `gate.py` | done — runs the audit first, then policy thresholds (k>=3, delta>=2, no regression), intersection compare, hash + lineage printout |
| archive | `arms/archive/` + `decisions.md` | done — header names parent; DECISIONS entries are append-only |
| provenance | `git` in `~/.pi/agent` | done — harness commits, `harness_rev` recorded per run |
| maintain | `maintain.py` + weekly timer | done — integrity, research index, lineage, proposal yield, prune |
| persist | `mem` + PDSA cycles | done by hand every cycle (not automated; see open item) |

Still open (deliberately): branching/dev-subset evolution (2609.37834), a judge-based screening
layer for expensive evaluation (2609.19526), and automated run-end memory capture.

## Files

- `suite/suite.json` — tasks: prompt, seeded files, verifier shell command (exit 0 = pass).
- `arms/base.md`, `arms/*.md` — harness specs.
- `run.py` — runs an arm over the suite; writes `runs/<stamp>-<arm>.json`; appends the ledger.
- `gate.py` — compares two run files under the k-aware rule; prints accept/hold/reject + reasons.
- `ledger.jsonl` — append-only: arm hash, parent, suite hash, reps, per-task results, decision.
- `maintain.py` — housekeeping: prune `runs/` beyond N, verify ledger chain, report drift.

## At ceiling: the cost axis (cycle 15)

Three cycles (10, 11, 12, 15) failed to find a task class where the base arm drops below 1.0; input
size, dependency depth and prose volume all collapse into "the model scripts it". A saturated suite
makes the gate unable to accept anything, so `policy.json` now carries `gate.cost_win_frac` (0.10):
when accuracy is tied at k≥3 with no regression, an arm that cuts **output** tokens by ≥10% is
accepted as `ACCEPT_COST`. It is labelled as cost, never as capability, and is re-measured next
cycle. Capability headroom (cycle 16 hypothesis) must come from authored output under many
simultaneous constraints, or from probing an opaque oracle — not from bigger inputs.

## Review (the part that keeps it relevant)

`bin/pi-review` walks the setup, not the metrics: AGENTS.md size/dangling refs, suite saturation and
evidence age, unverified delegation share and dead roster entries, brief budget ratio, guard/timer
health, skill frontmatter, publish attempt age, stale PDSA cycles. It writes `review.md`, exits 1 on
a hard failure, runs weekly (`pi-review.timer`) and `pi-preflight` fails when the review is >10 days
old. Metrics catch a system that degrades; the review catches one that stopped mattering.

## Maintenance (the part that keeps it alive)

- `maintain.py --check` after every session that mutates the genome; exits non-zero if the suite
  hash drifted, the ledger chain is broken, or an accepted arm is missing from `arms/archive/`.
- Weekly: `mem consolidate --digest`, and re-read this design's PDSA cycle. Scheduled by a
  systemd --user timer (`selfimprove-maintain.timer`), no LLM calls, so it costs nothing.
- Any accepted arm must land in `AGENTS.md`/`skills/` only via a human-visible diff in git (the
  agent dir is not a repo yet; `git init` there is a pending decision — see PDSA cycle).
