# Delegation policy (v3.3, 2026-11-15)

How this agent decides *whether*, *what*, *to whom* and *in what order* to delegate. The prose is
the hypothesis; `delegation/ledger.jsonl` and `pi-delegate flow` are the evidence. Change a rule only
with a ledger row, an A/B run (`selfimprove/`, k≥3), or a cited paper.

Research base: `research/ai-swarm-delegation.md` (verified ids, one retraction caught) and
`research/org-delegation.md` (organizational practice mapped to agents). Short version: delegation
pays for **context isolation**, **parallelism over a verified partition**, and **independence** —
never for role-play. Output tokens are the expensive ones; children return folds, not transcripts.

## 0. The five rules everything else follows from

1. **Partition, not persona.** A dispatch is justified by a separable work item, not by a job title.
2. **One owner per artifact, one acceptance per item.** Two writers on one file is a merge conflict
   with extra steps; an item without a check is a rumour.
3. **WIP ≤ what can be integrated.** Little's law: cycle time = WIP / throughput. Four concurrent
   children is the cap; eight per fan-out is the ceiling, not a target.
4. **Contract before dispatch (Definition of Ready).** Missing ACCEPTANCE or SCOPE means not ready.
5. **Authority comes from reproduced evidence, never from an agent's name.** A fold is an address;
   the parent re-reads one reference, the verifier re-runs the command.

## 1. Delegate when (structural cues, all cheap to check)

| Cue | Why (evidence) | Agent |
|---|---|---|
| The subtask reads a lot and the parent needs a *digest* | child context dies with the task; parent keeps the fold (2510.11967; 2609.09233) | `scout` |
| One fixed rule over many independent items | item independence means zero cross-agent communication | `bulker` |
| External evidence with checkable ids | 40 abstracts would poison the parent; ids are verifiable | `scout` (evidence mode) |
| Mechanical, checkable change: named files + named command | verification converts risk into a boolean | `worker` then `verifier` |
| A claim about to be reported, authored by the judge | independence, not capability: a different family catches self-review (2609.32635) | `verifier` |
| ≥2 subtasks on **disjoint** file sets, no unowned hub file | proactive scope scheduling lifted clean integration 1/9 → 9/9 (2610.07261) | parallel `worker` + `integrator` |
| The work must be split by *phase* and one phase reverses the other | multi-agent helped extraction but hurt screening (2606.28362) | gate per phase |

**Shell-first:** if `rg`/`awk`/`jq` answers it (counts, sums, greps, joins), delegate nothing. A
30-shard aggregate was solved solo in 5–7 s; an arm told to delegate it dispatched nothing and ran
slower. Counting is not a reading problem.

## 1c. Routing signals: Inkling decides the route, the regex is the fallback, Laya advises (measured)

The three decisions — *when* (solo / delegate / window), *how* (which route), *who* (which agent) —
are made by the cue classifier in `decide()` plus the ledger posterior. **Since 2026-11-17 the 7-way
route is decided by `inkling-2-small`** (`pi-delegate route`), not by the regex: it won a 22-case
held-out set 21/22 (95%) to the regex's 9/22 (41%), with 12 discordant pairs and inkling right on all
twelve (sign test p≈2.4e-4). The rule was written before the run (`delegation/route-eval-heldout.json`
`_rule`) and every clause was met. **Laya is still not in the decider path** — it lost the only fair
comparison (25%, `delegation/route-eval.py`, 24 tasks, 2026-11-15).

| signal | Laya zero-shot | inkling-2-small | regex | note |
|---|---|---|---|---|
| 7-way route | 25% (6/24) | **79–83%** (19–20/24) | 62% (15/24) | pairs disagree on 7 cases, inkling ahead 6:1 (sign test p=0.125 — direction, not proof) |
| `visible` (window?) | 88% (21/24) | **100%** (24/24) | cue added | both positives caught, no false positive |
| `wide_reading` | 62% (15/24) | **88–96%** (21–23/24) | — | the use that pays today: raw 1M ctx, no subagent prompt |
| `splittable` | 29% (7/24) | **79–88%** (19–21/24) | — | Laya's worst gate; the model's best argument |

