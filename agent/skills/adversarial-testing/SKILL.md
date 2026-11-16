---
name: adversarial-testing
description: "How to break software on purpose, and how to run a tester panel that fails in different ways (boundaries, state, oracles, hostile input, fault injection, security, recovery, access). Use before claiming a change works, when a suite is green but unproven, when a bug escaped, and whenever dispatching tester subagents."
---

# Adversarial testing

Two rules carry most of the value:

1. **A panel is only diverse if its members fail differently.** Same model + same spec + same
   hints = Knight & Leveson's multiversion failure, at N× the cost (doi:10.1109/TSE.1986.6312924).
   Diversity has to be *assigned*: different model family, different starting artifact, different
   technique, no shared findings before the merge.
2. **A finding without a repro is an opinion.** Exploration finds; a repeatable case proves.

Evidence for the panel rules: `research/tester-diversity.md` (Hong & Page 2004; Woolley 2010;
Itkonen et al. 2007/2013; Papadakis et al. ICSE 2018).

## The lens matrix

Assign each tester a **disjoint row**. Two testers on one row is a duplicate, not a panel.

| lens | what breaks | technique | oracle |
|---|---|---|---|
| **boundaries** | off-by-one, empty/null, unicode, max length | equivalence classes + boundary values | spec/schema |
| **state** | double submit, cancel mid-flight, retry, reentrancy, crash-resume | state model + interleavings | the state machine |
| **oracle** | "it ran fine" while output is wrong | differential vs old/reference impl; round-trip | second implementation |
| **hostile input** | parsers, paths, encodings, huge/deep payloads | fuzz + shrinking; ugly corpus | crash/hang/divergence |
| **environment/faults** | disk full, perms, latency, clock skew, SIGKILL mid-write | fault injection, chaos | invariant survives fault |
| **scale/data** | 0/1/many, duplicates, concurrent writers, overflow | generate + compare | conservation invariants |
| **change/compat** | upgrade with old data, migration re-run, version skew | replay old fixtures | old behaviour preserved |
| **security** | authz on ids, injection sinks, SSRF, secrets in logs | threat model (`redteam`) | attacker gain |
| **recovery/UX** | lying errors, partial writes, silent truncation, a11y | read the error path, keyboard-only, screen reader | user can recover |

Technique catalogue with concrete probes: `research/tester-diversity.md` §7. Use it as a checklist,
not as a script — the value is in picking the row the author did not think about.

## Panel protocol

- **Size**: 2 testers for a normal change, 3–4 for auth/money/data-loss surfaces. Four is a cap,
  not a target; §2 of `delegation/policy.md` (dispatch floor) still applies.
- **Assignment**: each gets `RISK AREA / TECHNIQUE / ORACLE / SCOPE / BUDGET` — never "test this".
  Distinct disks of attention; overlapping file *reads* are fine.
- **Independence**: dispatch in parallel, no parent findings in the prompt, different model family
  where the ledger allows. The verifier is not on the panel; a panel that judges itself is not a
  check.
- **Merge**: the parent unions the folds, dedupes by **root cause** (not by symptom), and ranks by
  severity × reachability. A finding reproduced by two lenses is one bug with higher confidence.
- **Close**: every finding becomes a repeatable case (scripted test) or is explicitly dropped with
  a reason. Findings that stay exploratory rot.
- **Test the test**: on a green suite, mutate the code once; if the suite stays green, that is the
  first finding.

## Anti-patterns (each one has already cost a run)

- **Persona diversity** — "you are a senior QA engineer" on the same model with the same context.
  A prompt, not a panel.
- **Coverage theatre** — reporting lines executed instead of behaviours broken.
- **One "test everything" contract** — nobody owns the risk, the fold is a survey.
- **Fix-while-testing** — the tester stops finding once it starts repairing; findings and patches
  come from different agents.
- **Trusting the green** — coverage and mutation score are weak proxies (ICSE 2018); only a
  reproduced failure is evidence.
- **Silent clean** — "no bugs found" with no coverage statement is indistinguishable from "did not
  look".

## Measuring the panel (PDSA, `mem pdsa`)

Per panel run, record: **unique root causes**, **false positives**, **tester-minutes**, and the
solo-test baseline for the same change. Keep it if unique root causes per dollar beats solo; cut
the lens that never produces a unique finding. Log verdicts with `pi-delegate verdict`.

## Dispatch

```
pi-delegate panel --target <path> --risk "auth token refresh"
```

prints ready-to-run `pi-delegate run --agent tester --task ...` lines with disjoint lenses. Then
`pi-delegate verdict pass|fail` on the panel as a whole.
