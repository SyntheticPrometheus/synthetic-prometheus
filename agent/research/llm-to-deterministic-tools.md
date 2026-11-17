# Using a language model to produce deterministic tools, instead of doing the job again each time

Question: a model improvises a procedure every session — same intent, different flags, different
column order, no record that two runs disagree. Can the model be used to make a process *more*
consistent (freeze it into a script that behaves identically every run) rather than less, and what
does the evidence say is the mechanism that makes that work?

Decision it flips: an LLM belongs in the **authoring** step and never in the **execution** step of
anything that recurs. A procedure becomes a capability only when it is (a) a script in `bin/`,
(b) pinned by a test that runs twice with identical output, and (c) guarded by a check that fails
when the pin rots. Re-deriving a command interactively is not flexibility; it is unmeasured variance.

Method: primary sources (arXiv abstracts and stated results), plus measurements on this host. Where a
number is the paper's result it is marked as such; where it is this machine's, the command that
produced it is named.

## 1. What the evidence actually says about LLM-written code

- **Plausibility is not correctness, and the gap is large.** *EvalPlus* (arXiv:2305.01210) augments
  HumanEval with **80×** more test cases via LLM- and mutation-driven input generation. Across 26
  models, the stricter suite **reduces pass@k by up to 19.3–28.9 %**, and it *changes the ranking*:
  two CodeLlama-based models beat ChatGPT on HumanEval+ while none did on the original HumanEval.
  The lesson is not "LLMs write bad code" — it is that **the test suite, not the model, decides
  whether code is correct**, and a small suite silently certifies wrong code and mis-ranks the
  candidates.
- **Self-repair is not a silver bullet; the feedback signal is.** *Is Self-Repair a Silver Bullet
  for Code Generation?* (arXiv:2306.09896) finds that "when the cost of carrying out repair is taken
  into account, performance gains are often modest, vary a lot between subsets of the data, and are
  sometimes not present at all", and attributes this to repair being "bottlenecked by the model's
  ability to provide feedback on its own code" — a stronger feedback source (a stronger model, human
  participants) produced "substantially larger gains". So: an LLM asking itself "is this right?" is
  weak; an LLM given a **deterministic oracle** (a failing test, a diff, an exit code) is strong.
- **Diversity comes from sampling; reliability comes from filtering.** *AlphaCode*
  (arXiv:2203.07814) reached a top-54.3 % average Codeforces rank, and its own account of that
  result lists "large-scale model sampling to explore the search space" and "filtering to a small set
  of promising programs" among the critical ingredients. The generator explores; the *filter* is
  what is trustworthy. A frozen script is the extreme case of that: sample once, keep exactly one
  candidate, and pin it with the filter.
- **Decomposition into checkable sub-goals is worth more than one big attempt.** *Draft, Sketch, and
  Prove* (arXiv:2210.12283) lifts an automated prover from **20.9 % to 39.3 %** not by a better
  model but by turning an informal proof into a *sketch* of verifiable sub-goals and directing search
  at each. Applied here: one tool that does one thing with one contract (argv → lines, exit code)
  beats one clever command that does five things, because each sub-goal is separately testable.
- **The sweet spot is short programs.** *Program Synthesis with Large Language Models*
  (arXiv:2108.07732) benchmarks "short Python programs from natural language descriptions" (MBPP,
  974 entry-level tasks) — which is exactly the size and shape of a CLI utility. Nothing about that
  setting requires the model at run time; it requires the model at *write* time.

The composite rule: **use the model where sampling is cheap and a test can adjudicate; use a
deterministic artifact where behaviour must repeat.** The model is a compiler from intent to code,
and the test suite is the type-checker.

## 2. The pattern that follows

1. **Author once.** The model writes the script from the contract (input, output shape, failure
   mode, the decision it encodes), because it knows the shape of the job.
2. **Pin it.** A test that fails loudly, plus the *double run*: execute the same test twice and diff
   stdout+stderr. Different output from identical input is a definitional failure of determinism —
   no model involvement needed to adjudicate.
