# Delegation and subagents — research digest (2026-11-14)

Question: when does delegating work to a subagent (fresh context, own model, own tools) beat doing it
in one context, and how should the *choice* be made and improved? Sources retrieved through the arXiv
API (search engines are bot-walled here); ids are arXiv. Implementation and its measured outcome:
`delegation/policy.md`, `skills/delegate/SKILL.md`, `selfimprove/arms/deleg-*.md`.

## What the literature says (claims worth acting on)

- **2609.09233** *Subagents vs Agent Skills* — executing a reusable procedure *as a subagent* beats
  loading it into the main context when the procedure has a clear input/output contract; the price is
  communication overhead. → contracts and fold shapes are not bureaucracy, they are the enabling
  condition.
- **2510.11967** *Context-Folding* — agents that branch into a sub-trajectory and fold it back to a
  concise summary match or beat ReAct with a 10× smaller active context. → children must return
  addresses (`path:line`), not copies.
- **2605.16205** *Context, Reasoning, and Hierarchy* — programmatic state abstraction beats
  deliberation per token; distributing deliberation tools across a hierarchy ("deliberation
  cascade") was up to 3.4× worse while using 1.8–2.7× the tokens; hierarchy *without* nested
  deliberation was best. → thin children, one level, judgement stays in the parent.
- **2606.00953** *When Parallelism Pays Off* — multi-agent coding gains come from cohesion-aware graph
  partitioning (hub files isolated, communities kept whole), not from agent count; up to 2.1× wall
  and −35% cost *when* the partition is cohesive. → never split a file; keep shared/hub modules in
  one worker.
- **2605.05007** *Uno-Orchestra* — selective delegation (decompose only when needed, choose worker
  model jointly) reaches ~16% higher pass@1 at ~10× lower cost than fixed workflows. → the decision
  is per task, not per system.
- **2601.12307** *A Strong Single Agent Baseline* — homogeneous multi-agent workflows are matched by
  one agent with KV-cache reuse; only genuinely heterogeneous workflows (different models) escape
  that bound. → delegation for role-play is a token tax; delegation for a *different model* (independence,
  or a cheap specialist) is the defensible case.
- **2604.17950** *CADMAS-CTX* — capability is context-dependent, so keep a Beta posterior per
  (agent, skill, context bucket) and route on `mean − uncertainty penalty`; beats static routing
  (GAIA 0.442 vs 0.381, SWE-bench Lite 22.3→31.4%). → exactly what `delegation/ledger.jsonl` +
  `pi-delegate report` implement.
- **2603.11011** *Task-Aware Delegation Cues* — delegation should be driven by task-typed cues
  (capability profile + coordination-risk prior), surfaced as an explicit, auditable decision.
  → `pi-delegate plan` prints the cue classification and the evidence behind the call.
- **2603.18000** *AgentFactory* — accumulate *executable* subagents (code) refined by execution
  feedback, not textual reflections; capability then compounds. → a delegation recipe that keeps
  passing gets promoted to a script/skill and stops being delegated.
- **2611.08905** *From Procedures to Permissions* — the skill's procedure is the supervision signal
  for per-subtask authorization; precise tool/workspace scoping gained +13.4pp tool and +24.1pp
  workspace permission precision and +11.6pp task success. → the agent's `tools:` frontmatter is the
  authorization, not a suggestion.
- **2605.27787** *Librarian* — output tokens cost 30–1000× an input token; MAS inflate output by
  re-exploring the same regions; a persistent search subagent that returns *short references* cut
  energy 11–30% at equal performance. → fold discipline is an energy decision.
- **2601.14470** *Tokenomics* — in a multi-agent SDLC, 59.4% of tokens go to iterative
  code-review/refinement, 53.9% are input tokens. → verify loops are where delegation spend
  accumulates; budget them.
- **2610.03010** *Engineering Sustainable Agents* — multi-agent designs use 6.36× the energy and
  6.07× the wall of non-agentic baselines with task-specific accuracy gains; 59 of 66 Pareto-optimal
  configurations were single-agent. → default solo; delegation must earn its place.
- **2605.08761** *EntCollabBench* — current models still fail at delegation, context transfer,
  parameter grounding and workflow closure even in role-specialised enterprise settings. → expect
  contract sloppiness; the parent must spot-check.

## Contradictions / open questions

- 2605.05007 and 2606.00953 show real multi-agent wins; 2601.12307 and 2610.03010 show single-agent
  parity at a fraction of the cost. The reconciliation is a *threshold*: delegation pays per subtask,
  below some size it cannot. The papers do not give the threshold in wall-clock terms — so measure it
  locally (below).
- Learned routers (Uno-Orchestra, BOT-Orch 2605.27073, MonoScale 2601.23219) need many labelled
  episodes. With a handful of dispatches, a cue-based policy plus a Beta posterior is the honest
  ceiling; RL-style routing is premature on this machine.

## Local measurement (this host, 2026-11-14, `selfimprove/`, k=3)

- **Recon delegation loses to the parent's own shell.** `log-fanout` (30 shards, 1,200 lines):
  base arm 6/6 pass in 28.5 s / 2,578 out-tokens; deleg arm 6/6 in 47.4 s and **zero dispatches** —
  the model answered with `rg`/`awk` in one call. Counting is not a reading problem.
- **Parallel workers on trivial disjoint edits lose ~10×.** `parallel-fix` (6 independent 3-line
  fixes, no hub file): base 3/3 in 19.6 s, $0.0030, 975 out-tokens; parallel-`worker` arm 3/3 in
  187.5 s, $0.0118, 7,729 out-tokens. Child wall times were 14–50 s each (spawn + model latency)
  for edits that take a second — concurrency cannot pay for a ~20 s dispatch floor.
- **Numbers to keep**: dispatch floor ≈ 14–50 s and ≈ 300–700 out-tokens per child on this host.
  A subtask is worth delegating when its solo duration ≥ ~10× that floor (≈ 3–5 min), or when the
  child's model family differs for an independence reason (verifier).
