# Pruning and Distilling Mixture-of-Experts into Dense Language Models

status: done
date: 2026-11-20
method: seeds -> hops -> primary sources; every claim carries an id

## Research

Round 0 (frame). Decision: **does mem retrieval need anything from MoE expert selection?** The
number that would flip it: recall@6 on `memory/eval.json` (n=22) moving off 0.909 by more than one
query, plus the token cost of the change.

- `arxiv:2605.28207` (Kim, Yun, Kim, Kim, Bae, Cho — KRAFTON/KAIST, v3 2026-11-10, NeurIPS 2026
  Oral) — the first framework that converts a trained MoE into a **fully dense** FFN (score ->
  select -> group -> concatenate -> distill from the MoE teacher), not a smaller MoE. 350
  configurations on Qwen3-30B-A3B; 7 scoring x 5 grouping x 2 magnitude-scaling methods. Scoping
  matters: prior art (`2310.01334` MC-SMoE, `2410.08589` HC-SMoE, `2506.23266` Sub-MoE,
  `2510.14436` MergeMoE, `2511.04805` PuzzleMoE, `2510.13999` REAP) all keep a router and stay
  sparse; REAP's gate x activation-norm scoring is reused here.
- `arxiv:2605.28207` §3.1–3.2 — **DO-ACP**: greedy selection maximising
  `log det(I + λ⁻¹ K_S) + Σ log I_e` over an expert-output Gram kernel `K`, with a cardinality
  constraint. The importance term is activation-conditioned (ACP); the log-det term prices
  *mutual redundancy* among the selected items. Prop 3.2's (1−1/e) bound holds for the shifted
  surrogate `log det(I + λ⁻¹K_S)` — and λ matters: large λ collapses the objective to the
  diagonal, i.e. plain score order (Thm 3.3). That degenerate case is the testable part.
- `arxiv:2605.28207` Table 16/26/27 — DO-ACP's margin over ACP (no diversity term) is **+0.89 pp**
  (Qwen3, 43.41 vs 42.52), **+2.02 pp** (DeepSeek-V2-Lite), **+0.35 pp** (GPT-OSS-20B). No seed
  variance, no error bars anywhere in the paper.
- `arxiv:2605.28207` Table 6 vs Table 3 — the headline "+6.3 pp over dense-to-dense pruning at
  matched params (1.6x faster)" compares against **one-shot** D2D (51.84 -> 58.10). At 0.3B tokens
  the paper's own Table 3 has Minitron-style **iterative** D2D at 40.20 vs DO-ACP 43.41, i.e. the
  gap halves to +3.2 pp; iterative D2D is absent from the 4B-token table. 1.6x is MoE-vs-dense
  teacher inference (73 vs 116 s/step on 2x B200), not the scoring method.
- `arxiv:2605.28207` §6 — limitations the authors state: a single teacher family per model pair,
  distillation budget ~4B tokens, no wall-clock claim for scoring itself.

**REJECTED for this host (measured, not assumed):** there is nothing to convert. `~/models` holds
6 GGUF files, all dense (gemma-4-E2B, Llama-3.2-3B, Ornith-9B, qwen2.5-1.5B, Qwen3-0.6B,
Qwen3-1.7B); no MoE checkpoint, 7.7 GB RAM, 2 cores, no AVX2, no GPU. The paper's output stage is
~4B-token distillation: that is not runnable here at any price, so implementing "MoE-to-dense" on
this box would be theatre. What is transferable is the **selection** half — a subset chosen for
joint importance *and* mutual non-redundancy — and this host does make that decision, in `bin/mem`
retrieval.

## Tangential (2x)

