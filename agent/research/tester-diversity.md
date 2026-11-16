# What a diverse tester panel is for, and what breaks software

Research note, 2026-11-16. Question: what do companies hiring testers actually select for, and
which techniques actually find bugs — so that tester subagents are chosen and instructed on
evidence rather than on "have several agents look at it".

Method: primary APIs only (Crossref, OpenAlex, arXiv, S2 where not rate-limited), plus the two
canonical practitioner bodies of work (Bach's Heuristic Test Strategy Model; Kaner's oracle /
exploratory testing). Ids below were re-fetched; each claim is marked **verified** (id resolved,
claim is in the paper's stated result) or **practice** (practitioner consensus, no controlled
study). Anything I could not resolve is in GAPS at the end.

## 1. Diversity helps — but only diversity *in the failure space*

- **Hong & Page 2004**, PNAS 101(46), doi:10.1073/pnas.0403723101 — *Groups of diverse problem
  solvers can outperform groups of high-ability problem solvers*. **Verified.** A group of
  randomly drawn, moderately able agents beat a group of the best agents, because agents with
  different heuristics cover different parts of a rugged solution landscape. The result is
  model-dependent, not a law: it holds when the problem is hard and the heuristics differ.
- **Replication, 2022**, doi:10.5281/zenodo.7484071 — reproduces the ordering "most of the time",
  not always. **Verified (record).** Diversity is a bet with a good base rate, not a guarantee.
- **Woolley et al. 2010**, Science 330:686, doi:10.1126/science.1193147 — *Evidence for a
  Collective Intelligence Factor*. **Verified.** Group performance on a battery of tasks loads on
  one "c" factor predicted by **social sensitivity, equal turn-taking, and the proportion of
  women** — and *not* by the group's average or maximum individual IQ. Translation for agents:
  what a panel needs is **equal budget and equal airtime, plus the ability to read each other's
  claims**, not more capable members. A panel where the first agent's framing dominates is the
  low-c panel from the paper.

So the design question is never "how many testers" but **"do these testers fail differently?"**
Two testers that share a model, a prompt shape and a reading of the spec have one tester's blind
spot at twice the price.

## 2. Independence is not free — it has to be engineered

- **Knight & Leveson 1986**, IEEE TSE, doi:10.1109/TSE.1986.6312924 — *An experimental evaluation
  of the assumption of independence in multiversion programming*. **Verified.** Independently
  developed versions of the same program failed **coincidentally far more often than probability
  predicts**: the same hard cases are hard for everyone. 793 citations; the result has held up.

This is the single most useful paper for agent panels. "Independent" agents built from the same
base model, given the same spec and the same hints, are N-version programming with the same
failure correlation. Independence must be *manufactured*: different model family, different
starting artifacts (spec vs. diff vs. behaviour), different technique, and **no priming with the
parent's or the first tester's findings**.

## 3. Exploratory beats scripted — at finding, not at proving

- **Itkonen, Mäntylä & Lassenius, ESEM 2007** — *Defect Detection Efficiency: Test Case Based vs.
  Exploratory Testing*. **Verified (record).** Exploratory sessions found defects that the
  scripted cases did not, at a higher detection rate per hour; scripted cases bought
  repeatability. The practical reading: **exploration finds, scripts prove.** A bug found
  exploratorily is not done until it is turned into a repeatable case.
- **Itkonen et al., IEEE TSE 2013** — *The Role of the Tester's Knowledge in Exploratory Software
  Testing*. **Verified (record).** Tester knowledge (domain and product) drives what gets
  explored: testers with a model of the system generate better hypotheses, testers without one
  re-walk the same paths. So an agent that is handed a *model of the product* (invariants, states,
  trust boundaries) tests better than one handed a file list.
- **ESEM 2009**, *How do testers do it?* — **verified (record)**: manual testers work from
  concrete artifacts (the build, the bug tracker, the last failure) and from each other, not from
  abstract coverage targets.

## 4. The oracle problem is where most bugs are missed

Kaner's framing (**practice**, widely taught): you can execute a million inputs, but a bug is only
found when you know what the answer *should* have been. Most "we tested it" failures are oracle
failures, not input failures. Three oracles an agent can actually build:

1. **Differential** — run a second implementation (old version, reference impl, another library)
   and diff the outputs. This is how compilers and parsers are actually broken.
2. **Metamorphic** — an invariant under transformation: sorting twice = sorting once; parse(print(x))
   = x; paginating changes the page, not the set; adding an unrelated row changes no total.
3. **Invariant/property** — QuickCheck (**Claessen & Hughes, ICFP 2000, verified record**):
   state properties and let the generator search, then **shrink** to a minimal counterexample.

A tester that only eyeballs output is doing half the job; a tester that names its oracle can be
checked.

## 5. Green tests prove less than they look

