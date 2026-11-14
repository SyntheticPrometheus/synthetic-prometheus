# Delegation policy (v2, 2026-11-14)

How this agent decides *whether*, *what* and *to whom* to delegate. Terminal state of the policy is
the ledger in this directory; the prose here is the hypothesis, the ledger is the evidence. Change a
rule only together with a ledger row or an A/B run that justifies it (`selfimprove/`, k≥3).

Research basis: `research/delegation.md` (mem #47). Short version: delegation pays for **context
isolation** and **parallelism**, not for role-play; output tokens are the expensive ones, so children
must return folds, not transcripts; hierarchical deliberation is worse than flat execution.

## 1. Delegate when (structural cues, all cheap to check)

| Cue | Why (evidence) | Agent |
|---|---|---|
| The subtask reads a lot and the parent needs a *digest* (repo-wide search, inventory, "where is X", log/config survey) | child context dies with the task; parent keeps only the fold (Context-Folding 2510.11967). Subagent execution beats loading the same procedure as a skill when the contract is crisp (2609.09233) | `scout` |
| One fixed rule over many independent items (triage N files, extract M rows) | item independence means zero cross-agent communication; rule stays in the contract, model only applies it | `bulker` |
| External evidence gathering (papers, upstream docs) with citations | 40 abstracts would poison the parent context; ids are checkable, so trust is cheap | `researcher` |
| The work is *mechanical and checkable*: named files, named verification command | verification converts delegation risk into a boolean; the parent keeps judgement | `worker` then `verifier` |
| A claim that matters is about to be reported, and the author of the claim is also the judge | independence, not capability: a separate context with a different model family catches the failure modes a self-review rationalises (`verifier`) | `verifier` |
| ≥2 subtasks that touch **disjoint** file sets and share no hub file | partition the graph; shared/hub files must stay in one agent or context transfer eats the gain (Cohesion-aware Coder 2606.00953) | parallel `worker` |

## 1b. Measured thresholds (this host, k=3, selfimprove/runs 2026-11-14)

The literature says delegation pays *per subtask* but never says how big a subtask must be. Measured
here:

- **dispatch floor ≈ 14–50 s wall and ≈ 300–700 output tokens per child** (spawn + model latency +
  contract + fold). Six parallel `worker`s fixing 3-line files were 187.5 s vs 19.6 s solo (9.6×
  wall, 7.9× output tokens, 3.9× cost) at identical pass rate.
- **counting/extraction is not a reading problem.** A 30-shard, 1,200-line aggregate task was solved
  solo in 5–7 s with `rg`/`awk`; an arm instructed to delegate it dispatched *nothing* and was
  slower anyway.

So: **shell-first** — if a one-liner in the parent's own tools answers it (counts, sums, greps,
joins), delegate nothing. Delegate only when the subtask is content that must be *understood*, or is
worth ≥ ~10× the dispatch floor of solo work (≈ 3–5 min), or when independence (different model
family) is the point.

## 2. Do not delegate when

- **The parent would hold the same context anyway.** Homogeneous multi-agent workflows are matched
  by one agent with KV-cache reuse (OneFlow 2601.12307); delegation then only adds contract + fold
  tokens.
- **The task is one file / one symbol.** Contract overhead exceeds the saving (`SOLO_CUES` in
  `bin/pi-delegate`).
- **The work is dependency-dense** or the "split" is by file count over a tightly coupled module
  (same paper: gains come from cohesion, not from agent count).
- **The value would be a style role** ("architect", "reviewer persona") on the same model — that is
  a prompt, not a delegation; it burns tokens and buys nothing.
- **You would nest deliberation.** Putting critique/self-improvement loops at every level of a
  hierarchy degraded results up to 3.4× while using 1.8–2.7× more tokens (deliberation cascade,
  2605.16205). One level of delegation, thin children, judgement in the parent.
- **The subtask's success cannot be checked** in under a minute. Delegation without verification is
  a rumour; either add a check or do it yourself.

## 3. Contract (what every dispatch must carry)

Six fields, never implied: **inputs** (paths, ids, exact question), **outputs** (fold shape, see
§4), **acceptance** (the command or citation rule that decides pass/fail), **scope** (files/dirs it
may touch), **forbidden** (what not to do: refactors, other dirs, network), **budget** (turns/time).
Least privilege is part of the contract: each agent's `tools:` line is its authorization
(2611.08905 learns exactly this mapping from skills and gains 24pp on workspace permissions).

## 4. Fold discipline

Children return a fixed shape (`STATUS/CHANGED/EVIDENCE/RISKS`, `VERDICT/CHECKED/EVIDENCE/FIX`,
`ANSWER/REFS/GAPS`) and nothing else. Rules that follow from the cost asymmetry (output tokens cost
30–1000× an input token, 2605.27787):

- no file bodies, no transcripts, no "here's what I did" narration;
- references (`path:line`) instead of excerpts; ≤20 refs;
- the parent re-reads what it needs itself — a fold is an address, not a copy;
- ≤60 lines per fold. Anything longer is the child failing to compress.

## 5. Learn (the loop)

1. every dispatch appends a row to `ledger.jsonl` (extension and `pi-delegate run` alike);
2. the parent records the real outcome with `pi-delegate verdict pass|fail --sha <task_sha>`;
3. `pi-delegate report` keeps a Beta(1+pass, 1+fail) posterior per (agent, cue bucket) and ranks by
   `mean − sd` (risk-aware routing, CADMAS-CTX 2604.17950), and emits KEEP / DROP / MEASURE proposals;
4. a proposal is a *hypothesis*, not a change: it goes through `selfimprove/run.py` + `gate.py`
   (k≥3, same-session baseline) before it becomes a rule here;
5. recurring verified recipes are **promoted to code** — a script or skill — rather than re-delegated
   (AgentFactory 2603.18000: executable subagent accumulation beats textual experience).

Cadence: review `pi-delegate report` at the weekly maintenance tick; write the PDSA row.

## 6. Changelog

- **v1 (2026-11-14)** — initial policy from the paper sweep; 5 agents (scout, worker, verifier,
  researcher, bulker); ledger + posteriors + verdicts; A/B harness flag `run.py --subagent`.
- **v2 (2026-11-14)** — two falsified hypotheses, one threshold added. (a) Recon delegation on a
  30-shard aggregate: no dispatch happened and the delegating arm was slower — counting belongs to
  the shell (§1b, shell-first). (b) Parallel workers on six disjoint 3-line fixes: 9.6× wall and
  7.9× output tokens at equal pass — concurrency cannot amortise the ~20 s dispatch floor (§1b).
  Consequence: delegation is now reserved for understood content, independence, and subtasks ≥10×
  the floor. Verifier unchanged (its cost is ~$0.0014 / 18 s per check, paid only for claims that
  get reported). Gate gained `--cost-win-frac` for equal-pass token wins; neither arm met it.