Held-out run, authored fresh on 2026-11-17 and never used for tuning (`route-eval-heldout.json` +
`-result.json`): 7-way **inkling 21/22 (95%) vs regex 9/22 (41%)**, identical over two runs;
`visible` 22/22, `wide_reading` balanced 0.80 (2 misses, both many-small-file bulk work),
`splittable` balanced 0.87–0.89 with **4 false positives, all on many-small-file work** (h14 h15 h18
h19: "1,200 tickets", "300 markdown files", "8 vendored libraries"). Latency p50 2.5 s / p90 8.0 s,
$0.00018 per case. The regex's failure is structured, not noise: on the held-out set it missed **all
four** `worker` cases (said solo), **all three** `parallel_workers` cases (said solo/scout), 2 of 3
`bulker` and 2 of 3 `window` — the routes where a wrong decision costs the most.

So: **the `visible` probe is the one usable Laya signal.** `pi-delegate route --laya` prints it and
suggests `pi-term` at p≥0.7; the `window` regex cue remains the decider, and a disagreement is logged,
not obeyed. The 7-way answer is printed for the record and never overrides the regex.

**Inkling's place now (the route decider, with guards):**
- `pi-delegate route "<task>"` calls `inkling-2-small` (2.5 s p50, ~$0.0002) and uses its answer as
  `route:`; the regex and its buckets are printed under it, and a disagreement says so. Guards, all
  exercised: any call error/timeout/neutralised answer (not one of the 7 routes) falls back to the
  regex and the command still exits 0; `routes.jsonl` memoises by `task_sha`, so a repeat task is
  0.2 s and offline (the first call is the only one that pays); `PI_ROUTE_INKLING=0` or
  `--no-inkling` restores the regex decider for offline work and for the local rails.
- **Not promoted:** the binary gates. `splittable` stays advisory because its held-out false positives
  are all cheap-to-fan-out bulk work — obeying it would buy parallel workers for a `bulker` job.
  `visible` is already fully caught by the regex cue plus Laya's advisory probe. `wide_reading` is
  good enough (0.80 balanced) to *suggest* `scout` on big-text work, not to override the route.
- **Wide reading / bulk typing**: where Laya was wrong by design (`splittable` 29%, `wide` 62%), one
  Inkling call on the whole text beats Laya plus a subagent prompt — a 200k-token read costs ~$0.03 at
  1M ctx. Reach for it before `laya-label` when the items are few and the cost of a wrong label is high.
- It does **not** replace `local-batch`: that rail is offline and free, and independence from cloud
  models is the point of it; Inkling is escalation residue, in the same rung as `bulker` and below it.
- The bar it cleared is the bar a `fit()` must still clear: ≥5 labels/route from `routes.jsonl`
  **and** a held-out win, with the rule written before the run. A future demotion needs the same
  evidence in reverse — `pi-review` re-runs `route-eval.py` and `--cases route-eval-heldout.json`
  and compares against `route-eval-heldout-result.json`; a held-out drop below the regex for two
  runs reverts `PI_ROUTE_INKLING=0` and files a bug (`pi-agenda bug`).

How Laya earns the route later: every `route --laya` appends to `delegation/routes.jsonl`;
`pi-delegate route-report` reports labels per route and says when there are ≥5 per option (the
`fit()` floor). At that point fit on the labels and A/B against the regex on a held-out set; a fit
that beats 54% on held-out cases becomes the decider, and only then. Until then, hybrid use (Laya
when confident, regex otherwise) measured **no gain** (54% at any threshold from 0.3 to 0.6, before
the `window` cue; the regex is 62% now).

## 1d. Targets are heterogeneous — cloud families, local rails, Laya

Delegation does not mean “the same model in a fresh context”. The roster is deliberately spread
across families, and the machine has local targets that do not pay for tokens at all.

