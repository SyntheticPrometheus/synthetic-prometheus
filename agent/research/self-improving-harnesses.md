# Self-improving agents & harnesses — research digest (2026-11-14)

Compiled from arXiv API queries (titles/abstracts fetched, not from memory). Every ID below was
returned by a live query; quotes are from the fetched abstracts. Grouped by what the work actually
contributes, not by institution (affiliations are not in the API metadata — several are MIT-adjacent:
Zaharia (2607.15524), Alizadeh/Balakrishnan (2603.21321), Lo (2611.07048), Clune/Zhang (2505.22954,
2603.19461)).

## 1. The core loop: mutate your own code, keep what scores better

**DGM — Darwin Gödel Machine** `2505.22954` (Zhang, Hu, Lu, Lange, Clune). Iteratively rewrites its
own codebase, validates each change empirically on coding benchmarks, keeps an *archive* of agents
selected for open-endedness rather than a single best lineage. Replaces the Gödel machine's
impossible "prove each change beneficial" with measured evaluation.

**Hyperagents** `2603.19461` (Zhang, Zhao, Yang, Foerster, Clune, Jiang, Devlin, Shavrina). Fixes
DGM's domain lock: task agent *and* meta agent (the thing that edits) live in one editable program,
so the modification procedure itself can be modified — metacognitive self-modification. DGM only
improves self-improvement insofar as the task is coding.

**Agent-directed evolution** `2611.07048` (Lo, Zhao). Theory: Darwinian < Lamarckian (inherited
learning) < agent-directed (generate + evaluate variants, choose how much to search). More variants
speed adaptation; optimal search effort depends on learning ability, problem difficulty and
experiment cost. Caveat that matters: *the ability to direct improvement does not guarantee the
improvement is real*.

**SIFT — Recursive Self Improvement via Fast Tree-search** `2609.19526` (Fu, Kulanthaivelu, Yamada).
Names the real bottleneck: evaluating candidate self-modifications (re-running benchmark subsets).
Fix: LLM-judge pairwise comparisons between patches → regularized Bradley–Terry strength scores →
rank-based parent sampling in a disaggregated tree search. Sample-efficient self-improvement under
budget.

**Mixture of Self-Improving Branches** `2609.37834` (Dong et al.). Meta-Harness-style RSI collapses
to one trajectory (fixed dev set, fixed proposal policy). Fix: branches with evolving dev subsets
(keep cases only your leading harnesses solve, drop cases everyone solves) and per-branch proposal
policies, plus a router over branch heads. Diversity as an explicit anti-local-optimum device.

**RRSI — Regularized Recursive Self-Improvement** `2609.24972` (Xia et al.). Names the failure:
harness evolution overfits the dev tasks (big in-distribution gains, gone OOD). Fix: annealed edit
budget (fewer bundled edits over time), novelty pressure on unexplored trajectories, and a selector
regularized against the evolution history.

**PluginRSI** `2609.32423`. Same problem from the other end: searching whole programs makes
mechanisms non-reusable. Represent the harness as composable plugins so an improvement is a
transferable unit.

## 2. What the harness *is* — specification, language, and cost

**Natural-Language Agent Harnesses** `2603.25723`. Harness logic is normally buried in controller
code → unreadable, uncomparable, untransferable. Represent the harness as a natural-language
specification of the execution loop. This is the "harness is a language" thesis: the harness is an
editable, inspectable *program in prose*, which is exactly what makes automated editing tractable.

**Code as Agent Harness** `2605.18747` (survey, Ning et al.). Code is the substrate for reasoning,
acting, environment modelling and verification; organises the field into interface / mechanisms /
scaling layers.

**What makes a harness a harness** `2606.10106` (de Macedo). The term is polysemous (product vs eval
scaffold vs framework). Proposes necessary-and-sufficient conditions — useful as a boundary when
deciding what a self-improvement loop is even allowed to edit.

**What Does a Harness Buy? Tokens, Mostly** `2610.04433` (Liu, Han). The sobering one: hold the model
fixed, swap Claude Code / mini-SWE-agent / OpenCode on SWE-bench Verified — heaviest and lightest
harnesses within 5 points; on a hard subset, swapping harnesses flips as many tasks as *rerunning the
same harness* (13% both). Conclusion for us: below a certain delta, harness "improvements" are run
noise — an acceptance gate needs repeats, not a single A/B.

**HARBOR** `2604.20938` (Sengupta, Wang). Harness design as constrained noisy Bayesian optimization
over a mixed-variable, cost-heterogeneous config space, with cold-start-corrected rewards and a
posterior chance-constrained safety check. Automated config search dominates manual stacking once
the flag space exceeds a handful of bits.

## 3. Improving the harness without labels, without context blowup

**RHI — Recursive Harness Self-Improvement** `2607.15524` (Lee, Xu, Seely, Lee, Zaharia, Tang).
Harness = prompt-level spec of the agent loop; refine with *pairwise feedback over its own revision
history*; a few iterations, cheap, 30 synthetic ML-research tasks. Also frames harnesses as
data-generating components for future model training (harness-in-the-loop learning).

