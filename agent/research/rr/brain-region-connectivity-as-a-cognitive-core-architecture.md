# Brain region connectivity as a cognitive-core architecture

status: done
date: 2026-11-20 (run 2: complete accounting; literature pass added 2026-11-20 19:15Z, GAPS section materialised)
method: seeds -> hops -> per-row accounting; every claim carries an id

## Research
- `brainpk:manifest` — the zip holds 7 CSV tables and **124 data rows** (34/14/10/21/11/19/15), one atlas of directed circuits and one signal legend. It is a function-labelled map of principal pathways, not a connectome, so the transferable unit is the *function class* (relay, gating, selection, prediction, state), not a region.
- `brainpk:readme` — most behaviours are distributed and regions do not own single functions (memory alone spans hippocampal formation, medial temporal cortex, thalamus, prefrontal and sensory association cortex), so a one-region-per-module mapping is wrong by the package's own statement.
- `brainpk:signal-pathway-ref` — connections carry qualities beyond data (gain, gating, disinhibition, prediction error, state) and "excitatory" is context-dependent, so a mapping that only adds edges misses the modulatory class; those are the caps, gates and schedules already here.
- `brainpk:atlas-index` — the atlas is organised subsection-by-subsection, i.e. a machine can walk it: 124 addressable rows, each with a principal input, output and function.
- `brainpk:readme` — the package names its own limit (principal pathways only; laterality relative; net effect differs from transmitter), so every line here is a functional correspondence with a falsifier, never an anatomical equivalence.
- `brainpk:manifest-conservation` — the accounting identity this run ships: **124 = 116 claimed + 8 excluded**, every row once. The previous run mapped 14 function classes but never accounted for the 124 rows, so "the zip" was summarised rather than consumed; this run consumes it (see GAPS for what still cannot be claimed).
- `oa:10.1162/neco.2007.19.2.442` — Bogacz & Gurney, *The basal ganglia and cortex implement optimal decision making between alternative actions* (Neural Computation, 2007, 459 cites): selection is **competition with disinhibition**, not a dispatcher that chooses; the loser is actively held down. Predicted here: a gate needs a default-off state and an explicit release, and a gained schedule should show latency to release.
- `oa:10.1016/s0893-6080(02)00044-8` — Doya, *Metalearning and neuromodulation* (Neural Networks, 2002, 802 cites): one scalar per modulator sets a *learning rate / gain*, not a message. Predicted here: caps and limits belong to the schedule layer, and their effect must be one parameter wide, never an argument to the tool they constrain.
- `oa:10.1016/j.neuron.2005.04.026` — Yu & Dayan, *Uncertainty, neuromodulation, and attention* (Neuron, 2005, 2010 cites): expected and unexpected uncertainty are signalled by different channels. Predicted here: `probe`/`falsify` (unexpected) and `pi-control cap` (expected) are distinct signals and merging them loses the distinction.
- `oa:10.1038/4580` — Rao & Ballard, *Predictive coding in the visual cortex* (Nature Neuroscience, 1999, 6682 cites): the signal carried upward is the **residual**, and the model is the downward path. Predicted here: a session brief should carry what changed against the plan, not a re-statement of the plan.
- `oa:10.1146/annurev-psych-122414-033634` — Sporns, *Modular Brain Networks* (Annu Rev Psychol, 2015, 1529 cites): modules are cheap only if the between-module edges are few and costly-by-design. Predicted here: the 15 unmapped capabilities below are not a mapping backlog but evidence of modules the harness has not declared.

## GAPS (what this run does not claim)
- 15 agenda-referenced capabilities have no brain row (`bin/pi-core-map --gaps`): falsify, wait, term, peer, cadence, burn, accounts, senate, speaker, techwatch, local-reap, selfimprove-local, session-watch, pergola-health, dns-check. Each is a function class the package *does* name (error discovery, state control, scheduling, monitoring); the map is silent, not the source.
- Pairings are judgement: `--package` verifies accounting (unique, live, counted), not correctness. A wrong-but-unique `brain_id` passes. The literature above narrows what a pairing should predict, it does not test it.
- No behavioural improvement is measured. The only metric today is `resolved == rows` (14/14); nobody has shown a mapped path makes a turn cheaper, a gate safer or a schedule more honest.
- 8 rows are excluded as structural support (CSF, ventricles, meninges, white-matter classes) — declared, not claimed.
- This section is new: the earlier text forward-referenced `GAPS` without one existing, which is the failure mode this file is supposed to catch.

## Tangential (2x)
- tangential: event-driven gating of what enters a session context — from brain-region-connectivity-as-a-cognitive-core-architecture — could replace eager context loading with a salience gate, cutting tokens per turn (measurable in the context brief).
- tangential: reward-modulated skill selection — from brain-region-connectivity-as-a-cognitive-core-architecture — could let `bin/pi-mind` weight which skill a row tries next by measured success instead of recency.

