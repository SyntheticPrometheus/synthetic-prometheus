---
name: laya
description: Local Laya decision model — zero-token typed decisions (choice / score / boolean) over text in one forward pass. Use when you need cheap, repeatable, calibrated classification of many items (triage, routing, intent, urgency, guardrail flags, yes/no checks) instead of spending an LLM turn per item, or when you want a probability with a stated confidence rather than a generated judgement.
---

# Laya — local System-1 decision model

Laya is a non-autoregressive encoder (+ typed decision heads): you hand it a state and a
set of typed questions, it returns labels, full probability distributions and a calibrated
confidence in one forward pass. No text generation, no token cost, deterministic.

Installed here at `~/.pi/agent/laya` (venv, CPU torch). Exposed to pi as MCP server `laya`.

## Reach for it when

- Bulk labelling/triage: N texts → same small set of labels, with per-item confidence so you
  can escalate only the uncertain ones to a real model turn.
- Repeated structured judgements inside a loop (routing, filtering, dedup decisions, flagging).
- You want a probability, not prose: spend the LLM turn only where Laya is unsure.
- Screens that must be free and instant-ish: `--preset guard` (jailbreak/injection),
  `--preset moderation`, `--preset triage`, `--preset email`, `--preset router`.

Do **not** use it for open Q&A, summarising, reasoning chains, or high-stakes single calls with
no human review. Zero-shot accuracy on novel label sets is mediocre (see Limits); it is a fast,
cheap base, and `fit()` makes it much better on your own labels.

## Tools (new sessions: `mcp__laya__*`; direct = callable as a normal tool)

| tool | use |
|---|---|
| `laya_predict` (direct) | state + questions → answers (choice/score/noul), probabilities, confidence |
| `laya_predict_batch` (direct) | `{"requests":[{state,questions},...]}` — one forward pass, 2–3.6x cheaper than looping |
| `laya_route` (direct) | routing decision only, no weights loaded (~0.2 s cold) |
| `laya_decide` | JSON-schema in → typed values out (enum/bool/int with min-max) |
| `laya_preset` | one of `triage`, `email`, `guard`, `moderation`, `router` |
| `laya_predict_long` | documents longer than the context window (windowed) |
| `laya_shortlist` / `laya_tournament` | >20 choice options (budget per option collapses otherwise) |

**`state` must be a JSON object**, e.g. `{"request": "..."}` — a bare string fails validation.

```json
{"state": {"request": "Billed twice for March, refund or we cancel."},
 "questions": {
   "dept": {"type": "choice", "instructions": "Which team handles this?",
            "criteria": {"billing": "invoices, payments, refunds",
                         "technical": "bugs, outages, errors",
                         "other": "everything else"}},
   "urgency": {"type": "score", "instructions": "How urgent?",
               "criteria": ["can wait", "this week", "today"]},
   "churn": {"type": "noul", "instructions": "Do they threaten to cancel?",
             "labels": {"true": "A", "false": "B"}}}}
```

`choice` → `choice` + `probabilities`; `score` → expected level on the ordered criteria list;
`noul` → `noul` = P(true). `confidence` is calibrated (0–1); gate on it.

Slash command in interactive sessions: `/triage <text or path>` → the triage preset, shown as a
label/confidence table with low-confidence flags.

## Shell path (works in any session, cold start ~7 s)

```bash
L=~/.pi/agent/laya/.venv/bin
$L/laya "text" --preset triage --predict            # human readable
$L/laya "text" --questions /tmp/q.json --predict --json
$L/laya --batch tickets.txt --predict --batch-size 8 --sort-by-length --json   # JSONL out
$L/layaq '{"dept":{...}}' "the text"                # compact label+conf summary (helper)
```

## Measured on this host (4-core Ivy Bridge, CPU only, English checkpoint, 842 MB fp16)

| workload | wall |
|---|---|
| cold start / model load | 5.7–7.0 s |
| 1 question | ~2.0 s |
| 3 questions, one pass | ~3.3 s |
| 4 states × 1 question, batch | ~4.1 s |
| peak RSS (model resident) | ~2.8 GB |

Sessions keep the model warm in the MCP process, so per-call cost is the 2–3 s forward pass, not
the load. Prefer `laya_predict_batch` for lists. The model is 421M params fp16; GPU (T4) does
33 ms — this box cannot.

## Limits that bite (from upstream docs + measured here)

- Boolean-word choice labels (`yes`/`no`, `true`/`false`) are followed verbatim — use semantic
  or opaque labels (`A`/`B`).
- `noul` is label-sensitive on the English checkpoint: pass `criteria` keyed `true`/`false` and
  a distinct `labels` pair, and sanity-check polarity on a positive control before trusting it.
- Ordinal `score` is the weakest primitive; `laya-multilingual` also has a first-slot bias.
- The shipped English checkpoint warns `invalid temperatures` on load for some entries — treat
  those confidences as uncalibrated and validate on your data.
- High-cardinality choice: >20 options → `laya_tournament` or `laya_shortlist`, or the per-option
  token budget starves.
- Negation is not safe (see upstream issue #377): validate the exact wording you serve.

## Making it accurate on your data (`fit`, no gradients)

```python
import laya
agent = laya.Agent("convaiinnovations/laya")
agent.fit("labels.csv", questions=questions)   # CSV: state, <question ids>
report = agent.fit(...); report["serving"]     # heads that beat zero-shot; may be empty = honest no
agent.save_calibration("calib/")               # temperature + conformal q-hat + review line
```
Fit needs ~5 rows per option of the widest question plus a held-out quarter (min 10). Reuse
`save_calibration`/`load_calibration` so a fit is not thrown away.

## Files

- `~/.pi/agent/laya/` — venv, `bench.py`, `mcp_probe.py`/`probe2.py` (end-to-end MCP checks),
  `NOTES.md` (setup + PDSA cycle).
- `~/.pi/agent/mcp.json` — server entry (`LAYA_MODELS=english`, `LAYA_THREADS=4`,
  `LAYA_PRELOAD=1`). Adding `multilingual` costs another ~650 MB / 2 GB RSS.
- Upstream: github.com/NandhaKishorM/laya, HF `convaiinnovations/laya`.
