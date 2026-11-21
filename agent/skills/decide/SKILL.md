---
name: decide
description: Record and re-measure a decision you delegated or that changes a recurring row, a spend or a guard — frame it as options with a metric, measure first, fix the mechanism, name a guard that runs and a dated falsifier, then close it kept/reverted/superseded. Use when you say "you decide", "best for the system", "make the call", when a change alters an agenda row or a cost, and when a decision record comes due.
---

# Decide — a decision is finished when its falsifier is read

One line: **no record, no decision; no runnable guard, no record; no dated falsifier, no record.**

Read first: `DECISIONS.md` (the protocol D1–D8 and every record), `INCIDENTS.md` (the failure
classes a guard is supposed to prevent).

## The loop

1. **Frame** — the question as a choice between named options, and "best for the system" as a
   number (cost/day, runway, risk, time). No metric means it is a mood, not a decision.
2. **Measure** — one evidence pack before choosing. Label estimates as estimates; the 2026-11-17
   record said "~$0.25 and 240 s per report" and never measured it.
3. **Second opinion** — Laya only for a typed choice, and record its confidence *and* the fact that
   its calibration on this class is unproven (25% on 7-way routing). Agreement at 0.65 is weak
   evidence, not corroboration. It never decides.
4. **Fix the mechanism** — the row type, the filter, the cadence, the interface. "Try harder" is
   not a decision.
5. **Guard that runs** — a check, a filter, a refusal, a loaded rule. Prose in a row's notes is a
   wish; if prose is all that is possible, say so in the record.
6. **Falsifier with a date** — metric, threshold, date. The record stays `open` until then.
7. **Record once** — `bin/pi-decide new ...`; other files link to it. Four copies drift.
8. **Re-measure** — `pi-decide due` (also a `pi-preflight` check) fails on an overdue record;
   close it `kept`, `reverted` or `superseded` with the number that decided it.

## Commands

```bash
pi-decide new --title T --question Q --options "a|b" --evidence E --choice C \
              --guard "what runs (path)" --falsifier "metric < threshold by DATE" --review-by DATE
pi-decide list [--open]
pi-decide due            # exit 1 when an open record is past review-by
pi-decide close N --status kept|reverted|superseded --note "the number"
pi-decide selftest       # 9 cases, no network
```

`new` refuses a missing field, a non-date review, a guard that names no existing path or command,
and a falsifier with no date. That refusal is the point: the shape is the protocol.

## What this replaces

The 2026-11-17 earning-rail decision was handled well in the moment (measured first, structural
fix, guard, falsifier) and badly as a system: four copies of the record, a claim rule that is prose
rather than a check, a cost figure that was estimated, and no mechanism that would ever read the
falsifier. `DECISIONS.md` + `pi-decide` + the `decisions` preflight check are the guard for that
class — a decision that cannot be re-measured is not allowed to look finished.