| target | model | why this one |
|---|---|---|
| `scout` | `~google/gemini-flash-latest` | cheap long-context digest; returns refs, not bodies |
| `worker` | parent default (`deepseek-v4.1-flash`) | scoped edits; cheap output tokens |
| `verifier` | `anthropic/claude-haiku-5.5` | **different family on purpose** — independence is the value, not capability (2609.32635) |
| `integrator` | `anthropic/claude-haiku-5.5` | seam judgement after a fan-out; same family as verifier is fine here |
| `bulker` | `~deepseek/deepseek-v4-flash-latest` | one rule, many rows; the rule is in the contract |
| `tester` | `anthropic/claude-haiku-5.5` | break-it lens; read-only on product code, writes only scratch tests |
| `redteam` | `~google/gemini-flash-latest` | different family again: abuse/threat-model lens, proof-of-concept only |
| `debator` | `~google/gemini-flash-latest` (opposing side run on `anthropic/claude-haiku-5.5` via `--model`) | adjudicates a *design* choice: steel-mans both sides from numbers, names the falsifier and the decision rule. Measured 2026-11-16: 6 dispatches, $0.36, and two of three planned fixes were changed by the opposing side's arithmetic (a median-of-bimodal FAIL was an artefact; raising the brief budget was the wrong lever) |

Roster discipline, measured 2026-11-16: `bulker` and `redteam` had **never been dispatched** in the
week after they were written, and `pi-review` proposed deleting them. One real dispatch each —
bulker classifying the window's 57 agenda rows, redteam threat-modelling the text channel — found
a CRITICAL shell injection that four tester panels and six debators had not (their lenses were
correctness and design, not abuse). An unused agent is a hypothesis, not a capability: dispatch it
once on real work or delete it.

**A model change is a policy change.** The ledger posterior is per model and context bucket
(CADMAS-CTX 2604.17950); swapping a child's model silently invalidates the cell. `pi-delegate run`
resolves the agent's own model and strips inherited `PI_*` for exactly this reason.

**Local targets (this host, measured 2026-11-15):**

| rail | what it is | measured | use for |
|---|---|---|---|
| `laya` | 421M typed-decision model (choice/score/noul) | ~2 s/call warm, 0 tokens | routing hints (`visible`), bulk labelling, guard presets |
| `local-gen` | one-shot GGUF batch, no Pi harness | 0.7 s/item warm, ~22 s cold | <20 items, offline, one fixed rule |
| `local-batch` | resumable bulk + cross-model agreement gate | 620–3,700 items/h; 16/16 precise at 40% coverage (26/26 with Laya at 65%) | hundreds+ items; the escalation file is the residue for cloud |
| Pi subagent on `local/*` | the harness wrapper | **397 s for a 2-token reply** (6.9k-token prompt at ~17 t/s prefill) | **not used** — `pi-delegate run` refuses it unless `--allow-local` |

Rule: **local does the bulk, cloud sees the residue.** Local is for offline/unattended/free work
where the answer is checkable by agreement or a cheap rule; cloud is for judgement, verification,
formatting the local models fail, and anything the parent must trust without a second source. Never
put the parent session on a local model (the harness prompt alone is minutes of prefill). The live
list is `pi-delegate targets`; per-model spend is in `pi-delegate flow`.

## 1e. Tester panels: diversity is assigned, not assumed

The roster's testers are `tester` (functional/adversarial, technique-driven) and `redteam`
(security/abuse). A panel is 2–4 testers on **disjoint lenses**, never 2–4 copies of "test this".

Why (research: `research/tester-diversity.md`):

- Hong & Page 2004 — diverse moderate heuristics beat the best homogeneous ones, but the effect is
  conditional (2022 replication: "most of the time"). Diversity must sit **in the failure space**,
  so lenses are assigned by failure class, not by job title.
- Knight & Leveson 1986 — independently built versions fail coincidentally far above chance. Same
  model, same spec, same hints ⇒ correlated blind spots. Force *different family, different
  starting artifact, no shared findings before the merge*.
- Woolley 2010 — group performance tracks equal airtime and social sensitivity, not average
  ability. Equal budget per tester; the loudest fold does not win.
- Itkonen et al. 2007/2013 — exploratory sessions out-find scripted cases, and tester knowledge
  (a product model, not a file list) decides what gets explored. Hence the contract requires
  RISK/TECHNIQUE/ORACLE, not "review".
- Papadakis et al. ICSE 2018 — mutation score and coverage only weakly stand in for real fault
  detection; a green suite is not evidence. Testers must mutate once and prove the suite red.

Rules:

1. **Panel of one is solo work** — a second tester must have a different lens or it is a duplicate.
2. **Contract fields**: RISK AREA / TECHNIQUE / ORACLE / SCOPE / BUDGET, plus the fold shape
   (`delegation/contracts.md` §7). "Test everything" is not ready.