- tangential: submodular / D-optimal subset selection under a cardinality constraint (Nemhauser 1-1/e, greedy marginal gain) — from pruning-and-distilling-mixture-of-experts-into-dense-languag — it is the general form of every "pick k of n" decision on this host (`mem` k, the <=4-agent fan-out in `bin/pi-delegate`, the layer pick in `local/prompt-layers.json`), so a correct implementation is reusable and a wrong one degrades all three.
- tangential: erasure / expert-merging as the alternative to pruning (HC-SMoE `2410.08589`, MergeMoE `2510.14436`, PuzzleMoE `2511.04805`) — from pruning-and-distilling-mixture-of-experts-into-dense-languag — the paper measures that pure pruning beats merging for diversity-aware scoring (top-7 configs are all K=k, no weight averaging); on this host that is evidence for the Raw-RAG additive-only journal in `bin/mem` and a reason not to build a summarise-and-merge path for context budgets.

## Systems impact

- `bin/mem.py` `search()` — change — evidence `arxiv:2605.28207` (DO-ACP) — replaced the hard
  "drop anything with jaccard > 0.72" duplicate filter with greedy D-optimal selection
  (`dopt_pick`, pure python, bordered-inverse rank-1 updates). Expected effect: more informative
  sets at small k. **Measured effect: none** — see Debate; it is therefore behind a flag
  (`search.use_dopt`, default False, `mem eval --dopt`), not on the ranking path.
- `bin/mem.py` `cmd_eval()` — change — evidence measured here (recall@6 read 1.000 warm and 0.909
  cold on identical code) — the eval bumped `memories.accesses`, which feeds `prior()`, so it
  ranked differently each run: **a measurement that mutates its own store cannot gate anything**.
  Now snapshots `(id, accesses, last_access)` before the run and restores it after; two consecutive
  runs print identical numbers (0.909 / 0.830).
- `bin/mem.py` `eval` — change — evidence same — gained `--k`, `--budget`, `--dopt/--no-dopt` so a
  tight-budget arm is measurable at all (was hard-coded k=6).
- `tests/mem-dopt.sh` — create — evidence Prop 3.2 / Thm 3.3 — pins the greedy against a
  brute-force log-det greedy on 25 synthetic pools (25/25), determinism, the redundant-pool
  ablation (w=0 must change the set, or the det term is decoration), and the Thm 3.3 degenerate
  case (incoherent pool -> importance order). 0.09 s, so it can run every time.
- `memory/eval.json` — change (open) — evidence n=22, recall@6 0.909 — the set is **saturated and
  too small**: one query is 4.5 pp, so no selection change can be resolved on it. Filed as a task,
  not done here.
- `~/.pi/agent/local/prompt-layers.json`, `bin/pi-delegate partition` — no change — evidence Thm
  3.3 — before applying D-optimal selection to either, the pool's off-diagonal coherence has to be
  measured; with few, dissimilar candidates the objective is plain score order and the machinery is
  dead weight.
- `bin/local-batch` / local model roster — remove nothing — evidence the paper's memory argument
  ("MoE needs all expert params resident") — does not apply: every local checkpoint is dense, so
  there is no resident-expert budget to reclaim.

## Loops

- loop: mem-eval-idempotency — metric: two consecutive `bin/mem eval` runs print the same recall@6 and mrr (was 1.000 then 0.955 then 0.955/0.858: three answers) — falsifier: any drift between the two runs — guard: `MEM_EVAL=1 tests/mem-dopt.sh` asserts idempotency and recall@6 >= 0.90 — cadence: agenda row `mem-eval` (1w, `exec:`), added 2026-11-20.
- loop: mem-dopt-keep-decision — metric: `bin/mem eval` recall@6 with `--dopt` vs without, same store — falsifier: `--dopt` beating the default by >= 2 queries (>= 9 pp at n=22) or saving tokens; that would promote it onto the ranking path — guard: `tests/mem-dopt.sh` fast half plus the `mem-eval` row's A/B arm — cadence: `mem-eval` (1w).
- loop: eval-set-ceiling — metric: queries in `memory/eval.json` (22) and misses by the best arm (2) — falsifier: reporting a gain of < 2 queries as a win — guard: task #322 (40-query held-out set); until it lands every retrieval claim here carries "n=22, one query = 4.5 pp" — cadence: none until #322 closes.

## Debate

