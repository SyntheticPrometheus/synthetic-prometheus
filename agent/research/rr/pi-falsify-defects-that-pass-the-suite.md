# pi-falsify: defects that pass the suite

status: done
date: 2026-11-20
method: owner idea -> primary sources -> a deterministic forge -> measured survivors

## Research
- `owner:pi-falsify-2026-11-20` — the idea, verbatim: a capability for "discovering bugs in software that already passes its entire test suite", named pi-falsify. Starting targets: `pi-control`, `mem`, `selfimprove/gate.py`; proposed interface `scan`, `reproduce FINDING`, `minimize FINDING`, `report`; injected faults are calibration, only real defects are evidence. It is the decision this run serves: can a cheap deterministic forge produce a number where "all tests green" was the only signal?
- `W2135937266` — Just, Jalali, Inozemtseva, Ernst, Holmes, Fraser (2014), "Are mutants a valid substitute for real faults in software testing?", 765 citations. Mutants correlate with real faults well enough to rank suites, but not perfectly; a surviving mutant is a hypothesis about a blind spot, not proof of a production bug. This is why the report says "behaviour the suite cannot distinguish" and not "bug".
- `W2725449579` — "Mutation Testing Advances: An Analysis and Survey" (2018), 683 citations. The two costs that decide whether a forge is usable are equivalent mutants (survivors that cannot be killed because behaviour is unchanged) and execution time; both must be reported, not hidden.
- `W1991999918` — "Efficient mutation testing by checking invariant violations" (2009), 176 citations. Mutants are most useful when tied to an independently stated invariant; that is the bridge from a survivor to a real defect and the next step here.
- `W2162036145` — "How Effectively Does Metamorphic Testing Alleviate the Oracle Problem?" (2013), 240 citations. Where no expected output exists, relations between executions (same input twice, scaled input, reordered operations) are the oracle. This is the cheapest route from injected faults to genuine discovery and is not built yet.

## Tangential (2x)
- tangential: metamorphic relations as the oracle for `mem` and `pi-control` — from pi-falsify-defects-that-pass-the-suite — could replace hand-written expected outputs with relations (idempotence, cap monotonicity, same answer warm/cold), which is the only way this reaches current-cost discovery rather than mutation scoring.
- tangential: a frozen held-out fault benchmark with a pre-registered 90% detection target — from pi-falsify-defects-that-pass-the-suite — could become the non-saturated evaluation this harness lacks; if the forge is tuned on the same 30 scenarios it reports on, the score is memorisation, not capability.