3. **Findings need a repro that runs twice**; unreproduced items are HYPOTHESES and are not counted.
4. **No fixing on the panel** — fixes come back as `worker` tasks; the panel's verifier is separate.
5. **Close the loop**: every finding becomes a scripted case or is dropped with a reason; the merge
   dedupes by root cause, and the panel gets one `verdict` row with unique root causes.
6. **Caps**: ≤4 testers, ≤4 concurrent (WIP rule §0.3), and the ≥10× floor still holds — a panel
   on a 3-line change is theatre.

`pi-delegate panel --target <path> --risk "<what breaks expensively>"` prints the ready dispatch
set. Routing note: `tester` is a new regex route (`breaking` cue) and is **unmeasured**; it is
behind `worker` in the order so patch tasks keep routing to `worker`. It enters the Laya decider
only after ≥5 labelled cases per lens and a held-out win (§1c).

## 2. Measured thresholds (this host, k=3, selfimprove/runs 2026-11-14)

- **Dispatch floor ≈ 14–50 s wall and ≈ 300–700 output tokens per child.** Six parallel `worker`s
  on 3-line files: 187.5 s vs 19.6 s solo (9.6× wall, 7.9× output tokens) at equal pass.
- **Delegate a subtask when it is worth ≥ ~10× the floor** (≈3–5 min of solo work), or when
  independence is the point, or when the reading would otherwise blow this context.
- **Re-verify the floor** with `pi-delegate flow` after any model or harness change; the number is
  a property of this machine, not of the literature.

## 3. Do not delegate when

- The parent would hold the same context anyway (homogeneous MAS ≈ one agent with KV reuse,
  2601.12307; budget-matched single agent within CI, 2608.23395).
- The task is one file / one symbol (contract + fold exceed the saving).
- The split is by file count over a coupled module (gains come from cohesion, 2606.00953).
- The parent cannot specify the question or check the answer — delegation then degrades accuracy
  (2611.16526). Write the spec or do it yourself.
- The value would be a style role ("architect", "reviewer persona") on the same model — a prompt,
  not a delegation.
- You would nest deliberation: critique loops at every level were up to 3.4× worse at 1.8–2.7× the
  tokens (2605.16205). One level, thin children, judgement in the parent.
- The subtask's success cannot be checked in under a minute. No check → no dispatch.
- The "win" is a retracted paper. Check `comment` for withdrawn/retracted before citing
  (2511.15755: 100% vs 1.7% claim withdrawn after a code audit).

## 4. Work intake — the org mapping

Organizations get delegation right with a backlog, a definition of ready, an owner, WIP limits, an
integration point and a retrospective. This harness has the same artefacts; use them by name.

| Organizational artefact | Harness artefact | Rule |
|---|---|---|
| Backlog / epic | `pi-agenda` tasks and goals | p1 bugs preempt; a new recurring item is a row, not a system |
| Ticket / issue | one dispatch row in `delegation/ledger.jsonl` | id = `task_sha`; never rewritten, superseded by verdict |
| Claim / assignee lock | `bin/pi-claim` + SCOPE field | claim the tree before the first write; one writer per file |
| Definition of Ready | `pi-delegate plan` contract check (6 fields) | <6 fields → not dispatched |
| WIP limit | `MAX_CONCURRENCY=4`, `MAX_PARALLEL_TASKS=8` | count `pi-delegate flow`; don't raise the cap to hide a stall |
| Definition of Done | fold shape + verdict row | "completed" ≠ correct; only a verdict closes the item |
| Code review | `verifier` on the acceptance command | evidence, not the worker's summary |
| Integration / release | `integrator` after a fan-out | owns hub files, runs the whole-task check |
| Retrospective | `pi-delegate flow` + `pi-delegate report` | weekly; proposals go through `selfimprove/gate.py` |

## 5. Partition rules (pre-dispatch, non-negotiable)

1. **Declare the shards** as file sets and run
   `pi-delegate partition --shard a=... --shard b=...` (add `--strict` for write work).
   Exit 2 = no fan-out.
2. **No file in two shards.** Hub files (`Cargo.toml`, `mod.rs`, `__init__.py`, lockfiles, schemas,
   CI workflows, migrations) belong to exactly one shard, or to the integrator.
