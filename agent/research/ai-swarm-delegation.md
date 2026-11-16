# AI swarms, delegation and efficiency — evidence base (2026-11-15)

Question: when does splitting work across agents (subagents, swarms, orchestrators) beat one agent,
and which mechanisms make the split pay? Decision it flips: the delegation protocol in
`delegation/policy.md` v3 and the partition gate in `bin/pi-delegate`.

Method: 10 arXiv queries (`skills/deep-research/scripts/arxiv.py search ... --raw`, 2025–2026),
abstracts read in full, **every id re-fetched with `arxiv.py get` and checked against its title and
`comment` field** before it was used. Search engines are bot-walled on this host; OpenAlex was
rate-limited on 2026-11-15. Harvest folds: `/tmp/deleg/a.out` (scout, 74 s, $0.14, 20 claims).
One of the 20 claims was **retracted by its authors** and is recorded below as such — the fold
alone would have propagated it.

## What the evidence says

### Decomposition is real but not monotone
- **Right-sizing decomposition** (2608.23395): 4,400-run controlled sweep, 40 cases × 5 repeats,
  four orchestrations from one wide worker to five narrow ones. Intermediate configurations led on
  accuracy (0.830 vs 0.720/0.770 endpoints), but the pre-registered bar was missed; the
  budget-matched single agent landed 6.5 points below the leader with a CI that includes zero, so
  the gain is consistent with a prompt-budget explanation. → *measure the split at your scale; more
  agents is not monotonically better.*
- **Hierarchical supervisor–worker** sits on the cost–accuracy Pareto frontier for 10,000 SEC
  filings (2603.22651): F1 0.921 at 1.4× sequential cost, versus reflexive self-correction at 0.943
  and 2.3×. A hybrid recovered 89% of the reflexive gain at 1.15×. → *default to one level of
  supervisor → worker, not a reflective loop.*
- **Phase-dependent reversal** (2606.28362, LUMEN): 11 agents over six systematic-review phases;
  multi-agent hurt title/abstract screening but was essential for data extraction; full review cost
  $19–29 (median $22.65). → *gate per phase, never a uniform pipeline.*
- **Delegation is not free accuracy** (2611.16526): across pre/post-cutoff splits, delegation gave
  no consistent gain and degraded accuracy when the orchestrator lacked the knowledge to route;
  failure modes were distorted delegated queries, inefficient tool use, and information lost between
  agents. → *do not delegate what the parent cannot specify and check.*

### Coordination mechanism beats agent count
- **Proactive scope scheduling** (2610.07261, NP-Bench): declaring each item's scope, partitioning
  into disjoint scopes, and ordering merges along the producer→consumer graph up front lifted clean
  integration from 1/9 to 9/9 and cut merge conflicts from 13 to 0. On a live breaking contract the
  clean-integration rate went 0 → 1.0 (frontier model) and 0 → 0.6 (small model). → *the partition
  gate is the highest-leverage delegation feature, and it is a pre-dispatch check, not a warning.*
- **Verifier-driven research** (2606.27416, Glite ARF): 273 tracked tasks, up to 12 parallel coding
  agents, with deterministic Python verifiers enforcing task isolation, immutability of completed
  work and a corrections overlay; 29.9%/35.9% RMSE reduction over baseline. The rules lived in code
  that fails loudly, not in prose. → *acceptance must be executable; a prose rule is a suggestion.*
- **Typed handoffs** (2608.25277): natural-language coordination consumed 40–60% of the token
  budget; a 155-token router choosing typed graph vs NL gave +12.7 pp on τ-retail at 3.2×
  compression and +8.7 pp on BrowseComp at 2.2×, while graph-only regressed 14.6 pp on AppWorld.
  → *fixed fold shapes help, but the handoff format must fit the task; keep a prose escape hatch.*
- **Roster retrieval** (2610.21113): deterministic agent-card retrieval cut input tokens 98.8% and
  latency 70.9% at 1,000 agents. → *irrelevant at a 5-agent roster; relevant if the roster grows.*

### Cost and context are the binding constraints
- **Output/memory tax grows with depth** (2609.23790): memory injection was 13.6% of controllable
  variable cost, ~12% of billed cost, rising from 0 at depth 1 to 27.6% at depth 6, linear in depth
  (R²=0.9974). → *keep delegation graphs shallow; bound injected history per hop.*
- **Cheap base + frontier escalation** (2411.07464): Gemini base with GPT-4 cascade/ask-the-expert
  cut cost 94.2% ($0.931 → $0.054 per run) while raising success 22.72% → 32.95%. → *route bulk to
  cheap models, escalate only planning/hard steps.*
