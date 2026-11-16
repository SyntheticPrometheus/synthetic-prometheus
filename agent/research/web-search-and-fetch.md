# Reaching the internet from this host — measured matrix and design

Compiled 2026-11-15. Method: (a) 30+ live probes of search engines, readers and APIs from this
machine, recorded with status/size/content checks; (b) arXiv abstracts read for five papers on
search-augmented systems and web-content extraction; (c) source read of the reference MCP fetch
server (`modelcontextprotocol/servers`, `src/fetch/.../server.py`) for its network policy. All
numbers below are from this host on this date; `bin/pi-web doctor` re-derives the matrix and
records it in `~/.cache/pi-web/health.json`.

Decision it informs: whether to keep hand-rolling `curl` per session (162 curl calls across 13
sessions in the two days before this note) or to build one measured access layer with visible,
attributable failures.

## 1. The question

How should this agent reach the internet, given that (i) search engines return bot challenges from
this IP, (ii) the free API budgets are shared per-IP, and (iii) the agent usually needs *technical*
sources (docs, papers, package metadata, issue threads), not general web pages?

Prior before measuring: 0.5 that a general keyless search path exists; 0.7 that a
`fetch → markdown` reader works well enough to replace `curl` + reading raw HTML.

## 2. Literature

- **Over-Searching in Search-Augmented LLMs** (2601.05503, EACL 2026; abstract read): search
  improves accuracy on answerable queries but **harms abstention on unanswerable ones**;
  over-searching is worse in complex reasoning and deep-research systems, is *exacerbated by noisy
  retrieval*, and **compounds across turns**; they introduce Tokens-Per-Correctness (TPC) to score
  the trade-off, and note that **negative evidence improves abstention**. Design consequence: an
  empty result must be reported as an empty result, and the tool must make a search cheap enough
  that searching is a choice rather than a gamble.
- **Search Arena** (2506.05334, ICLR 2026; abstract read): 24k crowd-sourced multi-turn
  interactions with search-augmented systems. Users prefer answers with **more citations even when
  the cited content does not support the claim**, and preference varies by source type — community
  platforms are generally preferred and encyclopedic sources "are not always appropriate and
  reliable". Design consequence: the tool must carry the source and URL *per result* so a citation
  can be checked, and the reporting rule is "quote the line you fetched", not "attach links".
- **Dripper** (2511.23119; abstract read): main-content extraction reformulated as constrained
  sequence labelling with a 0.6B model, trained on WebMainBench (7,809 pages, 5,434 domains);
  it **outperforms heuristics like Trafilatura** and rivals 685B-class models at 3.08 pages/s on one
  A100. Design consequence: heuristic extraction is a fallback, not the primary reader; a
  server-side main-content pipeline (r.jina.ai) is the default, and the local stdlib extractor
  exists only so `--raw` and reader outages still work.
- **WebSuite** (2406.01623; abstract read): failures of web agents should be attributed to specific
  *web actions* rather than scored end-to-end, because that is what makes them fixable. Design
  consequence: `doctor` reports per-source state and *reason* (blocked / throttled / rate limited /
  no results), and the preflight line names which sources are down.

## 3. Measured host matrix (2026-11-15)

Every row was probed with a real query ("tiling window manager" / "rust tiling") and the body
checked for result links vs challenge text.