## Systems impact
- `bin/pi-falsify` — create — evidence `owner:pi-falsify-2026-11-20` — `scan/reproduce/report/list-targets`; AST single-point mutants, disposable copy, the target's real suite as oracle; survivors stored with a deterministic id.
- `tests/pi-falsify.sh` — create — evidence `W2135937266` — pins score arithmetic (60% on the fixture), survivor reproduction, red-baseline refusal, non-Python refusal, shebang preservation.
- `bin/pi-probe` (renamed from the first, wrong build) — change — evidence `owner:pi-falsify-2026-11-20` — frees the name for the capability the owner specified; the probe runner (run a declared claim falsifier) survives under its own name, pin and preflight check.
- `agenda/schedule.json` — create — evidence `W2725449579` — row `falsify-scan` (1w) runs the scan on one target and records the score, so detection is a series rather than a one-off.
- `map.json` / `MAP.md` — change — evidence `owner:pi-falsify-2026-11-20` — the index names the new directory and tool.
- remove-first — no existing row, timer or fallback is replaced: mutation scoring did not exist, and `pi-tool check`/`pi-preflight` remain the gates. No new dependency (Python stdlib + the target's own suite).

Ranking (evidence strength × blast radius / cost): the forge first (one command turns "green" into a number); the pin second; the weekly row third. The LLM/hypothesis layers rank below all three because they cost tokens and have no measured yield yet.

## Loops
- loop: mutation-detection — metric: `bin/pi-falsify scan --target bin/pi-wait --test tests/pi-wait.sh` reports a mutation score and survivor count; the weekly row appends both to `falsify/log.jsonl` — falsifier: the score reaches 100% on the same target (the mutants are then too easy and the operator set must change), or four consecutive weekly scans produce no new survivor — guard: `tests/pi-falsify.sh` (9/9, run twice by `pi-tool check`) plus `pi-preflight` — cadence: agenda row `falsify-scan`, 1w.
- loop: survivor-to-defect — metric: survivors inspected and independently confirmed as real defects per month (target: 1) — falsifier: 8 weeks with 0 confirmed defects, or a confirmed defect that is an equivalent mutant (no observable difference) — guard: `pi-falsify reproduce` must still pass the suite and a named invariant must be violated — cadence: the monthly audit.

## Debate
- FOR: on `bin/pi-wait` the existing 7-case suite kills 3 of 30 single-point mutants — a 10% detection score — so "the tests are green" was measuring CLI shape, not behaviour. The forge is ~250 lines of stdlib Python, deterministic, needs no model, and produces a reproducible id for every survivor. That is a real number where the harness previously had only a boolean.
- AGAINST: 27 survivors are mostly untested internals and low-level `ctypes`/`errno` branches; several are equivalent or unreachable by design, so the score understates the suite and overstates the risk. Injected mutants are not real defects (`W2135937266`), and triaging survivors can cost more than writing the missing tests. A single 10% number from one target does not generalise.
- decision: keep — because the metric is honest about what it measures (suite discrimination, not correctness), the survivors are reproducible and cheap to inspect, and the first real-defect conversion is a separately falsified loop. The number that decided it: 3/30 killed, measured today, versus no measurement at all.

## Test
- red: before the shebang fix, `ast.unparse` dropped `#!/usr/bin/env python3`, so the suite executed the mutant as a shell script; `import sys` invoked ImageMagick's `import`, which waits on stdin, and the scan hung (found by the tool's own fixture). Fixed by re-attaching the shebang; the test now asserts the fixture keeps it.
- green: `sh tests/pi-falsify.sh` — 9 ok, 0 FAIL, identical twice; `bin/pi-falsify selftest` — 4 ok; `bin/pi-falsify scan --target bin/pi-wait --test tests/pi-wait.sh --limit 30 --timeout 8` — `30 mutants, 27 survived, 3 killed`, `SCORE 10% mutation detection`.
- tester: tester — technique: fault — replaced the shebang path, made the baseline red, made the target non-Python, and re-ran `reproduce` on a stored survivor; each fails loudly with the quoted reason.

## Implementation
- path: `bin/pi-falsify` — check: `bin/pi-falsify scan --target bin/pi-wait --test tests/pi-wait.sh --limit 30 --timeout 8` → `30 mutants, 27 survived, 3 killed / SCORE 10%` — status: done
- path: `tests/pi-falsify.sh` — check: `sh tests/pi-falsify.sh` → 9 ok, identical twice — status: done
- path: `bin/pi-probe` + `tests/pi-probe.sh` — check: `bin/pi-tool check pi-probe` → ok — status: done (renamed from the first build)
- path: `agenda/schedule.json` row `falsify-scan` (1w) — check: `bin/pi-agenda run falsify-scan` → score line — status: done
- path: `bin/pi-preflight` check `probe` — check: `pi-preflight` → probe ok — status: done

## Gaps
- No genuine production defect yet. The next experiment is `mem` and `pi-control` with metamorphic/invariant oracles; reproducing an incident in `INCIDENTS.md` does not count.
- No frozen 30-scenario injected-fault benchmark, so 90% detection and false-positive rates are not comparable across versions. This is required before any "self-improving search" claim.
- No LLM/Laya roles (`owner:pi-falsify-2026-11-20` directions 3 and 6): survivor triage and invariant proposal are still the analyst's. Filed as tasks, not claimed.
- `minimize` shipped 2026-11-20 as a command over the *program*, not the mutation: delta-debugging deletes statements while the suite passes both the mutant and the unmutated reduction, so the witness is the smallest program whose blind spot is preserved. Minimising a failing *behavioural trace* against an independent oracle is still unbuilt; that is the direction a real fuzzing forge needs.
- Equivalent mutants are not detected; the score counts them as survival, as `W2725449579` predicts.
