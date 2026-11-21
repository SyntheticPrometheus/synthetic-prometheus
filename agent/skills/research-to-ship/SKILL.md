---
name: research-to-ship
description: Turn a topic (or a list) into research, a doubled set of tangential topics, a systems-impact analysis, a self-improving loop, an implementation and a push — with testers and debators attacking every stage. Use when you ask to research something and actually change the system with it, when a technology might obsolete a tool or a row, or when a finding must end in a shipped commit rather than a digest.
---

# research-to-ship — a run, not a read

Formerly `recursive-research` (owner, 2026-11-19: the old name described step 1 of 7). The research
is the *input*; the shipped, tested change is the output. Tool unchanged: `bin/pi-research` owns the
shape (manifest, template, gate), since scaffolding and gating digests is exactly what it does.

One line: **research that cannot name the system it changes, the metric it moves, the observation
that would prove it wrong, and the commit it landed in has not happened.**

The shape is owned by `bin/pi-research`; this file owns the work inside it. The tool writes the
seven-section digest template, counts the doubled tangential set, and refuses (exit 1) a digest
missing an id, a metric, a falsifier, a real FOR/AGAINST, a named tester or an implementation
handle. So "deep" is a gate, not an adjective.

## The run

```bash
cd ~/.pi/agent
bin/pi-research new "topic one" "topic two" --date "$(date -u +%F)"   # manifest + templates
bin/pi-research status                                               # stage per topic
# ... steps 1-4 below, writing into research/rr/<slug>.md ...
bin/pi-research check        # the gate; exit 1 means the run is not done
bin/pi-research tangential   # the doubled set, as round-two seeds
```

One digest per topic. `status: draft` until step 4 has a path and a command; then `status: done`.
A topic that produced nothing is deleted from the manifest with a line saying why — an empty digest
is a failure that looks like work.

## Step 1 — recursive research, doubled

- **Round 0 (frame).** One line: the decision this could flip and the number that would flip it
  (`skills/curiosity`). No decision, no run.
- **Round 1 (seeds).** `skills/deep-research` ladder: OpenAlex/arXiv/Crossref ids, HN Algolia for
  practitioner signal, Wikipedia for definitions, GitHub REST for code. Search engines are
  bot-walled here; do not retry them.
- **Round 2 (recursion).** For every claim that changes a decision, ask its *parent* question and
  walk one hop out (references, citing works, the implementation the paper releases). Then
  **double**: the run must register `2 × N` tangential topics for `N` given topics — for each
  topic, two neighbours and the reason each could change something here. Tangential is only
  admitted if it could obsolete, shrink or replace a named thing on this host.
- **Testers in round 1.** `redteam` (external claims: is the source real, current, withdrawn,
  cherry-picked?) and `tester` (`technique: oracle` — can the claimed number be reproduced with a
  20-line calculation?). A claim neither can reach goes in `GAPS` and is not cited as fact.

## Step 2 — systems impact

Write one line per affected system in this tree (paths, not abstractions):

`<system or path> — create|change|remove — evidence \`<id>\` — expected effect`

Then **remove-first**: the cheapest improvement is usually deleting a row, a timer or a fallback
that measured nothing. Rank by (evidence strength × blast radius) / cost, and name the dependency
too — a change that helps `bin/pi-text` but breaks `text/config.json` is not a change.
Gate: `bin/pi-percolate check` before any change that adds a shared dependency.

**Debator here.** Two agents, one proposition each, in parallel (`agents/debator.md`):
"create/change X" FOR and AGAINST, both read-only, both required to produce a number and a
falsifier. The decision line records `keep|revert|supersede` and the number that decided it.
No debate, no implementation — a change with only one side argued is a preference.

## Step 3 — wrap it in a self-improving loop

Every accepted change gets a loop, or it is not accepted:

- **metric** — what is measured, and the command that measures it (a run, not a memory);
- **falsifier** — the observation that reverses the decision, with a date or a count;
- **guard** — a check that *runs* (`tests/<tool>.sh`, a `pi-preflight` check, an agenda `exec:`
  row). A promise is not a guard;
- **cadence** — the agenda row that runs it (`pi-agenda add ... --every`), never a new systemd unit;
- **PDSA** — `bin/mem pdsa new --plan "<hypothesis> / <metric>"`, closed Act/Study with numbers.

**Tester here** (`technique: fault` and `recovery`): break the guard on purpose — delete the file it
reads, make it exit 1, run it twice — and confirm it fails loudly rather than passing quietly.
A guard that cannot fail is decoration. `pi-tool lint` for polling, `pi-tool check` twice for
determinism.

## Step 4 — implement and finalise

1. `pi-tool new NAME` when the procedure is mechanical; pin it with `tests/NAME.sh`; `pi-tool
   check NAME` (runs twice, diffs).
2. `pi-claim reserve <paths>`; smallest change; match style; no drive-by refactors.
3. Tests first where the failure is nameable: red (the gate fails today) → green (it passes) →
   the exact output quoted into the digest.
4. `bin/pi-preflight` (blocking) and `bin/pi-agenda next` — a change that leaves the agenda behind
   is not finished.
5. Anything not implemented gets `bin/pi-agenda add-task`/`bug` with the repro and path, in the
   same turn. Never "later" in prose.

**Tester here** (`technique: boundary|hostile|security|access`): the adversarial-testing skill's
panel, one technique per agent, each required to produce a failing command or an explicit "could
not break it, here is what I tried". `redteam` reviews what the change exposes (new network path,
new file read, new credential).

## Step 5 — push

```bash
cd ~/.pi/agent && git status --porcelain   # named paths only, never `git add -A`
bin/pi-publish            # plan + secret scan + size + batching state
bin/pi-publish --push     # allowlist snapshot -> github.com/SyntheticPrometheus/synthetic-prometheus
```

Cite memory so the run is discoverable (`bin/mem add "Research base: <topic> — <finding>" -k source
-g research,<topic>`); `pi-preflight` fails on an uncited `research/*.md`.

## Anti-patterns this skill exists to stop

- A digest with no falsifier: it cannot be wrong, so it cannot be useful.
- Tangential topics chosen for adjacency in words, not for the system they could delete.
- A "loop" that is a cron entry with no metric — that is a timer, and it will run unread.
- Testers asked to "review" instead of to break a named thing with a named technique.
- Implementation reported as "the design is ready": step 4 ends with a path and a command output.