- **Papadakis et al., ICSE 2018** — *Are mutation scores correlated with real fault detection?*
  **Verified (record).** Mutation score does correlate with real fault detection — but so does
  plain coverage, and mutants are a proxy, not a proof. Coverage, mutation score and "all tests
  pass" are all *weak* evidence compared with a reproduced failure.
- Consequence for agents: **test the test.** Break the code deliberately (flip a comparison, delete
  a guard, return the default early) and confirm the suite goes red. A suite that stays green
  under mutation is documentation, not a check.

## 6. What companies actually select for (practice, from job specs and the RST/BBST canon)

Not "knows the tool". Recurring selection criteria:

- **Scepticism plus evidence discipline** — assumes the demo is hiding something, but every claim
  carries a repro.
- **Domain/model building** — can state the system's invariants, states, and trust boundaries
  after an hour of reading (Itkonen TSE 2013 is the empirical version of this).
- **Technique breadth** — boundaries, equivalence classes, state transitions, combinatorial
  reduction, oracles; not one tool.
- **Risk triage** — spends the hour where money, data loss or irreversibility live, not uniformly.
- **Bug-report quality** — minimal steps, expected vs actual, environment, severity with a reason.
  Companies weight this higher than raw bug count because a non-reproducible report costs more
  than it saves.
- **User plurality** — accessibility, locale, low-end device, non-expert mental model. This is the
  "diverse collection" that shows up in *hiring* language: testers who are not the developer's
  clone find the bugs the developer cannot imagine. Same argument as §1, applied to users rather
  than to testers.

## 7. Technique catalogue — how things actually break

Grouped by the failure class they target; this is the list the tester agent is built around.

| class | probes that find bugs |
|---|---|
| **Boundaries** | 0, 1, 2, max, max+1; empty vs null vs absent; off-by-one in ranges; first/last item; unicode, emoji, RTL, zero-width, combining marks, 4-byte chars; very long single token |
| **State & sequence** | double submit; cancel mid-flight; retry after partial success; reentrancy; out-of-order events; pause/resume; two clients on one resource; resume from a crash |
| **Oracle gaps** | differential vs. old version/reference; round-trip parse/print; idempotence; commutativity; "the total is unchanged" — invariants |
| **Input hostility** | whitespace-only, `-`, `--`, leading `~`, glob chars, newline in filename, `../`, absolute path, symlink, FIFO, `/dev/full`, non-UTF8 bytes, huge payload, deeply nested JSON |
| **Environment & faults** | dependency down/slow; disk full; permission denied; clock skew, DST, leap day, timezone; expired token mid-operation; low memory; SIGKILL between write and fsync |
| **Scale & data** | 0 / 1 / many; 10^6 rows; duplicate keys; concurrent writers; pagination drift; integer overflow; float equality |
| **Compatibility & change** | upgrade with existing data; downgrade; migration re-run; config from the previous version; plugin/API version skew |
| **Security / abuse** | trust boundary crossings; authz on every id (IDOR); injection in every sink (shell, SQL, HTML, template, log); SSRF from user-supplied URL; secrets in logs/errors; resource exhaustion; deserialization |
| **Recovery & honesty** | what the error message claims vs what happened; partial writes; silent truncation; data loss without a log line; "success" on a failed side effect |
| **Usability & access** | keyboard-only; screen reader labels; focus order; contrast; error recovery without data loss; cognitive load; non-expert mental model |

**Fault injection beats speculation**: an agent can usually create the fault (fill a tmpfs, chmod
000, kill -9 at the right moment, `iptables` a host) far more cheaply than it can reason about it.

## 8. Design implications — what this repo now does

1. `agents/tester.md` — one scoped **risk area + technique + oracle** per dispatch; returns only
   reproducible findings (`SEV | path:line | repro | expected vs actual`), plus what it did **not**
   exercise. Read-only.
2. `agents/redteam.md` — the security/abuse lens, threat-model driven, proof-of-concept only.
3. `skills/adversarial-testing/SKILL.md` — the lens matrix and the panel protocol (2–4 testers,
   disjoint risk areas, different families, no shared findings before the merge, equal budget).
4. `delegation/policy.md` §1e — panel rules and why a same-model panel is not a panel.
5. `pi-delegate panel` — prints a ready-made multi-lens dispatch set so the diversity is assigned,
   not improvised.

Measurement (PDSA, `mem pdsa`): **unique root causes per panel** and **false-positive rate per
tester**, against a solo-test baseline. Diversity that does not raise unique root causes per
dollar is decoration and should be cut.

## GAPS

- Could not resolve a controlled study on *tester* team diversity (as opposed to problem-solving
  teams); the hiring claims in §6 are practitioner practice, not measured.
- OSS-Fuzz / fuzzing yield statistics were not re-fetched (rate limits); no numbers quoted.
- The mutation-score vs. coverage nuance (§5) is from the ICSE 2018 record; I did not read the
  full text, so no effect size is quoted.
