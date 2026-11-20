# Recent compression algorithms with innovative useful features

status: done
date: 2026-11-19
method: GitHub releases (openzl, lz4, clp, brotli, xz) plus arXiv 2610/2611, 6 min

## Research
- `meta/openzl` v0.3.0 2026-09-29 — PivCo Huffman LZ plus a Compression Transformer that selects/trains coders, dict bundles, instant-parse decode — 3,062 MB/s decode (2.73x) and +34.9% numeric ratio vs zstd -19 — asymmetric: slow encode, fast decode.
- `lz4/lz4` v1.11.0 2026-11-04 — random access inside frames (LZ4F_seek/LZ4F_tell, resumeFrame) plus 4 KB+64 KB dict speedup — 2,352 MB/s decode, +88% on 4 KB blocks — seek is the feature, not the ratio.
- `arXiv:2610.37176v2` 2026-10-27 — permutation-based compression of the HNSW graph with SIMD Stream VByte at query time — up to 52.7% ratio, negligible latency — the graph index we keep in memory verbatim.
- `arXiv:2611.05871v1` 2026-11-04 — batch-invariant arithmetic coding parallelises the sequential token dependency on GPU — 5.8x encode, 3.0x decode — a GPU win with no meaning on this CPU.
- `y-scope/clp` v0.14.1 2026-10-27 — clp-json searches compressed JSON logs without full decompression — ratio/throughput not stated in the release — the interesting property is search without inflate.
- `google/brotli` v1.2.1 2026-10-21 and `xz` v5.8.4 2026-09-09 — security-only releases (CVE-2026-111497, GHSA-5qpq-xqfv-j9pg) after a 7-month patch lag — a decoder is an attack surface, so ratio is not the only axis.

## Tangential (2x)
- tangential: KV-cache and weight compression (GAAC, LittleBit, Bonsai 2) — from compression-2026 — it could move a 7B model's residency under 7.7 GB without changing the kernels, which is the local-independence question.
- tangential: ALP/adaptive float compression with SIMD FastLanes — from compression-2026 — it applies directly to the float embeddings stored beside memory.db, which no lossless text codec handles well.

## Systems impact
- bin/pi-burn reporting path — create — evidence `meta/openzl` v0.3.0 — a measured row for bytes-on-disk per subsystem (journals, memory.db, research caches) so a codec change is chosen on our bytes.
- research cache and session journal rotation — change — evidence `lz4/lz4` v1.11.0 — random access means a compressed log can be read without inflating the whole file, so retention can lengthen without a latency tax.
- brotli/xz decoders on untrusted input — remove — evidence `google/brotli` v1.2.1 — do not decompress fetched web payloads in-process; the CVE history is the argument, and pi-web already fetches text.

## Loops
- loop: corpus-compression — metric: bytes on disk and milliseconds to grep one month of journals — falsifier: a codec that saves 20% disk and doubles read latency — guard: tests/pi-research.sh plus a timed command in the digest — cadence: none until measured
- loop: decoder-surface — metric: number of C decoders reachable from fetched input — falsifier: a fetched payload that reaches a decoder with no sandbox — guard: pi-preflight secrets/web — cadence: each publish

## Debate
- FOR: OpenZL's 3,062 MB/s decode at +34.9% ratio would pay for itself on a 2-core Ivy Bridge, where decode speed is the whole cost / AGAINST: the release notes give no pre-AVX2 number, the Transformer tier trades CPU for ratio, and our corpus is a few hundred MB — not 1 GB of enwik
- decision: keep — because the measurement that decides is ours, and it is a task, not a package install

## Test
- red: no recorded bytes-per-subsystem figure exists, so any codec claim is unfalsifiable — green: du -sb on journals, memory.db and research caches piped into one table — output: not run yet, task filed
- tester: tester — technique: fault

## Implementation
- path: skills/research-to-ship/SKILL.md — check: bin/pi-research check --done — status: done
- path: research/rr/compression-2026.md — check: bin/pi-research check --done — status: done
- task #262 — measure zstd vs lz4 seek vs OpenZL on our own bytes before changing a path — status: open
