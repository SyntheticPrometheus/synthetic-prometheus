# mem — design & metric history

## Storage

SQLite (`~/.pi/agent/memory/memory.db`, WAL). Tables: `memories`, `entities`, `mentions` (memory↔phrase,
weighted), `edges` (typed, directed), `embeddings` (float32 L2-normalized blobs), `events` (audit),
`recalls` (every query + returned ids + latency + tokens, the raw material for PDSA), `pdsa`.
`mem_fts` is an FTS5 external-content index kept in sync by triggers.

Every write is appended to `memory/journal/YYYY-MM-DD.jsonl` **before** the DB commit, so the DB is a
rebuildable materialized view of the journal.

`memories.kind` sets the decay constant τ (lesson 180 d, decision 120 d, fact/source 90–120 d,
pref 60 d, note 30 d, task 14 d). `valid_from`/`valid_to`/`superseded_by` are the bi-temporal axis.

## Write path (mechanical, no LLM)

1. dedupe by uid (sha1 of title+body) or exact (title, body) match;
2. insert; extract ≤24 index terms = unigrams weighted by frequency (+0.6 if a tag) and adjacent
   non-stopword bigrams (phrase nodes, weight 0.8–1.0) → `entities` (with df) + `mentions`;
3. dense vector of `title. body` (MiniLM-L6 int8 ONNX, 256-token truncation, mean pool, L2 norm).

## Read path (`mem search`)

Five independent rankings, each min-max normalized:

| rank | source | notes |
|---|---|---|
| BM25 | FTS5, `bm25(...,4.0,1.0,2.0)` | AND-first, OR-fallback; prefix-quoted tokens |
| phrase | `entities`/`mentions` | idf-weighted (rare phrase hits dominate) |
| proximity | FTS5 phrase match on query bigrams | verbatim adjacency, cheap cross-encoder proxy |
| PPR | personalized PageRank, 4 iters, damping .85, ≤2 hops, 300-node cap | seeds = top-25 of BM25∪phrase∪proximity∪dense; edges from `edges` (×0.5) + co-mention (×0.25) |
| dense | MiniLM cosine, top-60 above 0.20 | brute-force numpy matmul; candidate-restrict beyond ~20k |

Fusion: `RRF(k=12)` with weights `[bm 1.0, phrase 0.85, proximity 1.15, ppr 1.1, dense 1.35]`.
Final score:

```
score = 1.45·fused + 0.50·ppr + 0.70·dense
      + 0.80·anchor_bigram_coverage + 0.45·title_term_coverage
      + 0.30·prior·scope_bonus
prior = importance · (0.65·exp(-age/τ) + 0.35) · (1 + 0.35·ln(1+accesses)) · validity(1.0 | 0.25)
pinned +0.12 ; digest ×0.9
```

Then: MMR-lite dedupe (token jaccard > 0.72 skips a hit), greedy fill of the token budget
(~4 chars/token, body capped at 900 chars), returns `--k` cards + a footer with hits/tokens/ms.

## PDSA metric history (`mem eval`, 20 fixed queries, ids in eval.json)

| cycle | change | recall@6 | MRR | avg tok | p50 ms |
|---|---|---|---|---|---|
| 1 | baseline: BM25 + phrase index + PPR + RRF + decay + MMR | 1.00 | 0.683 | 647 | 3.4 |
| 2 | query-bigram phrase-proximity ranking + anchor/title-coverage rerank | 1.00 | 0.758 | 672 | 4.1 |
| 3 | dense MiniLM-L6 int8 layer (weight 1.35 in RRF, 0.70 direct) | 1.00 | 0.912 | 662 | 12.1 |
| 4 | consolidation passes + semantic dedupe gate (cos ≥ 0.90) | 1.00 | 0.910 | 739 | 12.2 |
| 5 | BM25 sign fix, os._exit teardown, ORT_DISABLE_ALL, launcher shim, short digests | 1.00 | 0.935 | 681 | 11.9 |
| 6 | eval set 20 → 22 real cases; dense confidence gate tried then **reverted** | 0.955 | 0.867 | 666 | 14.9 |

Interpretation: recall@6 is saturated on a 20-query self-authored set, so MRR is the live metric.
Cycle 6 is open: the metric dropped because the corpus gained distractors *and* two new cases were
added — recall@6 fell to 0.955 on the first case that the store genuinely cannot answer
("is agent memory worth the cost" vs the MemoryTax entry). That is the desired direction of travel.

Cycle 5's BM25 fix alone was worth +0.023 MRR: FTS5's `bm25()` returns *negative* values, so the
earlier `1/(1+max(0,s))` clamped every match to 1.0 and only rank order survived; scores are now
`-s/(1-s)`-style positive mappings.

Corpus drift matters as much as code at this size: adding one plausible-but-secondary memory (#23) cost
0.027 MRR by outranking the canonical entry for one query. Attribute every delta from per-query ranks.

Ablation (20 queries, pre-cycle-6): lexical-only MRR 0.742 vs 0.933 with dense — the dense layer is worth
~0.19 MRR and is now always on. A complexity gate (skip dense when BM25 looks decisive) was implemented,
measured and **reverted**: a loose rule produced a wrong top-1 on a dogfooded query, and a safe rule
(>=3 query tokens all covered by the top-1 title, 1.5x margin) never fired on the eval set. Dead
complexity that can silently return a worse answer is a net loss; the cold-start cost moves to the
daemon/preload idea instead.
Cold CLI: ~300 ms when dense runs (venv python + numpy 112 ms + onnxruntime import 155 ms + session
38 ms), ~86 ms when the gate skips it (the old 745 ms was almost entirely interpreter teardown after
numpy/ort were loaded — `os._exit()` after flushing removes it). Warm in-process ≈ 12 ms.

## Known limits / next hypotheses

1. **Eval set is small and self-authored.** Grow it from real misses; treat recall@6 = 1.0 as "no
   discriminating power", not success. Add adversarial/ambiguous cases and distractor memories.
2. **Cold-start latency** (cycle 6, secondary): dense path is still ~300 ms, of which ~270 ms is
   numpy+onnxruntime import. Options: a tiny always-on daemon, a preloaded interpreter, or dropping
   onnxruntime for a hand-rolled int8 matmul over a bit-packed index. Target < 150 ms.
3. **Eval set is self-authored** (cycle 6, primary): 20 cases with recall@6 = 1.00 have no
   discriminating power. Add distractor memories, near-duplicate titles, ambiguous and multi-answer
   queries, and token-disjoint paraphrases; expect recall to drop — that is the point.
4. **No experience layer yet.** The surveys' third stage (distilling lessons into playbooks) is
   hand-done today; a `mem distill` that promotes repeated lessons into a playbook entry is the next
   structural bet — but only if the eval shows it helps.
5. **Dedupe precision at scale.** cos ≥ 0.90 is safe on 22 memories; re-validate at 500+ before trusting
   it unattended, and prefer linking over archiving when similarity is 0.85–0.90.
6. **Scaling.** Brute-force dense is fine to ~20k; beyond that, restrict scoring to the BM25∪PPR
   candidate union (already the code path for >limit), or add sqlite-vec + HNSW.