| endpoint | HTTP | verdict |
|---|---|---|
| `old-search.marginalia.nu/search?query=` | 200, 94 links, 25 result cards | **works** — small-web index: docs, blogs, technical writing. After ~10 queries in a few minutes it returned "the search engine is currently barraged by queries from bots" (a 997-byte page). Throttled per-IP, not blocked |
| `wiby.me/?q=` | 200, 3 results, any UA | **works** — curated old-web index, small but real sites |
| `r.jina.ai/<url>` | 200, markdown, `x-ratelimit-limit: 20;w=60` | **works** — the reader; metadata preamble + `Markdown Content:` body |
| Wikipedia API, HN Algolia, StackExchange, MDN, crates.io, Crossref, arXiv Atom, GitHub REST | 200 | **work** — structured, keyless (GitHub 10 req/min unauth, arXiv ≤1 req/3 s) |
| `api.openalex.org` | 429 `Insufficient budget... free daily budget shared by everyone on your network's IP` | **exhausted per-IP**; retrying cannot help |
| `api.semanticscholar.org` | 429 `Too Many Requests` | **rate limited per-IP** |
| `html.duckduckgo.com/html`, `lite.duckduckgo.com` | 200 with challenge / 202 | **bot-walled** |
| `bing.com/search` | 200, 120 KB, challenge markers, no external result links | **bot-walled** (matches mem #16: unrelated cached results) |
| `mojeek.com/search` | 200, 5 KB, challenge | **bot-walled** |
| `google.com`, `search.brave.com` | JS-only | **unusable without a browser** |
| `startpage.com` | Anubis challenge (`anubis_version` payload) | **bot-walled** |
| `ecosia.org` | 403 "Just a moment..." | **bot-walled** |
| `searx.be` / `searx.tiekoetter.com` / `priv.au` / `opnxng.com` | 200 challenge / 429 | **unusable**; `search.inetol.net` served a "Security check" page |
| `md.dhr.wtf/?url=` (markdown proxy) | 500 | **down** |
| `api.marginalia.nu/public/search/...` | timeout at 30 s | **unreachable** from here |

Three distinct failure classes, not one:

1. **Bot challenge** — the endpoint is alive and does not want this client. Retrying is abusive and
   useless; the correct response is to say so and use another source.
2. **Shared per-IP budget** — OpenAlex/Semantic Scholar. Retrying is useless; the budget is the
   network's, not the agent's.
3. **Throttle** — Marginalia under load. Retrying after minutes works; retrying immediately makes it
   worse.

## 4. Design decisions and their evidence

| decision | evidence | consequence in `bin/pi-web` |
|---|---|---|
| default `search` = Marginalia + Wiby + HN + Wikipedia, technical sources on request | §3: these are the ones that answer; §2 Over-Searching: fewer, better-targeted sources | `--source` adds mdn/stackexchange/crates/github/arxiv/crossref/openalex |
| reader first, heuristic extraction second | Dripper (§2) | `get` → r.jina.ai; on failure local HTMLParser with boilerplate peel |
| per-source failure reasons, not one "search failed" | WebSuite (§2) | every adapter's error is ranked and printed; `doctor` records `blocked/throttled/429/no results` |
| cache with TTL + ETag on everything | Over-Searching TPC (§2), and the shared IP in §3 | `~/.cache/pi-web/http`, 304 revalidation, `(cached)` in output |
| cooldown on throttle | §3 class 3 | 15-minute cooldown file; a later call skips the host and says why |
| never retry a budget 429 | §3 class 2 | body sniffed for "insufficient budget"/quota before the retry branch |
| robots.txt for page fetches, local-address refusal, RFC1918 block | reference implementation (`mcp_server_fetch`: robots.txt for autonomous fetches, private-destination guard, capped body read) | `robots_allowed()`, `guard_url()`, `--allow-local` escape, 3 MB body cap |
| `api --shape` instead of raw JSON by default | local failure history: 5 consecutive `KeyError: 'issues'` on the GitHub search API (the key is `items`) | shape prints keys/types/list sizes two levels deep; `--jq` is the escape hatch |

## 5. What would falsify this

- `pi-web doctor` shows Marginalia working *and* Wiby working while sessions still hand-roll `curl`
  for search → the skill is not routing; fix the route or delete the tool.
- A task where the reader (`jina`) returns a login wall or a cookie banner and the local extractor
  does better regularly → flip the default.
- Marginalia's throttle becomes permanent for this IP → `search` degrades to Wiby + APIs; the
  honest answer then is "no general web search here", and the skill must say that rather than
  implying one exists.
- `selftest.py` green but `doctor` reporting "no results" from a working endpoint → a parser has
  drifted from the site's markup; add the live HTML as a fixture (that is how the Marginalia and
  Wiby fixtures in `skills/web/fixtures/` were captured).

## Sources

arXiv (abstracts read): 2601.05503 Over-Searching · 2506.05334 Search Arena · 2511.23119 Dripper ·
2406.01623 WebSuite. Implementation read: modelcontextprotocol/servers fetch server (robots.txt,
private-destination guard, readability → markdown, body cap). Live probes: §3, reproducible with
`bin/pi-web doctor`. No web pages were used to write this note: search engines are bot-walled here,
which is the subject of the note.
