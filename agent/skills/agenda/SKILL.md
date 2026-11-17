---
name: agenda
description: One schedule for everything that recurs plus the tasks and goals it serves — what is due now, what to tick off, how to add work without starting another timer. Use at session start, before starting new work, when asked what is pending/overdue/next, when something should recur, and when a timer might have silently stopped.
---

# Agenda

`bin/pi-agenda` is the single store for three kinds of row:

| kind | what it is | how it recurs |
|---|---|---|
| **obligation** | something that must happen again (soak check, weekly review, stranding queue) | `cadence` (`15m`…`1mo`) + `next_due` |
| **task** | one-shot work with an owner, a priority and optionally a due date | never — it closes |
| **goal** | a long-lived outcome with a metric and a horizon | tasks and obligations point at it |

One systemd timer (`pi-agenda.timer`, every 10 min) runs `pi-agenda tick --run --notify --quiet`.
It is deliberately dumb: two indexed queries, write `agenda/DUE.md`, run only local `exec:`
obligations that are due, notify at most every 6 h. No model, no network, ~0.3 s.

The tick cannot work a `session:` row, so the row `due-dispatch` (10 min) is the *consumer*:
`pi-text dispatch --due` opens a headless session for any session row more than `DUE_GRACE_S`
(300 s) late, up to `due_budget(demand)` sessions a day, and that session works the row and touches
it. Lateness is therefore bounded by one dispatch cycle, not by whether a human left a session open.

## Session start, in one command

```
pi-agenda next
```

Prints due obligations, overdue tasks, the next four due times, open tasks, goals with progress,
strikes, stale PDSA cycles, and a warning for any backing systemd timer that is dead or stale.
Exit 2 means something is due — that is the signal to work the list before new work.

## Bugs: fix now or file, never hand back

A bug found while working is **fixed in the same turn** or filed immediately:

```
pi-agenda bug "Parked windows leave a sliver at the edge" \
  --repro "frame-window on 3 tiles: the two unframed ones are clamped to the edge" \
  --ref "README.md#known-limitations" --due 7d
pi-agenda bugs          # what is open, with repro and ref
```

Filed bugs are priority 1 by default and due in 3 days. `pi-agenda next` prints a **Bugs** section
and a **Stale priority-1** section, and exits 2 when a priority-1 task is older than 3 days; the
tick notifies on both. `pergola-dev` works the bug queue before the backlog. The report to the owner
is "fixed" or "queued as #N" — never "here is a bug, remember it".

## Working it

```
pi-agenda due                  # only what is due (exit 2 when anything is)
pi-agenda touch <obligation>   # did a session obligation -> reschedule by its cadence
pi-agenda run <obligation>     # execute an exec: obligation now
pi-agenda done 7 | drop 7 | snooze 7 2d
pi-agenda show                 # every obligation with cadence, next due, strikes
pi-agenda add-task "…" --goal pergola-1.0 --source session --priority 1 --due 3d --ref BACKLOG.md
pi-agenda sync                 # strikes for every timer: obligation whose unit died
pi-agenda log 20               # what actually ran, how long, ok/failed
```

## Timeliness: due is a deadline, not advice

Five rules exist because on 2026-11-15 nine `session:` rows sat 13–15 h late while the digest
was written to a file no running context read, and two sessions once worked one list (INC-5):

1. **A late run never moves the schedule later.** `next_due` advances along the original grid
   (`next_slot`): a 6 h row worked 90 min late is next due 4.5 h later, not 6 h. Recording
   `now + cadence` made the effective period cadence + lateness (~2× for a 10-min row).
2. **Grace is one dispatch cycle (~300 s), never a fraction of the cadence.** A 6 h row that is
   allowed to be 90 min late is exactly the "overdue" the owner sees.
3. **The consumer's budget must cover the schedule's demand**: `due_budget` = max(6, 1.5 ×
   Σ(86400/every_s) over enabled session rows). Eight rows need 5.3 sessions/day; a 3/day cap grew
   the backlog every day. `pi-text check` fails when the budget is below demand.
4. **A live session is blind after its first `next`.** A session that stays open past the next due
   time re-runs `pi-agenda next` at each task boundary; `due-dispatch` covers the case where it
   does not.
5. **Reading the digest holds the rows.** `pi-agenda next` writes every due `session:` row it
   prints into `agenda/hold.json` (holder pid, 4 h TTL, refreshed by each `next`) and the consumer
   skips a held row, so two sessions never work one row; `touch` releases it, and a dead holder
   pid or a stamp older than 4 h releases it too.

`pi-text check` (blocking in `pi-preflight`) also fails when `due-dispatch` has not run for three
cycles, or when a session row is >2 h late with zero dispatch attempts in 24 h. The tick phones
(at most every 6 h) when a session row is 30 min late, a bug is open, a p1 is stale, or a p1 is due
within 24 h — an auto-filed failure task gets `due = now + 1 day` for exactly that reason.

