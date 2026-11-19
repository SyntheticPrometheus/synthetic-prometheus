# New models 2026 (US, China, elsewhere) with innovative features

status: done
date: 2026-11-19
method: pi-web over HN, arXiv, model cards and release notes, 2026-06..2026-11 window

## Research
- `moonshotai/Kimi-K3` 2026-07-27 — 69 linear-attention layers + 24 gated MLA layers with a 2048-token indexer, LatentMoE, NoPE — 2.8T total / 104B active, 1M ctx — the linear+sparse KV split is what makes 1M context affordable.
- `deepseek-ai/DeepSeek-V4.1-Flash` 2026-09-10 — causal encoder-decoder asymmetric MoE with a 4x compressed KV cache — 552B total / 8B in 16B out active, $0.05/$0.20 per 1M — the cheapest credible bulk target we have.
- `nvidia/Nemotron-3.5-Lightning-30B-A3B` 2026-08-11 — hybrid Mamba-Transformer MoE shipped with NeMo Switchyard, a staged agent router — 30B/3B active, 4x output speed — the router pattern, not the weights, is the transferable part.
- `mistral.ai/news/mistral-large-4-oss` 2026-10-29 — three-tier controllable reasoning modes plus RL-tuned defensive security — 1T params, open weights — a reasoning-depth knob is a cost control we currently approximate with prompt text.
- `artificialanalysis.ai/models/celeris-1` 2026-07 — non-autoregressive diffusion LLM, 716–2,082 tok/s at $0.20/$0.70 per 1M — proprietary, size undisclosed — fast batch, but Inception's Mercury API shut down in Nov 2026, so the vendor risk is measured.
- `ikawrakow/ik_llama.cpp#2138` 2026-06-08 — scalar fallback for the fused MoE gate makes Gemma 4 26B-A4B decode on pre-AVX2 Ivy Bridge at 5.2 tok/s — 26B does not fit 7.7 GB — proves the kernel path, not the fit.
- `simonwillison.net/2026/Nov/3` 2026-08-16 — Qwen 3.8 27B can read raw weights as a tool (weight-space programming) — 27B is ~17 GB at Q4 — interesting, and out of reach on this host.

## Tangential (2x)
- tangential: NeMo Switchyard staged routing — from new-models-2026 — it could replace the flat regex-first routing in bin/pi-intent with a staged escalation that is measured per stage.
- tangential: controllable reasoning-depth modes — from new-models-2026 — it could turn our "think harder" prompt text into a per-call parameter with a token budget we can price.

## Systems impact
- bin/pi-intent routing table — change — evidence `nvidia/Nemotron-3.5-Lightning-30B-A3B` — a staged escalation (cheap model, then frontier on low confidence) with the escalation rate recorded, not a single threshold.
- bin/local-batch model choice — change — evidence `deepseek-ai/DeepSeek-V4.1-Flash` — re-price the residue tier at $0.05/$0.20 per 1M before sending volume to a local model that costs 40 minutes.
- bin/pi-techwatch source list — create — evidence `artificialanalysis.ai/models/celeris-1` — add model-card and release-note feeds; two of the six findings came from GitHub release pages, not from HN.

## Loops
- loop: model-routing-eval — metric: escalation rate and cost per answered task — falsifier: the staged router costs more per answered task over 100 tasks — guard: intent/eval.py --gate — cadence: intent-eval (7d)
- loop: techwatch-window — metric: new models reported per month with a primary source — falsifier: a month where the only entries are benchmark bumps — guard: bin/pi-techwatch --check — cadence: techwatch

## Debate
- FOR: a routed two-model pipeline is measured cheaper (74% cost cut reported by LangChain on 7% of calls) and Switchyard is open source / AGAINST: our own 7-way routing benchmark had Laya at 25% vs 54%, so a router change must pass intent/eval.py, not a vendor blog
- decision: keep — because the gate exists and a failed replay voids the change

## Test
- red: bin/pi-intent classifies a routing case it has never seen without an escalation path — green: intent/eval.py --gate — output: exit 0 only with a policy hash replay
- tester: redteam — technique: oracle

## Implementation
- path: skills/recursive-research/SKILL.md — check: bin/pi-research check --done — status: done
- path: research/rr/new-models-2026.md — check: bin/pi-research check --done — status: done
- task #263 — deferred tool loading, the one prompt-side saving in the window at −85% schema tokens — status: open
