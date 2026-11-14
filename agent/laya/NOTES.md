# Laya on this host — setup, measurements, PDSA

Upstream: github.com/NandhaKishorM/laya (Apache-2.0), HF `convaiinnovations/laya`.
Non-autoregressive encoder + typed decision heads: `choice`, `score`, `noul` (boolean) in one
forward pass, calibrated confidence, no text generation.

## What is installed

```
~/.pi/agent/laya/.venv          uv venv, Python 3.12.16, laya 0.4.32, torch 2.15.0+cpu,
                                transformers 5.23.0, vegaml 0.16.1, mcp 2.x
~/.pi/agent/mcp.json            pi MCP server "laya" -> .venv/bin/laya-mcp-server
~/.pi/agent/bin/layaq           shell one-shot wrapper (compact output, --preset/--questions/
                                --schema/--batch)
~/.pi/agent/skills/laya/SKILL.md  when/how to use it as an agent
~/.pi/agent/prompts/triage.md   /triage <text> slash command (table of label + confidence)
~/.pi/agent/laya/{bench.py,mcp_probe.py,probe2.py}   repro scripts
HF cache                        ~/.cache/huggingface (english checkpoint, 842 MB)
```

Install: `cd ~/.pi/agent/laya && uv venv --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install --torch-backend=cpu "laya[mcp]"`

MCP env: `LAYA_DEVICE=cpu`, `LAYA_MODELS=english`, `LAYA_THREADS=4`, `LAYA_PRELOAD=1`.
Verified in a fresh headless session: `mcp__laya__laya_predict`, `mcp__laya__laya_predict_batch`,
`mcp__laya__laya_route` are direct tools and `codemode` is active for the rest.
`toolExposure` makes `laya_predict`, `laya_predict_batch`, `laya_route` direct tools; the rest
(`laya_decide`, `laya_preset`, `laya_tournament`, `laya_shortlist`, `laya_predict_long`,
`laya_route_batch`, `laya_status`) stay codemode-only. `pi mcp list` verifies.

Hardware: Ivy Bridge 4-core CPU, 7 GB RAM, no usable CUDA (NVS 5200M). CPU fp32 only.

## Measured (2026-11-14)

| workload | wall | notes |
|---|---|---|
| `laya "<text>"` route-only | 0.25 s | no weights |
| model load / cold start | 5.7–7.0 s | per process; MCP keeps it warm per session |
| predict, 1 question | 2.0 s | |
| predict, 3 questions | 3.3 s | one forward pass |
| predict, 5 questions (triage) | ~8 s | long preset instructions, 379 tok |
| `predict_batch`, 4 states × 1 question | 4.1 s | ~1 s marginal per state |
| peak RSS with english resident | 2.8 GB | |

Quality spot checks (English checkpoint, zero-shot):
- "billed twice, refund or we cancel" → `billing` 0.987, `churn` 0.27, `refund_requested` 0.86 ✓
- "Server 500s on /api/checkout since the 14:02 deploy" → `technical` 0.46 (weak but right)
- triage on a blocking outage → `is_urgent` P(true)=0.14 ✗ — the documented `noul` label
  sensitivity on the English checkpoint (it renders `false:`/`true:` by default). Use
  `labels: {true: "A", false: "B"}` plus `criteria`, or a 2-option `choice`, and validate.

## Known limits (upstream docs)

- Near-chance zero-shot on novel typed-decision label sets (0.36 vs 0.32 random); `fit()` with
  ~5 rows/option + calibration is what makes it good on your own labels.
- Boolean-word choice labels are followed verbatim; `score` is the weakest primitive;
  `laya-multilingual` has a first-slot bias on `score`.
- >20 choice options starve the per-option token budget → `laya_tournament` / `laya_shortlist`.
- Negation is not safe (issue #377): validate the exact wording served.
- Checkpoint load prints `invalid temperatures ... treated as uncalibrated` for some entries.

## PDSA

Cycle `laya-cpu-latency` (open): see `mem pdsa list`.
Plan: 2–3 s per decision on this CPU is 60–90x the T4 number; hypothesis — an INT8 ONNX graph
(`laya-ort`, OS-level ONNX Runtime, 4 threads) reaches ≤1.0 s per 3-question decision and
≤1.5 GB peak RSS at no accuracy cost (≤2% label flips on a 50-item fixture), which would make
per-item triage cheap enough to run inline. Metric: median wall per 3-question predict, peak RSS,
and label-flip rate vs the PyTorch path on the same fixture.
Do (done so far): PyTorch baseline installed and measured (table above).
Study/Act: pending the ONNX export; if the hypothesis fails, keep the 2–3 s CPU path and close
the cycle with the numbers.