- FOR: the paper is a NeurIPS oral with 350 configurations and it validates the exact mechanism
  mem lacks — the hard jaccard 0.72 threshold bans redundancy with no notion of importance, while a
  Gram log-det greedy prices it and carries a (1−1/e) guarantee. On a store of 344 memories with
  heavy topical overlap (the CORE/KEEP memory bands are dense with restatements of the same
  preferences), redundancy is exactly the failure mode, and mrr moved +0.003 with no recall loss.
- AGAINST: the margin the paper actually measures for the diversity term over plain importance
  scoring is +0.89 / +2.02 / +0.35 pp on 7B–30B models with **no error bars and no seeds**, and its
  headline +6.3 pp is against a strawman one-shot baseline its own Table 3 halves to +3.2 pp. On
  this host, from a reset store, the arms are indistinguishable: recall@6 0.909 with the old filter
  and 0.909 with D-optimal (mrr 0.830 vs 0.833, +13 tokens); the tight-budget arm (k=3, 400 tok)
  is 0.818 either way and λ ∈ {0.25, 0.5, 1.0} and w=0 all land on the same number. A mechanism
  whose measured effect is zero on the only eval that exists does not earn the hot path.
- decision: keep — off the ranking path; because the deciding number is 0.909 vs 0.909 (n=22,
  from a reset store, two reproducible runs). The code and its pin stay (`mem eval --dopt`), the
  default does not change; the change that *did* earn its place is the eval idempotency fix, which
  turned three different answers into one.

## Test

- red: `bin/mem eval` twice in a row printed recall@6 1.000 then 0.955 and mrr 0.860 then 0.858 —
  the eval was writing `accesses`, and `prior()` reads it. green: `bin/mem eval` twice —
  output: `0.909 / 0.830` both times (idempotent after the snapshot/restore).
- red: my first `dopt_pick` used the wrong bordered-inverse gain (`log1p(λ⁻¹kᵀA⁻¹k)` instead of
  `log((1+λ⁻¹) − λ⁻²kᵀA⁻¹k)`) and picked a different set than brute force. green:
  `tests/mem-dopt.sh` — output: `ok greedy == brute force on 25 synthetic pools (25/25)`.
- tester: `redteam` — technique: oracle — attacked the 4 external claims; verdict: novelty VERIFIED
  (all six priors stay sparse), +6.3 pp OVERSTATED (iterative D2D omitted, gap halves to +3.2 pp at
  0.3B tokens), DO-ACP margin OVERSTATED (+0.89/+2.02/+0.35 pp, no seeds), submodularity claim
  OVERSTATED (bound holds for the shifted surrogate, not the objective as printed). Weakest claim:
  the +6.3 pp headline.
- tester: fault injection on the guard — technique: fault — re-introduced the bordered-inverse bug
  in a copy of `mem.py` and ran the pin against it: `FAIL greedy == brute force on 25 synthetic
  pools (0/25)`, so the guard fails loudly rather than passing quietly.
- tester: ablation — technique: boundary — `MEM_DOPT_W=0` on a redundant pool must change the
  selected set (`on=[0,1,10,3,12,2] off=[0,1,2,3,4,5]`), otherwise the det term is decoration;
  and an incoherent pool must keep importance order `[0,1,2,3]` (Thm 3.3).

## Implementation

- path: `bin/mem.py` (`dopt_pick`, `cos_gram`, `DOPT_*`; `search.use_dopt` default False; `cmd_eval` snapshot/restore of `accesses` + `--k/--budget/--dopt`) — check: `tests/mem-dopt.sh` PASS in 0.09 s, `MEM_EVAL=1 tests/mem-dopt.sh` PASS in 55 s, `bin/mem eval` twice prints 0.909/0.830 both times — status: done
- path: `tests/mem-dopt.sh` — check: `pi-tool check mem-dopt` (runs twice, diffs) — status: done
- task #322 — the 22-query eval set cannot resolve a 4.5 pp change, so a 40-query held-out set is the precondition for any further retrieval claim.
- task #321 — applying D-optimal selection to `bin/pi-delegate partition` and `local/prompt-layers.json`, gated on measuring pool coherence first (Thm 3.3 makes it a no-op on small, dissimilar pools).
