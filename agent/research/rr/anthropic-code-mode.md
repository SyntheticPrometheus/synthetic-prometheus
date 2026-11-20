# Anthropic code mode: code execution as tooling

status: done
date: 2026-11-19
method: pi-web over Anthropic engineering/research posts, Cloudflare blog, HN, arXiv (7 fetches, 5 min)

## Research
- `anthropic.com/engineering/code-execution-with-mcp` 2025-11-04 — MCP servers presented as a TS file tree + sandboxed execution cut a run from 150,000 to 2,000 tokens (98.7%), vendor-stated — the argument is context, not speed.
- `anthropic.com/research/advanced-tool-use` 2025-11-24 — programmatic tool calling averaged −37% tokens (43,588→27,297) and GIA 46.5%→51.2%; a search tool with deferred loading cut 77k→8.7k tokens and Opus 4.5 79.5%→88.1% — hybrid, not wholesale.
- `anthropic.com/engineering/claude-code-sandboxing` 2025-10-20 — OS sandbox (bubblewrap + network proxy) instead of a container, −84% internal permission prompts — the only version that fits 8 GB with no VM.
- `blog.cloudflare.com/code-mode-mcp` 2026-02-20 — an entire API as TypeScript in a V8 isolate at ~1,000 tokens of schema — vendor claim, hosted isolate is the lock-in risk.
- `arxiv:2402.01030` 2024-02 (CodeAct, ICML) — executable Python actions beat JSON tool calls across 17 LLMs, up to +20% success — independent of the vendor posts.
- `arxiv:2607.05743` 2026-07-07 — systematization of 39 execution-security papers: command denylists fail 69–98% of the time, TOCTOU and MCP threats overlap — isolation, not filtering.
- `arxiv:2610.32555` 2026-10-23 — MCP-Injector, 1,350 cells: realistic tool faults cut task score 60% (8.08→3.23/10) and model scale bought nothing (120B vs 20B, p=0.96) — retries in the harness, not a bigger model.

## Tangential (2x)
- tangential: OS-level bubblewrap sandboxing (sandbox-runtime) — from anthropic-code-mode — it could replace the denylist instinct in our tester step with a capability the tester can actually try to break.
- tangential: deferred tool-schema loading (defer_loading / Tool Search) — from anthropic-code-mode — it could remove the fixed tool-schema prompt we pay on every turn, including on local models where prefill is minutes.

## Systems impact
- skills/research-to-ship step 4 — change — evidence `anthropic.com/engineering/claude-code-sandboxing` — the tester is told to try the sandbox escape before the feature test, because a denylist is the failure mode.
- bin/pi-delegate ledger — change — evidence `arxiv:2610.32555` — a child that failed on a tool fault should be retried by the parent, and the retry count recorded; today the verdict is pass/fail only.
- codemode sandbox claim — create — evidence `arxiv:2607.05743` — state what the JS sandbox can reach (no fs, no net) in the skill that tells a tester to attack it, so "isolated" is checkable.

## Loops
- loop: dispatch-fault-retry — metric: share of failed dispatches with a recorded retry — falsifier: two weeks with no retry recorded while a child failed on a tool error — guard: bin/pi-delegate verdict — cadence: none, per-dispatch
- loop: research-gate — metric: `bin/pi-research check` exit code and failure count — falsifier: a published digest that omits a falsifier — guard: bin/pi-preflight research — cadence: every publish

## Debate
- FOR: 150k→2k tokens and +20% success (Independent CodeAct result) say code-as-action is cheaper than one call per step / AGAINST: all the token numbers are vendor-reported, and 69–98% denylist failure means a local sandbox is a new attack surface we would have to test, not inherit
- decision: keep — because the security paper is the load-bearing evidence: isolation + a tester who tries to escape, not a denylist

## Test
- red: `bin/pi-research check --done` on a skeleton digest exits 1 with 21 failures — green: `bin/pi-research check --done` — output: exit 0 once the five digests are filled
- tester: tester — technique: access

## Implementation
- path: bin/pi-research — check: bin/pi-tool check pi-research — status: done, with the seven refusal rules pinned by seven mutations
- path: research/rr/anthropic-code-mode.md — check: bin/pi-research check --done — status: done
- task #261 — sandbox the code-execution path in bubblewrap and have a tester try the escape — status: open