3. **Freeze it.** It lives in `bin/<name>`, versioned, with the contract in its docstring. From then
   on the *script* owns the behaviour; a session calls it instead of reconstructing it.
4. **Guard the pin.** A check that runs on a schedule (here: `pi-preflight`'s `tools` check) so the
   test cannot be deleted or start silently producing different output.
5. **Spend the model on the residue.** Interpreting a failure, writing the *next* test, choosing
   between two candidate tools — not re-typing the command.

Determinism has concrete obligations, all statically checkable: sorted enumeration (`find | sort`,
globs sorted), `LC_ALL=C`, no `$RANDOM`/`$$`/localized `date` in output, UTC ISO-8601 or elapsed
seconds, no network in the default path unless that is the point.

## 3. What changed in this harness

- **`bin/pi-tool`** — `new` scaffolds a tool *with* its contract and a golden test; `check` runs
  every pin **twice** and diffs (this is the determinism check, and it needs no model); `lint` fails
  on nondeterminism smells and polling loops; `list` shows which scripts are pinned.
- **`tests/`** — the pin directory; `tests/<tool>.sh` is a POSIX-sh golden test, and a `--selftest`
  (flag or subcommand) counts as a pin.
- **`bin/pi-preflight` check `tools`** — blocking: an unpinned tool or a failing lint fails publish.

Measured before/after: **49 of 52** scripts in `bin/` had no test and no selftest; **5** are now
pinned and green. The first `pi-tool check` run found three real defects, which is the argument for
the check in one line:

| finding | what it was |
|---|---|
| `pi-claim` | its selftest printed a temp-directory path → two identical runs differed (fixed: label names the command, not the path) |
| `pi-preflight` | it had no `--selftest` at all; a loose match was invoking the *live* checks, whose RAM and percolation numbers differ per run (fixed: detection requires a registered flag/subcommand) |
| `pi-wait` | its own selftest printed elapsed times and tmp paths → normalised to print detail only on failure |

Note what did *not* happen in any of those: a model was asked whether the test passed. The diff and
the exit code decided.

## 4. Falsifier

If, after a month, the pinned-tool count has not grown past ~15 and the same few procedures are still
being re-improvised, then the bottleneck is not the test harness — it is that a session cannot tell
"this is the third time" from "this is the first". The next change is then a frequency signal (count
repeated command shapes in the session logs and surface the top ones), not more scaffolding.

## Citations

- Liu et al., *Is Your Code Generated by ChatGPT Really Correct? Rigorous Evaluation of Large
  Language Models for Code Generation* (EvalPlus), arXiv:2305.01210 —
  <https://arxiv.org/abs/2305.01210>. Results quoted: 80× HumanEval test augmentation; pass@k
  reduced by up to 19.3–28.9 %; ranking changes on HumanEval+.
- Olausson et al., *Is Self-Repair a Silver Bullet for Code Generation?*, arXiv:2306.09896 —
  <https://arxiv.org/abs/2306.09896>. Quotes: gains "modest … sometimes not present at all";
  repair "bottlenecked by the model's ability to provide feedback on its own code".
- Li et al., *Competition-Level Code Generation with AlphaCode*, arXiv:2203.07814 —
  <https://arxiv.org/abs/2203.07814>. Result quoted: top 54.3 % average Codeforces ranking; critical
  ingredients include large-scale sampling and filtering to a small candidate set.
- Jiang et al., *Draft, Sketch, and Prove: Guiding Formal Theorem Provers with Informal Proofs*,
  arXiv:2210.12283 — <https://arxiv.org/abs/2210.12283>. Result quoted: 20.9 % → 39.3 % from
  sketch-guided decomposition into checkable sub-goals.
- Austin et al., *Program Synthesis with Large Language Models*, arXiv:2108.07732 —
  <https://arxiv.org/abs/2108.07732>. MBPP: 974 "short Python programs … from natural language
  descriptions".
- Local measurements: `bin/pi-tool list`, `bin/pi-tool check`, `bin/pi-preflight` on 2026-11-17.
