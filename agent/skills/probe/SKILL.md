---
name: probe
description: Run the probe a claim was supposed to face before anything ships — record a claim with the observations that would kill it, execute them, and get survived, falsified or error. Use when a digest, decision, agenda metric or PDSA cycle states a falsifier, when a claim is about to be reported as true, or when "we verified it" needs an exit code instead of a sentence.
---

# probe — run the probe a claim was supposed to face

## The gap this closes

This harness already *demands* falsifiers: `pi-decide new` refuses a record without a dated one,
`pi-research` refuses a digest whose loop has no falsifier, every `mem pdsa` cycle carries a
falsifying metric. Nothing ever **ran** one. A falsifier checked only for presence is decoration:
the claim was never exposed to the observation that could kill it, and "we will know by 2026-12-01"
became a promise nobody reads.

`bin/pi-probe` stores a claim together with the commands that could kill it, runs them, and
answers with an exit code. **Survived is evidence, not proof** — Popper, not a certificate. A probe
that could not run is an error, never a survival.

## Contract

```sh
pi-probe add --claim "the daemon is stable" --name stable \
    --falsifier "grep -q Traceback /tmp/daemon.log"      # fires if the bad thing was observed
pi-probe add --claim "the tree is publishable" --name publishable \
    --holds-if "pi-preflight --quiet"                    # fires if the necessary condition fails
pi-probe run stable publishable   # exit 0 survived · 1 a probe fired · 2 error
pi-probe run --all [--json] [--timeout SEC]
pi-probe list                     # last verdict per claim
pi-probe show NAME                # the record as JSON
pi-probe due                      # exit 1 on a survived claim past --review-by
```

Two probe shapes, because both are honest:

| flag | written as | fires when |
|---|---|---|
| `--falsifier CMD` | a killer: search for the counter-observation | exit 0 |
| `--holds-if CMD` | a necessary condition the claim needs | exit non-zero |

Exit 126/127, a timeout, or a signal is `error`; it never counts as survival. `add` refuses
`true`/`false`/`:`/empty, a claim with no probe, a duplicate name (unless `--force`), and a
malformed date. Records are one JSON file per claim under `$PI_FALSIFY_DIR`
(default `~/.pi/agent/falsify/`), written atomically; every run appends to `falsify/log.jsonl`
so "I ran the falsifier" is auditable.

## How to use it in the loop

1. When a claim is about to ship, write the observation that would prove it wrong **as a command**.
   If it cannot be written as a command, say so — that is a claim that cannot be tested, not a
   falsifier.
2. `pi-probe add …` at the moment the claim is made, not later.
3. `pi-probe run NAME` before reporting the claim. Quote the verdict line and the probe.
4. On `falsified`: the claim is dead. Fix it or report the kill; do not soften the wording.
5. On `error`: fix the probe. An unrunnable falsifier is a defect in the claim's evidence.
6. `pi-probe due` on a review pass: a claim past its review date that was never falsified is
   stale evidence.

## Limits (stated, not hidden)

- A probe can be a badly chosen proxy; survival only means that probe did not fire.
- Probes run in `/bin/sh` with `LC_ALL=C`, no network by default policy (nothing stops one, but a
  network probe is a measurement of remote state and belongs behind `bin/pi-wait`/backoff).
- The registry is local to this machine. It is not a theorem prover, a monitor, or a CI service.

## First live claim

`text-channel-alive` — the two-way text channel still answers: `--holds-if "pi-text check"`
(most checks on this machine exit 0 when healthy, so they are necessary conditions, not killers),
review-by 2026-11-27. The tool's own spec is
this file plus `pi-probe --help`; its pin is `tests/pi-probe.sh`, run twice by `pi-tool check`.
