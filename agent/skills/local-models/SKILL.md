---
name: local-models
description: Run small GGUF models locally on this host (llama.cpp router as a systemd user service, `bin/local-gen` one-shot batch, `bin/local-batch` unattended resumable runner with the corroboration gate, `local/*` models in Pi). Read this when the goal is offline independence rather than cost — the measured verdict is that local time is cheap and unattended wall-clock is free, so the way to cut cloud reliance is local-does-the-bulk + escalate-only-the-residue, gated by cross-model agreement (16/16 precise at 40% coverage). Every frontmatter value must avoid a colon followed by a space inside an unquoted plain scalar, because YAML reads that as a nested mapping and the loader silently drops the skill. Never run a Pi session or subagent on a local model here (measured 397 s for a 2-token reply, 6.9k-token harness prompt).
---

# Local models on this host

Measured 2026-11-14. Everything below is a number I ran, not an estimate.

## Hardware ceiling (this machine)

| Fact | Value | Consequence |
|---|---|---|
| CPU | i7-3520M, 2 cores / 4 threads, **AVX1 only, no AVX2** | prefill 12-27 tok/s |
| RAM | 7.7 GB total, **~5 GB held by the desktop session** | one model at a time; two resident models swap (51.9 s per trivial request vs 2.1 s) |
| GPU | Intel HD4000 + NVS 5200M (Fermi, cc 2.1) | unusable for modern CUDA; CPU only |

## Speed (llama-bench -t 4, and warm server requests)

| Model | size | pp512 | tg128 | 200-tok prompt task |
|---|---|---|---|---|
| Qwen3-0.6B Q8_0 | 604 MB | 48.0 t/s | 19.8 t/s | ~5-11 s |
| Qwen2.5-1.5B Q4_K_M | 1.04 GB | 26.6 t/s | 12.1 t/s | ~4-11 s |
| Qwen3-1.7B Q4_K_M | 1.03 GB | 25.6 t/s | 9.9 t/s | ~6-21 s |
| Llama-3.2-3B Q4_K_M | 1.87 GB | 12.2 t/s | 5.4 t/s | ~10-21 s |

Prefill is the cost that matters: a 2,000-token input is ~118 s on the 1.5B and ~165 s on the 3B.

## Quality — it depends on the task, and 5 items are not evidence

Structured single-step tasks (extract JSON / 2-sentence summary / conventional-commit subject /
one tool call), 5 tasks:

| Model | score | notes |
|---|---|---|
| Llama-3.2-3B-Instruct Q4_K_M | **5/5** | only one that formats a conventional commit and emits a valid tool call |
| Qwen2.5-1.5B-Instruct Q4_K_M | 3/5 | clean extraction, sloppy commit format |
| Qwen3-1.7B Q4_K_M | 2/5 | needs `/no_think`; weak on format |
| Qwen3-0.6B Q8_0 | 1/5 | unusable |

**Classification is the opposite ranking** — 40 labelled issue titles → bug/feature/docs/chore,
temp 0, canonical option order: **Qwen2.5-1.5B 28/40 (70%)**, Llama-3.2-3B **21/40 (52%)**. The 3B
over-predicts `bug`. So: 3B for formatting/structured output, 1.5B for labelling and anything
throughput-bound. Do not generalise one task's ranking to another (`raw.json` in this directory keeps
every graded output).

## The error gate (this is what makes unattended offline use safe)

Repeated sampling does **not** help: 3 votes at temp 0.8 changed 28/40 → 27/40 and escalated 0 items,
because the errors are systematic, not sampling noise. Agreement between identical prompts is
worthless.

Two cheap signals do work, measured on the same 40 items:

| Signal | Accuracy where it says "trust local" | Coverage |
|---|---|---|
| cross-model agreement (1.5B == 3B) | **16/16 = 100%** | 40% |
| 3 option-order shuffles all agree | 25/30 = 83% | 75% |
| both conditions | 15/15 = 100% | 38% |

**Laya is the better second source.** Same 40 items, `bin/laya-label` (one forward pass, no
generation): Laya alone **36/40 (90%)** — ahead of both GGUF models — and the pair gates:

| Signal | Accuracy where trusted | Coverage |
|---|---|---|
| 1.5B == Laya | **26/26 = 100%** | **65%** |
| majority of 3 (1.5B, 3B, Laya) | 30/32 = 94% | 80% |
| all three agree | 16/16 = 100% | 40% |

So the default pipeline is **Laya + one GGUF to corroborate** (65% of items never touch a cloud
model, at measured 100% precision on this task), not two GGUF models. Laya's `confidence` is *not*
usable as a gate on this checkpoint: median 0.638 when wrong vs 0.530 when right, and it ships
invalid temperatures (the library warns so). Use agreement, not confidence.

So the working shape is: run local on everything, trust only what two independent sources confirm,
and send the residue — the genuinely hard items — to a cloud model. Cloud sees ~40-60% of the
volume, and only the part worth paying for. `bin/local-batch` implements exactly this
(`--second-model` + `--shuffle-votes`, escalation file written for the residue).

Throughput for unattended work (1.5B): 0.96 s/item single-vote labelling → ~3,700 items/hour;
5.8 s/item with the full gate → ~620 items/hour, i.e. an 8-hour night is ~5,000 gated items.

## Coverage is the competence signal (measured on a real corpus)

Same pipeline, two tasks, 2026-11-14:

| task | corpus | trusted by both sources | accuracy where trusted | wall |
|---|---|---|---|---|
| 4-way issue triage | 40 labelled items | 65% | 100% (26/26) | ~2 s/item |
| 6-way memory `kind` | 87 live memory rows | **25%** (22/87) | 68% (15/22) | 10.5 min (7.3 s/item) |

