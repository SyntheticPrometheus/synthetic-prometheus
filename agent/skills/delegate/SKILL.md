---
name: delegate
description: Decide whether, what, to whom and in what order to delegate — partition disjoint scopes, write the six-field contract, dispatch subagents or a parallel fan-out, integrate, verify by reproduced evidence, and log the verdict so the policy improves. Use before any task that reads widely, splits into independent parts, needs an independent check, or would otherwise flood this context; also when tempted to do a multi-agent role-play.
---

# Delegating work

Policy of record: `~/.pi/agent/delegation/policy.md` (v3). Contracts: `delegation/contracts.md`.
Ledger: `delegation/ledger.jsonl`. Roster: `~/.pi/agent/agents/*.md`. This file is the *procedure*.

One line: **delegate for context isolation, a verified partition, or independence — never for
role-play.** Output tokens are the expensive ones; children return folds, not transcripts.

## 0. Shell-first (measured)

Ask: *could `rg`/`awk`/`jq` answer this in one call?* If yes, delegate nothing. A 30-shard aggregate
was solved solo in 5–7 s; an arm told to delegate it dispatched nothing and ran slower. Counting,
summing, listing and joining are shell work; **understanding** is delegation work.

Dispatch floor on this host: ~14–50 s wall and ~300–700 output tokens per child. Delegate a subtask
when it is worth ≥10× that (≈3–5 min solo), or when independence is the point, or when the reading
would blow this context. Six parallel workers on 3-line edits were 9.6× slower than doing them here.

## 1. Route (before opening files)

| Situation | Route |
|---|---|
| Reads a lot, I need a digest ("where is X", inventory, survey) | `subagent` → `scout` |
| One fixed rule over many independent items | `bin/laya-label` / `bin/local-batch` first; `bulker` for residue |
| <20 items, offline, one fixed rule | `bin/local-gen` (no harness, 0.7 s/item warm) |
| External evidence (papers, upstream docs) with ids | `scout` evidence mode; verify ids yourself |
| Mechanical change with a named check command | `worker`, then `verifier` |
| A claim I am about to report and I authored the evidence | `verifier` (different model family, fresh context) |
| Two or more subtasks on disjoint file sets, no unowned hub file | parallel `worker`, then `integrator` |
| Work whose phases reverse each other (screen vs extract) | gate per phase — one agent per phase, not one uniform pipeline |
| One file / one symbol / dependency-dense module | **solo** |
| A workflow that would need critique at every level | **solo** — deliberation cascade (3.4× worse) |
| Long-running, human-visible, or second opinion | `bin/pi-term --name <slug> "..."` — tiles itself, closes on exit |
| No TUI / cron / script | `bin/pi-delegate run --agent X --task "..."` |

Cheap check: `bin/pi-delegate plan "<task>" --files N` prints cues, the DoR field count, current WIP,
and the ledger's posterior for that agent×bucket cell. `pi-delegate route --laya "<task>"` adds the
local second opinion: the regex still decides; Laya's only usable signal is `visible` (window), and
it is advisory (policy §1c).

## 2. Intake: ready → partitioned → dispatched

1. **Definition of Ready** — six fields present (`GOAL/INPUTS/OUTPUT/ACCEPTANCE/SCOPE/BUDGET`). If
   `plan` says <6, fill them or do it solo. No ACCEPTANCE → no dispatch.
   **Goldfish rule (EGM, 2026-10)** — INPUTS are paths, never "the conversation so far": a child that
   inherits my framing cannot find my blind spot. For a doc a child must *act on* (policy, skill,
   runbook), spend one zero-context `scout` pass asking it to paraphrase the doc under two headings
   before I treat the doc as authoritative — an unparaphrasable section is a Blocker. Measured: 9 of
   10 findings on `delegation/policy.md` were real gaps, 1 min per doc (`research/egm.md`).
