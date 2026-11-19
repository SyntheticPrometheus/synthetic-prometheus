# Percolation (Broadbent & Hammersley, 1957) as a maintenance model — evidence base

Question: does statistical percolation theory answer a question this machine's maintenance work keeps
answering by hunch — *which failure could not be survived, and where does redundancy actually pay?* —
and can the answer be measured instead of asserted?

Decision it flips: a resource is a single point of failure by **percolation centrality** (share of
capability-to-capability routes through it), not by how many tools mention it; and an unmitigated
resource is a bug worth a restore path, not a fact worth noting.

Method: primary sources only, read as abstracts + statements of result. Crossref DOI lookups for
every citation below (`api.crossref.org/works/<doi>`), arXiv API for the percolation-centrality
paper; no search engine was used (bot-walled on this host, `skills/web`). Numbers quoted from a paper
are marked as its result; numbers about *this* machine are measured by
`bin/pi-percolate` on 2026-11-15 and reproducible with `pi-percolate --json`.

## 1. What the original model says

- **Broadbent & Hammersley 1957**, *Percolation processes I. Crystals and mazes*, Proc. Cambridge
  Philos. Soc. 53:629–641, [10.1017/S0305004100032680](https://doi.org/10.1017/S0305004100032680).
  The paper asks, in the abstract's words, "how the random properties of a 'medium' influence the
  percolation of a 'fluid' through it": each site (or bond) of a lattice is open with probability p,
  and one asks for the probability that open sites connect across the lattice. Everything here is a
  restatement of that question with "site" = resource and "connects across" = capabilities still
  reach each other.
- **Hammersley 1957**, *Percolation processes II*, same journal 53:642–645,
  [10.1017/S0305004100032692](https://doi.org/10.1017/S0305004100032692) — the companion paper's
  abstract says the first "omitted the proof of the theorem on the connect[ivity]"; the existence of
  a sharp critical probability is a theorem, not an intuition, and it is what licenses talking about
  a *transition* rather than a gradual loss.
- **Suding & Ziff 1999**, Phys. Rev. E 60:275–283,
  [10.1103/PhysRevE.60.275](https://doi.org/10.1103/PhysRevE.60.275) — exact site thresholds for
  lattices (square 0.5927…). Useful as a caution: the famous numbers are **lattice constants**. A
  dependency graph is not a lattice, so no tabulated p_c applies; it has to be measured.

## 2. What carries over to a dependency graph

- **Molloy & Reed 1995**, *A critical point for random graphs with a given degree sequence*,
  Random Structures & Algorithms 6:161–180,
  [10.1002/rsa.3240060204](https://doi.org/10.1002/rsa.3240060204) — a giant component exists iff
  ⟨k²⟩/⟨k⟩ > 2. Inverting for random removal of nodes at rate 1−p gives the threshold used in the
  tool: **p_c = ⟨k⟩/⟨k²⟩ = 1/κ**.
- **Callaway, Newman, Strogatz & Watts 2000**, *Network robustness and fragility*, Phys. Rev. Lett.
  85:5468, [10.1103/PhysRevLett.85.5468](https://doi.org/10.1103/PhysRevLett.85.5468) — percolation
  on graphs with arbitrary degree distributions; the same ⟨k⟩/⟨k²⟩ form. "Robust yet fragile" is the
  title of the follow-up literature for a reason: the *average* and the *ordering* are different
  questions.
- **Cohen, Erez, ben-Avraham & Havlin 2000**, *Resilience of the Internet to random breakdowns*,
  Phys. Rev. Lett. 85:4626, [10.1103/PhysRevLett.85.4626](https://doi.org/10.1103/PhysRevLett.85.4626)
  — for a scale-free graph the random threshold goes to zero as N grows while a *targeted* removal of
  a small fraction collapses it. This is the theorem behind "the ordering matters, not the mean", and
  the reason `pi-percolate` reports three orderings instead of one number.
- **Buldyrev et al. 2010**, *Catastrophic cascade of failures in interdependent networks*, Nature
  464:1025–1028, [10.1038/nature08932](https://doi.org/10.1038/nature08932) — when two networks
  depend on each other, the transition becomes **first-order**: the system looks fine, then it is
  gone, instead of degrading smoothly. Capabilities and resources are exactly such an interdependent
  pair, which predicts a cliff-shaped P(f) — and the measurement below is cliff-shaped.
- **Watts 2002**, *A simple model of global cascades on random networks*, PNAS 99:5766–5771,
  [10.1073/pnas.082090499](https://doi.org/10.1073/pnas.082090499) — cascades happen in a *window* of
  connectivity, not monotonically: more coupling is not always safer. A caution against reading
  "reduce dependencies" as a goal in itself.
- **Piraveenan, Prokopenko & Hossain 2013**, *Percolation centrality*, PLoS ONE 8(1):e53095,
  [10.1371/journal.pone.0053095](https://doi.org/10.1371/journal.pone.0053095) — importance is a
  function of the *percolation state*: a node's centrality during a cascade differs from its
  centrality at rest. Implemented here as weighted-endpoint betweenness over resources, computed at
  rest and again averaged over eroded states at the transition.

## 3. The mapping (what `bin/pi-percolate` actually builds)

| percolation | here |
| --- | --- |
| site | a **resource**: file, directory, venv, `pass` key, port, non-universal system binary |
| occupied site | the resource is present |
| connectivity | two capabilities are adjacent when they *share a required* resource |
| a lattice's degree k | number of required resources a capability has |
| open cluster | capabilities that run **and** can still reach each other |
| p_c | measured by removing 1/20 of the resources at a time, 120 trials per point |

A capability is "down" if **any** required resource is missing (AND-semantics — no partial
degradation), unless the source probes for that resource first (`command -v`, `[ -x ]`,
`.exists()`, `shutil.which`), which is the only fallback the machine actually has.

## 4. What it measured on this machine (2026-11-15)

```
66 capabilities, 104 resources, 177 required deps, 11 components, cohesion S(0)=0.79
κ = ⟨k²⟩/⟨k⟩ = 8.7   →   p_c ≈ 1/κ = 0.115   (asymptotic; the sweep is the number that counts)
half the connected mass gone at: 5/104 resources (random) · 3/104 (blast-radius order) · 3/104 (percolation-centrality order)
fragility 1.7–1.8×  →  the ranked orders are ~1.7× more damaging than chance
                        (range over 10 runs: random f_P samples 0.048–0.056)
independence check at f=0.25: (1−f)^k predicts 51% survival, measured 50%
restorable: 75% of capability weight has a restore path on every resource it needs
```

Findings that changed how the machine is maintained:

1. **The ranked order and the centrality order agree** (f_P 0.029 both). So the target list is not a
   modelling artefact: the biggest blast radii *are* the bridges. For a graph this shallow there is no
   "harden the bridges, not the hubs" trade-off to make — which is itself the answer, and it is
   measured rather than assumed.
2. **The largest single-failure blast radii were all restorable except one pair**: `venv:laya`
   (10.3% of capability weight) and `venv:memory` had **no declared pins** — no `requirements.txt`
   anywhere — so "the venv is rebuildable" was a belief, not a fact. Pins now exist
   (`laya/requirements.txt`, `memory/requirements.txt`), and the probe that found the gap is the one
   that confirms the fix.
3. **`agenda/agenda.db` is the only copy of the machine's schedule.** `journal.jsonl` records what
   *ran*; the obligations themselves (cadence, owner, command, `next_due`), the tasks and the goals
   exist only in an untracked SQLite file. It is now exported to `agenda/schedule.json` on every tick
   and restorable with `pi-agenda restore`.
4. **Failures do not arrive in bundles** here (bundling ratio 0.99): the independence model `(1−f)^k`
   predicts survival well, so a capability's risk is its own dependency count, not the sharing. That
   is the falsifier for the obvious objection to graph models, and it passed.
5. **17 of 66 capabilities are islands** — session-owned agenda rows and MCP servers that share no
   required resource. They cannot be broken by another failure; they also cannot help each other.

## 4b. Audit 2026-11-18 — the unmitigated row was the ledger, not the machine

At the start of the run: 109 capabilities, 143 resources, 78% of capability weight restorable, six
`none` rows. The largest — `agent:delegation/ledger.jsonl`, 6.2%, the only unmitigated resource
above the gate's 5% — is the one file `pi-commit-guard` refuses to stage, so "just track it" was
closed by design. What changed:

- `pi-delegate ledger` keeps a last-known-good `ledger.jsonl.bak` (append-only ⇒ a copy is a valid
  snapshot at any instant), `--restore` puts it back and parks the damaged copy as `.corrupt`, and
  the 1 h `ledger-backup` agenda row keeps it fresh. Pinned by `tests/pi-delegate.sh`
  (truncate → restore 2/2 rows; a missing backup refuses and leaves the ledger alone).
- The five `agent:text/*` rows were extraction error, not fragility: `poll.lock`, `dispatch.lock`,
  `due.lock`, `dispatch.log` and `due-escalated.json` are created by the tool itself (`open("w")`
  for the flock slots, `open("a")` for the log, a 12 h stop-trying map) and carry no unique record
  — `text/dispatch.jsonl` does, and it has a `.bak`. Measured by importing `bin/pi-text` against an
  empty root: all five appear on the first lock/append. `mitigation()` now says `rebuildable` for
  exactly those names, and only those.

Result: restorable 78% → 84%, no unmitigated resource above the 5% gate, fragility unchanged
within sampling noise (1.7–1.8×). The remaining `none` rows are all ≤2.1% (publish state,
`win-log.jsonl`, a bare `bin` path, browser/autostart config) — recorded rather than acted on.

## 5. Limits (what this model does not see)

- **Static, literal extraction**: paths, quoted relative names, `pass <key>`, `host:port`, venv
  interpreters, a fixed non-universal binary list. A resource computed at runtime from an environment
  variable is invisible. `pi-percolate deps <cap>` prints exactly what was extracted, so any wrong
  conclusion can be traced to the extraction rather than argued about.
- **Universal tools are excluded on purpose**: `bash`, `python3`, coreutils are resources every
  capability shares; including them pins the whole graph to one hub and says nothing actionable. If
  those break, the model is not the tool you want.
- **Asymptotic vs finite**: p_c = ⟨k⟩/⟨k²⟩ is an infinite-graph result. At n≈100 nodes the sampled
  sweep is the number that means anything, and the sample noise on f_P is about ±0.01 (0.048–0.049
  across runs).
- **AND-semantics overstates damage**: a capability with a fallback path that the extractor cannot
  see is counted as broken. The error direction is known and conservative for hardening decisions.
- **Not measured at all**: *time* (a resource that fails at 03:00 costs nothing until the tick),
  *money* (a break that stops the earning rail), and *human attention* (the only resource that never
  comes back). The graph only knows reachability.

## References

1. Broadbent, S. R. & Hammersley, J. M. (1957). *Percolation processes I. Crystals and mazes.* Proc.
   Cambridge Philos. Soc. 53:629–641. doi:10.1017/S0305004100032680
2. Hammersley, J. M. (1957). *Percolation processes II.* Proc. Cambridge Philos. Soc. 53:642–645.
   doi:10.1017/S0305004100032692
3. Suding, P. N. & Ziff, R. M. (1999). *Site percolation thresholds for Archimedean lattices.* Phys.
   Rev. E 60:275–283. doi:10.1103/PhysRevE.60.275
4. Molloy, M. & Reed, B. (1995). *A critical point for random graphs with a given degree sequence.*
   Random Structures & Algorithms 6:161–180. doi:10.1002/rsa.3240060204
5. Callaway, D. S., Newman, M. E. J., Strogatz, S. H. & Watts, D. J. (2000). *Network robustness and
   fragility: percolation on random graphs.* Phys. Rev. Lett. 85:5468. doi:10.1103/PhysRevLett.85.5468
6. Cohen, R., Erez, K., ben-Avraham, D. & Havlin, S. (2000). *Resilience of the Internet to random
   breakdowns.* Phys. Rev. Lett. 85:4626. doi:10.1103/PhysRevLett.85.4626
7. Buldyrev, S. V. et al. (2010). *Catastrophic cascade of failures in interdependent networks.*
   Nature 464:1025–1028. doi:10.1038/nature08932
8. Watts, D. J. (2002). *A simple model of global cascades on random networks.* PNAS 99:5766–5771.
   doi:10.1073/pnas.082090499
9. Piraveenan, M., Prokopenko, M. & Hossain, L. (2013). *Percolation centrality: quantifying
   graph-theoretic impact of nodes during percolation in networks.* PLoS ONE 8(1):e53095.
   doi:10.1371/journal.pone.0053095