The consumer is `pi-text dispatch --due` and it is the *only* thing that opens sessions for these
rows, so its two failure modes are now separate and visible (2026-11-16): `--due` must route before
`--detach` in `cmd_dispatch` (the detach branch respawns the text-task dispatcher; dropping `--due`
meant the row was never worked — the argv test is the regression check), and the due child waits
`acquire_dispatch_lock(wait=180)` for a text session instead of dropping its 30-min slot silently,
writing `route: due-busy` to `text/dispatch.jsonl` if it still loses.

## Texts — the channel the agenda dispatches for

`AGENTS.md` § Texts holds the two laws (a text is a request; the channel opens a session for it). This is the
operational protocol behind them, moved here so the instruction file stays short.

**Inbound** is polled by the `text-inbox` agenda row (10 min); each message is filed as a task (`source=text`),
receipted with that task id, and then a session is opened. **Receipts** state what really happens next, derived
from the live `running.json` / dispatch lock, in the owner's local clock (logs stay UTC).

**Routing** — `pi-text dispatch`, `--dry-run` prints the decision; protocol, not vibes:

| decision | when | what happens |
|---|---|---|
| `answer` | `status`/`help` wording | answered from the agenda, no model |
| `ask` | too short to be work | reply sent, nothing filed |
| `resume` | explicit continuation cue **and** a specific shared subject **and** a non-live session from the last 24 h | `pi --session` in a visible tiled window that texts its own summary |
| `fresh` | default | headless one-shot session, gone when it prints |

**Caps**: one run at a time (flock), `MAX_PER_HOUR = 6`, `--timeout 900` wall clock, and a dispatched session
cannot dispatch again. `pi-text hold ID…` marks tasks an interactive session owns so a background run cannot race
it. **Reading**: `pi-text inbox` (exit 3 = nothing), `pi-text watch --timeout 300` to block; use `send --working`
for an interim answer that must **not** disarm the nudge ladder (2 h / 8 h / 24 h). `pi-text check` is blocking in
`pi-preflight` and fails after a day of silence.

**Transport** is ntfy (free, no account; the topic is in `pass pi/text-topic` — a capability: keep it private), and
switches to Telegram automatically once `pass pi/telegram-bot-token` exists. No SMS: a real number costs money *and*
needs a public webhook for the reply leg, which this host cannot offer.

`bin/pi-bg` says what is running now (background / foreground / scheduled-overdue) as panel indicators 21/22/23,
with `bin/pi-agenda-view` and `pi-bg --watch` opening as windows from the app menu — see `skills/desktop`.

## An empty queue is skipped, not spent (bug #198)

A `session:` row can be due with nothing to do — `pergola-dev` on 2026-11-17 opened a session after all 19
BACKLOG items were closed, and that session re-verified a clean tree 20 times in 70 s. Register the row's queue
check in `agenda/session-checks.json` (`{"<obligation id>": "<shell command>"}`): exit 0 means work exists, any
other exit means the queue is empty and its **last output line** is the reason. `pi-text dispatch --due` runs those
checks before it opens anything, records a `due-empty` ledger row, rolls the row forward with `pi-agenda touch`,
and spends no tokens. A check that cannot run (exit 126/127, timeout) counts as *work* — a guard that fails open
would retire a row forever. `pi-text dispatch --due --dry-run` prints the `idle` lines, so the decision is
inspectable without scheduling anything.

## Rules

- **One recurring thing = one obligation row.** Do not create a new timer for a new cadence; add
  a row. Timers are for *external* watchers (frantic board, publish windows); cadences live here.
- **A `session` obligation is finished by doing it, then `touch`.** The tick never marks it done —
  that would be a lie the digest tells tomorrow.
- **A failure becomes a priority-1 task automatically** (exec obligation non-zero, or `sync` finds
  a dead timer). Fix the class, then close the task: see INCIDENTS.md.
- **`timer:<unit>` obligations are checks, not work.** They exist so a silent timer cannot hide:
  `sync` strikes them when the unit is inactive or has not fired for 21 days.
- **Goals carry numbers, not adjectives** (`gate items green 2/5`, `USDC 0/25`). `set-goal` after
  measuring; a goal that has not moved in a month is either wrong or dead — say which.
- **Keep the default set small.** Every obligation is a claim on future attention; delete it
  (`enabled=0` via sqlite, or `add-obligation` with the same id and a long cadence) when it stops
  earning its slot.

## What it replaced

Seven systemd timers each with their own schedule, a markdown TODO, `mem pdsa` cycles and the
frantic queue — none of which could tell you *what is due now*, and all of which were capable of
failing silently. `pi-review` still scores the whole harness weekly; `pi-agenda` is the thing that
puts a due date on it.