2. **Partition** (only for fan-out) — declare shards and run the gate:

   ```sh
   pi-delegate partition --cwd <dir> --shard a=src/a --shard b=src/b --strict
   ```

   Exit 2 = stop. No file in two shards; hub files (`Cargo.toml`, `mod.rs`, `__init__.py`,
   lockfiles, schemas, CI, migrations) owned exactly once; keep a directory whole when it has an
   implicit hub; order merges producer→consumer.
3. **WIP** — ≤4 concurrent, ≤8 per fan-out, one level deep. `flow` shows the real WIP; do not raise
   the cap to hide a stall.

## 3. Contract (write it before dispatching)

Six fields, never implied (templates in `delegation/contracts.md`):

```
GOAL: <one sentence, verifiable>
INPUTS: <exact paths / ids / question; no "the repo">
OUTPUT (fold): <STATUS/CHANGED/EVIDENCE/RISKS | ANSWER/REFS/GAPS | VERDICT/... | rows + COUNT>
ACCEPTANCE: <command or citation rule that decides pass/fail>
SCOPE: <files/dirs it may touch; "read-only" for scout/verifier; hub file owner>
BUDGET: <turns or minutes; stop and report "blocked" rather than wander>
```

Least privilege lives in the agent's `tools:` line — never hand a scout write access "just in case".

## 4. Dispatch

- In session: `subagent` with `{agent, task}`, `{tasks:[...]}`, or `{chain:[...]}`. Prefer one
  dispatch over a chain; chains are for recon → act only.
- Parallel only after the partition gate passes. One worker per shard; no shared hub file.
- Outside a session: `pi-delegate run ...` (same contract, logs itself).
- **Local models are a target, not a subagent.** `run` refuses `local/*` (measured 397 s for a
  2-token reply); use `local-gen` / `local-batch` / `laya` instead. `pi-delegate targets` lists every
  target and its model.
- A separate interactive chat (`pi-term`) is for work that needs a human in the loop or outlives
  this session — not for a 30-second scout answer.

## 4b. Windows: open tiled, close when done

A terminal chat, build or watch window is a delegation with a human in the loop; it follows the same
lifecycle as a child.

- `pi-term --name <slug> [--cwd DIR] "<task>"` opens it, waits for the map, **tiles** (`pi-tile`),
  focuses it, and records it. `--exec "<cmd>"` for a non-chat window; `--tmux` when it must survive
  the window (no tile).
- **Cap two visible windows.** A third is a queue; close or hand off first.
- **Closing is the default**: the terminal/session exits with its command. `--keep` is explicit and
  named in the report. `pi-term --close <id|title>` for an idle chat; `pi-term --reap` for targets
  whose work is gone or older than the TTL (12 h), plus `pi-*` tmux sessions whose pane is no longer
  pi. The 6 h `window-reap` agenda row runs it; `pi-preflight` `windows` fails on an orphan.
- **Shoot before you close.** A window is evidence only while it exists and is tiled; after the
  close, cite the shot log, not the window. Tiling/capture rules: `skills/windows/SKILL.md`.
- **No orphan across a handoff**: name the window and its fate in the report; the next session runs
  `pi-term --list` before opening its own.

### Worked example — one visible window per surfaced item (owner, 2026-11-15)

When a session surfaces several independent fixes, do not grind them in the parent and do not
role-play a team: write one six-field contract per item (each naming its agenda task id) and give
each its own parallel pi session in its own tiled window.

```sh
# per item: one window, one task id, one disjoint scope, acceptance command in the prompt
DISPLAY=:0 bin/pi-term --cwd ~/.pi/agent --name burn-runway "$(cat /tmp/dispatch/p74.txt)"
```