3. **Keep a directory whole** when it shares an implicit hub (`mod.rs`, `__init__.py`); a shard is a
   cohesive unit, not a file count.
4. **Order merges along the producer→consumer graph**; a consumer starts only after its producer's
   interface is frozen (2610.07261).
5. **Shard size:** 1–3 files or one cohesive module, and each shard's solo cost ≥10× the floor.
   Six 3-line edits are one solo task, not six children.
6. **Cap:** ≤4 concurrent, ≤8 per fan-out, one level deep. More is a queue, not a swarm.

## 6. Roles and decision rights (RACI-shaped, no role-play)

| Role | Decides | Executes | Checked by | Tools |
|---|---|---|---|---|
| parent | scope, partition, acceptance, accept/reject | integration judgement, final report | own re-read + verifier | all |
| `scout` | nothing (read-only) | search, digest | parent re-reads one ref | read-only |
| `bulker` | nothing (rule is fixed by parent) | applies one rule to N items | count check (`COUNT: rows/items`) | read-only |
| `worker` | nothing (contract is fixed) | scoped edit + acceptance command | `verifier` | read+write in scope |
| `verifier` | pass/fail on evidence | re-runs the check | parent reads the evidence lines | read-only |
| `integrator` | seam fixes only | merge, whole-task check | verifier / parent | read+write, after workers |

Rules: the parent is the only **accountable** role; a child is **responsible** for its item and
**informed** of nothing else. A verifier may veto on evidence, never on taste. No agent gets write
access "just in case" — `tools:` frontmatter is the authorization (2611.08905; 2606.31174 found no
model above 50% workspace-permission precision, so the parent writes SCOPE explicitly).

## 6b. Human-visible work — window lifecycle

A separate terminal chat, a build window or a watch window is a *delegation with a human in the
loop*. It follows the same rules as a subagent: it is opened for a named reason, it is placed so it
can be seen, and it is closed when the work is done.

- **Open** with `bin/pi-term --name <slug> [--cwd DIR] "<task>"`. It launches the terminal, waits
  for the window to map, tiles the desktop (`pi-tile`, the same primitive `pi-shot` uses), focuses
  it, and appends a row to `~/.local/state/pi-win/terms.jsonl`. The title is `pi: <slug>: <task>`,
  so the window is identifiable in `pergola list` and in a screenshot.
- **Use `--exec "<cmd>"`** for a non-chat window (test run, build, log watch). Use `--tmux` for work
  that must survive the window (ssh, long run); it has no tile to place.
