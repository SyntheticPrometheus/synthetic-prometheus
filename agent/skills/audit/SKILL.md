---
name: audit
description: Periodic activity audit — take the window since the last audit, measure it with one cheap evidence pack, rank findings by money, then attack them with adversarial debators and tester panels before shipping guarded fixes. Use on the agenda's weekly "audit" row, when you ask "what has this system actually done / what should change", when money or runway is in question, and before committing to a large piece of new work.
---

# Activity audit — measure the window, then break your own fixes

One line: **an audit is not a review of code, it is a review of what the system actually did** — and
its product is a small number of changes that survive an opponent and a tester, not a list of
observations.

Distinct from the neighbours, deliberately:

| skill | question it answers | output |
|---|---|---|
| `pi-review` (weekly, automated) | are the *signals* green? | pass/warn/fail table, no judgement |
| `session-review` | where is the *conversation* friction? | repeated asks, gaps, long chains |
| `self-improve` | is harness variant B better than A? | k-rep eval, gate, lineage |
| **`audit`** | what did the system **do** in this window, and what must change? | ranked findings, debated, fixed, guarded |

## The loop

```bash
cd ~/.pi/agent
skills/audit/scripts/window.py scan --record        # 1. evidence (≈5 s, or 70 s without --fast)
skills/audit/scripts/window.py selftest             # 0.1 s: the pack's own 27 boundary cases
```

`selftest` is not decoration: the pack shipped with 24 defects a two-tester panel found in the first
hour (a truncated ledger erasing itself, an unreadable instrument reading as a real finding, crashes
exiting 1 — the same code as "suspects found"). Each class is now a case, `pi-preflight` runs it as
`audit pack` on every publish, and the cases are mutation-checked: put back the closed-pairs REPEAT
bug and `score-repeat-on-second-unclosed-scan` goes red. **Assert the discriminating line, not a
substring that some other fixture also produces** — the verifier found one assertion that passed for
the wrong reason, and that is the normal shape of a theatre test.

`scan` prints SESSIONS / MONEY / SCHEDULE / GUARDS / DELEGATION / TASKS / MEMORY / REPO / SUITE and a
**SUSPECTS** list. A suspect is a *lead*, not a finding: the pack composes `pi-burn --cap`,
`pi-cadence --json`, `pi-preflight`, `pi-delegate flow`, `mem brief`, the suite run ledger and
`session-review`'s miner rather than re-deriving them — so when an instrument is wrong, the audit
fixes the instrument instead of arguing with it.

**2. Convert suspects to findings, money first.** For each suspect name the command that decides it,
run that command, and write the finding as *number → cause → the default-if-silent cost*. The audit
that produced this skill found that 63% of a $14/day burn sat above a context ceiling that
`settings.json` claimed to enforce — that ordering (money, then correctness, then tidiness) is the
standing rule, because the only finding that ends the whole setup is the one that ends funding.

**3. Debate the contested ones.** For every finding whose fix is a *choice* (spend this, move that,
raise the other), dispatch both sides — never one:

```bash
bin/pi-delegate run --agent debator --timeout 420 --task "FOR: <proposition>. INPUTS: <files,
numbers>. FOLD: SIDE / strongest case / opponent's best case / flip-if / decision rule."
bin/pi-delegate run --agent debator --model anthropic/claude-haiku-5.5 --timeout 420 --task "AGAINST: …"
```

Measured 2026-11-16: six dispatches, $0.36, and **two of three planned fixes were reversed by the
opposing side's arithmetic** — a median of a bimodal gap distribution is not a rate, and raising a
budget does not fix an allocator. A proposition that survives both sides ships; one that does not
was never a fix.

**4. Break the fixes.** One tester per fix, disjoint lenses from `skills/audit/lenses.json`
(boundaries / state / oracle / faults / hostile-input / recovery / access). A passing self-test is
not a panel: in the same audit, four testers found 8 defects — a real 2.00× cadence failure reading
as 0.93× because duplicate timestamps halved the mean — in code that already had a green self-test.

**5. Ship each fix with its guard.** A finding is not closed by a fix; it is closed by something
that *runs*: a check (`pi-preflight`), a refusal (`accept --reason`), a probe in `check`, a ledger
row. Append to `INCIDENTS.md` (what happened → cause → guard → where it lives) and, if data outside
this task was at risk, file `pi-agenda bug` with a repro. Then verify by re-running the instrument
that reported the problem, and commit only your own hunks.

**6. Close the loop** — this is what makes the next audit cheaper:

```bash
skills/audit/scripts/window.py close --findings 5 --fixed 4 --spend 2.10 \
  --lens tester/boundaries=2,tester/oracle=0 --notes "one line: what changed"
skills/audit/scripts/window.py score      # yield, repeats, and the two rules below
```

## Self-improvement rules (the part that changes this skill)

`score` compares consecutive runs and then *acts*:

- **A repeat suspect is the worst result.** A suspect id that appears in two consecutive runs means
  the previous fix did not hold. The next audit spends its first hour there, not on new ground, and
  the finding goes back into `INCIDENTS.md` with a stronger guard.
- **Cadence is measured, not chosen.** $/fixed-finding above $6, or two runs with no fixed finding,
  lengthens the row to 14 d (`pi-agenda edit audit --cadence 14d`); a repeat suspect shortens it to
  3 d. The default is 7 d.
- **Lenses retire.** A lens with 0 reproducible findings in two consecutive runs goes into
  `lenses.json:retire` and is not dispatched again; a lens with ≥2 findings gets a second dispatch
  next run (`lenses.json:double`). An unused agent is a hypothesis — `pi-review` proposed deleting
  `bulker`/`redteam` for never having run; their first real dispatches found a CRITICAL shell
  injection, so the rule is *exercise or delete*, not *keep for later*.
- **A selftest is a hypothesis until mutated.** Break the fix in a copy and watch the case go red;
  if it stays green, the case is decoration (2026-11-16: one of 27 did exactly that).
- **Amend this file.** When a run teaches something the next run must know (a new suspect class, a
  threshold that was wrong), add it here or to the pack — a lesson that lives only in a memory row
  does not change behaviour.

## What this pack cannot see (say so in the report)

It counts what is logged. It cannot see a UI that looks wrong, a service that is up but useless, or
a fix that is correct and pointless — those need you or a screenshot (`bin/pi-shot`). And the
window is only as honest as the journals: the 2026-11-16 audit's first pass read 0 tool errors
across 11,000 calls because `pi` stores tool results in their own row, which no real window produces
— *a suspicious zero is a suspect too*.

## Cost

Evidence pack: ~5 s (`--fast`) / ~70 s, no tokens. The judgement is the spend: 6 debators ≈ $0.36,
4 testers ≈ $0.10, plus this session. Target **< $6 per fixed finding**; report the real number in
`close --spend` so `score` can enforce it.
