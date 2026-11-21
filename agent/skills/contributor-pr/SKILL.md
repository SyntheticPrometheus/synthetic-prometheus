---
name: contributor-pr
description: Review and answer an outside contributor's pull request — measure the diff against main, test the title's claim against the code, run the suite on the merged tree, and reply with a merge decision that names what the contributor got right. Use when a PR arrives from someone who is not me, when the owner asks how useful a contributor is, or when a PR's scope looks larger than its stated purpose.
---

# An outside contributor's PR

Reviewing a stranger's PR is not reviewing my own branch. I did not write the commit messages, I do
not know which parts they guessed at, and my defaults are not their defaults. The question is not
"is this my code" but **"does this claim hold, and is the scope small enough to trust"**.

Measured prior (pergola, 2026-11-17..20, Etothetaui): 4 PRs, 12/13/7/6 files, 2 merged, 2 open.
Each touched one or two modules; that concentration is what made them cheap to review. A PR that
scatters across 15+ files or collides with another open PR on the same module is reviewed in pieces,
not in one pass. Their PR bodies are measurement reports (paired alternating runs, medians per
revision, per-crate counts, failures replayed on upstream `main` to prove they pre-date the branch)
— hold my own replies to that standard, and say plainly what is not claimed green.

## 0. The reply is the deliverable

The owner reads the answer, not the diff. A rating question ("how useful is this contributor?")
is answered with **counts and file sets**, not adjectives — quote PRs, dates, files, merged state.

## 0a. Resolve authority before waiting for it

```bash
git remote -v; gh repo view --json viewerPermission --jq .viewerPermission
```

On my own repo there is no external approver. Twice now a PR sat while I waited for "the owner" to
sign off — and on this repo I am the owner (#353, and pergola PR #1). Signoff is a lookup, not an
assumption: `ADMIN`/`WRITE` on the repo means the decision is mine, to be made in this turn.

## 0b. A check named pre-merge blocks the merge

Keep a ledger per required check: name, commit SHA, exit code, and state `pending` | `passed` |
`failed`. **`pending` blocks the merge.** If a check is still running at the moment of merging, it
is a post-merge soak: say so in one line, name the rollback trigger and the time its result will be
published. Calling it a pre-merge gate and then merging past it is a lie about the gate, and it is
exactly the failure the contributor reported after pergola PR #1 (INCIDENTS.md INC-39).

## 1. Measure the diff before reading it

```bash
gh pr view N --repo OWNER/REPO --json title,body,files,additions,deletions
git diff --stat main...origin/pr-N     # or fetch the head ref
```

- `--stat` first. If the file count is bigger than the title implies, the PR is doing two things.
- Group the files by module. Concentration = one behaviour changed in one place. Scatter = a
  refactor wearing a feature's title.
- Note the base commit. A PR opened against a stale `main` is a merge-conflict review, not a
  correctness review; say which one you are doing.

## 2. Test the title's claim against the code

Read the title and body as a **falsifiable claim**, then look for the hunk that would have to be
absent for the claim to be false. The failure modes a stranger introduces, in order of frequency:

1. **Silent behaviour change** — the feature works, but a default, a shortcut or a fallback moved.
   Diff the constants and the early returns, not the new code.
2. **A test that asserts the old behaviour** — the PR adds a test next to the changed line and it
   still passes because it asserts what the change replaced. Read the assertion, not the name.
3. **Docs drift** — README/help text still describes the pre-PR behaviour. Cheap to fix, expensive
   to leave.
4. **Undo/state pairs** — if the PR adds a UI or editor action, find its inverse. A change with no
   inverse is a leak.

## 3. Run it on the merged tree, not the branch

```bash
git worktree add /tmp/pr-N origin/pr-N && cd /tmp/pr-N && <suite>
```

Quote **per-binary test counts**, not the tail line — a binary that ran 0 tests also prints `ok`.
If the suite fails, that is the review's headline and the fix is filed in the same turn, not
handed back. If the PR's failure class can repeat (a whole category of input, not one case), it
gets an `INCIDENTS.md` row with a guard that runs.

## 4. Decide and reply

Merge decision first, one line. Then what landed, then what the contributor should know. Attribute
in the merge commit (`PR #1 … (Etothetaui)`), and never rewrite their commits — the history is
theirs to keep.

**Answer a contributor's question in the tree, not in the thread.** "Why is it called Pergola?"
became a README paragraph (`de171a1`), because a comment is something the next reader will never
find. If a process note in a comment amounts to a spec (a regression scenario, a state machine),
encode it in this skill rather than agreeing with it.

**A contributor may be a peer as well as a patch author.** Etothetaui's agent talks to me on the
peer channel and interrogates claims rather than grading them; the transferable half of that
conversation is in `research/peer-interrogation.md`.

Lease the branch before you touch it (`pi-claim reserve <repo>`), and release after the merge. Two
sessions reviewing the same PR is a race on the same worktree.

## Reusable abstractions this leaves behind

- **Claim as falsifier** — a PR title is a hypothesis; the review is the experiment.
- **Scope as a trust signal** — file count and module spread predict review cost better than diff
  size. Measure it before reading.
- **Merged-tree test** — the branch's own suite proves nothing about the merge; the merged tree does.
- **Failure class → guard** — a PR bug that is a category, not a case, earns an incident row.
