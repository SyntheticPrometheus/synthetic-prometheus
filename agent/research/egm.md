# Google's Elephant-Goldfish Model (EGM) — research digest (2026-11-16)

Question: what is EGM, and which parts of it are worth taking into this harness's systems and
protocols? Sources: opensource.googleblog.com post (2026-10-22), github.com/google/elephant-goldfish-model
(Apache-2.0, "not an officially supported Google product"), egm.dev, plus the skill/agent markdown
read directly from `main`.

## What it actually is

Not a model. It is a **process + plugin**: 7 `SKILL.md` skills, 9 subagent personas in `agents/*.md`,
document standards, and per-harness manifests (Claude Code, Codex, Cursor, Windsurf, Copilot,
Antigravity, OpenCode). Nothing model-side; every mechanism is markdown instructions plus fresh
subagent dispatch.

- **Elephant** = the long-lived context window. Holds project memory, drafts the spec, "No Code"
  rule — design only. Human makes the trade-offs.
- **Goldfish** = a *stateless* subagent: the doc plus its linked source files, **no conversation
  history**. Used only to review, never to write.
- Lifecycle: brainstorm → draft → review (5 stages) → resolve → implementation.

The five review stages (`skills/egm-review/SKILL.md`):

1. **Initial zoom out** (`zoom-out` + `inventive-catalyst`): is this the right thing at all.
2. **Comprehension test** (`comprehension`): the reviewer must *paraphrase* the design and say how
   the existing system works, under two fixed headings; an unparaphrasable section is a Blocker.
3. **Critic review** (`design` + `structural` + `style`) via `egm-review-loop`, antagonistic.
4. **Intermediate zoom out**: re-check after fixes.
5. **Implementation readiness** (`implementation-readiness` + `codebase-details` + `style`): go/no-go
   that every file path, structure and signature is present, so the implementer makes **no design
   decisions**.

Rules worth naming because they are the machinery, not the marketing: max **1 re-audit per stage**
(anti-loop); every finding severity-tagged Blocker/Major/Nit; artifact-first (reports to files, never
chat dumps); banned flattery adjectives and banned apologies; a review that cannot spawn a *fresh*
context must **stop** rather than review in-context ("a review in the same context is not a Goldfish
review").

## Evidence status — weak

No benchmark, no A/B, no numbers anywhere in the repo or the post. The claim is social: "thousands of
Googlers use this plugin every day to ship production Google code". `TESTING.md` tests frontmatter
schemas, link integrity and workflow gates — it does **not** test whether EGM output is better. Treat
it as a named default with a plausible mechanism, not a measurement.

## What we already have (so the overlap is real, not imagined)

| EGM mechanism | Ours |
|---|---|
| Goldfish = fresh-context reviewer | `verifier` subagent, deliberately *another model family* (`delegation/policy.md` v3.3), `pi-delegate verdict pass\|fail` |
| Contract before dispatch | 6-field GOAL/INPUTS/FOLD/ACCEPTANCE/SCOPE/BUDGET; `pi-delegate plan` refuses incomplete ones |
| Go/no-go before acting | `selfimprove/gate.py`, `pi-preflight` |
| Rules as hypotheses | PDSA in `mem pdsa`, arms in `selfimprove/arms/` |
| No flattery / no filler | AGENTS.md style rules, "answer first" |

So the useful part is not "fresh reviewer" — it is the three things we *don't* have: the **paraphrase
gate**, the **doc↔code drift report**, and the **readiness check as a literal go/no-go on a plan**.

## Tested here, not assumed

I ran EGM's comprehension persona (adapted verbatim, `scout` as a read-only fresh context) against
`delegation/policy.md` (257 lines). Cost: one subagent run, ~1 min, no edits.

- It produced a coherent two-heading paraphrase — correct in substance (v3.3, 6-field DoR, 4/8 WIP,
  local-bulk/cloud-residue, regex decider vs advisory Laya).
- 10 findings, of which ~9 are real gaps a new implementer would hit: no base directory for the
  relative paths (`delegation/ledger.jsonl`, `bin/pi-claim`), `decide()` named with no file, "context
  bucket" and the stripped `PI_*` vars undefined, `pi-claim`'s subcommands and exit codes unspecified,
  `agents/*.md` frontmatter location unstated, `win-log.jsonl` path missing.
- 1 false positive: it flagged "noul" as a typo — it is Laya's real task type. Precision ≈ 9/10 at
  one run; triage is still the parent's job.

Conclusion: the paraphrase gate earns its place. It is cheap (one read-only child), and it finds the
failure mode our own docs are most exposed to — they assume the reader already knows the tree.

## What I would take, ranked by cost/benefit

1. **Comprehension gate on operator docs** (adopt). One line in `skills/delegate` DoR: a doc that a
   child must *act on* (policy, skill, runbook) gets one paraphrase pass by a zero-context child
   before it is cited as authoritative; unparaphrasable section = Blocker. ~1 min per doc. Measured
   above at 9/10.
2. **Goldfish handoff rule** (adopt as wording, free): state the child's input as *the doc plus the
   files it links*, never "the conversation so far". Our contracts say INPUTS but do not forbid
   inherited framing; EGM's isolation rule is the sharp version.
3. **1-re-audit cap** (adopt as wording, free): after one re-review of a stage, residual findings
   are recorded as accepted trade-offs. Directly relevant — review loops are our known time sink.
4. **Drift report** (worth building, not vendorable). `pi-preflight docs`: compare each skill/policy's
   claims (paths, command names, counts) against the tree. We have no such check today (`bin/` has
   `pi-review`, `pi-preflight` only). EGM's version is a prompt, not a script; ours should be a check.
5. **Vendoring the plugin as-is** (reject). It targets Claude/Codex/Cursor plugin manifests, assumes
   `ask_question`-style gates and nested subagents; frontmatter keys (`disable-model-invocation`,
   `license`) are not pi's. Adapting the two personas is cheaper than carrying 283 files we would
   never run.

## Reject / do not copy

- The full 5-stage pipeline with per-stage checkpoint gates: 6+ child runs per document. Our budget
  rule (~15–50 s, 300–700 tok floor per dispatch) makes a 6-stage doc review a luxury for anything
  smaller than a release.
- "No Code" elephant sessions: we are a single operator harness; the design/edit split costs a
  context hand-off we do not have budget for.
- The marketing frame ("design is the new code", "human judgment is the artifact"). Fine as a slide,
  unusable as a rule.