What made it work (measured that evening): 4 windows opened tiled by `pi-term` (it waits for the
map and calls `pi-tile`), 4 `pi` jobs live in the same tree, each child ran `pi-claim reserve` on its
own paths, and the two first folds produced single-file commits (`f8061ab` touched only
`bin/pi-session-watch`, `6ac737b` only `bin/pi-cadence`) — the partition held. The prompt carries:
the task id, the exact acceptance command with "paste its output", the scope plus "never `git add
-A`", a 10–20 min budget, and "`pi-agenda done <id>` only if the evidence is real, then print the
fold and stop, leaving the window open". Cap at 4 concurrent; a fifth is a queue. `bin/pi-shot`
proves the tiles exist; the parent re-runs each acceptance command before believing the fold.

**The loop, not the batch (owner, 2026-11-15).** A verified fold is the end of that child: close its
window (`pi-term --close <id>`) and `pi-claim reap` so its path reservations drop, then open a new
window for the next item as it surfaces. Keep the fan-out alive; never leave four finished chats
sitting as decoration, and never close the parent chat. Before dispatching, `pi-claim check <tree>
<paths>` — if a live session already reserved the path, its window is the one working that item (a
`text-dedupe` window was already on `bin/pi-text` when #79 came up, so #79 was not re-dispatched).

## 5. Integrate (the step everyone skips)

After a fan-out, dispatch `integrator` with the shard folds, the hub files, and the **whole-task**
acceptance command. Integration is a named responsibility: hub files, imports, registration,
ordering, conflict resolution. If two shards changed the same contract, stop — the partition was
wrong; fix ownership, do not let the integrator guess.

## 6. Fold and verify

1. Read only the fold. Longer than its shape → do not accept it; take the refs and read them.
2. Before acting, spot-check one reference (`path:line`) or re-fetch one id. Cheap, catches
   confident garbage.
3. For anything reported as done: `verifier` on the acceptance command; it must reproduce the
   evidence itself, not read the worker's summary.
4. Authority comes from evidence, not from the agent's name: an orchestrator that trusts a
   subagent's identity over contradicting evidence acted on the risky answer 72% of the time
   (2609.32635). Reproduce, then believe.
5. **One re-audit cap** (EGM): a review gets one re-review after fixes. Past that, record the
   residual findings as accepted trade-offs and move on — a second loop is negotiation, not
   verification.
6. Log the outcome — this is what makes the next decision better:

```sh
pi-delegate verdict pass --last --note "scout refs matched when re-read"
pi-delegate verdict fail --last --note "digest missed the socket writer in proxy.ts"
```

## 7. Keep the loop alive (weekly)

```sh
pi-delegate flow  --days 30          # throughput, cycle time, first-pass yield, rework, $/verified pass
pi-delegate report                   # per agent×bucket posterior + KEEP/DROP/MEASURE
```

- KEEP / DROP / MEASURE per cell; a cell with mostly unverified rows is MEASURE, never success.
- A policy change needs evidence: `selfimprove/run.py --subagent --arm arms/deleg-par.md --reps 3`
  and let `gate.py` decide. One dispatch is noise; three verified samples is the floor.
- A recipe that keeps passing is promoted to a script or skill and stops being delegated
  (2603.18000: executable accumulation beats textual experience).
- Record the cycle in `mem pdsa` and the durable lesson in `mem`.

## Anti-patterns (each measured as a loss)

- Multi-agent for its own sake: 6.4× energy, task-specific accuracy gains (2610.03010).
- Fan-out by file count over a coupled module: communication overhead eats the speedup.
- Fan-out without the partition gate: 1/9 clean integration vs 9/9 with upfront scopes (2610.07261).
- Scout that pastes code: you paid for isolation and imported the tokens anyway.
- Worker that re-plans: the plan was the parent's job.
- Verifier that reads the worker's summary: it verifies prose, not truth.
- Reviewer handed the conversation instead of the document: it audits my assumptions back at me.
- Nested subagents three levels deep: every level re-pays the contract and loses the thread.
- Citing a retracted paper because the abstract had a good number (2511.15755).
