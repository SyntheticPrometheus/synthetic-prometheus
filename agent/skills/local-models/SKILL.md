---
name: local-models
description: Run small GGUF models locally on this host (llama.cpp router as a systemd user service, `bin/local-gen` one-shot batch, `bin/local-batch` unattended resumable runner with the corroboration gate, `local/*` models in Pi). Read this when the goal is offline independence rather than cost — the measured verdict is that local time is cheap and unattended wall-clock is free, so the way to cut cloud reliance is local-does-the-bulk + escalate-only-the-residue, gated by cross-model agreement (16/16 precise at 40% coverage). Every frontmatter value must avoid a colon followed by a space inside an unquoted plain scalar, because YAML reads that as a nested mapping and the loader silently drops the skill. A Pi session on a local model now fits a measured 1,409-token prompt (extensions/local-slim.ts, guarded by bin/pi-local-ctx) so a turn is 1-3 min instead of a 25-minute prefill, but batch tools are still the default for volume.
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

## Quality per second — `bpb`, the number the tok/s table was missing

Measured 2026-11-21 with `bin/local-bpb` on the frozen corpus `local/bpb-corpus.txt` (5,989 B of
this repo's own prose; sha256 in every row). Recipe: `llama-perplexity -c 256 --chunks 1 -t 2`,
`bpb = log2(PPL) * tokens / bytes` — bits per byte, vocabulary-independent, lower better. Full
table and reasoning: `techwatch/bpb-table.md`.

| model | bpb | tok/s | score (tok/s ÷ bpb) |
|---|---|---|---|
| Qwen3-0.6B-Q8_0 | 1.630 | 40.6 | **24.9** |
| qwen2.5-1.5b-instruct-Q4_K_M | **1.517** | 25.4 | 16.8 |
| Qwen3-1.7B-Q4_K_M | 1.562 | 23.6 | 15.1 |
| Llama-3.2-3B-Instruct-Q4_K_M | 1.434 | 11.2 | 7.8 |
| gemma-4-E2B-it-Q4_0 | 2.045 | 9.6 | 4.7 |
| Ornith-1.5-9B.i1-IQ2_M | **1.341** | 4.3 | 3.2 |

The rule this buys: **a model is chosen on two numbers, not one.** Quality alone says Ornith-9B
(18 % better per byte, 9.5× slower); speed alone says Qwen3-0.6B. The middle is
`qwen2.5-1.5b-Q4_K_M` — best bpb of the fast models, 7 % better per byte than the 0.6B for 37 %
less throughput, and the one that also won the 4-way classification suite. `gemma-4-E2B` is the
worst of both worlds here (PPL 54 on our own prose, quarter speed) — do not default to it.
`raon-1-nano` has no number: this llama.cpp build (12110) does not know the `raon1nano`
architecture, so it does not load — an unmeasured model is not a candidate.

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

## An interactive Pi session on a local model (fixed 2026-11-16)

The earlier record here said a Pi session fits 16k but a cold turn costs ~25 min of prefill, and
blamed the context size. Both halves were wrong: the failure looked like a context problem and was
a prompt problem.

| layer | tokens |
|---|---|
| AGENTS.md | 2,875 |
| skills list (one description per skill) | 3,771 |
| MCP tool declarations + server blurb (laya/web/repomap) | 3,992 |
| memory brief + subagent tool | 704 |
| base prompt + 4 core tools + cwd | 1,246 |
| **full harness prompt** | **12,588** |

Against `-c 16384` with `maxTokens` 2048 that is 1.4k tokens of headroom: the first tool result
forced compaction, and every compaction re-prefills 12.6k tokens at 7.8 tok/s. That is the whole
"16k fills up immediately and then times out". Context size was never the cause.

`extensions/local-slim.ts` now applies a local profile automatically (provider `local`/`llama.cpp`
or any loopback `baseUrl`): four tools (`bash read edit write`), a 1,200-character instruction card,
the 200-token memory brief, no skills list, no MCP, no AGENTS.md. **Measured: 1,409 tokens of
prompt + tools, 1,524-1,663 tokens counted by the provider for a whole first request**
(1,205 with `pi --no-mcp`, which is the only way to drop the built-in MCP extension's own 204-token
section — it writes `<mcp_servers>` after every other `before_agent_start` handler). Cloud models are
untouched: same request keeps 15 tools and the 32.5k-char prompt.

`bin/pi-local-ctx` is the guard: it fails when the measured local prompt is above 4,000 tokens (so a
silently disabled profile is a red run, not a slow session), when models.json and the router disagree
on context, and when the compaction reserve leaves no room. `pi-preflight` runs it.

Measured wall clock with the profile, full harness request (`pi -p --mode json "hi"`):

| model | cold turn | prefill | turn 2+ re-prefill |
|---|---|---|---|
| qwen2.5-1.5B | 94 s | 1,436 tok at 19.2 tok/s = 75 s | n/a (new process per run) |
| Llama-3.2-3B | 182 s | 1,220 tok at 7.0 tok/s = 174 s | 23 tok (llama.cpp slot cache), seconds |
| 1.5B tool cycle | 79 s | bash `wc -l` → answer, two requests | |

So: a session is usable for small tasks now, and the 3B is 2x slower per turn than the 1.5B for
better formatting. Two caveats, both measured:

- **The 3B invents tool calls.** Asked to "reply with exactly: ready” it called `read` on a directory
  (EISDIR), then `read` of an invented path (ENOENT), then sent an invented `edit` payload — ~60
  requests at ~20 s each before answering. `local-slim` refuses an identical repeat, ends the run
  after 3 consecutive failed calls and after 12 calls, which turns that 20-minute hang into one
  refused round + an answer. Prompt rules help but are not a guarantee; the refusal is.
- **Batch tools remain the default for volume.** The profile fixes interactive stalls, not throughput:
  one turn is still 0.5-3 min of wall clock, so `bin/local-batch` (0.96 s/item) stays the way to run
  bulk work.

Numbers, method and the raw layer deltas: `local/prompt-layers.json`. Failure record and guard:
`INCIDENTS.md` (2026-11-16).

## Standing (no supervision)

- `bin/pi-selfimprove-local` (agenda row `local-selfimprove`, 1d) — the self-improvement loop's
  free half: measures the base arm on a cheap 6-task subset with a local GGUF and drafts a
  candidate from the failures, $0, detached via `pi-done`. The gate (k≥3, real model) stays
  cloud, because the 1.5B scores 0/3 on those tasks (`selfimprove/DESIGN.md`, v1.1).
- `systemctl --user list-timers local-audit` — weekly 04:20 audit of the live memory rows through the
  full pipeline; report at `~/.pi/agent/local/audit-<date>.md` with retag candidates, residue ids and
  the log. Cheap (`Nice=10`, idle IO), ~20 min, no cloud call.
- `bin/pi-preflight` prints `ok local` / `warn local` (router up, N GGUFs, Laya importable) on every
  run, so a stopped router or a broken venv cannot silently turn "offline capable" into "offline".

## Disk-paged big models (colibri) — evaluated, and the answer is no

2026-11-16, asked whether paging weights from disk (`JustVugg/colibri`, 51.5k★, Apache-2.0, pure C:
hot experts VRAM, warm RAM, cold streamed from disk; the same idea as llama.cpp's mmap, AirLLM's
layer streaming and Apple's *LLM in a flash* paper, plus a learned LRU/pinned expert cache).
I ran **its own planner** against this box (`c/setup_catalog.py` + `assess()` over MemTotal):

| | value |
|---|---|
| catalog rows that fit | **1 of 12**: only `qwen3-coder-30b` is "tight" (needs 8 GB, best 18 GB, 19.4 GB disk) |
| the other 11 | `needs-ram` — floors are 10 GB (qwen36), 16 GB (deepseek/glm), 24 GB+, i.e. dense part alone ≥3.5 GB |
| this machine | 8.2 GB total, **~2.5 GB actually free** with the desktop up |

Three blockers, each measured here:

- **RAM**: the floors are above our total, not above our free.
- **ISA**: `flags` = ssse3 sse4_1 sse4_2 avx, no AVX2/FMA. colibri's IDOT ladder is
  `avx512-vnni → avx-vnni → avx2 → (NEON/VSX) → scalar`; prebuilt engines need AVX2, and the
  grouped-int4 path (`IDOT_GS`) requires it outright (#2106, #2694).
- **Disk**: `/dev/sda` is a WD3200BEVT 5400 rpm HDD at **59.7 MB/s** measured sequential read
  (`dd` over the 3B GGUF). Their reference datapoints run on NVMe (Kimi K3: experts at 6.3 GB/s).

Arithmetic for the one candidate, Qwen3-Coder-30B-A3B (≈15.8 GB of experts / 48 layers / 128
experts ≈ 2.6 MB per expert, 8 routed × 48 layers ≈ **1 GB of expert bytes per token**):

| cache hit rate | disk time/token | tok/s |
|---|---|---|
| 0% | 16.6 s | 0.06 |
| 50% | 8.3 s | 0.12 |

Measured neighbours: the same model on a **12 GB tablet with UFS flash** = 0.33 tok/s (#2283);
GLM-5.2 on a Sandy Bridge W520 with 32 GB = 618 s per prompt (#2106); GLM-5.3-Flash on a 6-core,
25 GB box with an ordinary disk = 20 s/token warm, 44 s cold. Also #2831 (open): colibri's CPU
K-quant matvec is **2-5x behind ggml on the same bytes**, so even inside the RAM budget llama.cpp
is the faster engine here.

GLM-5.3 is in the catalog (`glm-5.3`, 419 GB disk, 16/24 GB RAM) — it changes nothing for us, the
RAM floor is the same 16 GB as 5.2.

### The cliff, measured here (2026-11-16)

Do not argue about this from theory: a cgroup that forces the page cache out measures it directly.
`systemd-run --user --scope -p MemoryMax=<X> -p MemorySwapMax=0 -- bash -c 'drop_caches; llama-bench -m <3B Q4, 1925 MiB> -p 0 -n 4 -t 4 --no-warmup'`
(the model's pages must be first-touched *inside* the scope, or they are charged to whoever
faulted them first and the limit does nothing — a naive run shows only 2.4× at 1.2 GB and is wrong):

| MemoryMax | tok/s (tg4) | RAM saved | slowdown | reclaim events |
|---|---|---|---|---|
| 3 G (fits) | 2.12 cold / 4.2 warm | 0 | 1× | 0 |
| 1500 M (78 % of the model) | **0.03** | 425 MiB | **70×** (141× vs warm) | 12 454 |
| 1000 M (52 %) | **0.02** | 925 MiB | 105× (210× vs warm) | 32 521 |

**A dense model has no graceful degradation.** Saving a quarter of the memory costs two orders of
magnitude, because every weight is needed by every token — the working set is the whole file, and an
LRU cache one byte smaller than the working set misses every time. This is why MoE pages well and
dense does not: the only models worth streaming are ones whose *per-token working set* is a small
fraction of their bytes, and among models that already fit in 8 GB there are none (the smallest MoE
worth paging, qwen3-coder-30b, needs an 8 GB RAM floor). To make a small model smaller, quantize it
(Q4 → IQ3/IQ2) or make it sparse at the *neuron* level (PowerInfer, ZipLM); paging a dense 1–3 B buys
nothing and costs everything.

What would change the verdict, and by how much: a MoE whose dense trunk is small, on a machine with
≥16 GB **and** an SSD. Then 16 GB + 400 MB/s gives ~2.5 s/token on I/O and ~0.3-0.5 tok/s after the
2-core AVX1 ceiling — a 3-minute answer, versus 25 s from the 1.5B. Paging buys *capability*, never
speed. Re-open only above those floors, and measure `COLI_MODEL_MIRROR`/`DIRECT=1` rather than
trusting the README table.

## Keeping the verdict current

The independence case rests on measurements that go stale, so the watch is scheduled, not remembered:
`bin/pi-techwatch` (arXiv/HN/GitHub primary APIs, deduped, screened against the bar above) runs on the
weekly `techwatch` agenda row; the monthly `techwatch-review` session turns each hit into
test/watch/no in `~/.pi/agent/techwatch/verdicts.md`; `pi-preflight` prints `warn watch` when the last
report is >10 days old or every source failed. Full protocol: `~/.pi/agent/techwatch/PROTOCOL.md`.
First sweep's thesis (2026-11-16): the field's answer to big-model-small-machine is **fewer bits per
weight** (ternary, BITCOS, multiplication-free CPU kernels), not streaming — which is the same
conclusion our own 70x paging cliff forces.

## Why this is not a cost lever

Current default model (`deepseek/deepseek-v4.1-flash`): $0.006/M in, $0.50/M out.
A 200-in/40-out task therefore costs **$0.0000212**; 1,000 of them cost **$0.021**.
Local at ~20 s/task would spend **5.6 hours** to save those 2 cents. Local generation buys privacy
and offline capability here, not money.

Cheaper cloud levers that actually move the bill: the `:batch` tier of the same model
($0.2/M out, 2.5x cheaper), cache reads ($0.005/M), and a cheap model for bulk work at all
(`bulker` already pins `~deepseek/deepseek-v4-flash-latest`).

### The knobs a local session depends on (verified 2026-11-16)

The router used to serve `-c 8192` while `models.json` declared 16,384, so every turn died with
`400 request (12924 tokens) exceeds the available context size (8192)`. That is fixed, and the
prompt is now ~1.5k tokens instead of 12.6k (the section *An interactive Pi session on a local
model* above has the layer-by-layer measurement):

| knob | now | why |
|---|---|---|
| `llama-router.service` | `-c 16384` (14.9k usable after 1024 output) | headroom for the 1.4k prompt plus a real conversation |
| ...`-ctk q8_0 -ctv q8_0` | KV at 16k: 3B 0.87 GB instead of 1.7 GB | 3B RSS 2.53 GB, fits the 3.4 G cgroup |
| ...`--models-max 1` | one child resident | two children cost 2.72 GB on a box with ~5 GB for the desktop |
| `settings.json` `compaction.modelOverrides[local/*]` | `reserveTokens: 2048` | auto-compaction fires at `ctx - reserve`; the stock 16384 reserve on a 16384 window is **0**, i.e. compact every turn, each one another full prefill |
| `models.json` `maxTokens` | 1024 for local models | bounds the worst case (1,024 tok at ~12 tok/s is ~85 s); an answer needing more is a cloud task |

The guard is `bin/pi-local-ctx` (also run by `pi-preflight` as `ok local ctx`): declared vs served
ctx, served ctx vs the measured local prompt in `local/harness-prompt.json`, the compaction reserve
in force, and a 4,000-token ceiling on the prompt that fails when `local-slim` is not in effect. It
sends no completion, so it cannot hang; `--measure` records a new prompt size and `--served N`
exercises the failure path.

## What is set up

- Router: `systemctl --user status llama-router` (unit at
  `~/.config/systemd/user/llama-router.service`), models in `~/models/*.gguf`,
  `-c 16384 --parallel 1 -t 4` on `127.0.0.1:9931`. Concurrency is a *loss* here
  (0.56x for 4 slots — generation is bandwidth bound), hence one slot.
- Pi sees them as `local/<file basename>` via `~/.pi/agent/models.json`, and gets the ~1.5k-token
  local profile from `extensions/local-slim.ts` (section above). `pi --no-mcp` drops the last 204.
- `~/.pi/agent/bin/local-gen` — one-shot: stdin items → JSONL on stdout. Unloads other models first
  (two resident models swap) and retries twice on a restart.
- `~/.pi/agent/bin/laya-label` — bulk typed labelling with Laya (`--labels`, `--instructions`,
  `--chunk`): ~1.3 s/item on short titles, ~2.8 s/item on 300-char bodies. Chunk 8-16 items per
  forward pass; long texts padded together OOM the box past ~24. The 6-way memory-`kind` taxonomy is
  beyond it (poor zero-shot accuracy on overlapping label sets) — that is a task to escalate, not a
  model to blame.
- `~/.pi/agent/bin/local-bpb` — quality, not just speed: one JSON line per GGUF with
  `ppl`, `bpb` (bits/byte, vocabulary-independent, lower better), `eval_tok_s` and
  `score = eval_tok_s / bpb` on the fixed corpus `local/bpb-corpus.txt` (sha256 in every row),
  recipe `llama-perplexity -c 256 --chunks 1 -t 2` from `research/karpathy-transfer.md`. Pinned by
  `tests/local-bpb.sh`; the shelf's ranking lives in `techwatch/bpb-table.md`.
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
