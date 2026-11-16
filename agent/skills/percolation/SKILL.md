---
name: percolation
description: "Treat the harness as a percolation problem — which single resource failure takes a measured share of the machine with it, and does the machine still reach itself after f of its parts are gone. Use when deciding what to harden or back up, when something failed and you want to know what it took down, when a check reports that fragility regressed, before adding a shared dependency to a new tool, and when a failure looks systemic. Runs bin/pi-percolate; theory and verified citations in research/percolation.md."
---

# Percolation — fragility you can measure instead of argue

One line: **a capability is only as alive as its required resources and its reachability; measure
both, name the single failure that costs the most, and give it a restore path.**

`bin/pi-percolate` builds a bipartite graph from what is on disk — capabilities (`bin/`, enabled
`systemd --user` units, `exec:` agenda rows, MCP servers) and the resources they require (files,
venvs, `pass` keys, ports, non-universal system binaries) — then removes resources and asks the two
questions percolation theory exists to answer:

- **F(f)** — share of capability weight still *running* after a fraction f of resources fail.
- **P(f)** — share still running **and** in one connected component. This is the headline: a
  harness that cannot reach itself does not do its rounds. It collapses far earlier than F, and the
  collapse is a cliff rather than a slope because capabilities and resources are interdependent
  (Buldyrev et al. 2010 — see `research/percolation.md`).

## When to reach for it

| Situation | Command |
| --- | --- |
| "what could take the machine down" | `pi-percolate` (full report, ~2 s) |
| before adding a shared dep to a new tool | `pi-percolate` then read the `harden` table |
| a check says fragility regressed | `pi-percolate` → harden, or `pi-percolate accept` if intended |
| something broke and you want the blast radius | `pi-percolate --json` and search the resource |
| "is my extraction of X right?" | `pi-percolate deps bin/pi-text` |
| weekly | the `percolation-audit` agenda row |

## Reading the output

```
graph      66 capabilities, 104 resources, 177 deps, 11 components, cohesion S(0)=0.79
random / degree / bridge  — three removal orders; each says "half the mass gone at k/N resources"
fragility  1.7×  →  the ranked orders are worse than chance ⇒ a named weak point exists
harden     weight share lost if that one resource fails; `NOT restorable` is the actionable column
bridges    rank now → rank at the transition (percolation centrality, Piraveenan et al. 2013)
islands    capabilities that share nothing: unbreakable by others, and no help to each other
```

Rules of thumb, measured on this machine rather than assumed:

- **`NOT restorable` is the whole point.** A big blast radius with `git`, `package` or `rebuildable`
  is a bad hour; the same radius with `none` is data you cannot get back. Harden those first.
- **Blast radius and percolation centrality can disagree.** When they do, centrality is the one that
  predicts cascade damage; `degree`-ordered removal only re-tests the hub you already knew about.
- **A capability's own risk is its required-resource count**, not the sharing: the independence model
  `(1−f)^k` predicted 49% survival at f=0.25 where the sweep measured 48%. If the `model check` line
  ever reads ≪1, failures *are* arriving in bundles and the per-frame reading is wrong.
- **Don't chase the asymptotic p_c.** `p_c ≈ ⟨k⟩/⟨k²⟩` is an infinite-graph result; at n≈100 the
  sweep is the number, and its noise is ±0.01 on f.

## The two moves that actually pay

1. **Give an unmitigated resource a restore path.** This is what turned the audit into work:
   `laya/requirements.txt` and `memory/requirements.txt` (both venvs were 12% of capability weight
   with no pinned deps) and `agenda/schedule.json` + `pi-agenda restore` (agenda.db is the only copy
   of the schedule). A restore path is worth more than a redundant copy, because it survives the
   corruption case too.
2. **Add a fallback the extractor can see.** `command -v`, `[ -x ]`, `.exists()` all mark a dep as
   probed — the capability then survives a missing resource instead of vanishing from the graph.
   Any fallback that the source does not probe for is, from the machine's point of view, not a
   fallback.

## The gate

`pi-preflight` runs `pi-percolate check --quick`, which compares a full audit against
`percolation/baseline.json` and fails when the structural collapse point gets 25% worse, or when a
new unmitigated resource appears above 5% of the machine's weight. It deliberately does **not** fail
on a stable single point of failure — a gate that cannot be passed stops being read (see the `units`
latch in `bin/pi-preflight`). After a deliberate change: `pi-percolate accept`, and say why in the
commit message.

## Limits

Literal, static, AND-semantics. Runtime-computed resources are invisible; a capability with an
unseen fallback counts as broken (so the error direction is conservative for hardening); `bash`,
`python3` and coreutils are excluded as universal. `pi-percolate deps <cap>` shows exactly what was
extracted — trace a surprising verdict there before believing it. Full derivation, citations and the
2026-11-15 measurement: `research/percolation.md`.