## Systems impact
- `core/brain-map.json` — change — evidence `brainpk:manifest` — adds a `package` block (124 rows, index path, 8 exclusions and why) so the map declares its source size.
- `core/brain-map-index.tsv` — create — evidence `brainpk:atlas-index` — 124 lines, one per package row: `package_row -> brain_id`. This is the accounting the first run did not have; its rows are decisions, not prose.
- `bin/pi-core-map` — change — evidence `brainpk:manifest-conservation` — `--package` verifies the index: each package row claimed once, every claim names a live brain row, exclusions match the declared count, no brain row claims nothing. Added to the weekly row.
- `tests/pi-core-map.sh` — change — evidence `brainpk:atlas-index` — four new cases: clean index passes; an unaccounted row fails; a claim naming a deleted brain row fails; a duplicate claim fails.
- `agenda/schedule.json` — change — evidence `brainpk:signal-pathway-ref` — row `core-map` (1w) runs `--quiet --gaps --package --record`; the earlier run's "no new row" conclusion is superseded by the owner's monitor request.
- remove-first — nothing in the package replaces an existing row, timer or fallback: the 8 excluded rows are structural support (CSF, ventricles, meninges) with no component to delete. No dependency added; `pi-percolate` unchanged (one python3 stdlib import, no new resource).

Ranking (evidence strength × blast radius / cost): the index (all 124 rows checkable, one file) first; `--package` next; digest prose last.

## Loops
- loop: core-map-package — metric: `bin/pi-core-map --package` reports `124 rows, 116 claimed, 8 excluded, 0 problems` and each run appends `package_rows/claimed/excluded/problems` to `core/brain-map-ledger.jsonl` — falsifier: any run reporting a problem, or `claimed+excluded != 124` — guard: `tests/pi-core-map.sh` (16/16) plus the tool's exit 1 — cadence: agenda row `core-map`, 1w.
- loop: core-map-paths — metric: `resolved == rows` (14/14 today) — falsifier: a mapped path missing — guard: `tests/pi-core-map.sh` — cadence: same row.
- loop: core-map-gaps — metric: count of agenda-referenced capabilities with no brain row (13 today) — falsifier: a capability the schedule depends on that the map never absorbs after two cycles — guard: the row prints them; `--record` keeps the series — cadence: same row.

## Debate
- FOR: 116 of 124 package rows can be claimed by an existing harness function and the remaining 8 are structural support, so the package is consumable end to end; a row added to the source with no claim now fails a check within a week, at the cost of one TSV and ~60 lines of python.
- AGAINST: an index of 116 correspondences proves paths exist, not that any pairing improves behaviour; the mapping is one analyst's judgement and the check verifies accounting, not correctness — a wrong `brain_id` passes as long as it is unique. The first run's real weakness was not thin prose, it was that nobody argued the 14 pairings.
- decision: keep — because the artifact's only claim is accounting (`124 = 116 + 8`, unique claims, live ids), and that claim is falsifiable today; the correctness of individual pairings is now a reviewable diff (`brain-map-index.tsv`) rather than hidden prose, and a scheduled verifier samples it.

## Test
- red: before `--package`, a fixture index of 3 rows with a 4th line exits 0 silently (the map cannot see its source), and a line naming a deleted brain row also exits 0.
- green: `sh tests/pi-core-map.sh` — 16/16 `ok`, rc 0, run twice, outputs identical; the four package cases quote `ok --package accepts a fully accounted index`, `ok --package fails when a row is unaccounted for`, `ok --package fails on a claim naming a deleted brain row`, `ok --package fails on a duplicate claim`.
- tester: `tests/pi-core-map.sh` — technique: fault — replaced the index's second claim with `nosuch` and with a duplicate tag; both exit 1 and name the row, not a silent pass.
- verifier — technique: oracle — recomputed `124 = 116 + 8` from the CSVs, checked every tag against CSV order and every destination against the 14 live ids, then sampled 12 assignments across all 7 CSVs: verdict `PASS (accounting)`, 11 agree / 1 disagree — `01#12` (frontal eye fields: voluntary saccades) was assigned `salience`, which is wrong; reassigned to `motor`.

## Implementation
- path: `bin/pi-core-map` + `core/brain-map.json` + `core/brain-map-index.tsv` — check: `bin/pi-core-map --quiet --gaps --package` → `brain-map: package 124 rows, 116 claimed, 8 excluded` — status: done
- path: `tests/pi-core-map.sh` — check: `sh tests/pi-core-map.sh` → 16 ok, 0 FAIL, identical twice — status: done
- path: `agenda/schedule.json` (row `core-map`, 1w) — check: `bin/pi-agenda run core-map` → `ok (brain-map: package 124 rows, 116 claimed, 8 excluded)` — status: done
