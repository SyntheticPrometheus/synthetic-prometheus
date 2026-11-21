---
name: web
description: "How this host reaches the internet, measured — pi-web search/get/api (MCP tools web_search, web_get, web_api) over the sources that actually answer, with the bot-walled engines named so they stop being re-tested. Use whenever a task needs a web page, a package, a paper, a doc or a current fact; before writing a curl by hand; and when a source fails, to run pi-web doctor instead of guessing."
---

# Web — the measured matrix, not a search engine

One line: **APIs answer, readers work, engines are walled; ask the source that answers and cache
what it said.**

## Entry points

| need | MCP tool | CLI |
|---|---|---|
| find pages / discussions / docs | `web_search {query, n?, sources?}` | `pi-web search "q" [--source …]` |
| read one URL as markdown | `web_get {url, max_chars?, raw?}` | `pi-web get URL` |
| call a JSON API | `web_api {url, shape?, jq?}` | `pi-web api URL --shape` / `--jq '.items[0]'` |
| which sources work *today* | — | `pi-web doctor` |
| cache size / clear | — | `pi-web cache --stats` / `--clear` |

Default search sources: `marginalia,wiby,hn,wikipedia`. Add technical ones explicitly:
`--source arxiv,crossref,mdn,stackexchange,crates,github,openalex` (each has its own rate limit).

## What actually answers (2026-11-15, re-measured by `pi-web doctor`)

| source | state | note |
|---|---|---|
| Marginalia (`old-search.marginalia.nu`) | works, **throttled by shared IP** | the small-web index: docs, blogs, technical writing. On "barraged by bots" the tool sets a 15 min cooldown and serves the last good SERP for that query marked `(stale)` |
| Wiby (`wiby.me`) | works | curated old web; small index, real sites |
| r.jina.ai (reader) | works | URL → markdown, 20 req/min keyless |
| Wikipedia, HN Algolia, StackExchange, MDN, crates.io, GitHub, Crossref, arXiv | work | structured APIs; arXiv wants ≤1 req/3 s, GitHub 10/min unauthenticated |
| OpenAlex, Semantic Scholar | **per-IP budgets shared with the whole network** | 429 "insufficient budget" or "too many requests"; use Crossref/arXiv today, retry tomorrow |
| DuckDuckGo (html/lite), Bing, Google, Brave, Mojeek, Startpage, Ecosia, public SearXNG | **bot-walled** | challenges, "verify you are human", or unrelated cached results. `doctor` re-probes them so this line can go stale safely |
| PyPI | JSON per package only (no search) | `pi-web api https://pypi.org/pypi/<pkg>/json --shape` |

Do not re-test an engine because a result was disappointing — run `doctor`; it records the reason
per source (blocked, throttled, rate limited, no results) into `~/.cache/pi-web/health.json`.

## Rules that come from evidence, not taste

- **Do not search what is already known locally.** Over-searching is measurably harmful: it hurts
  abstention on unanswerable questions and compounds across turns (2601.05503). Check `mem search`,
  the repo, and `pi-repomap find` first; search is for facts that are outside this machine.
- **Cite the URL and quote the sentence.** Users prefer answers with more citations *even when the
  citations do not support the claim* (Search Arena, 2506.05334) — so a citation here means a
  fetched URL plus the line it came from, not a list of links attached after the fact.
- **Prefer the primary source to the encyclopedia** for practice (docs, changelog, RFC, source
  code); Wikipedia is for definitions and orientation.
- **An empty result is information.** Report "no source returned anything, here is what failed"
  rather than narrowing until something plausible appears.
- **Extraction is not neutral**: server-side main-content rendering (jina) beats local heuristics on
  messy pages (Dripper, 2511.23119 shows a 0.6B model beating Trafilatura); `--raw` exists for when
  you want the page as the site made it, not a summary of the main text.

## Working notes

- Everything is cached in `~/.cache/pi-web/http/` with TTL + ETag; a repeat call is free and shows
  `(cached)`. `--max-age 0` forces a fresh fetch.
- Per-host token buckets, one retry on 429/5xx honouring `Retry-After`; a *budget* 429 (OpenAlex) is
  not retried because retrying cannot help.
- `web_api --shape` exists because indexing a response you have not looked at is a real failure
  mode here: five consecutive `KeyError: 'issues'` calls in one session on the GitHub search API
  (the key is `items`).
- No login walls, no CAPTCHA solving, no browser. If a source needs a session, the answer is a real
  API or a runbook step driven by you (`skills/account-setup`), not a scrape.

## Guard and PDSA

- `skills/web/scripts/selftest.py` — offline parser/extractor/cache/limiter/shape/MCP assertions,
  run by `pi-preflight` as the `web` check. A parser that silently stops matching fails preflight;
  a source that is down does not (that is `doctor`, a warning).
- Throttle behaviour: a repeat query is served from the last good Marginalia SERP, marked `(stale)`
  with a line saying the source is throttling, instead of failing closed. The first query for a new
  search still fails honestly, because there is nothing cached to stand in for it.
- Metric: curl-in-bash calls per session that could have been `pi-web` (baseline 162 over 13
  sessions, 2026-11-15) and web-call failures. Hypothesis: routing through the tool cuts both and
  makes failures attributable. If sessions keep hand-rolling curl, delete the skill.
- Evidence and the source matrix rationale: `research/web-search-and-fetch.md`.
