---
name: memory
description: Persistent agent memory — capture durable facts, decisions and lessons; recall them with hybrid BM25+dense+graph search; consolidate on a schedule. Use at the start of every session (mem brief), before assuming anything about you/machine/history (mem search), when something durable is learned (mem add), and when running or recording PDSA improvement cycles (mem pdsa).
---

# Agent memory

`~/.pi/agent/bin/mem` — SQLite store, no LLM in the retrieval loop, ~10 ms warm recall.

Design rules that must not be violated:
- **Raw text is never rewritten or deleted.** Digests and graphs are indexes *over* raw entries.
  (Reason: Raw-RAG, arXiv 2610.30755 — transformed stores lose evidence coverage.)
- **No LLM extraction tax on writes.** Writes are mechanical and cheap; the model decides what
  matters, the store just indexes it well.
- **Conflicts are resolved by invalidation, not deletion** (bi-temporal `valid_to`/`superseded_by`).
- **Archived ≠ gone.** Archived rows stay in the DB and in `memory/journal/*.jsonl`.

## Session protocol

1. **Open** — the `memory-boot` extension already injects `mem brief` (pinned core + key lessons +
   recent + open PDSA) into the system prompt as the `session_memory` section, so it is usually
   already in front of you. Re-run `mem brief` yourself if that section is missing or empty.
2. **Recall before assuming** — `mem search "phrase"` whenever the answer might already be known
   (owner preferences, machine facts, past decisions, "why did we do X"). Budget default 1400 tok;
   use `--k 3 --budget 400` for cheap confirmation.
3. **Capture as you go** — `mem add` for anything that would still matter next week.
4. **Close** — add the lesson(s) learned, record/advance the PDSA cycle, and leave the store
   consolidated. A session with no new memory should be the exception.

## Capture rules

Write when any of these is true: a preference/constraint from you; a machine/infra fact that
took work to discover; a decision plus its reason; a mistake and its fix; a reusable procedure;
a source worth citing. Do not write: restatements of the current task, transient file contents,
or anything inferable in one command.

```
mem add "<verbatim body, 1-4 sentences of real content>" \
  -t "short dense title" -k fact|pref|decision|lesson|task|note|source|playbook \
  -i 0.5 -g comma,tags -s global|project:<path>|topic:<x> [--pin]
```

- `-i` importance: 0.95 = never forget (mandate, hard constraints), 0.8 = important, 0.5 = default,
  0.2 = trivia. Decay is `importance × exp(-age/τ)` with τ by kind (lesson 180 d, fact 90 d, task 14 d),
  so a low-importance note genuinely fades unless re-accessed.
- `-k lesson` is reserved for distilled, transferable insight ("X fails because Y; do Z instead").
- `--pin` for the handful of entries that belong in every session (mandate, core architecture).
- Superseding an outdated fact: `mem add` the new one, then `mem supersede <old> <new>`.

## Recall

`mem search` fuses five rankings with RRF — BM25 (FTS5, title×4), idf-weighted phrase/entity index,
verbatim bigram proximity, personalized PageRank over the memory/entity graph, and MiniLM cosine —
then reranks with anchor/title coverage + decayed importance, applies MMR-lite dedupe, and fills a
token budget. Cost knobs: `--k`, `--budget`, `--scope project:/path` (boosts matching scope), and
`--no-dense` (lexical+graph only: ~89 ms cold but −0.19 MRR, so only for speed-critical loops).
`--json` for machine consumption. After a recall actually answers the question: `mem used <ids...>`.

## Consolidation ("sleep") — weekly, or when live memories > 150

```
mem consolidate --digest          # dry-run first: --dry-run
```
Does four things, in order: (1) archives paraphrase/near-duplicates (cos ≥ 0.90 or jaccard ≥ 0.80),
keeping the stronger one and linking both; (2) auto-supersedes conflicting entries when the newer text
carries update cues ("now", "migrated", "no longer") and the pair is similar; (3) decay-archives entries
below the activation floor older than 45 d; (4) `--digest` builds extractive theme digests
(kind=digest) that link to their sources. Review with `mem stats` and the `events` table.

## PDSA — the standing philosophy

Every system built or run gets an explicit, measured improvement loop. No system is "done"; keeping a
cycle open is the normal state.

```
mem pdsa new --plan "Hypothesis + the metric that would falsify it"
mem pdsa update --cycle N --do "what changed" --metric-before 0.68 --metric-after 0.76 --status open
mem pdsa update --cycle N --study "measured result + why" --act "keep/revert/next hypothesis" --status closed
mem pdsa list
```
Rules: a cycle without a number is not a cycle; `--act` must say *keep*, *revert*, or the next
hypothesis. Revert anything that fails its metric — keep the note explaining why.

Feedback loop for this memory system specifically: whenever a real recall misses, add that query to
`~/.pi/agent/memory/eval.json` with the expected id, then `mem eval -v`. The eval set is the ratchet.

## Ops

| command | use |
|---|---|
| `mem doctor` | capabilities, dense layer status, embed latency |
| `mem eval -v` | recall@6 / MRR / tokens / ms on the fixed eval set |
| `mem embed` | (re)build dense vectors after bulk imports |
| `mem reindex` | rebuild FTS + entity index from `memories` |
| `mem export --format md\|jsonl` | human/git-friendly dump |
| `mem get <id>` | full record + entities + edges |
| `mem forget <id>` | archive (reversible: `archive` flag, raw text retained) |

Backups: `cp memory.db` + `journal/` is sufficient; journal is append-only and precedes every write,
so the DB can be rebuilt from it. Tests: `MEM_HOME=/tmp/memtest mem ...` runs against a scratch store
(the dense model/venv stay shared under `~/.pi/agent/memory`).

Extension: `~/.pi/agent/extensions/memory-boot.ts` injects the brief at session start via
`systemPromptOptions.sections` (diffed by Pi, not a full prompt replacement); it fails open — if `mem`
errors, the session simply starts without the block.

Failure modes: dense layer silently off if `memory/venv` or `memory/model` is missing (lexical+graph
still work — check `mem doctor`); cold CLI ≈ 295 ms with the dense layer (numpy + onnxruntime import),
≈ 89 ms with `--no-dense`, warm in-process ≈ 15 ms; `--budget` too small silently truncates
results, so read the footer line. `bin/mem` is a 4-line `sh` launcher → `bin/mem.py` (the real code).

See `references/research.md` for the literature this is based on and `references/design.md` for the
scoring math and metric history.
