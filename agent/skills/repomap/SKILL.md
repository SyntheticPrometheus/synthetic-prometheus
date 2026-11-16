---
name: repomap
description: "Ranked, token-budgeted map of a codebase plus symbol lookup — the repomap, symfind and outline MCP tools (or the pi-repomap CLI) to choose which files are worth reading in an unfamiliar or large tree, and to find where a symbol is defined and which files reference it. Use before a wide grep-and-read pass, when a task names an identifier or a module, or when deciding whether a tree is small enough to read wholesale."
---

# Repomap — structure before grep

One line: **the task names something; the map says which files that something lives with, inside a
budget you choose.**

This harness reads code with `grep` and `read`. That answers "where is this token" and nothing else.
`pi-repomap` answers the question that actually precedes a wide read: *for this task, which files
matter, and what is in them*. It parses definitions, builds a definition→reference graph, PageRank
it (personalised by the files and identifiers the task mentions) and renders the highest-value
symbols that fit a token budget.

## Three entry points

| need | MCP tool (preferred) | CLI |
|---|---|---|
| where do I start in this tree | `repomap {path, budget?, focus?, mention?}` | `pi-repomap map PATH --budget 1500 --mention IDENT` |
| where is X defined, who uses it | `symfind {name, path?}` | `pi-repomap find X --root PATH` |
| what is in this one file | `outline {file}` | `pi-repomap outline FILE` |
| warm/refresh the index | — | `pi-repomap index PATH` |

The MCP server (`pi-repomap mcp`, registered in `mcp.json`) is direct-exposed, so the tools are in
the prompt; no extra setup.

## Recipes

```bash
# first contact with a repo: bias the ranking with the words the task used
pi-repomap map ~/Projects/pergola --budget 1200 --mention note_configure --focus crates

# a definition and its blast radius in one call (cheaper than grep when the name is common)
pi-repomap find windows --root crates

# before editing a long module
pi-repomap outline bin/pi-agenda
```

Budget is tokens at chars/4, so `--budget 1000` is roughly 4 000 characters. On a tree under ~60
files, 500 tokens already covers every file once; spend the rest on depth.

## When the map is the wrong tool (measured, not opinion)

`skills/repomap/scripts/bench.py` samples symbols and files and reruns the same renderer with three
naive orderings (alphabetical, by size, by identifier count). Numbers below are from
2026-11-15 on this machine; `bench.py --json` reproduces them.

| condition | repomap | best baseline | verdict |
|---|---|---|---|
| task names the identifier (pergola, 26 files) | 100% file@500 tok, mean rank 1.5 | 73–100%, rank 10–12.6 | use it |
| task names the identifier (agent tree, 1074 files) | 100% file@500 tok, mean rank 1.3 | 18–48%, rank 33–44 | use it |
| no hint at all, 1074 files, 1000 tok | 12% of files | 12–15% | **do not** expect a blind map to find an arbitrary file |

So: **pass `--mention`/`mention` or `focus`.** The map is a way to spend a hint, not a substitute
for one. And for a name you already know, `grep` is one call and ~50 tokens — the map wins when the
name is unknown, ambiguous, or you need to see structure before choosing.

## What it does not do

- No LSP, no types, no scopes: symbols come from per-language regexes (python, rust, go, ts/js, sh,
  markdown, extensionless shebang scripts). Reflection-generated names and macro-built symbols are
  invisible. Verified by `scripts/selftest.py`.
- A symbol shown is a signature line, not a body. Read the file for the body.
- Binary/large files (>512 KB) and `node_modules`, `target`, `vendor`, `upstream`, `publish` are
  skipped by default; pass `--exclude REGEX` for more.
- Docs (`.md`) are shown at 35% of their PageRank so code ranks first; the digest is still useful for
  "where is this documented".

## Guard and evidence

- `scripts/selftest.py` — 24 assertions on a fixture tree (extraction per language, budget,
  ranking, cache, `find`, `outline`, MCP handshake). `pi-preflight` runs it as the `repomap`
  check, so a regex that silently stops matching fails preflight rather than quietly degrading maps.
- `scripts/bench.py` — the ranking comparison above.
- Research and the counter-evidence: `research/repo-map-code-localization.md`.

## PDSA

Metric: tool calls and tokens spent before the first correct file is opened on a task that starts
with an unfamiliar tree (baseline: the 2026-11-15 session that ran one grep 18 times). Hypothesis:
`map --mention` replaces 2–4 exploratory greps with one 500–1500-token call. Study it on the next
three unfamiliar-tree sessions; if the map is never opened, delete the skill rather than let it
drift.