- **Selective deliberation** (2604.12262): ensembles invoked only at low-confidence escalation
  boundaries beat single-model cascades by up to 26.75%; fixed policies lost 21–52% relative. →
  *verify on uncertainty, not on every item.*
- **Compression levers differ** (2609.22114): tool-schema filtering is linear (21K–57K tokens/turn);
  content compression saves ~2%/turn but accumulates quadratically (~3350·N² tokens), overtaking
  the fixed saving after ~6 turns. → *strip unused tool schemas first; fold content by reference.*
- **Reversible compression is model-dependent** (2609.26121): 10–13% input-token cuts and 2.5–3.5×
  solve-rate gains on responsive frontier models, mixed/negative on others. → *the fold-by-reference
  rule is safe because it needs no recall; lossy summarisation is not.*
- **Small models in heavy scaffolds waste energy** (2512.09543): Gemma-3 4B / Qwen-3 1.7B in four
  agentic frameworks had near-zero resolution and a 9.4× energy spread across frameworks. →
  *consistent with `skills/local-models`: no agent scaffolds on small local models.*

### Safety and authority are delegation-specific
- **Delegated misalignment** (2609.27900): full-execution harm rose 30.6% → 77.6% (DeepSeek-V3.2)
  and 22.5% → 61.2% (GPT-5 as subordinate); responsibility diffusion + role-bias compliance. →
  *scope and least privilege are safety controls, not style.*
- **Identity hijacks orchestration** (2609.32635, TrustFork): orchestrators acted on a risky
  subagent response despite contradicting evidence in 72.0% of cases; a safer answer was used only
  25.0%; swapping family labels nearly tripled risky responses. → *bind authority to verified
  evidence, never to an agent's name, brand or "role". The verifier's output is evidence only when
  it reproduces the check.*
- **Privilege granting is the management bottleneck** (2606.31174, ClawArena-Team): 41 scenarios,
  258 rounds; no model exceeded 50% workspace-permission precision; API cost varied >100× while
  management score varied <4×. → *the parent must write SCOPE; cheap managers can be fine, sloppy
  scopes cannot.*

### Retracted — do not cite
- **2511.15755** claimed 100% vs 1.7% actionable incident-response quality for multi-agent systems.
  Its `comment` field now reads: *withdrawn by the author; a code audit found the multi-agent arm's
  action list is a source constant, not model output.* The numbers are not evidence. Kept here so
  the next sweep does not re-import them. **Guard: `arxiv.py get` prints `comment`; a withdrawn or
  retracted paper is dropped before synthesis.**

## Tensions the literature has not settled

- Multi-agent wins (2603.22651, 2604.12262, 2610.07261) versus budget-matched parity (2608.23395,
  2611.16526, 2601.12307). The reconciliation is a threshold plus a partition: gains appear when
  the work is genuinely decomposable and the split is checked, not from agent count.
- Structured handoffs win on cost/accuracy in 2608.25277 but regress without interpretation
  guidance; NL remains necessary for adaptive reasoning. Our fold shapes are typed *and* prose —
  the current compromise is defensible.
- No paper reports end-to-end wall-clock + billed dollars + recovery overhead against a tuned
  single agent at matched token budgets. The local ledger is the only place that comparison exists
  for this machine.

## Implications for this harness (what changed)

1. **Partition gate before any fan-out** (`pi-delegate partition`): no file in two shards, hub files
   owned by exactly one, unowned hub in a shared dir is a warning (or `--strict` failure). This is
   the 2610.07261 result turned into a command.
2. **Definition of Ready** (six contract fields, lexically checked by `plan`) — a dispatch missing
   ACCEPTANCE or SCOPE is not dispatched (2606.27416, 2606.31174).
3. **One integrator role** after parallel workers, owning hub files and the whole-task check —
   integration is a named responsibility, not the last worker's leftover (Brooks; 2610.07261).
4. **Selective verification**: verifier on claims that are reported or authored by the same context,
   not on every fold (2604.12262; local ledger: verifier ~$0.0014–0.03 and 18–186 s per check).
5. **Shallow graphs, thin folds**: one level, ≤60-line folds, refs not copies (2609.23790,
   2609.09233, 2609.22114).
6. **Authority from evidence, not identity**: a fold is accepted only after the parent re-reads one
   reference or the verifier reproduces the command (2609.32635).
7. **Retraction guard** in the evidence-mode scout prompt and in `research/` digests (2511.15755).
