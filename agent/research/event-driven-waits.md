# Waiting on events instead of sleeping on timers — evidence base and what it changed

Question: this harness spends turns doing `sleep 60; <check>` and `while ! <cond>; do sleep; done`.
A `sleep` is a poll: it wakes whether or not anything happened, the interval is a guess, and every
wake-up is a model turn. The kernel already knows when a process exits, when a writer closes a file,
when a line lands in a log. So: *which of these waits have a real event behind them on this host, and
what does the blocking primitive cost?*

Decision it flips: a wait is not "how long do I sleep" but "which event am I waiting for" — and,
one level up, **whether the session should be waiting at all**. Blocking on the right event is the
*second* best answer; the best one is that the job announces its own completion and the session has
already gone to do something else. Both are implemented (`bin/pi-wait` blocks; `bin/pi-done` pushes),
and a sleep loop is a defect that `pi-preflight` blocks.

Method: primary sources only — man7 for `pidfd_open(2)` and `inotify(7)`, freedesktop for
`sd_notify` and `systemd-run`, the `entr` README for the file-watch idiom. Every claim about *this*
host was measured on 2026-11-17 with the commands shown and is reproducible. No search engine was
used (Marginalia was cooling down; `skills/web` names the bot walls).

## 0. The measurement that motivates this

Parsed every `bash` tool call in `~/.pi/agent/sessions/**/*.jsonl`:

| quantity | value |
|---|---|
| bash tool calls | 13,303 |
| calls containing `sleep` | 1,009 (7.6 %) |
| …a `while`/`until` watch loop | 352 |
| …literally `sleep N; <check>` | 45 |
| declared sleep seconds | 305,193 s ≈ **84.8 h** of requested wall clock |

The 84.8 h is an upper bound (many sleeps live inside `timeout`-bounded loops that exit early), but
the shape is unambiguous: the default way this harness waits is a timer, and a timer costs a turn
whether or not the state changed. That is the cost being removed, not the seconds.

## 1. Process exit: `pidfd_open` + `poll` is the correct primitive

`pidfd_open(2)` returns a file descriptor that refers to a task; the man page states it is
"close-on-exec" and, with `PIDFD_NONBLOCK`, that a `waitid(2)` on an untimed-out task returns
`EAGAIN` rather than blocking. A pidfd is pollable, so `poll()` on it returns exactly when the task
terminates — no `/proc` scan, no PID-reuse race (the unsafe part of `kill -0` loops).

Measured on this host (Linux 6.x, Python 3.11 whose `os.pidfd_open` wraps the syscall):

```
poll returned [(3, 1)] after 2.00 s ; child rc 0     # fires at exit, not at an interval
reparented (non-child) target:      [(3, 1)] 1.00 s # works when the target is not our child
pi-wait --selftest: "pid: wait costs ~0 CPU  0.0 ms cpu for 1 s wall"
```

Two facts a poll-based design cannot give you:
- **Blocking is free.** 1 s of waiting on a pidfd costs 0.0 ms of CPU in the waiter. A 1 s sleep
  loop also costs ~0 CPU *while asleep*, but it wakes 1–60 times to ask a question it already had
  the answer to, and each of those wake-ups is a tool call in this harness.
- **Status is only available for your own children.** `waitpid` on a non-child returns
  `ECHILD`; the *event* is still observable, the exit code is not. `bin/pi-wait pid` reports `?`
  for that case rather than pretending.

`subprocess.run(timeout=…)` already blocks correctly (`fork` + `wait4`), which is why
`bin/pi-delegate` was never the problem — the problem is what a *session* does after backgrounding
a job: it loses the pid and starts sleeping.

## 2. File completion: inotify, with two measured traps

`inotify(7)` is "monitoring filesystem events"; a watch on a *directory* reports events for files
inside it, which is how a path that does not exist yet can still be waited on.

Measured, and both results change the design:

```
CLOSE_WRITE,CLOSE a.txt          # echo > file           → one event, at close
MOVED_TO b.txt                   # write tmp; mv tmp b   → the atomic-publish event
CLOSE_WRITE c.txt  × ~400        # writer that opens/closes per line → one event per line
```

- `IN_CLOSE_WRITE` means "a writer finished with this file", which is exactly the completion
  question — but a producer that opens/closes per line (a shell `for` loop without a shared fd, a
  logger that reopens) emits one event per line. Hence `--stable MS`: the timer is only a
  *coalescer* after an event has already arrived, never the trigger.
