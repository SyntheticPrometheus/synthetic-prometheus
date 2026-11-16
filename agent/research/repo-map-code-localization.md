# Repo maps and code localization — evidence base for `pi-repomap`

Compiled 2026-11-15. Method: targeted arXiv API queries (`skills/deep-research/scripts/arxiv.py`,
phrases only — the index is field-scoped and long natural-language queries return nothing), full
abstracts read for five papers, plus a direct read of the reference implementation
(Aider-AI/aider, `aider/repomap.py`, 867 lines, fetched from raw.githubusercontent.com). OpenAlex is
the fallback when arXiv rate-limits (429s were frequent; `research/litwalk.py` is the cached path).
Search engines stay unusable on this host (mem #16).

Purpose: decide whether to build a structural code-intelligence tool, and constrain its design so
the parts the literature disagrees about are measured locally instead of assumed.

## 1. The question and the decision it flips

Does a harness that can already `grep` and `read` gain anything from a precomputed **repo-level
structure** (symbols + reference graph, rendered to a token budget)?

- If yes: an unfamiliar-tree task starts with one map call instead of a grep/read chain, and the
  map should bias toward the task's identifiers.
- If no (the CodeScout position, §2.4): keep the shell-only workflow, spend the effort on search
  ergonomics instead.
- Either way the *shape* of the answer ("map is useful only when it is given a hint") changes how
  the tool is advertised, so it must be measured rather than argued.

Prior: 0.6 that a hint-conditioned map helps; 0.3 that a blind map helps on a large tree.

## 2. What the literature says

### 2.1 Localization is the bottleneck, and graphs are one way to attack it

- **LocAgent** (2503.09089, EMNLP-style; abstract read): parses a repo into a *directed
  heterogeneous graph* of files/classes/functions with imports, invocations and inheritance, and
  lets the agent do multi-hop search over it. Reports up to **92.7% file-level localization** and a
  **12%** improvement in downstream issue resolution (Pass@10) at **~86% lower cost** than a
  SOTA proprietary baseline. The claim that matters here: representing structure explicitly is
  cheap for the model to use, because it is one artifact instead of N greps.
- **RepoGraph** (2410.14684, ICLR 2025; abstract read): a *plug-in* repository-level code graph
  (definitions and references at line level). Plugged into four existing methods across two
  approach families on SWE-bench it "substantially boosts the performance of all systems" and
  reaches SOTA among open-source frameworks; also tested on CrossCodeEval. This is the strongest
  evidence that the graph is a *harness* improvement, not a model improvement — it transfers.
- **Repository Memory** (2510.01003, ICLR 2026; abstract read): agents handle each task from
  scratch; adding memory built from **commit history** (recent commits, linked issues, summaries of
  actively evolving modules) "significantly improves LocAgent" on SWE-bench-verified and
  SWE-bench-live. Relevant to us as the *next* axis: structure first, then history. Not built yet.

### 2.2 Retrieval helps, but blind retrieval is weak

- **CodeRAG-Bench** (2406.14497; abstract read): across basic, open-domain and repository-level
  generation, retrieving high-quality context gives "notable gains", but **current retrievers
  struggle especially when lexical overlap is low**, and generators fail to improve with limited
  context quality. Translation: similarity search is not a substitute for structure, and structure
  is not a substitute for knowing what the task is about.

### 2.3 The reference implementation: Aider's repo map

Read from source, not from a blog post. `RepoMap.get_ranked_tags` builds `defines`/`references`
dictionaries from tree-sitter tags, then a `networkx.MultiDiGraph` with edges definition-file →
reference-file, weight `1/√(len(definers)·len(referrers))`, plus a `0.1` self-edge for
never-referenced definitions. It runs **PageRank** with a personalization vector that is 100×
larger for files in the chat, files whose name matches a mentioned identifier, and files named in
the conversation. `get_ranked_tags_map` then **binary-searches the number of ranked tags** to land
under a token budget (15% tolerance), rendering a tree with `⋮` for elision. Three design choices
are worth copying verbatim: personalization from the conversation, ranking *tags* not files, and a
token budget rather than a file count.

### 2.4 Counter-evidence — a shell-only agent can match graph tools

- **CodeScout** (2603.17829; abstract read): argues that recent work "equip[s] the agent with
  complex, specialized tools, such as repository graphs derived from static analysis", and shows
  that with a good RL recipe **a standard Unix terminal alone** is competitive or superior to
  models 2–18× larger, sometimes approaching closed models that use specialized scaffolds, on
  SWE-Bench Verified/Pro/Lite. This is the honest reason not to treat a repo map as a capability
  upgrade: the map must earn its place by *what it saves*, and it must degrade gracefully when the
  agent would rather grep.

### 2.5 Synthesis

The literature agrees on three things and is silent on the fourth:

1. explicit structure helps localization (LocAgent, RepoGraph);
2. retrieval without task context is weak (CodeRAG-Bench);
3. the winning representations are graph-shaped and budget-limited (Aider);
4. **nobody reports the ablation that matters for a small harness** — does the map help *without* a
   hint? CodeScout implies "grep is enough" there. So measure it locally.

## 3. What was built, and the choices the evidence forced

`bin/pi-repomap` (CLI + MCP stdio server), `skills/repomap/` (skill, `bench.py`, `selftest.py`).

| decision | evidence | consequence |
|---|---|---|
| definition→reference graph + PageRank | RepoGraph, LocAgent, Aider | `rank_files()` mirrors Aider's edge weight `1/√(defs·refs)` and 0.1 self-edge |
| personalize on mentioned identifiers and paths | Aider; CodeRAG-Bench (context must be task-shaped) | `--mention` / `--focus`; MCP `mention` argument |
| token budget, not file count | Aider's binary search | `--budget` in tokens at chars/4; renderer stops on the budget |
| regex extraction, not tree-sitter | this machine has neither tree-sitter nor ctags; no new dependency allowed | ~25 rules for python/rust/go/ts/js/sh/md + shebang detection; `selftest.py` covers each language |
| breadth-first rendering | measured (§4): depth-first hides the rest of the tree at 500 tokens | one symbol per file per pass, then a `(cont.)` pass |
| docs down-weighted to 35% | measured: `.md` files reach the top on PageRank alone and crowd out code | code ranks first at equal rank |
| keep grep | CodeScout | skill says: known name → grep; unknown/ambiguous → map |

Two things were deliberately **not** built: embeddings (CodeRAG-Bench: weak under low lexical
overlap; `bin/mem` already owns dense retrieval) and commit-history memory (§2.1, next axis, needs
its own measurement).

## 4. Measured on this machine (2026-11-15)

`skills/repomap/scripts/bench.py` samples symbols defined in exactly one file and asks, for each,
whether the map at 500/1000/2000 tokens contains the defining file and the definition. Baselines run
the *same renderer* with order-only substitutions: alphabetical, by file size, by identifier count.

### pergola (26 files, 539 symbols, 30 samples)

| condition | repomap | path | size | ident |
|---|---|---|---|---|
| mentions the identifier — file@500 tok | **100%** | 100% | 100% | 100% |
| mentions the identifier — mean file rank@1000 | **1.5** | 12.6 | 10.1 | 10.1 |
| no hint, file-uniform sample — file@1000 | 100% | 100% | 100% | 100% |

Small trees saturate: at 500 tokens every file is already listed once, so only the *rank* differs.

### agent tree (1 074 files, 3 940 symbols, 40 samples)

| condition | repomap | path | size | ident |
|---|---|---|---|---|
| mentions the identifier — file@500 | **100%** | 35% | 40% | 48% |
| mentions the identifier — mean file rank@1000 | **1.3** | 32.8 | 43.5 | 41.7 |
| no hint, file-uniform sample — file@1000 | 12% | 15% | 12% | 12% |
| no hint, symbol sample — file@2000 | 78% | 70% | **100%** | **100%** |

Index cost: 0.30 s cold / 0.16 s warm on 1 074 files (mtime-keyed cache); map render < 100 ms.

**Reading the numbers honestly.** With a hint the map is decisively better than every naive
ordering (100% vs 35–48% at 500 tokens; the defining file lands at rank 1.3 vs 33–44), which is the
usage the tool is now documented for. Without a hint, nothing wins: at 1 000 tokens only 65 of 555
symbol-bearing files fit, so 12–15% of files is what *any* ordering covers, and "biggest files
first" is as good as PageRank on a symbol sample (which over-represents big files by construction).
The blind map is therefore **not** a way to find an arbitrary file in a large tree; `grep` is.

## 5. What would falsify the design

- Three unfamiliar-tree sessions where `map --mention` is never opened or never changes the first
  file read → the skill is prompt cost with no behaviour change; delete it (skill PDSA).
- A task where the map's first file is wrong and a single grep was right → record it; if it recurs,
  raise the `mention` requirement in the skill rather than lowering the budget.
- `selftest.py` passing while `bench.py` recall@500 drops below 80% on the agent tree → the ranking,
  not the extraction, has regressed; the guard must include a bench floor (not yet enforced).

## Sources

arXiv (abstracts read): 2503.09089 LocAgent · 2410.14684 RepoGraph · 2510.01003 Repository Memory ·
2406.14497 CodeRAG-Bench · 2603.17829 CodeScout (counter-evidence).
Implementation read: Aider-AI/aider `aider/repomap.py` (PageRank bipartite map, personalization,
binary search on token budget). No web pages were used — search engines are bot-walled here.