The residue size is not a failure of the pipeline, it is the pipeline telling me the task is outside
the local models' competence: on the crisp taxonomy it answers two thirds at 100% precision, on the
overlapping 6-way one it refuses three quarters and is only 68% right where it does answer. **Read the
escalation rate before trusting the residue-free rows.** Laya alone scored 39/87 (45%) on the memory
kinds — zero-shot accuracy on a novel, overlapping label set is exactly where it is weak (see the
`laya` skill's own Limits), so that task is a candidate for `laya.fit()` on the stored labels, not for
a bigger GGUF.

## Standing (no supervision)

- `systemctl --user list-timers local-audit` — weekly 04:20 audit of the live memory rows through the
  full pipeline; report at `~/.pi/agent/local/audit-<date>.md` with retag candidates, residue ids and
  the log. Cheap (`Nice=10`, idle IO), ~20 min, no cloud call.
- `bin/pi-preflight` prints `ok local` / `warn local` (router up, N GGUFs, Laya importable) on every
  run, so a stopped router or a broken venv cannot silently turn "offline capable" into "offline".

## Why this is not a cost lever

Current default model (`deepseek/deepseek-v4.1-flash`): $0.006/M in, $0.50/M out.
A 200-in/40-out task therefore costs **$0.0000212**; 1,000 of them cost **$0.021**.
Local at ~20 s/task would spend **5.6 hours** to save those 2 cents. Local generation buys privacy
and offline capability here, not money.

Cheaper cloud levers that actually move the bill: the `:batch` tier of the same model
($0.2/M out, 2.5x cheaper), cache reads ($0.005/M), and a cheap model for bulk work at all
(`bulker` already pins `~deepseek/deepseek-v4-flash-latest`).

**Never** run a Pi session or subagent on a local model on this host: Pi's own harness prompt is
6.9k tokens, which took **397 s to answer "ok"** (2 output tokens, measured 2026-11-15). An earlier
3.2k-prompt attempt prefilled at 7.3 tok/s and had not finished after 7 minutes. `pi-delegate run`
refuses `local/*` for this reason; use `local-gen` / `local-batch` (no harness).

## What is set up

- Router: `systemctl --user status llama-router` (unit at
  `~/.config/systemd/user/llama-router.service`), models in `~/models/*.gguf`,
  `-c 8192 --parallel 1 -t 4` on `127.0.0.1:9931`. Concurrency is a *loss* here
  (0.56x for 4 slots — generation is bandwidth bound), hence one slot.
- Pi sees them as `local/<file basename>` via `~/.pi/agent/models.json` (only for one-off
  single-turn use; see the harness-prompt warning above).
- `~/.pi/agent/bin/local-gen` — one-shot: stdin items → JSONL on stdout. Unloads other models first
  (two resident models swap) and retries twice on a restart.
- `~/.pi/agent/bin/laya-label` — bulk typed labelling with Laya (`--labels`, `--instructions`,
  `--chunk`): ~1.3 s/item on short titles, ~2.8 s/item on 300-char bodies. Chunk 8-16 items per
  forward pass; long texts padded together OOM the box past ~24. The 6-way memory-`kind` taxonomy is
  beyond it (poor zero-shot accuracy on overlapping label sets) — that is a task to escalate, not a
  model to blame.
- `~/.pi/agent/bin/local-batch` — unattended: resumable by id (a kill, OOM, or reboot costs one item),
  progress + ETA on stderr, corroboration gate, residue written to an escalation file, exit 1 when
  anything is unresolved.

```bash
# quick, all items answered, no gate
printf '%s\n' "Login page 500s on empty email" "Bump ruff to 0.5.0" \
  | ~/.pi/agent/bin/local-gen -s "Label each line bug|feature|docs|chore. Label only."

# overnight, gated, resume-safe (run from a directory you can find again)
# 1. Laya labels everything offline (cheap, strongest single source here)
~/.pi/agent/bin/laya-label -i items.jsonl -o laya.jsonl --chunk 8 \
  --labels bug,feature,docs,chore --instructions "Which kind of software change is this?" \
  --criteria '{"bug":"something is broken","feature":"new capability","docs":"documentation","chore":"maintenance"}'

# 2. a GGUF corroborates; only disagreement reaches the escalation file
setsid nohup ~/.pi/agent/bin/local-batch -i items.jsonl -o out.jsonl -s \
  "Label the item with exactly one of: {opts}. Reply with the label only." \
  --choice bug,feature,docs,chore --temp 0 --agree-with laya.jsonl \
  --escalate residue.jsonl > batch.log 2>&1 &
```

`{opts}` is required with `--shuffle-votes`: the option list must be substituted in place, or the
model re-reads a canonical list and agrees with itself. Only the items in `residue.jsonl` are worth a
cloud call, and they arrive with every vote recorded so the parent does not re-derive them.

Add a model: drop a GGUF in `~/models/` and `systemctl --user restart llama-router`.
`bin/local-gen --models` lists what the router sees.

Re-run the quality check after adding or swapping a model (objective graders, no LLM judge, ~5 min
for four models): `python3 ~/.pi/agent/skills/local-models/eval.py` — writes `raw.json` with every
raw output so a failure is never graded blind. Fixed rows are the Llama-3.2 / Qwen2.5 / Qwen3 set;
edit `MODELS` and `TASKS` for a different comparison.

Reproduce the gate numbers (`items-labelled.jsonl` = 40 items with hand-checked labels):

```bash
python3 votes.py 3        # does repeated sampling help? (no: 28/40 -> 27/40, 0 escalations)
python3 signals.py        # which signal predicts a wrong answer (cross-model: 16/16 at 40%)
```

Both scripts unload other models first and print the table above; `signals.py` writes
`signals.json` beside the script with every answer if you need to re-grade differently.
