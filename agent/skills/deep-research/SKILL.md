---
name: deep-research
description: Run a citation-graph literature review over OpenAlex and arXiv, then write a cited digest into research/ and a memory row. Use when the owner asks for deep research, a literature review, "look into papers", or evidence for a design decision; search engines are bot-walled on this host.
---

# Deep research — a citation graph, not a search engine

One line: **walk the literature from seeds, cite every claim by id, and write the digest where the
next session will find it.**

## Source ladder (this host)

| Source | Use | Command |
|---|---|---|
| OpenAlex | citation graph, abstracts, ids | `research/litwalk.py` (cached, no key) |
| arXiv | frontier papers, full abstracts | `scripts/arxiv.py` |
| GitHub REST | repos, issues, code search | `pi-web api URL --shape` (or `--jq`) |
| Wikipedia API | definitions, background | `pi-web search --source wikipedia` |
| HN Algolia | practitioner signal | `pi-web search --source hn` |
| Crossref | papers when OpenAlex is budget-dead | `pi-web search --source crossref` |
| direct URL | known page | `pi-web get URL` (reader + cache) |
| Marginalia / Wiby | general web, small-web index | `pi-web search` |
| search engines | **do not use** | Bing/DDG/Google/Brave/Mojeek are bot-walled; `pi-web doctor` re-probes why |

`pi-web` caches everything (TTL + ETag), rate-limits per host and refuses local addresses, so a
repeat fetch is free and a throttle is reported instead of retried. Two budget facts, measured
2026-11-15 and recorded in `research/web-search-and-fetch.md`: **OpenAlex and Semantic Scholar use
per-IP free budgets shared with the whole network** — when they 429, use Crossref/arXiv that day
and do not retry. `pi-web doctor` writes the live matrix to `~/.cache/pi-web/health.json`.

## Workflow

1. **Frame the question and the decision it could flip.** Use the curiosity skill: a prior in
   0.3–0.7 and a named action that changes if the answer is different.
2. **Seeds.** Write `seeds.json` — a JSON array of 10–20 canonical query strings (title-ish works).
   ```bash
   cd ~/.pi/agent
   python3 research/litwalk.py seeds seeds.json        # -> seeds.resolved.json
   ```
3. **Walk** two hops over references + citing works:
   ```bash
   python3 research/litwalk.py walk --seeds seeds.resolved.json --out walk.json --depth 2 --cap 400
   ```
4. **Report** the subgraph, scoped by title/abstract regex:
   ```bash
   python3 research/litwalk.py report --in walk.json --top 60 --since 2020 \
     --grep "agent|memory|harness" --grep-title "agent|memory" --json-out next-seeds.json
   ```
5. **Frontier.** Pull recent arXiv papers your seeds would miss:
   ```bash
   python3 skills/deep-research/scripts/arxiv.py search "self-improving agents" --max 20 --sort submittedDate
   python3 skills/deep-research/scripts/arxiv.py get 2611.15885
   ```
6. **Read abstracts, extract claims.** Every claim gets an id (`W…` for OpenAlex, `YYMM.NNNNN` for
   arXiv) and a number only if the paper states it.
7. **Write the digest** to `research/<topic>.md` (format below).
8. **Cite it in memory** so `pi-preflight` can see the link:
   ```bash
   bin/mem add "Research base: <topic> — <one-line finding>" \
     -t "Research base: <topic>" -k source -i 0.8 -g research,<topic>
   ```
9. **If it changes a system**, open a PDSA cycle (`mem pdsa new --plan "..."`) and name the metric.
10. `bin/pi-preflight` checks that every `research/*.md` is cited by a memory row. Run it.

## Digest format (match `research/curiosity-creativity.md`)

```markdown
# <Topic> — evidence base for <decision>

Compiled <date>. Method: <seeds, hops, filters, arXiv frontier>. Raw harvest: <path>.
Every claim is tied to a retrievable id; numbers are stated only where the paper states them.

## <Section>
- **<Claim>** (<Author Year>, <id>): <finding>. <number if stated>.
- ...

## Gaps / conflicting evidence
- <what the literature does not settle>

## Implications for <system>
- <what changes in the harness / design>
```

## Rules

- **Primary sources only.** Do not cite a blog post that cites the paper; follow it back.
- **No invented numbers.** If the abstract does not state it, write "not stated in the abstract".
- **Distinguish claim from inference.** "The paper reports X" vs "this implies Y for us".
- **Note conflicts.** Two papers disagreeing is a finding, not a nuisance.
- **Cache and pace.** `litwalk.py` caches; arXiv is one request at a time. Do not hammer.
- **Delegate the harvest, not the judgement.** If the reading is wide, send a `scout` with the
  seed list and ask for a fold of ids + claims; do the synthesis and citation check here.

## Exercise

```bash
python3 ~/.pi/agent/skills/deep-research/scripts/arxiv.py search "agent memory" --max 3
```

If it prints three papers with ids and abstracts, the skill is live. If it fails, fix the script
before using it in a real review.