- **Cap: two visible `pi-term` windows at once.** More is a queue, not parallelism (Little's law);
  close or hand off before opening a third.
- **Close is the default.** The terminal exits when its command exits; a tmux session dies when the
  command exits. `--keep` is an explicit exception and must be named in the report, with the reason
  the window outlives the task.
- **Explicit close** with `pi-term --close <id|title|session>` when the work is done but the chat is
  idle; `pi-term --reap` closes registered targets whose work is gone or older than the 12 h TTL
  (`--ttl`), plus `pi-*` tmux sessions whose pane is no longer pi. The 6 h agenda row `window-reap`
  runs it; `pi-preflight` check `windows` fails on an orphan, so a forgotten window is a red check,
  not a habit.
- **A window is evidence only while it exists and is tiled.** Take the `pi-shot` before closing it;
  after the close, the claim must cite the shot log (`win-log.jsonl`), not the window. The
  tiling/capture rules are `skills/windows/SKILL.md`.
- **No orphan windows across a handoff.** If the task moves to another session, the report names the
  window and whether it stays open; the next session runs `pi-term --list` before opening its own.

## 7. Contract and fold (Definition of Ready / Done)

Six fields, never implied: **GOAL** (one verifiable sentence), **INPUTS** (paths/ids, no "the repo"),
**OUTPUT** (fold shape), **ACCEPTANCE** (command or citation rule), **SCOPE** (files/dirs, read-only
or write), **BUDGET** (turns/minutes; stop and report blocked). Copy-paste templates:
`delegation/contracts.md`.

Fold shapes: `STATUS/CHANGED/EVIDENCE/RISKS` (worker), `VERDICT/CHECKED/EVIDENCE/FIX` (verifier),
`ANSWER/REFS/GAPS` (scout), rows + `COUNT: n/N` (bulker), `STATUS/MERGED/CHECK/RISKS` (integrator).
≤60 lines; refs (`path:line`) not copies; no transcripts. Output tokens cost 30–1000× input
(2605.27787); memory injection grows linearly with depth and is 27.6% of cost at depth 6
(2609.23790).

## 8. Escalation ladder (cheapest instrument that can answer)

`shell` → `laya`/`local-batch` (typed decisions, offline) → `bulker` → `worker` → parent →
`verifier` (different family) → human. Escalate when: two attempts fail the same check; confidence
is below the threshold that matters; the partition gate fails twice; the claim will be reported; or
the work needs a decision the parent cannot make from the evidence. Do not escalate to a bigger
model to compensate for a missing acceptance check (2411.07464: cheap base + selective escalation
cut cost 94.2% while raising success).

## 9. Learn — the loop (PDSA)

1. Every dispatch appends a ledger row (extension and `pi-delegate run` alike).
2. The parent records the real outcome: `pi-delegate verdict pass|fail --sha ... --note ...`.
   `expire` closes rows nobody checked; an unverified cell is reported as MEASURE, never success.
3. Weekly: `pi-delegate flow` (throughput, cycle time, first-pass yield, rework, cost per verified
   pass) and `pi-delegate report` (per agent×bucket posterior, KEEP/DROP/MEASURE).
4. A proposal is a hypothesis: A/B it through `selfimprove/run.py` + `gate.py` (k≥3) before it
   becomes a rule here.
5. A recipe that keeps passing is **promoted to code** (script/skill), not re-delegated
   (2603.18000: executable accumulation beats textual experience).
6. Every closed cycle writes `mem pdsa` (Plan/Do/Study/Act) and, if durable, a `mem add`.

Cadence: `delegation-retro` on the agenda (weekly); the `flow` JSON is the Study artefact.

## 10. Changelog

- **v1 (2026-11-14)** — initial policy from the paper sweep; 4 agents; ledger + posteriors +
  verdicts; A/B flag `run.py --subagent`.
- **v2 (2026-11-14)** — two falsified hypotheses: recon delegation lost to the shell; six parallel
  3-line workers were 9.6× slower. Added shell-first, the ≥10× floor, and the ≥3-verified-samples
  rule.
- **v3 (2026-11-15)** — org-shaped protocol: Definition of Ready (6 fields, checked by `plan`),
  partition gate (`partition`, from 2610.07261's 1/9 → 9/9), WIP caps, `integrator` role,
  RACI-shaped decision rights, escalation ladder, flow/economics metrics (`flow`), retraction
  guard. Evidence: 19 verified arXiv ids + org literature; one retracted claim caught and barred.
- **v3.4 (2026-11-16)** — tester panels (§1e): `tester` + `redteam` agents, assigned disjoint
  lenses (boundaries/state/oracle/hostile-input/faults/compat/security/recovery), equal budget,
  no shared findings before the merge, repro-or-hypothesis, test-the-test. `pi-delegate panel`
  emits the dispatch set. Evidence: `research/tester-diversity.md` (5 verified ids, 1 replication).
- **v3.3 (2026-11-15)** — heterogeneous targets (§1d): the roster's four cloud families, plus the
  local rails (laya / local-gen / local-batch) and a measured refusal of Pi subagents on `local/*`
  (397 s for a 2-token reply). Added `pi-delegate targets`, per-model spend in `flow`, and the
  `--allow-local` guard.
- **v3.2 (2026-11-15)** — routing signals measured (§1c): Laya 7-way 25% vs regex 54%, hybrid no
gain; `visible` 88% so it advises the window decision only; added the `window` cue + WINDOW route,
`pi-delegate route` / `route-report` and `delegation/route-eval.py` to accumulate labels for a
future `fit()`.
- **v3.1 (2026-11-15)** — window lifecycle (§6b): `pi-term` now tiles the window after it maps,
  records it, closes on command exit, and reaps orphans/stale targets (`--list`, `--close`,
  `--reap`, `--ttl`); two-window cap; 6 h `window-reap` agenda row; `pi-preflight` check `windows`.
  Rationale: the org rule is “a window you open is a window you place and a window you close”,
  and an untracked window is the visual equivalent of an unverified fold.
