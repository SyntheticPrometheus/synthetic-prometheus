# Hutter Prize winners and how their solutions work

status: done
date: 2026-11-19
method: prize.hutter1.net (http, https fails TLS hostname check), mattmahoney.net LTCB, winner repos

## Research
- `prize.hutter1.net` 2026-07-24 — active 500,000 EUR contest, 85,485 EUR paid, CHM funding #9–#11: under 99,420,425 B on 1 GB enwik9, one core, under 10 GB RAM, under 50 h — the rules bound compute, so a method that needs a cluster is not eligible.
- `prize.hutter1.net` #1 2006-09 — paq8hp5 (Rhatushnyak): PAQ8 context mixing plus an XML/Wikipedia dictionary preprocessing — 17,073,018 B on enwik8 (5.86x) — reversible preprocessing before statistics is the oldest trick in the list.
- `github.com/amargaritov/starlit` #5 2021-05 — Doc2Vec + TSP article reordering, HP transforms, cmix with an 850 MB PPMD and a 200-cell LSTM mixer — 115,352,938 B (8.67x) — reordering by semantic similarity beats a stronger model fed unsorted text.
- `github.com/saurabhk/fast-cmix` #6 2023-07 — cmix-hp plus devirtualisation, cache-locality and hash-map work — 114,156,155 B (8.76x) — the same models, faster, bought headroom for a heavier one under the time cap.
- `github.com/kaitz/fx2-cmix` #8 2024-09 — voyage-large-2 embeddings + t-SNE + k-means ordering, four stemmed streams, online reverse dictionary, mixer update skipping — 110,793,128 B (9.03x) — two of those four are preprocessing, not modelling.
- `github.com/blahem/cmix-lex` #9 2026-06 — payload_lex reorders the PHDA9 tail by Lehmer rank and hints the page cache (MADV_DONTNEED) — 109,671,639 B (9.11x) — a reversible structural reorder of metadata.
- `prize.hutter1.net` #11 2026-07-24 — fx2-cmix-T (Ivanov): replaces the online LSTM with a 6M-parameter Transformer pre-trained on enwik9 for 26 h on 8x RTX 5090, decoded CPU-only — 100,424,672 B (9.96x), 7.46% better — train offline, infer on one core.

## Tangential (2x)
- tangential: small pre-trained Transformer as a residual/prior head (fx2-cmix-T, cmix-obias) — from hutter-prize — it could score dedup/closure candidates in mem on CPU with an offline-trained 6M model instead of a cloud embedding call.
- tangential: embedding-ordered batching (starlit, fx2-cmix) — from hutter-prize — sorting work so a finite window sees similar items consecutively is a cache strategy for our batch runner, not just for a compressor.

## Systems impact
- bin/local-batch ordering — change — evidence `github.com/amargaritov/starlit` — order work by similarity before batching, so a shared prefix or context is reused; measure tokens and wall time per item.
- mem dedup/closure scoring — change — evidence `prize.hutter1.net` #11 — an offline-trained tiny model decoding on CPU is the shape that fits 7.7 GB; a cloud embedding is the thing it would replace.
- skills/local-models claim — change — evidence `prize.hutter1.net` #1 — preprocessing gains compound even on a strong backend, so a prompt/token-normalisation pass deserves the same trial as a smaller model.

## Loops
- loop: asymmetric-model-trial — metric: dedup precision and CPU ms/item against the current path — falsifier: no precision gain at 2x the CPU cost over 500 pairs — guard: tests/pi-research.sh plus a labelled 500-pair set — cadence: none until the set exists
- loop: ordering-effect — metric: tokens and seconds per batch under random vs similarity order — falsifier: no difference over 10 batches — guard: bin/local-batch log — cadence: local-batch retrospective

## Debate
- FOR: the current record is won by an asymmetric model (GPU train, CPU decode) and a 7.46% margin, which is exactly our constraint / AGAINST: every entry is single-purpose compression on a 1 GB corpus with 50 hours of one core, and our dedup task has labels, not a code length
- decision: keep — because the transferable claim is the asymmetry and the preprocessing, both testable on a labelled set before any model is trained

## Test
- red: mem dedup has no labelled pair set, so no threshold can be falsified — green: bin/pi-research check --done — output: exit 0, five digests pass with an id per claim
- tester: redteam — technique: oracle

## Implementation
- path: skills/research-to-ship/SKILL.md — check: bin/pi-research check --done — status: done
- path: research/rr/hutter-prize.md — check: bin/pi-research check --done — status: done
- task #264 — test an offline-trained tiny model on mem dedup before buying more cloud embedding — status: open