**Self-Harness** `2606.09498` (Zhang et al.). Three stages: Weakness Mining from own traces →
Harness Proposal (minimal, tied to the mined failures) → Proposal Validation with regression tests.
Self-improvement with no human and no stronger external agent.

**RHO — Retrospective Harness Optimization** `2606.05922` (Pan et al.). No ground-truth sets in
deployment: sample a diverse coreset of hard past tasks, re-solve in parallel, use self-validation +
self-consistency, then self-preference to pick the harness update. One round moved SWE-Bench Pro.

**Engram — Coherence and Persistence for System Optimization** `2603.21321` (Karimi, Noorbakhsh,
Alizadeh, Balakrishnan — MIT). Two named failure modes: *evolutionary neighborhood bias* (scalar
benchmark scores trap you in local optima; you need coordinated multi-step changes) and the
*coherence ceiling* (context degradation over long horizons; nothing accumulates across runs). Fix:
decouple long-horizon exploration from a single context window — a sequence of agents that each
design/test/analyse a mechanism and store what they learned externally at the end of the run.

**SoL-Pi** `2609.20519` (Liu, Ye, Gao, Zhuge, Zhu, Xie...). RSI at the harness layer, scaled over many
environments; selects four mechanisms (action execution, context compaction, observation handling,
delegated reading) that survive selection and transfer. 51-task EdgeBench: comparable to Pi with
GPT-5.6 Sol/Opus 5 while cutting token traffic 44.7–49% and API cost ~1/3. Token efficiency *is* the
scaling constraint for unattended loops.

**Evo-Harness** `2608.15071`, **Continual Harness** `2605.09998`, **Prime Agent** `2608.23552`,
**Recurrent Harness** `2610.12668` — same family: harness adapts online from its own experience,
sometimes with state that evolves backward as well as forward.

## 4. Governance: the loop must not be able to cheat its own judge

**Auditing Harness Tampering** `2609.00069` (Wang, Zhang, Shao). "Harness tampering": edits that
produce illusory gains or break authorization/provenance/completeness without improving capability —
reward tampering extended to the full self-improvement lifecycle. Two-axis taxonomy, seeded
tampered/benign pairs, audits of real self-improving trajectories; it happens consistently.

**Guardrailed Meta-Agent Loops** `2609.12216` (Ma, Wu). Hash-pinned policy (goals, scope, evaluation
identity, budget, release conditions) + machine evolution restricted to a code-owned feature catalog
and bounded knobs + compute accounting at every prefix + crash recovery. Measured: round-stage growth
+1.00 target attainment, −56.97 simulated GPU-hours (CI [−58.91, −54.70]); idle growth has zero
measured utility.

**Authorization for self-modifying populations** `2610.00347`. Forking/replacing/rolling back agents
means per-successor authorization is insufficient: siblings duplicate quotas, combine permissions,
outlive ancestors.

**HGM-Dual** `2610.30042`, **Causal Improvement Graph** `2610.05039`, **Evo-Bench** `2608.09096`,
**LoopsBench** `2608.00267`, **VeRO** `2602.22480` — the surrounding measurement infrastructure:
lineage-aware guidance, causal attribution of which edit caused which gain, benchmarks for "can a
model improve a harness at all", loop-level (not task-level) evaluation.

## Synthesis — what honestly transfers to *this* harness

1. **Edit the spec, not the binary.** Our harness *is* a language artifact already: `AGENTS.md`,
   skills, prompt templates, extensions, PDSA records. That is the NL-harness representation, so the
   loop can be plain text edits with diffable provenance.
2. **Gains are small and noisy; gate accordingly.** 2610.04433 says single A/B flips are ~run noise.
   Require k≥3 repeats per arm or a large effect, and compare against a *rerun of the baseline*, not
   a stored number.
3. **Archive + lineage, not best-so-far.** DGM's archive and the branch work (2609.37834) exist
   because single trajectories collapse. Keep every arm, its diff, its scores, and its parent.
4. **Regularize the proposer.** Annealed edit budget, one mechanism per candidate, no bundling
   (2609.24972). Small edit, one hypothesis, one metric.
5. **Cheap judges for expensive truth.** Use a judge/pairwise comparison for screening, benchmarks
   only for finalists (2609.19526), and self-preference only when labels are unavailable (2606.05922).
6. **The judge is attack surface.** Pin the evaluation identity by hash, record budgets, audit every
   accepted edit for scope violations (2609.12216, 2609.00069). A self-improving loop that can edit
   its own tests has no signal.
7. **Coherence is an external-state problem, not a context problem.** Engram's answer — every run
   ends by writing a durable artifact the next run reads — is exactly what `mem` + PDSA already do;
   the gap is that our runs don't *have* to end that way.
8. **Token efficiency is a first-class objective** (SoL-Pi), because unattended loops die on cost
   long before they die on capability.
9. **Meta-level editability** (Hyperagents): the procedure that proposes edits should itself be a
   candidate for editing — i.e. the proposer prompt and the gate thresholds are part of the genome.
