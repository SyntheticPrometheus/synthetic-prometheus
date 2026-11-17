# delegation/ — the measurable delegation loop

Small directory on purpose: three documents and one append-only log.

| file | role |
|---|---|
| `policy.md` | the versioned prose rules (v3). Citations to `research/ai-swarm-delegation.md` + `research/org-delegation.md` |
| `contracts.md` | copy-paste six-field contracts (scout/worker/verifier/bulker/integrator) + DoR/DoD |
| `ledger.jsonl` | append-only evidence: one row per dispatch, one row per verdict |
| `routes.jsonl` | routing decisions (regex + optional Laya) for the fit-readiness report |
| `route-eval.py` | routing benchmark: 24 tuning cases, or any held-out set via `--cases` (policy §1c) |
| `route-eval-heldout.json` + `-result.json` | 22 fresh cases + the run that promoted inkling to decider (§1c) |
| `README.md` | this file |

Related code, deliberately outside this directory so the log stays data:
- `extensions/subagent/index.ts` — in-TUI `subagent` tool (upstream pi example + local ledger patch)
- `agents/*.md` — the roster (scout, worker, verifier, bulker, integrator); frontmatter `tools:` is
  the least-privilege authorization
- `bin/pi-delegate` — `plan` / `partition` / `run` / `verdict` / `report` / `flow` for dispatches
  outside a TUI (the in-TUI path shares the same ledger)
- `bin/pi-term` — new interactive pi chat or `--exec` window: tiled on open, named, recorded,
  closed on exit; `--list` / `--close` / `--reap` are the lifecycle (policy §6b)
- `skills/delegate/SKILL.md` — the procedure the parent agent follows

## Row schema (dispatch)

```json
{"ts":"...","mode":"single|parallel|chain|cli","agent":"scout","agent_source":"user",
 "model":"~google/gemini-flash-latest","status":"completed","stop_reason":"stop",
 "bucket":["recon"],"task":"<first 200 chars>","task_sha":"<12 hex>",
 "input":11905,"output":407,"cache_read":2915,"cache_write":0,
 "context_tokens":5285,"turns":3,"cost":0.0211,"wall_ms":12000}
```

`bucket` is written by `pi-delegate` (cue classifier) and omitted by the extension; `report` then
re-derives it from `task` with the same classifier. Rows are never rewritten — a wrong row stays as
evidence and gets a `verdict` or a superseding row instead (Raw-RAG rule).

## Row schema (verdict)

```json
{"ts":"...","type":"verdict","task_sha":"<12 hex>","verdict":"pass|fail","note":"...","by":"parent"}
```

Only verdicts feed the posterior. `status: completed` means the child *finished*, not that the work
was right; a cell full of unverified rows is reported as `MEASURE`, never as success.

## Commands

```sh
pi-delegate plan "find every place the repo writes to the socket" --files 20
pi-delegate partition --shard a=src/a --shard b=src/b --strict --min-lines 60   # fan-out gate
pi-delegate run --agent scout --task "..." --cwd ~/proj          # headless, logs itself
pi-delegate verdict pass --last --note "digest matched the code I re-read"
pi-delegate report                                               # posteriors + proposals
pi-delegate flow --days 30 [--json]                              # cycle time, yield, $/pass
pi-delegate targets                                             # agents/models + local rails
pi-delegate route "<task>"                                       # inkling decides (regex fallback, cached)
pi-delegate route --no-inkling "<task>"                          # regex decides, offline
pi-delegate route --laya "<task>"                                # + Laya second opinion
pi-delegate route-report                                         # labels/route, fit readiness
python3 delegation/route-eval.py                                 # 24-case routing benchmark
python3 delegation/route-eval.py --cases delegation/route-eval-heldout.json \
  --inkling thinkingmachines/inkling-2-small \
  --json-out delegation/route-eval-heldout-result.json           # held-out re-check (falsifier)
```

In an interactive session the same decisions are made with the `subagent` tool (it streams in the
TUI and logs the same rows); `pi-delegate` is for scripts, cron, and the self-improve suite.

## A/B a policy change

```sh
python3 selfimprove/run.py --arm arms/deleg.md --tasks log-fanout,parallel-fix \
        --reps 3 --subagent --usage --tag deleg-v2
python3 selfimprove/gate.py runs/<base>/result.json runs/<deleg>/result.json --k 3 --cost-win-frac 0.25
```

`--subagent` enables the subagent tool + this roster for *both* arms (tool availability stays
constant; only the arm spec varies). `--usage` switches the child to `--mode json` so the run
record carries `tokens_in/tokens_out/cost_usd` — without it a delegation arm can only be judged on
pass rate, which is exactly the metric delegation is *not* supposed to move.

## Why not just spawn more agents

Measured elsewhere, repeatedly: multi-agent designs cost 6.4× the energy of a single agent with
task-specific accuracy gains (2610.03010), 59% of tokens in a multi-agent SDLC go to iterative
*build/review/verify* loops (2601.14470), and delegation only pays when the subtask is
context-lossy or genuinely parallel (2605.16205, 2606.00953, 2609.09233). The ledger is the only
thing that turns those priors into this machine's own numbers.
