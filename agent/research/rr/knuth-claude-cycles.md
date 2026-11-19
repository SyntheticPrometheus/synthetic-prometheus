# Knuth's Claude Cycles: how the cycles were found

status: done
date: 2026-11-19
method: Knuth's claude-cycles.pdf, HN 47557166, the Lean formalization repo, arXiv 2605.09489

## Research
- `knuth/claude-cycles.pdf` 2026-02-28 — the problem is a decomposition of the Z_m^3 Cayley digraph into three directed Hamiltonian m^3-cycles for all m>2 — 3 cycles over m^3 vertices — the search space is what defeats hand proof.
- `knuth/claude-cycles.pdf` 2026-02-28 — Filip Stappers required a plan.md update after every exploreNN.py; Claude Opus 4.6 found the odd-m construction by simulated annealing at exploration 31, about one hour in — a state log, not a longer context.
- `knuth/claude-cycles.pdf` 2026-04-14 — Knuth proved the odd case (760 Claude-like solutions) and reports the even case m>=8 proved by GPT-5.4 Pro — the episode ends with formal verification, not with a transcript.
- `github.com/kim-em/KnuthClaudeLean` 2026-03-05 — Lean 4.28 formalization, ~1,600 lines, 3 axioms, with a Comparator that audits Challenge.lean (the spec) rather than the AI-produced proof body — trust the statement, check the model.
- `github.com/no-way-labs/residue` 2026-03-06 — GPT-5.4 (symbolic) paired with Claude Opus 4.6 (MRV solver) under a residue.md prompt, 67,000x speedup and empirical checks to m=30,000 — two solvers in different modes beat one.
- `HN:47557166` 2026-03-28 — 261 points, 184 comments: the thread's consensus is breadth and heuristics from the LLM, formal proof from the assistant — 2 of the 3 artefacts are verification, not search.
- `arxiv:2605.09489` 2026-05-10 — resolves a related Knuth exercise (SB(m,n) has no Hamiltonian cycle for m=3 mod 4 with even n) by a sign-of-permutation argument — the neighbourhood is still productive after the main result.

## Tangential (2x)
- tangential: Comparator-style spec auditing — from knuth-claude-cycles — our verifier could check a small named acceptance file instead of reading a child's whole transcript, which is the same trust boundary at a fraction of the context.
- tangential: dual-solver orchestration (symbolic + local search) — from knuth-claude-cycles — pairs a cloud model with the deterministic CP/SA solver we already run instead of asking one model to do both jobs.

## Systems impact
- skills/recursive-research step 1 — change — evidence `knuth/claude-cycles.pdf` — a long exploration must checkpoint to a plan file, so a resumed run does not restart from prose.
- skills/delegate policy — change — evidence `github.com/kim-em/KnuthClaudeLean` — a verifier audits the acceptance criteria, not the child's narrative; the acceptance line already exists and is unused.
- bin/pi-senate and bin/pi-percolate — remove — evidence `arxiv:2605.09489` — no change is implied; recorded so a reader knows the neighbourhood was walked and rejected.

## Loops
- loop: explore-checkpoint — metric: checkpoints written per exploration round in a long dispatch — falsifier: a resumed run repeats an experiment already logged — guard: bin/pi-research check — cadence: none, per-dispatch
- loop: verifier-spec — metric: share of verdicts that quote the acceptance line — falsifier: a verifier pass with no quoted criterion — guard: pi-delegate verdict — cadence: weekly review

## Debate
- FOR: two artefacts out of three in the episode are verification, so our money is better spent on the check than on the search / AGAINST: the search was one hour of a frontier model and 31 anneals, so the case rests on a single unreplicated run
- decision: keep — because the Lean Comparator gives an independent artefact, so the claim does not rest on the transcript

## Test
- red: a dispatch resumes with no plan.md and repeats a logged experiment — green: bin/pi-research check --done — output: exit 0, all seven sections present with an id on every claim
- tester: tester — technique: state

## Implementation
- path: skills/recursive-research/SKILL.md — check: bin/pi-research check --done — status: done, step 1 and step 4 name the checkpoint and the spec audit
- path: research/rr/knuth-claude-cycles.md — check: bin/pi-research check --done — status: done
- task #265 — require plan.md checkpoints after each exploration step and audit the spec, not the transcript — status: open
