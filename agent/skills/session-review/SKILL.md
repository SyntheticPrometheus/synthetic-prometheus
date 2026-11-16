---
name: session-review
description: Mine pi session logs for friction — repeated asks, user corrections, capability gaps, tool errors, long tool chains — and turn the recurring ones into skills, prompts, protocols or memory rows. Use when the owner asks to review recent sessions, when interactions feel repetitive or slow, or on a weekly reflection pass.
---

# Session review — turn friction into harness changes

One line: **a skill is justified by a repeated or expensive workflow, not by a good idea.**

## Run the miner

```bash
python3 ~/.pi/agent/skills/session-review/scripts/mine.py --since 24h
```

Options: `--since 24h|7d|YYYY-MM-DD|all`, `--cwd SUBSTR`, `--out FILE`, `--json`,
`--max-items N`. It reads `~/.pi/agent/sessions/*/*.jsonl` and prints:

- sessions scanned, with asks / tool calls / errors
- repeated asks (exact and near-duplicate)
- user correction markers ("please continue", "did you", "I can't", ...)
- assistant capability-gap phrases ("I can't browse", "no API", ...)
- failed tool calls
- long tool chains (≥25 calls) and the tools that dominate them

It is a finder, not a judge. Read the excerpts; the context decides whether a signal is a
missing skill or just a hard task.

## Classify each signal

| Signal | Artifact |
|---|---|
| The same manual procedure in ≥2 sessions | **skill** (`skills/<name>/SKILL.md`) |
| A capability the agent keeps re-explaining | **memory row** + a line in `AGENTS.md` |
| A check that must always run | **guard** in `bin/pi-preflight` or a hook; add to `INCIDENTS.md` |
| A workflow the owner triggers by name | **prompt template** (`prompts/*.md`) |
| Behavior that should happen without being asked | **extension** (`extensions/*.ts`) |
| A one-off preference or fact | **memory row** only |
| A doc the owner reads | `AGENTS.md` / `PUBLISHING.md` / `PASSWORDS.md` |

A skill is the right answer only when the workflow **repeats**, is **not already covered** by a
`bin/` tool or a protocol doc, and has a **checkable output**. Otherwise write the memory row.

## Create the skill

1. `skills/<name>/SKILL.md` with frontmatter `name` and a routing-useful `description` (what +
   when). Keep it short; put scripts in `skills/<name>/scripts/`.
2. Exercise it once — run its main command, or read the file it routes to. A skill that was never
   run is a guess.
3. Add a `mem add` row: what the skill does, why it exists, the evidence (session id / repeated
   ask). Use `-k lesson` or `-k decision`.
4. If it changes the harness, open or advance a PDSA cycle (`mem pdsa`). If it guards a failure,
   add the entry to `INCIDENTS.md` with the guard's location.
5. `bin/pi-preflight` and `bin/pi-review` must still pass. Commit the tree.

## What not to do

- Do not create a skill for a one-off. The prompt cost is small, but the routing noise is real.
- Do not duplicate an existing skill or protocol doc; link to it instead.
- Do not paste raw session content (it may contain private text) into a skill.
- Do not claim a skill works without running its command once.

## Output template

```
Scanned N sessions (since X). Top friction:
1. <pattern> — <session ids> — <artifact created or why not>
2. ...
Created: skills/<a>, skills/<b>. Exercised: <command + result>.
Not created: <candidate> — one-off / already covered by <doc>.
```

## PDSA for this skill

Metric: repeated asks and correction markers in the next review. Hypothesis: a review that ends
in one exercised skill reduces the same signal next week. If the same friction returns, the skill
was too vague or the wrong artifact — fix the skill, do not add another one.
