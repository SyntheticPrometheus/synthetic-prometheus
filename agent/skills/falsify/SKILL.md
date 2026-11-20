---
name: falsify
description: Attack a green test suite — mutate a target, run its own suite against each mutant, and report the behaviours no test distinguishes, with a reproducible survivor id. Use when a suite is green but unproven, after a tester found defects in code that already passed, when the self-improvement suite looks saturated, or when asked what the tests do not cover.
---

# falsify — make green tests mean more

A green suite proves the tests ran, not that the code is right. The 2026-11-20 audit found 12 real
defects in code whose self-tests passed. `bin/pi-falsify` attacks that with a deterministic mutation
forge: apply one semantic change to the target, run the target's **own** suite against a disposable
copy, and keep the mutants the suite still passes.

```sh
pi-falsify scan --target bin/pi-wait --test tests/pi-wait.sh [--limit N] [--timeout S] [--json]
pi-falsify reproduce FINDING     # re-run one survivor; prints REPRODUCED or STALE
pi-falsify minimize FINDING      # shrink the program, keeping the blind spot; writes a witness
pi-falsify resources [--json]    # the last scan's work split by engine, with cost
pi-falsify report [--json]       # the last scan's score and survivors
pi-falsify list-targets          # tools that already have tests/<name>.sh
```

Operators are single-point and stdlib-only: comparison (`<`↔`<=`, `==`↔`!=`, `in`↔`not in`),
boolean (`and`↔`or`), integer constants (`0`↔`1`), and `+ - * //` swaps. A survivor is a behaviour
no test distinguishes — **a hypothesis, not a proven production bug**. Equivalent mutants inflate
the count; the score is a lower bound on suite blindness.

## Reading the number

- `SCORE 10%` on `bin/pi-wait` means 3 of 30 single-point mutants were caught: the suite verifies the
  CLI contract, not the internals. That is the measurement, not a verdict on the tool.
- A survivor is worth reading when its line is on a path you believe is tested. `reproduce` gives
  the deterministic counterexample: the suite exits 0 with that change in place.
- `minimize` delta-debugs the target: it deletes statements while the suite passes **both** the
  mutant and the unmutated reduction, and it never deletes a statement containing the change. The
  witness in `falsify/minimized/<id>/` is the smallest program the suite still cannot tell apart —
  code the suite does not pin down, not a proven bug.
- `resources` reports calls and cost per engine (deterministic / laya / local / free_hosted / paid).
  Today's forge is deterministic-only by construction; paid escalation stays at zero because no
  control permitted spend, and that is a statement about this run, not a general capability.
- A real defect needs more than a survivor: an independently stated invariant that the mutant
  violates in *unmodified* code. Reproducing an `INCIDENTS.md` entry does not count.

## Do not

- Do not call a survivor a bug in a report. Say "the suite cannot distinguish this".
- Do not tune the operator set on one target and quote its score as general capability.
- Do not run it on a target whose baseline suite is already red; the tool refuses, and that refusal
  is the correct answer.

## Loop

The weekly `falsify-scan` row scans `bin/pi-wait` and appends the score to `falsify/log.jsonl`.
Falsifier: 100% on the same target (mutants too easy, change the operators) or four weeks with no
new survivor (the operator set is stale). The monthly audit converts survivors to confirmed defects
or closes them as equivalent. Research base:
`research/rr/pi-falsify-defects-that-pass-the-suite.md`; pin: `tests/pi-falsify.sh`.
