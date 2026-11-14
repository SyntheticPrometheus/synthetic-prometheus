# Research: efficient agent memory & RAG (compiled 2026-11-14)

Method: arXiv API (`export.arxiv.org/api/query`) across 12 topic queries, 48 hits screened, 16 abstracts
read in full. General web search engines are bot-blocked from this host (see "Search access" below);
GitHub REST and HN Algolia used for implementation-side checks.

## The five families

1. **OS-style tiering** — MemGPT (2310.08560): context window = RAM, external store = disk, small
   pinned core always resident, everything else paged in by the model itself via function calls +
   interrupts. Takeaway adopted: a small pinned core block + budgeted paging beats one flat index.
2. **Extract-and-consolidate memory layers** — Mem0 (2504.19413): LLM extracts salient facts per turn,
   consolidates (ADD/UPDATE/DELETE), retrieves top-k; big LOCOMO gains and large token savings vs full
   context, plus an optional graph variant. Weakness: a lossy writer — whatever the extractor skips is
   unrecoverable.
3. **Temporal knowledge graphs** — Zep/Graphiti (2501.13956): every edge carries event time and ingestion
   time, so stale edges are invalidated instead of deleted; 94.8% vs 93.4% DMR over MemGPT, better on
   LongMemEval, and lower latency because retrieval is a graph query, not an agentic loop. Takeaway
   adopted: bi-temporal columns + `supersedes` edges.
4. **Graph retrieval with spreading activation** — HippoRAG (2405.14831): open KG of phrase + passage
   nodes, Personalized PageRank seeded on query phrases; up to +20 points on multi-hop QA with
   *single-step* retrieval. HippoRAG 2 (2502.14802) adds deeper passage integration + online LLM use
   because pure graph retrieval *regressed* on simple factual recall — structure must sit on top of raw
   retrieval, never replace it. LightRAG (2410.05779) adds dual-level (entity + theme) retrieval and
   incremental updates. Takeaway adopted: PPR over a memory/entity graph as one ranking in a fusion.
5. **Hierarchical abstraction** — RAPTOR (2401.18059): recursively cluster + summarize into a tree and
   retrieve at several levels (+20 pts QuALITY). TiMem (2601.02845) makes the same idea temporal and
   complexity-aware (75.3% LoCoMo, 76.9% LongMemEval). Takeaway adopted, cheaply: extractive theme
   digests that *link to* originals instead of replacing them.

## The counter-evidence that shaped the design

- **Raw-RAG** (2610.30755): naive dense retrieval + rerank over *raw* history beat the strongest agentic
  memory systems in 6 of 7 benchmark/model settings across LoCoMo, LongMemEval, MEME and
  MemoryAgentBench. Cause: transformed stores lose *coverage* of the relations and dependency paths
  needed to derive answers; coverage beats utilization. → Never destroy raw text; indexes are additive.
- **MemoryTax** (2610.29823): designed memory (Mem0) only beat full context with a weak reader model, and
  its build cost exceeded an entire full-context rollout; a stronger reader cannot recover what a weak
  writer omitted. → No per-write LLM extraction; mechanical indexing + a strong reader searching raw text.
- **"Is complex agentic memory always needed?"** (2610.30755's sibling framing) and the survey
  2512.13564 both argue the field over-attributes wins to structure that plain retrieval + good ranking
  already provides. → Structure earns its place only where it measurably helps: here, multi-hop
  association (PPR) and paraphrase (dense), validated per-metric on the eval set.

## Consolidation & forgetting

- **SleepGate** (2603.14517): stale associations cause proactive interference that grows log-linearly
  regardless of context length; fix = conflict-aware temporal tagging, selective eviction, and merging
  survivors into summaries during periodic micro-cycles. → `mem consolidate`: dedupe, auto-supersede on
  update cues, decay-archive, optional digests.
- **TiMem** (2601.02845): recall effort should scale with query complexity; cheap queries shouldn't pay a
  multi-hop graph walk. → `--k`/`--budget` knobs (full adaptive complexity routing is an open cycle).
- Surveys **2605.06716** (storage → reflection → experience) and **2512.13564** (forms/functions/dynamics)
  give the maturity ladder: this system is at "storage + reflection"; the experience layer (cross-task
  abstraction: playbooks distilled from lessons) is the next stage.

## Context engineering & self-improvement

- **ACE** (2510.04618): treat context as an evolving **playbook**; update by structured incremental edits
  (generate/reflect/curate) instead of rewriting — prevents brevity bias and context collapse; +10.6%
  agents, +8.6% finance, lower adaptation cost. → AGENTS.md/skills are edited append-then-prune, with the
  reason kept; memory entries are immutable once written (supersede, never mutate).

## Retrieval engineering notes

- Fusion by reciprocal rank fusion is robust when ranking scales disagree (BM25 vs cosine vs PPR).
- BM25 via SQLite FTS5 (`bm25(mem_fts, 4.0, 1.0, 2.0)`) needs no service and is ~1 ms; prefix-quoted terms
  (`"tok"*`) plus an AND-first / OR-fallback strategy handles partial matches.
- Phrase-proximity matching on query bigrams is a cheap proxy for a cross-encoder and fixed the
  "hipporag 2 vs hipporag" confusion in the eval set.
- MiniLM-L6 quantized int8 ONNX (22 MB) + onnxruntime gives ~7 ms query embedding, 142 ms model load;
  mean-pooled + L2-normalized vectors make cosine a plain dot product, so brute-force scan over a few
  thousand memories is fine (numpy matmul). Beyond ~20k memories switch to candidate-restricted scoring.

## Search access from this host (verified, not assumed)

Blocked: Bing (HTML and RSS return unrelated cached results), DuckDuckGo html/lite (202 challenge),
Google and Brave (JS-only payloads, no static results), searx instances (429 / anubis challenge),
r.jina.ai proxy for search engines (403 abuse block).
Working: arXiv API, GitHub REST (unauthenticated), HN Algolia, Wikipedia API, direct `curl` of known URLs,
r.jina.ai for ordinary pages.

## Sources

2310.08560 MemGPT · 2504.19413 Mem0 · 2501.13956 Zep/Graphiti · 2405.14831 HippoRAG · 2502.14802 HippoRAG 2 ·
2410.05779 LightRAG · 2401.18059 RAPTOR · 2601.02845 TiMem · 2603.14517 SleepGate · 2510.04618 ACE ·
2610.30755 Raw-RAG · 2610.29823 MemoryTax · 2605.06716 / 2512.13564 / 2609.08599 surveys