- `IN_MOVED_TO` is the only trustworthy "the artifact exists and is complete" signal. A producer
  should write `out.tmp` and `mv` it into place; `bin/pi-wait file` names the event
  (`created` / `closed_write` / `moved_to`) so a caller can tell which happened.

`entr` (eradman) exists precisely because "run arbitrary commands when files change" is a
long-standing need; its README documents the same rebuild-on-change idiom that `--stable` and
`IN_CLOSE_WRITE` encode. `inotifywait` from inotify-tools does the same, but `bin/pi-wait` calls
`inotify_init1`/`inotify_add_watch`/`read` through `ctypes` so there is no external dependency and
no version skew in a script that must run on a bare box.

## 3. Log completion: an append stream, not a `tail -f` poll

`pi-wait pattern RE --file LOG` watches `IN_MODIFY` and reads only the new bytes, so it resolves on
the first line matching the pattern. This is what replaces `sleep 90; cat cand.log` — the wait ends
when the job says it is done (`DONE rc=0`, `verdict fail`), not when someone guessed 90 s.

The honest limit: a producer that never writes a terminal line cannot be waited on this way. The fix
is on the producer side — write an explicit completion event (a `done` file via atomic rename, or
`sd_notify`'s `READY=1`).

## 4. systemd: `--wait` when you start it, MainPID when it is already running

`systemd-run` documents that `--wait` / `--pipe` make it wait for a transient service; without them
it "return[s] after the command has begun execution". So *run-and-wait* has a first-class answer.

For a unit that is already running there is no equivalent, and this was measured rather than
assumed: for a `--collect` transient unit, `busctl --user monitor` with a `PropertiesChanged` match
on the unit path emitted nothing, and `journalctl --user -u <unit>` recorded `Starting`/`Started`
but never a stop line — the unit is unloaded so quickly that no stop event reaches the journal.

What does work: the unit's **MainPID**. `systemctl --user show -p MainPID --value <unit>` → pidfd →
`poll`. Measured: a unit whose remaining life was 1.5 s was reported exited after 1.18 s, 0 CPU.
Caveat stated in the tool: MainPID exiting is not the same as the cgroup being torn down
(`ExecStopPost` may still run); for "is my job done" it is the right question.

`sd_notify()` is the protocol for the other direction — a service announcing start-up completion
(`READY=1`) and, with `WATCHDOG_USEC`, liveness. A service that supports it can be waited on
correctly by the manager instead of by a socket probe. This harness's units are `Type=oneshot`
timers, so it is not used here yet; it is the right answer for any future long-running service.

## 5. Sockets and remote state: the one place polling is legitimate

`pi-wait port` uses `connect()` as its event: a refused connection is the only "not yet", and it
retries with exponential backoff (20 ms → 500 ms). There is no kernel event for "a remote HTTP
endpoint will be ready"; a bounded, backed-off probe is the correct instrument, and the rule is to
*say so* rather than sleep and hope. This is why `pi-wait` has no `--until-cmd`: re-running a
command on a timer is the defect, and a general escape hatch would be used to reintroduce it.

## 5b. Push instead of block: the job fires the notification

Blocking still costs a turn. The stronger version is: start the job detached, return immediately,
and let the thing that already knows the job ended tell someone. On Linux that thing is the service
manager, and it has the hook built in — `OnSuccess=` / `OnFailure=` on a unit name another unit to
start when the job ends.

Measured on this host (2026-11-17):

```
systemd-run --user --unit=ntest-ok  --property=Type=exec \
    --property=OnSuccess=marker@ok.service  /bin/true        → FIRED ok
systemd-run --user --unit=ntest-bad --property=Type=exec \
    --property=OnFailure=marker@bad.service /bin/sh -c 'exit 3' → FIRED bad
sh -c 'systemd-run … sleep 2; exit 0'   → the unit survived the launching shell, notifier fired
systemd-run --user … /bin/true           → returned in 51 ms
```

So the whole pattern is: *start* (51 ms), exit the tool call, and the notification arrives later.
Three traps found by measuring rather than assuming:

- **`%n` does not expand inside a transient property**: `--property=OnSuccess=done@%n.service`
  fails with `Invalid unit name done@%n.service`. The notifier must be addressed explicitly, which
  is why the job id is generated first and the unit is `pi-done-notify@<id>.service`.
- **The notifier inherits the manager's environment, not the caller's.** A `--setenv=PI_AGENT_DIR=…`
  on the *job* unit does not reach the *notifier* unit, so a test that points both at a tempdir
  proves only that the notifier cannot find its record. The selftest therefore exercises the
  production paths — and that defect was caught by the selftest, not by review.
- **`--collect` unloads the unit at exit**, after which `systemctl show` has nothing to read. So the
  job body writes its own result record (`events/jobs/<id>.json`: rc, wall clock, last lines)
  *before* it exits, and the notifier reads that — never the unit's post-mortem state.

`bin/pi-done` is that pattern: `pi-done run --title T -- CMD…` starts a transient unit with
`OnSuccess`/`OnFailure` pointing at the notifier template (`pi-done-notify@.service`, installed on
first run), and returns. The notifier appends one row to `events/done.jsonl` (always), a desktop
notification (best effort), optionally a phone text (`--phone`) and an agenda task (`--task`). When a
caller genuinely needs the result *now*, `pi-done wait ID` delegates to `bin/pi-wait` on the unit's
MainPID and reports rc from the job record; a job that already finished returns immediately.

Consumption is the other half, and it must not be a poll loop either. The ledger is read when a
session looks (`pi-done log`), and the agenda row `job-done` (15 m, `exec:pi-done check --quiet`)
fails **only on an unseen failed job** — so a failure raises the next session's priority, while a
success cannot become p1 noise. This is the harness's own rule: an `exec` check may open judgement,
a cadence may not.

## 6. What changed in this harness

- **`bin/pi-wait`** — `pid` (pidfd), `unit` (MainPID), `file` (inotify, `--stable` debounce),
  `pattern` (append stream), `port` (backoff). Blocks, returns the event, prints elapsed time so the
  wait is measurable. `--selftest`: 10 cases, all passing; ≈3.2 s total, of which the CPU cost of
  the waits is ~0.
- **`bin/pi-tool lint`** — fails on `sleep` inside a `while`/`until`, and on `sleep N; <command>`
  (sleep-then-check), naming `bin/pi-wait` in the message. A line or file can opt out with
  `pi-tool: allow <reason>` — visible in review, never silent.
- **`bin/pi-preflight` check `tools`** — blocks publish on any lint error or any unpinned tool, so a
  polling loop cannot be added back quietly. Verified by injecting
  `while ! test -f /tmp/x; do sleep 5; done` into `bin/`: `pi-tool lint` exit 1,
  `pi-preflight` → `FAIL tools … polling-loop`.
- **`bin/pi-done`** — push completion: `run` (detached, 51 ms), `log`/`events`/`seen`/`check`
  (ledger), `wait` (block only when needed, via `bin/pi-wait`). Verified end to end: a 6 s job
  started and returned immediately, the ledger row appeared 6.0 s later with rc and wall clock and
  **no process was watching it**; `pi-done wait` on a finished job returns instantly; a failing job
  (`exit 5`) is reported as `FAIL … rc=5` and `pi-done check` exits 1 for it while an unseen
  success does not.

## 7. Falsifier

If, after a month of sessions, the share of bash calls containing `sleep` has not fallen below 4 %
(from 7.6 %), then the waiter was not the cause of the babysitting — the cause is a session that
starts a long job in the foreground at all. The next change is then on the producer side: make every
long-running entry point `bin/pi-done run` by default (so it is detached and self-announcing), rather
than asking sessions to remember to detach.

## Citations

- `pidfd_open(2)`, Linux man-pages — <https://man7.org/linux/man-pages/man2/pidfd_open.2.html>
  (fd refers to a task; `PIDFD_NONBLOCK`; `EAGAIN` from `waitid`).
- `inotify(7)`, Linux man-pages — <https://man7.org/linux/man-pages/man7/inotify.7.html>
  ("monitoring filesystem events"; directory watches cover files inside).
- `sd_notify(3)`, systemd 262 — <https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html>
  (start-up completion notification, `READY=1`, barriers).
- `systemd-run(1)`, systemd 262 — <https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html>
  (`--wait`, `--pipe`; async by default).
- `entr` — "Run arbitrary commands when files change", <https://github.com/eradman/entr>.
- Local measurements: this document's tables; `bin/pi-wait --selftest`; the session-log parse
  described in §0; the two systemd probes in §4.
