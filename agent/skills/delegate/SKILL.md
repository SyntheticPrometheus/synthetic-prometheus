---
name: delegate
description: Decide when and how to delegate work to subagents (isolated context) or to a parallel pi session, write the contract, fold the result back, verify it, and log the verdict so the delegation policy improves from evidence. Use before any task that reads widely, splits into independent parts, needs an independent check, or would otherwise flood this context; also use when tempted to do a "role-play" multi-agent dance that the literature says is a waste of tokens.
---

# Delegating work

Policy of record: `~/.pi/agent/delegation/policy.md` (v1). Ledger: `delegation/ledger.jsonl`.
Roster: `~/.pi/agent/agents/*.md`. This file is the *procedure*; the policy is the *why*.

The one-line version: **delegate for context isolation, parallelism, or independence — never for
role-play.** Output tokens are the expensive ones, so children return folds, not transcripts.

## 0. Shell-first (measured, do this first)

Ask: *could `rg`/`awk`/`jq`/a 3-line script answer this in one call?* If yes, delegate nothing — a
30-shard aggregate task was solved solo in 5–7 s with `rg`/`awk` while an arm told to delegate it
dispatched nothing and ran slower (`research/delegation.md`). Counting, summing, listing and
joining are shell work; **understanding** is delegation work.

Calibration from this host's ledger: one child costs ~14–50 s wall and ~300–700 output tokens
before it does anything. Delegate a subtask when it is worth ≥10× that (≈3–5 min of solo work), or
when the point is independence (a different model family), or when the reading would otherwise blow
this context. Six parallel workers on 3-line edits were 9.6× slower than doing them here.

## 1. Route (10 seconds, do it before opening files)

| Situation | Route |
|---|---|
| Reads a lot, I need a digest ("where is X", inventory, survey) | `subagent` → `scout` |
| One fixed rule over many independent items | `subagent` → `bulker` |
| External evidence (papers, upstream docs) with ids | `subagent` → `researcher` |
| Mechanical change with a named check command | `subagent` → `worker`, then `verifier` |
| A claim I am about to report and I authored the evidence | `subagent` → `verifier` (different model family, fresh context) |
| Two or more subtasks on disjoint file sets, no shared hub file | `subagent` parallel `worker` |
| One file / one symbol / dependency-dense module | **solo** — contract + fold costs more than it saves |
| A workflow that would need critique at every level | **solo** — deliberation cascade (3.4× worse) |
| Long-running, needs a human-visible window, or I want a second opinion | `bin/pi-term "..."` (new terminal) or `bin/pi-term --tmux` (detached) |
| No TUI / script / cron context | `bin/pi-delegate run --agent X --task "..."` |

Cheap check: `bin/pi-delegate plan "<task>" --files N` prints the cue classification, what the
ledger knows about that (agent, bucket) cell, and a decision.

## 2. Contract (write it before dispatching; six fields)

```
GOAL: <one sentence, verifiable>
INPUTS: <exact paths / ids / question; no "the repo">
OUTPUT (fold): <the agent's shape — STATUS/CHANGED/EVIDENCE/RISKS or ANSWER/REFS/GAPS or VERDICT/...>
ACCEPTANCE: <the command or rule that decides pass/fail; required for worker>
SCOPE: <files/dirs it may touch; "read-only" for scout/verifier>
BUDGET: <turns or minutes; stop and report "blocked" rather than wander>
```

Rules: no role-play, no "think like a senior engineer"; the child gets the procedure it must follow
and the check that proves it. Least privilege lives in the agent's `tools:` line — do not hand a
scout write access "just in case".

## 3. Dispatch

- In session: `subagent` tool, one of `{agent, task}`, `{tasks:[...]}` (≤8, 4 concurrent),
  `{chain:[...]}` with `{previous}`. Prefer one dispatch over a chain; chains are for
  recon → act only.
- Parallel only when the partitions are *cohesive*: no two workers edit the same file, and shared
  hub files (configs, `__init__`, schema, lockfiles) are either left alone or given to exactly one
  worker.
- Outside a session: `pi-delegate run ...` (same fold contract, logs itself).
- A separate *interactive* chat (`pi-term`) is for work that needs iteration with a human or will
  outlive this session — not for something a scout could answer in 30 seconds.

## 4. Fold and verify

1. Read only the fold. If it is longer than the shape it should be, do not accept it as-is; the
   child failed to compress — take the refs, read them yourself.
2. Before acting on a fold, spot-check one reference (`path:line`). Cheap, catches confident garbage.
3. For anything reported as done: `verifier` on the acceptance command; the verifier must reproduce
   evidence itself and must not be the worker's own summary.
4. Then log the outcome — this is what makes the next decision better:

```sh
pi-delegate verdict pass --last --note "scout refs matched when re-read"
pi-delegate verdict fail --last --note "digest missed the socket writer in proxy.ts"
```

## 5. Keep the loop alive

- Review `pi-delegate report` at the weekly tick (it is in the maintenance service) or after ~10
  dispatches: KEEP / DROP / MEASURE per (agent, bucket).
- A policy change needs evidence: run the candidate harness arm through
  `selfimprove/run.py --subagent --arm arms/deleg.md --reps 3` and let `gate.py` decide. One
  successful dispatch is noise; three verified samples is the floor.
- When a delegation recipe keeps passing, **stop delegating it**: write it as a script or a skill
  (executable accumulation beats re-derivation — AgentFactory 2603.18000).
- Record the cycle: `mem pdsa plan|do|study|act ...`, and add the lesson to `mem`.

## Anti-patterns (each one measured as a loss somewhere in research/delegation.md)

- Multi-agent for its own sake: 6.4× energy, small task-specific accuracy gains.
- Fan-out by file count over a coupled module: communication overhead eats the speedup.
- Scout that pastes code: you paid for isolation and imported the tokens anyway.
- Worker that re-plans: the plan was the parent's job; re-planning is duplication, not diligence.
- Verifier that reads the worker's summary instead of the artefact: it verifies prose, not truth.
- Nested subagents three levels deep: every level re-pays the contract and loses the thread.
