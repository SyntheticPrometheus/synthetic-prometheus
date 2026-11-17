# Incidents and their guards

Rule: **every failure gets a guard, not just a fix.** An entry is closed only when the guard is
something that runs (a check, a test, a refusal) or a rule that is loaded every session. A fix
without a guard is a promise, and promises are what failed the first time.

Format: what happened → root cause → guard → where the guard lives.

## 2026-11-17 — a due session opened with nothing in its queue and looped (bug #198)

- **What**: the 49-hour pergola pass (`01a1df87`) closed all 19 BACKLOG items and then ran 20 identical
  `git status; git log` calls in 70 s on a tree it had already confirmed clean (504 e2e launches, 42
  sessions), and `pergola-dev` was scheduled again the moment BACKLOG.md had no open item.
- **Cause**: the agenda knew the *row* was due but nothing knew whether the row's **queue** held work.
  `notes` is prose; `due_work()` opened a session on lateness alone.
- **Guard**: a row may register a queue check in `agenda/session-checks.json`; `pi-text dispatch --due`
  runs it before opening a session, records `due-empty`, rolls the row forward and spends nothing, and
  the due prompt carries a stop rule (an empty queue is reported once, never re-verified). A check that
  cannot run counts as work, so a broken guard cannot retire a row. Pergola's check is
  `scripts/backlog-open.sh` (exit 0 + `N open`, else the reason). Measured: `--dry-run` printed
  `idle pergola-dev: BACKLOG.md has no open item`, the real pass rolled the row to 2026-11-19 13:59 with
  a `due-empty` ledger row and no session; `pi-tool check pi-text` green on the six new cases.
- **Lives in**: `bin/pi-text` (`queue_state`, `split_idle`, `close_idle`), `tests/pi-text.sh`,
  `agenda/session-checks.json`, `~/Projects/pergola/scripts/backlog-open.sh`, `skills/agenda` § empty queue.

## 2026-11-17 — a new tool shipped with a selftest nobody had run

- **What**: `bin/pi-done` was in the tree with an uncommitted `--selftest`, and `pi-preflight`
  failed `tools` with `pi-done test failed: rc=1`. The selftest crashed on `A.all` (the fixture's
  fake argparse object had no attribute `all`) and, once that was fixed, still failed because it
  asserted `pi-done check` exits 1 for a *successful* unseen event — the opposite of the documented
  contract (only a failed job raises the agenda's priority; `--all` is the inbox view).
- **Cause**: the selftest was written from the tool's *intent* and never executed, so it encoded a
  contract the implementation had already moved away from. A test is evidence only if it has run.
- **Guard**: the selftest was made to assert both halves (`check` quiet on success, `check --all`
  exits 1, `check` exits 1 on a failure), and `pi-tool check` runs every pin twice inside
  `pi-preflight tools`, so a selftest that was never run blocks publish. Measured: 1 failure before,
  all cases pass after; the systemd round trip (OnSuccess/OnFailure) fires with nobody waiting.
- **Lives in**: `bin/pi-done` (`selftest`), `bin/pi-tool check`, `pi-preflight` check `tools`.

## 2026-11-17 — the "every tool is pinned" rule was prose

- **What**: `AGENTS.md` said "`pi-preflight`'s `tools` check makes an unpinned tool block publish",
  and `pi-preflight` was green — while `pi-tool list` reported **48 of 54** scripts with no test and
  no selftest. `tools()` ran `check` and `lint` and then returned success on the pinned count it
  had computed but never gated on.
- **Cause**: a policy written as a sentence and a check written as a report. The check read the
  number; nothing compared it to a threshold, and no baseline existed to say which debt was old and
  which was new.
- **Guard**: `pi-tool pins` (a ratchet against `tests/pins-baseline.json`): a tool that is not in
  the baseline and has no pin fails, and the unpinned count may not rise; `--update` is the only way
  to record a smaller baseline after pinning. `pi-preflight tools` now runs `pi-tool pins --quiet`
  and fails on new debt. Measured: baseline 46 unpinned, a new unpinned fixture tool fails the
  check, pinning one passes and reports it.
- **Lives in**: `bin/pi-tool` (`cmd_pins`, `unpinned`), `tests/pins-baseline.json`,
  `pi-preflight` check `tools`.

## 2026-11-17 — an index that described itself and so described nothing

- **What**: the tree had 22 areas, 55 tools, 20 skills, eight agents and eight top-level docs, each
  documented in its own README, and no single index — a session had to read forty files to learn
  what existed. Building `bin/pi-map` exposed two bugs in the index's own checks: the generated
  `MAP.md` was in the reference corpus, so it listed every tool and no tool could ever be an orphan;
  and the orphan regex required the next character to be `[\w.-]`, so a tool named at the end of a
  sentence (`bin/loose.`) was invisible. Stray artifacts also survived: `~/ok`, `themes/`, and two
  test units (`done@.service`, `marker@.service`) writing to `/tmp/ntest`.
- **Cause**: a generated artifact counted as source, which is the same class as a check reading its
  own output. The regex boundary was written for path names, not prose.
- **Guard**: `map.json` (curated purpose per area/doc) plus `bin/pi-map --check` fails on an
  undocumented path, a stale pointer, an empty unacknowledged dir, or an orphan tool; generated
  files are excluded from the reference corpus; the trailing boundary allows sentence punctuation;
  `pi-preflight map` blocks publish on staleness. `pi-preflight units` now fails on a user unit whose
  `ExecStart` writes to `/tmp/`. The strays were removed. Measured: `pi-map --check` green over 22
  areas / 55 tools, and the selftest proves each failure mode (undocumented dir, stale fingerprint,
  empty dir, orphan, self-reference).
- **Lives in**: `bin/pi-map`, `map.json`, `MAP.md`, `pi-preflight` checks `map` and `units`.

## 2026-11-16 — a 16k local context that "filled up immediately and timed out"

- **What**: every `pi` session on a `local/*` model died or crawled. The router serves `-c 16384`
  and models.json declares 16384, so the numbers agreed — and the session still ran out of context on
  the first tool result and took 25-30 min per turn.
- **Cause**: two failures stacked. (1) The harness prompt Pi sends is **12,588 tokens** (AGENTS.md
  2.9k, skills list 3.8k, MCP tool declarations + server blurb 4.0k, memory brief + subagent 0.7k,
  base prompt + 4 tools + cwd 1.2k), so with `maxTokens` 2048 the session had 1.4k tokens of headroom,
  overflowed at the first tool result, and each compaction re-prefilled the whole prompt at 7.8 tok/s
  at depth. The context size was never the problem — the prompt was 77% of it. (2) Once the prompt
  fit, the model still burned the turn: `Llama-3.2-3B` asked to "reply with exactly: ready" called
  `read` on a directory (EISDIR), `read` on an invented path (ENOENT), then sent an invented `edit`
  payload — ~20 s per round.
   
  Measured cause of the slow start: prefill is `54 ms/token` (1.5B) and `190 ms/token` (3B) at
  depth, so 13k tokens is 12-24 minutes before the first token.
- **Fix**: a local model gets a ~1.5k-token harness instead — four tools (bash, read, edit, write),
  a short instruction card, the short memory brief, no skills list, no MCP, no AGENTS.md. Cloud
  models are untouched (verified: same dump-server run keeps 15 tools and the full 32.5k-char prompt).
- **Guard**: `extensions/local-slim.ts` applies the profile automatically to any local/loopback
  model, and refuses the loop classes (identical repeat; 3 consecutive failed calls → terminate;
  12 calls per run). `bin/pi-local-ctx` now **fails** if the measured local prompt is above 4,000
  tokens (i.e. the profile is not in effect) as well as on declared-vs-served mismatch, and
  `pi-preflight` runs it. Numbers: `local/prompt-layers.json`.
- **Measured after**: 12,588 → 1,409 tokens of prompt + tools (1,663 for the whole first request
  on the 3B, 1,524 on the 1.5B), ~13.7k tokens of working room in 16k, one turn 94 s (1.5B) /
  182 s (3B) cold, 79 s for a full tool cycle, and turn 2+ re-prefill 23 tokens.
- **Lives in**: `extensions/local-slim.ts`, `extensions/memory-boot.ts` (200-token brief for local),
  `models.json` (maxTokens 1024 for local), `bin/pi-local-ctx`, `skills/local-models`.

## 2026-11-16 — a perfectly tiled screen that the harness called empty

- **What**: four terminals were tiled 2×2 on workspace 3 and the screenshot showed all four,
  but `pi-tile` printed `tiled 0/4` with every window flagged `parked`, `pi-tile status` said
  `hidden`, and `pi-shot` logged *"0 windows in shot"* — exit 0, no warning. The picture was
  right and every number attached to it was wrong.
- **Cause**: `visible` in `bin/pi-tile` was `win["desktop"] == 0`, a literal first-workspace
  test. Work here runs on workspace index 2, so the whole protocol was blind on every desktop
  but the first: `pi-shot --expect N`, `win-log.jsonl` and the `hidden` list all inherit it.
- **Guard**: `current_desktop()` (parsed from `wmctrl -d`, the `*` row) replaces the literal at
  every gate (`tile`, `status`, `describe`, `park`, `unpark`), rows carry `current`, and
  `pi-shot` now **exits 4** with *"N window(s) sit on this desktop but none landed in the shot
  — the picture is blind, not empty"* instead of writing a silent 0-window record.
- **Measured**: with `inside()` stubbed to False, `pi-shot --no-tile` exited 4 and named the
  windows; unpatched it exited 0. On the real desktop `pi-tile` went `0/4 parked` → `4/4 shown`
  and `pi-shot --expect 4` exited 0.
- **Lives in**: `bin/pi-tile` (`current_desktop`, `tile`, `status`, `park`, `unpark`),
  `bin/pi-shot` (blind-shot refusal), `skills/windows` (pitfall).

## 2026-11-16 — `pi-tile --park` booked a desktop the window never reached

- **What**: `pi-tile --park <id>` moved a window, wrote `parked.json` (desktop 3), printed
  `parked 0x… (desktop 1)`, and the window was back on the current desktop one `arrange` later —
  still in the shot, still called parked. `--unpark` then had nothing real to undo.
- **Cause**: pergola 0.4.0-dev re-applies a docked panel to the current desktop and `arrange`
  runs over the daemon's whole tree, so a bare `wmctrl -t` is undone; `park()` waited for
  `not in_tree` (5 s), ignored the failure and booked anyway. The printed desktop (`1`) was a
  hardcoded default, unrelated to where it was sent.
- **Guard**: `park()` floats the panel first (`pergola float --window`), then moves it; `main`
  re-checks every requested window **after** `tile()` and, if one came back, appends
  `did not park …` to `problems` and exits **3** — a park that did not happen is now a red run,
  not a sentence.
- **Measured**: `pi-tile --park 0x03167127` → `parked … (desktop 3)` then `PROBLEM did not park`,
  exit 3, window still at `+803 +466` on desktop 2. Raw `pergola float` + `wmctrl -t 3` alone
  *does* hold for ≥3 s, so the re-homing is the daemon's doing, not the WM's.
- **Measured 2026-11-17, second hole**: the first fix re-ran the repro and the window still came
  back. A debug build showed `arrange` re-docking the *floating* window into the tree; the
  geometry move was skipped (guard working) but the raise that follows a fresh dock was not, and
  xfwm4 answers a raise for a window on another desktop by mapping it on the current one. The
  daemon's own reads showed `_NET_WM_DESKTOP = 1` right after `arrange` and the window at `0` a
  moment later, with no `move_resize` in the log — the raise, not the move, was the culprit. The
  original diagnosis ("the daemon's reconcile") was wrong.
- **Fixed in pergola 0.5.0-dev**: the daemon now leaves a window alone when its `_NET_WM_DESKTOP`
  is another host desktop (or a sticky `0xFFFFFFFF`) — in `apply` (both the tiled and floating
  passes), `park_inactive`, the raise after a dock, and adoption; a newly opened window on another
  desktop is not adopted. The predicate is unit-tested and the e2e moves a **tiled** and a
  **floating** window to a second host desktop, runs `arrange`, and asserts each stays there.
  With the daemon no longer dragging it back, a bare `pergola float` + `wmctrl -t` holds, and the
  live `pi-tile --park` repro exits 0.
- **Lives in**: `bin/pi-tile` (`park`, `main`), `skills/windows`; the daemon side in
  `crates/pergola/src/daemon.rs` (`on_another_desktop`, `foreign_desktop`).

## 2026-11-16 — my commit carried three other sessions' edits

- **What**: the panel commit staged five paths; two of them (`INCIDENTS.md`, `bin/pi-preflight`)
  were *already* carrying work by other live sessions — three incident entries and the `local ctx`
  check — so that commit documents and ships work its author did not write. Nothing was lost, but
  the message lies and the review boundary is wrong.
- **Cause**: `git add <path>` stages a whole file. `pi-claim check` said `free` (the other sessions
  held no lease), and the commit gate only refuses a path another session reserved or touched within
  its recency window — an edit made two hours earlier is neither, yet its hunks are still there.
- **Guard**: `pi-claim reserve` now warns per requested path that already has uncommitted changes
  (`NOTE already modified before this reservation — … stage only your lines`) and logs a
  `reserve-dirty` event, so the split is visible before the edit instead of after the commit.
- **Measured**: reserving `bin/pi-agenda` (dirty from another session) printed the NOTE; a clean path
  (`bin/pi-mem-view`) printed nothing; the event appears in `claims/claim-log.jsonl`.
- **Lives in**: `bin/pi-claim` (`cmd_reserve`), `CONCURRENCY.md` (§ The five-line protocol), this
  file. The commit itself was amended to say which files carried foreign hunks.

## 2026-11-16 — every panel indicator's click was dead, and the tag was why

- **What**: adding the RAM indicator meant exercising its click, so `xdotool click 1` was pointed at
  the two indicators already on the panel — *due* and *bg* — and nothing happened:
  `pi-term --list` stayed empty. A probe click of `<click>touch /tmp/memclick.log</click>` never
  created the file; the same probe as `<txtclick>` did, immediately.
- **Cause**: two faults stacked, either one enough to kill the interaction. genmon 4.3.0 executes
  `<txtclick>`/`<iconclick>` and silently ignores a bare `<click>`; and genmon runs a click **with
  no terminal**, so even a firing bare view (`pi-runtime-view`, `pi-agenda-view`) had nowhere to
  print. The click targets were documented in `skills/desktop` from the day they were written and
  had never once been used.
- **Guard**: `bin/pi-preflight` check `panel` runs `pi-bg --panel bg|fg|due|mem` and fails on a bare
  `<click>`, on genmon XML that does not parse, on an empty `<txtclick>`, and on any of those four
  indicator classes missing from `panel-1`'s `plugin-ids`. It runs on publish and weekly maintenance.
- **Measured**: with the tags fixed, clicking *mem*/*due*/*bg* opened `pi: mem`, `pi: agenda` and
  `pi: runtime` and `pi-term --list` reported each `open` before `pi-term --close <slug>`; the mem
  tooltip and its amber/red thresholds were verified by screenshot on the live panel.
- **Lives in**: `bin/pi-bg` (three `<txtclick>` tags), `bin/pi-mem-view`, `bin/pi-preflight`
  (`panel`), `skills/desktop/SKILL.md` (§ *What the machine is doing*).

## 2026-11-16 — a model process nobody asked for held 1.1 GB of RAM for 32 hours

- **What**: killing one orphaned `llama-server` (a child of the router, 32 h old, idle) returned
  **1102 MB**: `used` 3007 → 1905 MB, MemAvailable 4832 → 5933 MB, zram DATA 809 → 239 MB. That was
  14% of a 7.8 GB box, and every summary I had was blind to it — top-PSS did not show it at all
  (RSS 2 MB, VmSwap 1109 MB): an RSS ranking cannot see a completely swapped-out process.
- **Cause**: `--models-autoload` spawns one `llama-server` child per model and only the *router* is
  supervised by systemd. Nothing watched per-model processes. This host's measured policy is one
  model at a time (two resident = 51.9 s per trivial request vs 2.1 s), so a second child is always
  waste, and a router child that keeps its KV/heap after the router stops using it is a leak.
- **Guard**: `bin/pi-local-reap` reaps a `llama-server` only when it holds ≥200 MB of anon+swap, has
  <1% lifetime CPU duty and is older than 2 h; it matches `/proc/pid/exe` (so a `bash -c` wrapper that
  merely mentions llama-server is never killed), keeps the busiest router child, and exits 1 under
  `--check`. Wired as a `warn local` line in `pi-preflight` and as the 2 h `local-reap` agenda row.
  Verified by starting a real `llama-server` (296 MB anon), reaping it, and by a `--check` exit of 1.
- **Lives in**: `bin/pi-local-reap`, `bin/pi-preflight` (`local`), `pi-agenda` row `local-reap`,
  `skills/local-models/SKILL.md` (*Disk-paged big models*).

## 2026-11-14 — a skill vanished from the prompt because of one colon

- **What**: every pi session started with `~/.pi/agent/skills/local-models/SKILL.md — Nested mappings
  are not allowed in compact mappings`. The warning was ignored for hours, so the skill that holds
  the local-model routing rules was simply not in the prompt: pi parses frontmatter with `yaml` and
  *skips the whole resource* on a parse error.
- **Cause**: the description was an unquoted plain scalar containing `cost: the measured verdict`. In
  YAML a colon-then-space inside a plain scalar starts a nested mapping, which is illegal on one
  line — the same trap every hand-written frontmatter value has.
- **Guard**: `bin/pi-fmcheck` parses every skill/agent/prompt frontmatter with the *same* `yaml`
  library pi uses (plus pi's own rules: slug name, description present and ≤1024 chars, unique
  names) and is a blocking `pi-preflight` check, so publish and weekly maintenance fail rather than
  ship a resource pi can never load. A broken-fixture and a real-tree test both fail as expected.
- **Lives in**: `bin/pi-fmcheck`, `bin/pi-preflight` (`frontmatter`), `skills/local-models/SKILL.md`
  (the rule is written into the description so it travels with the skill).

## 2026-11-14 — bugs reported to the owner instead of fixed or queued

- **What**: the visual pass on Pergola ended with "known limitations" and a list of things that
  looked wrong, handed to the owner to remember. Two of the three were real bugs (work area,
  overlay borders) and one was a design choice; none of them had an owner or a date.
- **Cause**: no rule said what to do with a bug at the moment it is found, so the default was to
  describe it. A description is not a fix and not a task — it is a thing the owner has to carry.
- **Guard**: a bug is **fixed in the same turn or filed** with `pi-agenda bug "<title>" --repro "…"
  --ref …` (priority 1, due 3d). `pi-agenda next` lists open bugs and exits 2 when a priority-1 task
  is older than 3 days; the 10-minute tick notifies on open bugs and stale p1s; `pergola-dev` works
  the bug queue before the backlog. The report to the owner is "fixed" or "queued as #N", never
  "here is a bug".
- **Lives in**: `bin/pi-agenda` (`bug`, `bugs`, `stale_p1`), `AGENTS.md` (Every failure gets a
  guard), `skills/agenda/SKILL.md`.

## 2026-11-14 — auth.json and the memory journal were committed to git

- **What**: the first provenance commit in `~/.pi/agent` tracked `auth.json` (an OpenRouter key) and
  `memory/journal/*.jsonl` (private chat content).
- **Cause**: `git add -A` with a `.gitignore` that listed directories but not secrets.
- **Guard**: history deleted and re-initialised; `.gitignore` now names every secret path; the
  publish path uses an **allowlist** (not a denylist) and greps the snapshot for key shapes and for
  the machine name before any push.
- **Lives in**: `~/.pi/agent/.gitignore`, `bin/pi-publish` (`scan()`), `bin/pi-preflight`.

## 2026-11-14 — global OOM killed the X session

- **What**: concurrent eval runs + Laya resident (2.8 GB) + torch exhausted 7.8 GB; the kernel killed
  dconf/pipewire/gvfs/dbus-broker and the session died.
- **Cause**: no cgroup limit on the eval children, and a 2.8 GB model preloaded for every session.
- **Guard**: `run.py` refuses to start below 1200 MB `MemAvailable` and wraps each `pi` call in
  `systemd-run --user --scope -p MemoryMax=2500M`; Laya is `LAYA_PRELOAD=0`.
- **Lives in**: `selfimprove/run.py`, `mcp.json`.

## 2026-11-14 — three judge defects in the self-improvement suite

- **What**: the verifier expected 1467 (true 1567); it counted only the literal token `5xx` and
  dropped a `500` line; the `spec-10` expected file said `cache: true` where the spec implies false.
  In all three the agent was right and the judge was wrong.
- **Cause**: hand-written expected values, never tested against a known-good answer.
- **Guard**: `selftest.py` must show a known-good answer PASSES and a known-bad answer FAILS for
  every task before any arm runs; the suite hash is pinned in the ledger; `gate.py` voids
  cross-hash comparisons; judge-owned `verify_files` are rewritten after the arm runs.
- **Lives in**: `selfimprove/selftest.py`, `gate.py`, `run.py`.

## 2026-11-14 — GitHub signup blocked as bot activity

- **What**: signup returned "unusual activity" (ID 3b334e10…, IP 96.255.73.39).
- **Cause**: a browser launched from a script (`setsid firefox --new-window …/signup`) plus a burst
  of unauthenticated `api.github.com` calls.
- **Guard**: never automate signup/login, never launch a browser at an auth flow, keep unauthenticated
  API traffic low; signup flows are driven one action at a time with a human available for the
  challenge.
- **Lives in**: `AGENTS.md` (publishing section), `PUBLISHING.md`, `RUNBOOK-accounts.md`.

## 2026-11-14 — xdotool clicks silently missed for 20 minutes

- **What**: pointer clicks did nothing on a page where keyboard worked; the "I agree" button looked
  enabled and was not in the tab order.
- **Cause**: `xdotool mousemove --window` uses the window's **frame** origin while `import -window`
  captures the **client** area — a 28px offset, 12px after `xfwm4 --replace`.
- **Guard**: calibrate the offset with one harmless click before a sequence, or use Tab+Enter; if
  clicks stop working, suspect the offset before clicking harder.
- **Lives in**: `AGENTS.md` (automation note), memory #71.

## 2026-11-14 — publish pushed a duplicate snapshot and failed on a rejected ref

- **What**: the weekly unit rebuilt the tree, counted all 58 files as changed, and the push was
  rejected (`fetch first`).
- **Cause**: no baseline snapshot to diff against, and no rebase path.
- **Guard**: `publish/last` stores the last pushed tree; a rejected push rebases once and retries;
  the unit is gated on `publish/enabled` so an unauthenticated machine produces no failed units.
- **Lives in**: `bin/pi-publish`.

## 2026-11-14 — a harness change was accepted on a single task and then reverted

- **What**: `cand-verify` won +2 on 2 tasks at k=6, then lost 3/3 on `long-reports` at k=3 on the
  full suite.
- **Cause**: one task dominated the aggregate, and the effect was run noise.
- **Guard**: k≥3 with a fresh baseline, no per-task regression, Δ≥2, and a per-task breakdown printed
  by the gate; a change that trades one class for another is a reject.
- **Lives in**: `selfimprove/gate.py`, `policy.json`, `decisions.md`.

## 2026-11-14 — the publish repo silently stopped publishing (three bugs in a row)

- **What**: `pi-publish --push` printed "pushed" while the remote stayed on the old commit; later a
  push failed with "origin does not appear to be a git repository"; the top-level README and
  PUBLISHING.md vanished from the snapshot.
- **Causes**, in the order they were found:
  1. `render()` did `rmtree(DST)`, which deleted the snapshot repo's `.git` — so every run
     re-initialised a repo with no remote, and `git` fell through to the parent repo.
  2. The reject path used `git pull --rebase`, which conflicts on a snapshot repo (every file is
     "added" on both sides) and left the repo stuck mid-rebase; the next push then no-ops.
  3. `README.md`/`LICENSE`/`PUBLISHING.md` were written *after* `render()`, so the reject path's
     re-render wiped them.
- **Guards**: `render()` preserves `.git` and writes README/LICENSE/PUBLISHING itself; a stuck
  rebase is aborted at start; a rejected push does `fetch` + `reset --hard origin/main` + re-render
  + commit (never rebase); the local branch is forced to `main`; `pi-preflight` now checks that the
  snapshot has README/LICENSE/PUBLISHING, that a remote exists, and that no rebase is in progress.
- **Lives in**: `bin/pi-publish`, `bin/pi-preflight`.

## 2026-11-14 — audit: "did we push the passwords?"

- **What**: after the first publish, the owner asked whether the passwords had been pushed. They had
  not — but nothing in the pipeline *proved* that, which is the actual deficiency.
- **Checked**: the literal Google password does not appear in the snapshot or in any commit of the
  publish repo (`git grep` over all revs); no `.gpg`/`.key`/`.pem` file is published; the only
  credential-adjacent files are `PASSWORDS.md` (the protocol) and `bin/pi-secret` (the helper), which
  carried the GPG **fingerprint** — a public key id, not a secret.
- **Guards**: `pi-preflight` now reads every entry in the password store and fails if any stored
  password appears in a git-tracked file or in the publish snapshot; `pi-publish` redacts the store's
  fingerprint from the published copy, so a template carries no key id at all.
- **Lives in**: `bin/pi-preflight` (`credentials`), `bin/pi-publish` (`redact`).

## 2026-11-14 — the secret guard lived only at the last gate

- **What**: incident #1's guard (secret scan) ran inside `pi-publish`, so it only fired at push time.
  A new secret-shaped file under a name `.gitignore` had never heard of would still be committed —
  the failure class was guarded at the exit, not at the entry.
- **Cause**: the guard was placed where the damage was noticed (publish), not where it happens (commit).
- **Guard**: `bin/pi-commit-guard.py` runs from `.git/hooks/pre-commit` and scans the *staged added
  lines* for every shape in `pi-publish`'s `SECRETS` list plus a hard path denylist; it exits 1 and
  prints the fix. `pi-preflight` fails if the hook is missing or its fallback shapes drift from
  `pi-publish`.
- **Lives in**: `bin/pi-commit-guard.py`, `.git/hooks/pre-commit`, `bin/pi-preflight` (`commit_guard`).

## 2026-11-14 — delegation policy was reading half-blind evidence

- **What**: 13 of 41 ledger rows had no verdict; `scout/recon` (5/6) and `scout/understand` (6/7) were
  mostly unchecked yet still printed a mean, and the report emitted no proposal for them — silence
  that looked like "nothing to change".
- **Cause**: proposals keyed on verified pass/fail counts only; unverified rows were dropped instead of
  flagging the cell as unmeasured.
- **Guard**: `pi-delegate report` now emits `MEASURE` and suppresses KEEP/DROP for any cell where more
  than half the rows are unverified, and prints a global warning when >30% of rows are open.
- **Lives in**: `bin/pi-delegate` (`report`).

## 2026-11-14 — the Google account was unreachable because the *login* was gated, not the mailbox

- **What**: told to "use the email you have", I drove Firefox to Gmail and hit Google's anti-bot
  device challenge (`Verify your info to continue` → QR scan with the recovery phone, or SMS). The
  password was in `pass` and useless. Reading a verification code was impossible from a shell.
- **Cause**: two mistakes stacked. (1) I treated "I have the account" as "I can read the inbox" —
  identity ≠ transport. (2) The default reach — GUI browser — was the only interface I had, so a
  wall that no browser can pass became a wall that *I* could not pass.
- **Guard**: a transport with no browser in it. `bin/pi-mail` reads the inbox over Gmail's Atom feed
  (`mail.google.com/mail/feed/atom/`) authenticated with cookies read from the persistent Firefox
  profile, and switches to IMAP automatically once `pass google/imap-app-password` exists (which
  needs 2-Step Verification — currently off, so App Passwords are unavailable). `pi-preflight` now
  prints `warn mail …` on every run, so silent session expiry is visible within a week.
- **Rule it produced**: AGENTS.md › Interface order — MCP/API/shell first, GUI last, and prefer a
  *persistent credential* over scripted clicks, because clicks die with the session.
- **Lives in**: `bin/pi-mail`, `bin/pi-firefox` (last-resort GUI driver), `bin/pi-preflight`, AGENTS.md.

## 2026-11-14 — `pkill -f <pattern>` killed my own shell, twice

- **What**: `pkill -f llama-server` and then `pkill -f 'longinput|batch.py'` each SIGTERMed the
  invoking `bash -c` process (exit 143). The first lost a benchmark run mid-flight; the second lost
  the cleanup step. The pattern was in my own command line, so I was a match.
- **Cause**: `-f` matches the full command line of *every* process, including the shell that is
  typing the pattern. Two occurrences in one session means the habit, not the instance, was wrong.
- **Guard**: `bin/killpat PATTERN` — same matching, but it excludes itself and its ancestry up to
  init, prints each victim before signalling, and has `-n` for a dry
  run. Use it instead of `pkill -f` any time the pattern could appear in my own command line
  (which, when I am grepping for the thing I started, is always).
- **Lives in**: `bin/killpat` (tested against the live router: dry run listed the two llama-server
  processes and not the calling shell).

## 2026-11-14 — a parallel session's `git add -A` committed a half-finished skill patch

- **What**: while vendoring mattpocock/skills, a second `pi` session committed the whole tree
  (`52ac829`), sweeping in my in-progress `upstream/PROTOCOL.md`, a draft
  `LOCAL-CHANGES.md`, and a first, botched rewrite of 12 skill files (literal `read(s)` text in two
  in-progress skills) that I had already replaced. Nothing was lost only because the working tree
  was still authoritative.
- **Cause**: `git add -A` from a session that could not see another session's in-flight files, and
  nothing at commit time looked at *content* — only at secret shapes and forbidden paths.
- **Guard**: the pre-commit guard now refuses (a) any staged file containing merge-conflict markers
  and (b) a staged `vendor/` tree that `bin/pi-skills verify` rejects (unregistered local edit,
  broken frontmatter, dropped bundled file). Bulk commits should list paths, never `git add -A`.
- **Lives in**: `bin/pi-commit-guard.py` (`content_problems()`), hook installed at
  `.git/hooks/pre-commit`, `bin/pi-skills verify`, `bin/pi-preflight` (`skills`).

## 2026-11-14 — two sessions edited `~/Projects/pergola` at once and duplicated each other's code

- **What**: while adding `_NET_WORKAREA` support, a second live `pi` session was working the same
  repo on a different backlog item. Within minutes the same `Atoms` struct held `net_workarea`
  twice, `workarea()`/`workarea_rect()` existed side by side, the overlay API had been changed under
  a daemon that still called the old signature, and `cargo build` was red — each of us looking at a
  file that the other had rewritten between two tool calls.
- **Cause**: nothing in the session start looked for other sessions in the same tree; `git status`
  showed uncommitted work but not *whose*. Both sessions assumed "uncommitted means mine".
- **Guard**: `bin/pi-claim check <tree>` — busy when another session holds a fresh
  `<tree>/.pi-claim` with a live agent pid, or when another session's log was written in the last
  10 min and names the tree (absolute *or* relative, since a session that already `cd`-ed writes
  `Projects/pergola`, not the absolute path). `bin/pi-claim <tree>` claims it for this session and
  refuses otherwise. Run the check before the first write to any shared tree; on BUSY, edit disjoint
  files, wait for the other session to commit, or release the claim when done.
- **Lives in**: `bin/pi-claim`, AGENTS.md › Engineering defaults (shared trees).

## 2026-11-14 — two system units sat failed for 11 hours and nothing read `systemctl --failed`

- **What**: `snapper-boot.service` (no snapshot of root on boot) and `grub-btrfsd.service` (no
  regeneration of the GRUB snapshot menu) had been failing since 10:11. The harness audited its own
  skills, secrets and timers every week but never looked at the init system.
- **Cause**: snapper on Arch only materialises a config listed in `/etc/conf.d/snapper`
  (`SNAPPER_CONFIGS=""`), so `/etc/snapper/configs/root` existed but was invisible to snapperd —
  `list-configs` was empty, `create-config` then refused because `/.snapshots` was already a
  subvolume. `grub-btrfsd` is a bash daemon that exits 1 when `inotifywait` is absent, with the
  reason only in its own stdout.
- **Guard**: `pi-preflight` check `units` fails on any failed `systemctl --system`/`--user` unit, so
  a dead daemon cannot survive to the next weekly review unnoticed. Same class, same day: tumblerd
  could not load five thumbnail plugins (missing optional libs) and pipewire logged RTKit
  `ServiceUnknown` — both had been in `.xsession-errors` for a day; `ffmpegthumbnailer`, `libgepub`,
  `libgsf`, `poppler-glib`, `libopenraw` and `rtkit` are now installed and `rtkit-daemon` enabled.
- **Lives in**: `bin/pi-preflight` (`units`), `/etc/conf.d/snapper`, `inotify-tools`, `rtkit`.

## 2026-11-14 — Laya SIGILLed twice on an AVX-512 kernel from torch's bundled MKL

- **What**: `laya-mcp-server` and `laya-vote.py` each died with SIGILL and left a 1 GB core dump.
  Both stack traces end in `mkl_vml_kernel_sCos_Z0HAynn` — a kernel whose first loop instruction is
  `vmovups %zmm26` (EVEX/AVX-512). The CPU is an i7-3520M: SSE4.2 + AVX, `CPUID.7.EBX = 0`, no
  AVX2, no AVX-512, so the instruction cannot decode.
- **Cause**: torch 2.15.0+cpu's oneMKL 2024.0 VML dispatcher selected an AVX-512 kernel on a
  non-AVX-512 CPU (MKL reports SSE4.2 for GEMM, so the wrong choice is specific to VML's threaded
  `mkl_vml_serv_threader` path). The cos/sin call is the rotary table in `laya/fast.py`.
- **Guard**: `MKL_ENABLE_INSTRUCTIONS=SSE4_2` in `mcp.json` (every MCP session) and `bin/layaq`
  (shell one-shot), set before torch is imported; `pi-preflight` check `laya-vml` fails the run if
  the flag is missing from either place or if the exact rotary-table cos/sin call crashes in the
  laya venv. Not proof of dispatch — it is the strongest testable guard until the MKL bug is fixed.
- **Lives in**: `~/.pi/agent/mcp.json`, `bin/layaq`, `bin/pi-preflight` (`laya-vml`),
  `laya/NOTES.md`.

## 2026-11-14 — global OOM again, with the earlier guard in place

- **What**: at 17:20 zram wrote back errors (`Write-error on swap-device 253:0`, i.e. zram0 full) and
  at 17:40 the kernel OOM-killed `llama-server` plus dconf/gvfs/gpg-agent/dbus-broker; the previous
  incident's guards (MemAvailable floor in `run.py`, MemoryMax on eval children) were in place and
  did not cover the model services.
- **Cause**: zram was the only swap (3.8 GB, zstd), and `llama-router` had no ceiling — an 8k-context
  load reached 4.6 GB VM. Under that pressure the kernel reaps session services.
- **Guard**: a 4 GB btrfs swapfile (`/swap/swapfile`, `chattr +C`, pri 10) as the disk backstop
  behind zram (pri 100), and `MemoryHigh=1800M`/`MemoryMax=3G` on `llama-router`. `pi-preflight`
  check `memory` fails when there is no non-zram swap or `llama-router` is uncapped.
- **Lives in**: `/etc/fstab`, `/swap/swapfile`, `~/.config/systemd/user/llama-router.service.d/memory.conf`,
  `bin/pi-preflight` (`memory`).

## 2026-11-15 — snapper timeline failed hourly for 6 h: active swapfile inside the snapshotted subvolume

- **What**: `snapper-timeline.service` failed every hour (`Creating snapshot failed`), while disk
  was 7% used and `snapper list` looked healthy. `pi-review` then failed with exit 1 because
  `pi-preflight`'s `units` check saw the failed unit — and `pi-review.service` was itself one of the
  failed units, so every later run failed on its own previous failure (a latch).
- **Cause**: the 4 GB OOM backstop from 2026-11-14 was created at `/swap/swapfile` inside `@`.
  btrfs refuses to snapshot a subvolume containing an active swapfile (`ETXTBSY`, errno 26). The
  unit's only symptom was one line in its own journal. The review latch was a separate bug: the
  check read `systemctl --failed` including the unit that runs the check.
- **Guard**: `/swap` is now a nested btrfs subvolume (`chattr +C`, swapfile inside), so `@`
  snapshots do not recurse into it; `pi-preflight` check `swap` walks every snapper `SUBVOLUME` and
  fails if a file-backed swap sits inside it without an intervening subvolume. `units` now excludes
  the harness's own units (`pi-review`, `pi-selfimprove`, `pi-publish`, `pi-preflight`, `pi-agenda`);
  those are judged by their own checks, so a failure can no longer latch.
- **Lives in**: `/swap` (subvolume), `/etc/fstab`, `bin/pi-preflight` (`swap`, `units`),
  `/etc/snapper/configs/root`.

## 2026-11-15 — five KeyError rounds against one JSON response

- **What**: harvesting i3/bspwm issue threads, the same `python3 -c "json.load(...)['issues']"`
  failed five times in a row in one session. The GitHub *search* API returns `items`, not `issues`
  (the *issues listing* endpoint returns a bare array). Each attempt was a full round trip plus a
  reread of the same payload, and the tool error was only `KeyError: 'issues'`.
- **Cause**: the response shape was assumed from a different endpoint and never inspected; there
  was no cheap way to see a shape, so the alternative was reading 10 KB of JSON by eye.
- **Guard**: `pi-web api URL --shape` prints keys, types, list sizes and two levels of sample values,
  and is the documented first move before indexing a response; responses are cached, so a retry
  costs nothing. `bin/pi-preflight`'s `web` check runs `skills/web/scripts/selftest.py`, which
  asserts the shape output (top-level keys, list element keys, and that recursion stops at two
  levels) — a regression there fails preflight instead of silently returning a 200-line dump.
- **Lives in**: `bin/pi-web` (`shape_of`, `api --shape`, MCP `web_api`), `skills/web/SKILL.md`
  ("Working notes"), `bin/pi-preflight` (`web`).

## 2026-11-15 — five sessions in one tree, and a guard that cried wolf

- **What**: five pi sessions wrote to `~/.pi/agent` inside four minutes; one created `bin/pi-text`
  and `text/` while another was mid-task in the same tree. Nothing was lost, because each commit
  named its paths. Separately, `pi-claim check` answered "busy" for a tree the *caller's own
  sibling session* had only read — with that many sessions every tree looks busy.
- **Cause**: the guard answered one question ("is a recent session log mentioning this tree?") where
  two were needed ("is someone live here" = advisory; "does someone own these paths" = blocking).
  Log recency cannot distinguish reading from writing, and the tree-level answer has no way to say
  "we can work on disjoint files", which AGENTS.md already permitted.
- **Guard**: `bin/pi-claim` v2 — a lease registry in `~/.pi/agent/claims/` (git-ignored) with
  **presence** (advisory) and **reservations** (blocking per path, nested-tree aware, stale-leased
  reaped, heartbeat+pid liveness). The pre-commit hook now calls `pi-claim guard --staged` and
  refuses a staged path that another live session reserved **or edited in its recent log**, so
  uncooperative sessions are covered too. `pi-preflight` fails on overlapping live reservations.
  `pi-delegate` passes `PI_CLAIM_OWNER` so a child's claim lands on the parent's lease.
  `bin/pi-claim selftest` (22 assertions, temp registry + temp repo, its own log file) runs in preflight.
- **Evidence it works, from the same day**: the gate refused the commit that shipped it —
  `AGENTS.md` had another session's uncommitted `## Texts` section staged alongside my two lines.
  The hunk was split out (HEAD + only my lines in the index, theirs left in the working tree) and
  committed with the per-path override; their section is still uncommitted and untouched.
- **Two false positives fixed before that**: a thinking block that *quotes* `{"type":"toolCall",
  "name":"edit"}` was counted as an edit (now the JSONL is parsed and `arguments.path` is read), and
  another session's already-committed edit still blocked for 60 min (now an edit older than the
  path's last commit is the baseline, not risk, and the window is 30 min).
- **Lives in**: `bin/pi-claim`, `bin/pi-commit-guard.py`, `bin/pi-preflight` (`claims`), `CONCURRENCY.md`,
  `AGENTS.md` (Shared trees), `.gitignore` (`.pi-claim`, `claims/`).

## 2026-11-15 — the owner's first texts were swallowed by a locked agenda DB

- **What**: the owner texted three times on the new `pi-text` channel. Two messages reached
  `text/inbox.jsonl` and were marked seen, but **no task was ever filed**, so no session would have
  acted on them — they were silently read and dropped. At the same time the 10-minute
  `pi-agenda tick --run` died with `sqlite3.OperationalError: database is locked` at the point where
  it records an obligation's run, so that obligation's `next_due` never advanced.
- **Cause**: the poller (`pi-text tick`) runs *inside* the agenda tick as an `exec:` row, and it
  files tasks by spawning `pi-agenda add-task` — a second writer against the DB its own parent is
  using. When that child lost the race it exited non-zero, and `pi-text` used `subprocess.run(...,
  check=False)` **without ever reading the return code**, so the failure was invisible: the message
  had already been appended to the inbox and added to `seen_ids`, which meant every later tick
  skipped it too. The parent tick meanwhile held a live sqlite connection across `fork()` of the
  exec children and crashed instead of retrying. Root cause of the lock itself is unproven (a WAL
  reset by a closing connection is the leading theory); the guards below contain it either way.
- **Guard**: (1) `pi-text` **parks** every message in `text/pending/<id>.json` *before* trying to
  file it, retries 4× with backoff, reads the child's exit code and logs stderr, and drains the
  queue on every later tick — a message cannot be "seen and dropped" any more. (2) `pi-agenda tick`
  closes its connection before forking exec children and retries the post-run row update 4× on a
  fresh connection; a run that still cannot be recorded is journaled, not a traceback. (3)
  `pi-text check` fails on any message parked >30 min, ≥6 consecutive poll failures, or a poller
  that has not run in 45 min, and is a blocking `pi-preflight` check (`text`).
- **Proved by**: 45 s and 130 s held write locks against the agenda DB (retry succeeded; park-then-
  drain succeeded), 5 ticks each raced by a competing CLI writer (exit 0 every time), and a stale
  parked message failing both `pi-text check` and `pi-preflight` (exit 1).
- **Lives in**: `bin/pi-text` (`file_tasks`, `cmd_check`), `bin/pi-agenda` (`cmd_tick`), `bin/pi-preflight` (`text`).

## 2026-11-15 — the text channel receipted nothing, so it looked dead

- **What**: the owner texted a real task and then, 20 minutes later, "Hello?" — and got no reply to
  either. Both messages *had* arrived (13 in `text/inbox.jsonl`, both filed as tasks #42 and #43),
  the poller was healthy, and `pi-text check` was green. The channel was receiving and answering
  nobody: the last outbound message was 33 min older than the last inbound.
- **Cause**: `pi-text tick` filed the task and stopped. The design leaned on "a session will see the
  task and reply", but sessions only exist when the owner is already at the keyboard — which is the
  exact situation the channel is for. Nothing in the system treated "message with no reply" as a
  fault, so nothing could notice it: `pi-text check` looked at polling, parking and filing, never at
  whether the owner had been answered.
- **Guard**: (1) the tick now sends a **receipt per batch** naming the filed task ids, and
  `pi-text inbox`/`watch` receipt too; (2) it answers `status`/`help` from the agenda with no model
  in the loop; (3) it arms a **nudge ladder** — 2 h, 8 h, then 24 h — per message with no session
  reply, so silence itself becomes an outbound message; (4) `send --working` keeps the ladder armed
  for an interim answer, and any normal `send` clears it; (5) `pi-text check` fails on any message
  unanswered for 24 h and is blocking in `pi-preflight`.
- **Proved by**: an end-to-end publish to the topic (`curl -d` → tick → task #44 → receipt with the
  id, then task #44 closed), a fake-transport unit pass over receipt/keyword/batch paths (1 ack per
  3-message batch, `status` answered without a model), and the ladder exercised at 1 h/3 h/10 h/30 h
  — nudge at the step, none before it, widening afterwards.
- **Lives in**: `bin/pi-text` (`ack`, `nudge`, `status_reply`, `cmd_tick`, `cmd_check`, `send --working`).

## 2026-11-15 — two window managers, and windows that existed but never drew

- **What**: while ricing the desktop, `pi-tile` reported three terminal windows `shown` at correct
  rects and `import -window root` / `ffmpeg -x11grab` both returned a screenshot containing **one**
  of them. The two missing ones were real, mapped, `WM_STATE Normal`, and were the owner's open
  terminals.
- **Cause**: a previous session had left `xfwm4 --compositor=off` running next to the real WM. The
  replacement never fully took over: `_NET_SUPPORTING_WM_CHECK` still pointed at the displaced WM,
  which kept managing (and minimising) windows nobody composited. Nothing in the stack checks how
  many WMs own the display; pergola's model is built from `_NET_CLIENT_LIST`, which looked correct.
- **Guard**: `pi-preflight` check `windows` now fails when more than one `xfwm4` is running against
  `:0` (nested `--display :70` test servers are excluded), naming both processes and the fix: a
  single `xfwm4 --replace`. Recovery is that same command; the displaced WM is not a state to
  reconcile, it is a state to replace.
- **Proved by**: the failure itself (2 WMs → shot lost 2 of 3 windows), the fix (one `xfwm4
  --replace` → all three rendered, `pi-shot --expect 3` green), and a unit pass over the check with
  synthetic `pgrep` output: one WM → ok, two on `:0` → fail, one on `:0` + one on `:70` → ok.
- **Lives in**: `bin/pi-preflight` (`wm_singleton`, wired into `windows`).

## 2026-11-15 — the schedule had one copy and two venvs had no pins

- **What**: a percolation audit of the harness (new `bin/pi-percolate`, model in
  `research/percolation.md`) ranked the resources whose single failure removes the largest share of
  capability weight. The top five were, in order, `git`, `pi-term`, `pass`, `venv:laya` (12.4% of the
  machine) and `mem`. Four were restorable — versioned or packaged — and two were not: `venv:laya` and
  `venv:memory` had **no `requirements.txt`/`pyproject.toml` anywhere**, so "reinstall the venv" was
  advice, not a procedure. Worse, the audit's `mitigation` probe on `agenda/agenda.db` found nothing:
  `journal.jsonl` records what *ran* — ticks, obligations, oks — never the obligations themselves
  (cadence, owner, command, `next_due`), the tasks or the goals. The whole schedule existed in one
  untracked SQLite file, and `memory-consolidate`'s rebuild story (write to the journal first) had no
  counterpart in the agenda.
- **Cause**: nothing in the machine ever asked *"could I rebuild this?"* — checks answered "is it
  up?", which is a different question. Venvs were created ad hoc (one by pip, one by uv), and the
  agenda stores state in SQLite because that is the right way to answer "what is due" fast, with no
  requirement that the answer survive the file.
- **Guard**: (1) `memory/requirements.txt` (20 pins) and `laya/requirements.txt` (56 pins, via
  `uv pip freeze`) now exist, so both venvs are `rebuildable` to the probe that found them missing;
  (2) `pi-agenda tick` rewrites `agenda/schedule.json` (obligations, tasks, goals, atomic replace)
  every 10 minutes and `pi-agenda restore [path] [--force]` rebuilds `agenda.db` from it — exercised
  end to end into a throwaway `PI_AGENT_DIR` (16 obligations, 40 tasks, 2 goals, identical roster);
  (3) `pi-preflight` check `graph` fails when the structural collapse point regresses 25% against
  `percolation/baseline.json` or a new unmitigated resource appears above 5% weight, and
  `percolation-audit` is a weekly agenda row.
- **Proved by**: the audit before (`venv:laya`, `venv:memory` → `none`; agenda.db → `none`) and after
  (`rebuildable`, `rebuildable`, `rebuildable`) with `pi-percolate --json`; the restore round-trip
  into `/tmp/agtest`; and the preflight gate passing on the recorded baseline after `accept`.
- **Lives in**: `bin/pi-percolate` (`mitigation`, `check`), `bin/pi-agenda` (`export_schedule`,
  `import_schedule`), `bin/pi-preflight` (`graph`), `skills/percolation/SKILL.md`,
  `research/percolation.md`.

## 2026-11-15 — a background session raced the interactive one and overran its budget

- **What**: the first real use of `pi-text dispatch` opened a headless session for the owner's
  "handle your due obligations" text. It edited `bin/pi-text`, `bin/pi-review` and `selfimprove/`
  while this interactive session held a lease on the same tree and was editing `bin/pi-text`; it
  ran 15 minutes against a contract that said "≤15 minutes", and my own 900 s timeout killed it
  mid-edit. It spent $0.139 and reported nothing, because a killed run has no last message.
- **Cause**: two gaps in the dispatcher, not in the session. (1) Nothing told a dispatched session
  that a *lease* makes a path someone else's work: `pi-claim` existed but the contract never
  mentioned it. (2) The budget was advice in a prompt instead of a rule the session could see
  itself against, so the only thing that stopped it was a kill — the one stop that loses the work.
- **Guard**: the dispatch contract now carries both as hard rules (stop and report the slice; run
  `pi-claim status --check PATH` before touching a path outside the task's project, and file a task
  instead of racing); `pi-text hold ID…` (`text/hold.json`) lets an interactive session mark the
  tasks it owns, and `dispatch` skips them — a held task also changes the failure message from
  "next run tries again" to "held, it will not retry"; the timeout still exists as the floor, and a
  timeout now reports what the run had produced instead of "no output".
- **Measured**: 4 dispatches — #49 10.2 s $0.0026 ok, #50 6.6 s $0.0015 ok, #46 900 s $0.139
  timeout, #52 240 s $0.040 timeout; #55 8.5 s $0.0013 ok. Both failures were broad or question
  tasks, which is what the hold list and the "a question gets an answer, not a refactor" rule
  address.
- **Lives in**: `bin/pi-text` (`CONTRACT`, `hold_list`, `run_one`), `text/hold.json`.

## 2026-11-15 — receipts claimed "no pi session is open" after that stopped being true

- **What**: the owner read the same sentence three times — "No pi session is open, so nothing has
  started yet" — while a session was running for an earlier task, and wrote: "Idk why you keep
  saying no pi session is open. If you receive a task that requires a pi session you should start
  one instead of complaining and not doing the task." They also caught every timestamp I quoted
  being five hours ahead of their clock.
- **Cause**: the receipt sentence was hardcoded in `ack()` at a moment when it was true, and stayed
  hardcoded after the mechanism changed under it. The times came from the ledger's UTC stamps, which
  are correct *for the ledger* and wrong for a human reading a phone.
- **Guard**: the receipt text is now derived from live state at the moment it is sent
  (`open_state()`: lock held → "already running, queued behind it"; hourly ceiling spent → "waits
  for the next slot"; otherwise → spawn the dispatch and say "I am opening a pi session for it
  now"), and every human-facing time goes through `local_clock()` (local time + zone), while the
  stored ledger stays UTC. The poller spawns the session itself rather than deferring to a row.
- **Proved by**: the receipt for task #55 read "Received at 13:18 EST … A pi session is already
  running for an earlier task; this one is queued behind it" while #52's dispatch held the lock, and
  the dispatch for #55 then answered in 8.5 s.
- **Lives in**: `bin/pi-text` (`open_state`, `spawn_dispatch`, `local_clock`, `ack`).

## 2026-11-15 — the WM guard fired on healthy displays, and a pkill hit a sibling session

- **What**: two follow-on failures from the new `windows` guard. (1) It reported "3 window managers
  on :0" on a desktop with exactly one: two of the processes were test managers on `:78`/`:79` whose
  command lines simply had no `--display`. (2) Cleaning up the leaked test sandbox with
  `pkill -f manual-sandbox3.sh` killed *my own shell* (the pattern matched its command line, exit
  143) and a pattern-kill of `xterm -T pergola-e2e-*`/`Xvfb :79` tore down generations of a sandbox
  that a *parallel interactive session* was actively using — its test run, not mine to reap.
- **Cause**: (1) process-to-display was inferred from the absence of a flag instead of read from the
  process; (2) "these processes look like the ones I created" is not ownership, and `pkill -f`
  matches the killer's own command line.
- **Guard**: `pi-preflight` `windows` now resolves each process's display — explicit `--display`
  first, otherwise the `DISPLAY` in `/proc/<pid>/environ` — and only counts managers on the target
  display (`PI_WM_DISPLAY`, else `$DISPLAY`, else `:0`); unit-checked against the real four-process
  set (`:70` explicit, `:0`, `:78`, `:79` → exactly one on `:0`). The cleanup rule is written down
  here: kill by pid after checking the parent chain (`ps -o ppid=`), never by pattern, and a sandbox
  whose parent is a live session belongs to that session.
- **Lives in**: `bin/pi-preflight` (`process_display`, `wms_on_display`, `wm_singleton`).

## 2026-11-15 — `pi-term --exec` failed inside the terminal, not in pi-term

- **What**: `pi-term --exec "~/.pi/agent/bin/rice-showcase"` opened a window whose only content was
  xfce4-terminal's `Failed to execute child` dialog. The argv was `shlex.split` and handed to the
  terminal, and no shell had expanded `~` — so the error appeared where nothing records it.
- **Cause**: expansion was assumed to happen in the terminal, and an unlaunchable command was passed
  on instead of refused.
- **Guard**: `--exec` now expands `~`/`$VARS` per argv token and refuses a first token that is not an
  executable (`pi-term: --exec: not an executable: …`, exit 2) before any window is opened.
  Measured: `pi-term --tmux --exec '~/…/pi-agenda show'` records the expanded path in the registry;
  `--exec "~/no-such"` and `--exec "definitely-not-a-cmd"` both exit 2 with that message.
- **Lives in**: `bin/pi-term` (`cmd_open`).

## 2026-11-15 — a killed session kept its lease, and the tree read as "busy" for an hour

- **What**: after the dispatch for text task #46 was killed at its 900 s timeout, `pi-claim check` in
  `~/Projects/pergola` still answered `busy` for that dead session (heartbeat 28 min old, pid gone,
  log silent 21 min) — because a lease with a dead pid stayed live until the session log was silent
  for `IDLE_MIN` (60 min). This session's pergola work started from a stale `BLOCKED`.
- **Cause**: `lease_live()` used one silence threshold for both cases. A live pid heartbeats; a dead
  pid cannot be writing a log at all, so 60 min of grace was waiting for a process that had exited.
- **Guard**: a dead pid now needs `DEAD_GRACE_MIN` (5 min, `PI_CLAIM_DEAD_GRACE`) of log silence to
  count as gone, while a live pid is unchanged. Measured: the dead lease was reaped on the next
  `pi-claim check` (free), and `pi-claim selftest` still passes all 21 checks.
- **Lives in**: `bin/pi-claim` (`lease_live`, `DEAD_GRACE_MIN`).

## 2026-11-15 — the weekly e2e obligation failed on a desktop two sessions were sharing

- **What**: `pergola-health --e2e` exited 1 at 09:00 with "geometry drift on 1 panel" and "cpu >10%",
  which struck the `pergola-e2e` row and filed task #14. The suite itself passed 43/43 at 13:00 on
  the same commit, and the 09:00 drift was another session dragging windows on the live display.
- **Cause**: one exit code answered two different questions — "does the code work" (the sandboxed
  e2e suite) and "is the live desktop tidy right now" (drift/CPU/tiles/orphans), and the second is
  not the suite's to answer on a shared desktop.
- **Guard**: with `--e2e`, the live-only observations are recorded as `warnings` in
  `health.jsonl` and the JSON, and no longer fail the run; the 12-hour soak (no `--e2e`) keeps the
  strict verdict it exists for. Measured: `--e2e --quiet` rc=0, log line
  `{"ok":true,…,"warnings":[],"e2e":1}`.
- **Lives in**: `scripts/health.sh` (`live_fail`, `WARNINGS`), installed as `~/.local/bin/pergola-health`.

## 2026-11-15 — dispatched text sessions were killed by the tick that spawned them

- **What**: text task #59 was filed at 20:40:35Z and first ran at 21:17:06Z — a 36-minute gap in
  which the dispatch children spawned at 20:40 and 21:00 produced no ledger row and no answer. A
  later `text/running.json` held `{"task": 66, "pid": 444361, …}` with the pid already dead and no
  outbox entry for that attempt. `pi-text dispatch --detach` returned 0 and "spawned" every time,
  so the channel reported success while the child was gone.
- **Cause**: `pi-agenda.service` is `Type=oneshot` with no `KillMode`, so it defaults to
  `KillMode=control-group`. The detached dispatch child uses `start_new_session=True`, which changes
  the session but *not* the cgroup — so when the tick's `ExecStart` exited, systemd SIGTERM'd the
  whole cgroup and killed the child mid-session. Measured with a transient unit: a child that
  writes a marker 8 s after the unit exits dies under `control-group` and survives under `process`.
- **Guard**: a drop-in `~/.config/systemd/user/pi-agenda.service.d/killmode.conf` sets
  `KillMode=process`, so only the tick's own process is signalled and a dispatched session finishes.
  `pi-text check` now queries `systemctl --user show pi-agenda.service -p KillMode` and fails with
  "a detached dispatch child will be killed when the tick exits" when it is not `process`. Measured:
  removing the drop-in makes `pi-text check` exit 1 with that line; restoring it exits 0.
- **Lives in**: `~/.config/systemd/user/pi-agenda.service.d/killmode.conf` (`KillMode=process`),
  `bin/pi-text` (`cmd_check`).

## 2026-11-15 — the agenda made its own rows late by design, and had no consumer for `session:` rows

- **What**: `frantic-queue` (6 h cadence) was **88 min overdue** when the owner asked why nothing had
  been done. `agenda/DUE.md` had listed it for 88 min; no session had touched it. The journal showed
  the same shape everywhere: `text-inbox` median gap **19 min against a 10 min cadence**,
  `session-watch` 20 vs 15, `due-dispatch` 39 vs 30.
- **Cause** (three, each measured):
  1. **Drift.** Every run recorded `next_due = now + cadence`, so the effective period was cadence +
     lateness, permanently: 10 min → 19 min, 6 h → 7.5 h. Lateness was baked in and never recovered.
  2. **Starvation.** Eight enabled `session:` rows need **5.3 sessions/day** (Σ 86400/every_s) and the
     consumer's cap was **3/day**. In 24 h `due-dispatch` opened **0** sessions (0 `route: due`
     ledger rows) across 14 runs — every one a silent no-op.
  3. **Grace.** Eligibility was max(30 min, min(6 h, cadence/4)) = **90 min** for the 6 h row, so the
     consumer could not act until a row was 25 % of its cadence late. The owner caught it at 88 min,
     two minutes before the consumer would have fired.
  4. **Silence.** The phone nudge required > 2 h lateness and the desktop notification 6 h, so 0–2 h
     late produced no signal at all.
- **Guard**: (a) grid-anchored advancement — `next_slot()` in the tick, `run` and `touch`, so a late
  run earns a shorter gap and never a later schedule; (b) grace fixed at 300 s (`PI_TEXT_DUE_GRACE`),
  so due is a deadline; (c) the daily budget is derived from the schedule
  (`due_budget` = max(6, ⌈1.5 × demand⌉)) and `pi-text check` fails when the budget is below demand,
  when `due-dispatch` has not run for three cycles, or when a `session:` row is >2 h late with zero
  dispatch attempts in 24 h — `pi-text check` is a blocking `pi-preflight` check; (d) the alert
  threshold is one dispatch cycle (30 min), and a priority-1 task due within 24 h now phones too
  (a failure task gets `due = now + 1 day`, so an auto-filed p1 rings instead of sitting in a file); (e) **holds**: `pi-agenda next` records every due
  `session:` row it prints in `agenda/hold.json` (holder pid, 4 h TTL, refreshed by each `next`,
  released by `touch`/`done`/`drop`), and the consumer skips a held row — cycle 33 measured two
  sessions on one task list, one holding a lease the other ignored.
- **Second cause, found by measuring it** (same evening): `pi-cadence` showed `text-inbox` still at
  1.96× and `due-dispatch` at 3.0× *after* the drift fix. The 10-min tick and the 10-min cadence beat
  against each other: a tick firing 11 s early (22:00:14 for a 22:00:25 slot) skipped it entirely and
  the gap became 20 min. Guard: `DUE_SLACK = 60` in `due_obligations` — a due time inside the tick's
  jitter is due; grid anchoring keeps it from double-running. Measured in a sandbox: a row due
  `now+30 s` is listed by `pi-agenda due`.
- **Measured**: budget 8/day vs 5.3/day demand (printed by `pi-text check`); the guard fires on a
  synthetic 4 h-late row — `agenda: frantic-queue is 4.0 h late with no dispatch attempt in 24 h —
  the consumer is not working it`; `next_slot`: 6 h row worked 90 min late → next in 4.5 h (was
  6 h), 10 min row worked 9 min late → next in 1 min (grid recovered, no drift).
- **Lives in**: `bin/pi-agenda` (`next_slot`, `DUE_ALERT_LATE`, `due --json`
  `session_demand_per_day`), `bin/pi-text` (`DUE_GRACE_S`, `due_budget`, `cmd_check` agenda rules),
  `skills/agenda/SKILL.md` § Timeliness.

## 2026-11-15 — session-watch kept texting every 15 min *after* the "fix", twice

- **What**: at 18:41 the owner asked for fewer updates; `bin/pi-session-watch` was changed to text
  on "a changed label **or real work in the window**". At 21:30 the owner repeated, more bluntly,
  that the process was already finished and 15-minute updates were noise (the sentence itself is
  omitted: owner texts are not publishable material — `pi-preflight chat-private`). Outbox: `[PROGRESS] pi 273962` at 02:29:29Z and `02:30:12Z` — two texts a
  minute apart about a session doing 49 calls, plus `[IDLE] ... at the prompt 3h26m` every 20 min
  before that.
- **Cause** (two, measured): (1) "work in the window" is true on almost every tick for a working
  session, so it bypassed the label test and produced a heartbeat — the opposite of the recorded
  rule (memory #185: *one text per state change, silence when nothing moved*). (2) **a manual run is
  a text**: I ran the watcher by hand twice to inspect it, and it texted the owner both times; the
  script cannot tell a diagnostic run from the 15-min obligation.
- **Guard**: the send condition is now `label changed, or a commit, or a new error` — tool calls and
  edits are never news. Verified on the live target: one line on the state change, then
  `(silent) [QUIET] ...` on three consecutive runs with 0 new calls. Rule added: inspect the watcher
  only with `--dry-run`; a bare run sends.
- **Lives in**: `bin/pi-session-watch` (main send condition), `INCIDENTS.md` + memory (the rule).

## 2026-11-16 — the due consumer was never invoked: `--due` was thrown away by `--detach`

- **What**: the owner, twice: "Frantic queue is always behind and overdue, that is an issue you need
  to address". Measured 06:30 local: `frantic-queue` (6 h) **4.5 h late**, `pi-agenda next` exit 2,
  and `text/dispatch.jsonl` had **0 `route: due` rows in its whole history** — the consumer had never
  opened a single session for a `session:` row, including the 14 runs logged on 2026-11-15.
- **Cause** (measured): `cmd_dispatch()` handled `args.detach` *before* `if args.due`, and that branch
  respawns `pi-text dispatch --max N --timeout T` — without `--due`. The agenda row is
  `exec:… pi-text dispatch --due --detach --quiet`, so every tick at 30 min spawned a **text-task**
  dispatcher, which correctly exited 3 (no text waiting) and logged `exit 0` in the agenda journal.
  The due branch was unreachable from the only caller that uses it. Reproduced by patching
  `Popen` and reading the argv of the spawn: before `dispatch --max 1 --timeout 900 --quiet`
  (no `--due`), after `dispatch --due --max 3 --timeout 900 --quiet`.
- **Second cause** (found while verifying, same run): the due child then lost the slot to the
  dispatch lock — `dispatch_running() == True` because a text session held it, `acquire_dispatch_lock()`
  returned None, and the function returned 0 **silently** (quiet). Measured: `route: due-busy` at
  11:35:21Z, "lock held 180 s; 1 row(s) still wait", while the text dispatcher (pid 544356) held the
  lock across a whole 900 s session. One chance per 30 min against a 15 min lock is starvation.
- **Guard**: (a) order in `cmd_dispatch()` is now recursion-guard → `--due` → `--detach`, so the due
  path owns its own spawn and keeps `--due`; (b) the due consumer takes **its own lock**
  (`text/due.lock`, `acquire_dispatch_lock(wait=30, path=DUE_LOCK)`) instead of the dispatcher lock,
  so a text session can no longer block the agenda — two sessions at once is normal here and
  MAX_PER_HOUR still bounds spawn rate, while two *due* passes never overlap; a lost slot writes a
  `route: due-busy` ledger row, so it is observable rather than silent.
- **Measured**: argv test — `dispatch --due --detach` spawned `dispatch --due --max 3 --timeout 900
  --quiet` (was `dispatch --max 1 --timeout 900 --quiet`); end-to-end at 11:43:51Z a real
  `route: due` row: `ref frantic-queue, rc 0, 57.6 s, 25 turns, $0.009`, the row touched at 11:43:38Z,
  and `pi-text check` went from exit 1 ("no dispatch attempt in 24 h") to exit 0 ("agenda 5.4 session
  rows/day within a 9/day budget").
- **Lives in**: `bin/pi-text` (`cmd_dispatch` branch order, `DUE_LOCK` +
  `acquire_dispatch_lock(wait, path)`, `cmd_dispatch_due` lock branch), this file,
  `skills/agenda/SKILL.md` § Timeliness.

## INC-7 — an idle `exec:` row was recorded as a failure (2026-11-16)

- **What happened**: `pi-agenda next` listed 13 priority-1 tasks titled `due-dispatch failed: exit 3`
  and `due-dispatch` carried 5 strikes, while `due-dispatch` was working exactly as designed.
- **Cause**: `pi-text` uses exit 3 as its "nothing to do" answer (`inbox`, `watch`, `dispatch`,
  `dispatch --due` all return it), and `pi-agenda`'s exec runner scored any non-zero exit as a
  failure: every 10-min tick with nothing overdue filed a p1 task and a strike.
- **Guard**: `bin/pi-agenda` now has one shared runner, `run_exec()`, and `IDLE_EXIT = 3`: exit 3
  records `last_ok=1`, `strikes=0` and a journal detail `idle (exit 3): …`. Both callers (`tick
  --run` and `run <id>`) use it, so a second copy cannot drift. Nothing else in the exec set uses 3
  (`pi-cadence` 1/2, `pi-burn` 0/1, `pi-term` 0/1, `pergola-health` 0/1).
- **Measured**: `run_exec` unit cases exit 0 → ok, exit 3 → ok/idle, exit 1 → fail, timeout → fail;
  end-to-end a throwaway `exec:sh -c "exit 3"` row recorded `last_ok=1 strikes=0` and filed no task
  (before: a p1 task per run); the 13 bogus tasks were dropped and `due-dispatch` strikes reset to 0,
  then `pi-agenda run due-dispatch` recorded `ok` and `pi-agenda next` shows no due-dispatch strike.
- **Lives in**: `bin/pi-agenda` (`IDLE_EXIT`, `run_exec`, `cmd_tick`/`_run_one`), this file.

## 2026-11-16 — every turn on a local model died with "exceeds the available context size"

- **What happened**: a session was routed to `local/Llama-3.2-3B-Instruct-Q4_K_M` (then
  `local/qwen2.5-1.5b-instruct-q4_k_m`) and each turn failed instantly with
  `400 request (14552 tokens) exceeds the available context size (8192 tokens)`; the prompt could
  not be reduced by talking differently, so the session was unusable.
- **Cause**: two numbers disagreed and neither was checked. `models.json` declared
  `contextWindow: 16384` for all four local models, while `llama-router.service` served
  `-c 8192`, so Pi emitted requests the server could never accept (measured full-harness prompt:
  **12,924 tokens**; a minimal invocation is **363**). One layer up, `settings.json` had the stock
  `compaction.reserveTokens: 16384` with no local override, and auto-compaction fires at
  `context > window - reserve` = **0** on a 16384 window — so even with ctx fixed the session would
  have compacted on every turn, and each compaction is another 12.9k CPU prefill.
- **Guard**: `bin/pi-local-ctx` compares declared vs served ctx and served ctx vs the recorded
  harness-prompt size **and** the compaction reserve in force for each local model; it sends no
  completion, so it cannot hang on a 30-minute prefill. `bin/pi-preflight` runs it on every check and
  prints `ok   local ctx` / `warn local ctx`. Both failure paths were exercised by kill test:
  `--served 8192` → FAIL on declared≠served and ctx<prompt; dropping the local compaction overrides
  → FAIL with "compaction reserve 16384 leaves 0 ctx". Measurement is stored in
  `local/harness-prompt.json` and `--measure` refreshes it.
- **Measured after the fix**: router `-c 16384 -ctk q8_0 -ctv q8_0 --models-max 1`; children report
  `n_ctx_slot = 16384`; 3B RSS 2.53 GB (fits the 3.4 G cgroup; f16 KV would have been 1.7 GB of it),
  1.5B 1.44 GB. The full harness then **ran end to end**: 12,931 input tokens on the 1.5B, `rc=0`,
  reply `ready`, **wall 2,318 s (38.6 min, ~1,800 s prefill)** with three other pi sessions competing
  for the two cores. Prefill degrades with depth (12.8 tok/s at 2k → 6.7 at 10.2k). So the honest
  answer is "it works, and the first turn is ~40 minutes": bulk work belongs in `local-gen` /
  `local-batch` / `selfimprove/run.py`, which issue 363-token prompts and finish in seconds.
- **Also reaped**: an orphaned `llama-server` on port 5601 (ppid 1, `-c 2048`) had held 1.21 GB for
  an hour, and the router was keeping **two** children resident (2.72 GB) on a box that gives the
  desktop ~5 GB — hence `--models-max 1`.
- **Lives in**: `bin/pi-local-ctx`, `bin/pi-preflight` (local ctx line), `models.json`,
  `~/.config/systemd/user/llama-router.service` + `.d/memory.conf`, `settings.json`
  (`compaction.modelOverrides` for `local/*`), `local/harness-prompt.json`, `skills/local-models`.

## 2026-11-16 — a text message could run shell as `host` before pi started

- **What**: the resume path (`pi-text` FOLLOWUP → `write_resume_script`) built a `/bin/sh` script
  by embedding the inbound message with `json.dumps(prompt)` inside double quotes. JSON escaping is
  not shell escaping. A message containing `$(cmd)` or a backtick executed as this user — before
  the model saw the prompt, with no confirmation and no tool policy. The transport is
  `ntfy.sh/<topic>`, where the topic name is the only secret; anyone who learns it can publish.
- **Cause**: one function conflated two encodings, and nothing exercised it with hostile input. A
  second, smaller hole sat beside it: `text/pending/{id}.json` used the transport's message id as a
  filename unchecked (`../x`, `None`).
- **Guard**: the prompt is written to a 0600 file and the script reads it with
  `-p "$(cat <file>)"`; the session id and path go through `shlex.quote`; `safe_id()` strips a
  message id to `[A-Za-z0-9_-]{1,64}`; inbound text is capped at 20 000 chars. `pi-text check`
  now **re-proves it on every run**: it builds a script with a `$(touch …)` / backtick / `";`-break
  payload, runs it against `PI_BIN=/bin/echo`, and fails if the marker file appears.
- **Measured**: the old construction (kept verbatim in the repro) created `PWNED_OLD` on this host;
  the new one passed the payload as one literal argv and created nothing. `pi-text check` exits 1
  on a copy patched back to the old `json.dumps` form and exits 0 on the fixed file.
- **Not fixed here**: the channel still authenticates a sender by topic secrecy alone, so a text
  can still *ask* the agent to do something (that is the feature). The design fix — an ntfy access
  token for publish, or a shared secret in the message — needs the owner's phone client, so it is
  filed as a task, not silently changed.
- **Lives in**: `bin/pi-text` (`write_resume_script`, `safe_id`, `MAX_INBOUND_CHARS`, `cmd_check`),
  this file.

## 2026-11-16 — the agenda's cadence verdict was arithmetic, and `n/a` hid a dead row

- **What**: `pi-cadence` reported `WORST text-dispatch 1.30x (19.5m vs 15.0m)` and exited 1 for
  hours, filing a p1 task, while the row was working. In the same report `local-reap` (2 h cadence)
  had run **once in 25 h** and printed `n/a` with exit 0.
- **Cause**: two errors of method. (1) The ratio was `median gap / cadence`. A 15-min row on the
  10-min tick can only land on every second tick, so its gaps are bimodal 10/20 min and the median
  is 20 by construction — the *rate* was 15.9 min (1.06x). (2) A row with too few gaps and a row
  that has stopped running both printed `n/a`, which on screen is the same as healthy.
- **Guard**: the fail test is the **mean** gap (the rate) with median and p90 printed beside it;
  `DEAD` = nothing recorded within 3x the cadence (evidence is the latest of `last_run`, the
  journal, and the obligation's new `created` column); a gross lateness now fails at any `n >= 1`
  instead of hiding behind `min_n`; duplicate timestamps are collapsed (they produced 0-second gaps
  that halved the mean); a row whose `every_s` is missing falls back to its `cadence` string and
  otherwise reports `BADCFG`; a disabled row no longer prints `overdue`. Self-test grew from 2 to 6
  cases including a bimodal 15-min row, a 2-h row silent for 25 h, and a disabled overdue row.
- **Measured**: `text-dispatch` 1.30x FAIL → 1.06x PASS; the new metric surfaced two rows the
  median hid — `due-dispatch` 12.6m vs 10m (13 skipped slots, most before 02:50Z) and
  `window-reap` 7.4h vs 6h (1 of 4 slots). `--self-test` 6/6.
- **Lives in**: `bin/pi-cadence` (`cadence_seconds`, `gaps`, `verdict_for`, `self_test`),
  `bin/pi-agenda` (`created` column + migration), this file.

## 2026-11-16 — the brief's fixed shares dropped 4 of 7 pinned rules

- **What**: `mem brief` allocated CORE 30% / KEY 34% / RECENT 22% / PDSA 14% and silently skipped
  rows that did not fit. At the live 900-token budget it printed 3 of 7 pinned rules and 3 of 10
  key lessons, while RECENT showed all 8 — the cheapest, most disposable section lost nothing.
  A superseded pin still appeared, because the CORE query was the one query without a
  `valid_to`/`superseded_by` filter.
- **Cause**: a fixed share per section is not a priority order. The cap was never the constraint
  (pinned + KEY + RECENT ≈ 1105 tokens against 830 usable) — the split was.
- **Guard**: pinned takes its real cost first (up to `CORE_SHARE = 0.80`), the rest splits what is
  left; every section prints `kept/total` and prints its header even when nothing fits; if the
  pinned set does not fit, optional sections are withheld with a one-line reason instead of being
  shown while a rule is missing; CORE/KEY/RECENT all filter superseded rows and `digest` kinds; the
  footer reports the measured `used` instead of `used + 40` (which printed `~54/0` at `--budget 0`).
  A budget below 120 now says so in one line instead of printing headers.
- **Measured**: at 900 → CORE 7/7 (was 3/7), KEY 2/10, RECENT 3/8; at the new 1100 default →
  CORE 7/7, KEY 4/10, RECENT 6/8, STATS 1051/1100. `--budget 0/100` → one honest line.
- **Lives in**: `bin/mem.py` (`cmd_brief`, `CORE_SHARE`), this file.

## 2026-11-16 — `pi-percolate accept --help` recorded a baseline, and the gate flapped on rank

- **What**: the fragility gate failed on "new single point(s) of failure" for two different
  resources on runs minutes apart, and `accept --help` did not print usage — it recorded a new
  baseline. The baseline then stored only the top 3 names.
- **Cause**: three mistakes in one gate: `accept` parsed no arguments; the gate compared top-3
  *names*, where ranks 3 and 4 sat 0.122 vs 0.119 apart, so a tie shuffle read as a regression; and
  `harden` was truncated to 8 rows, so a genuinely new hub at rank 9 could never fail anything.
- **Guard**: `accept` requires `--reason` (≥12 chars, `--help` prints usage and writes nothing),
  stores the **full** blast-radius table (`resource → weight`) plus the reason and an atomic write;
  `check` compares weights for known resources (`WORSENED = 0.02`) and full-table membership for
  new ones (`NEW_HUB = 0.05`); an unreadable baseline fails with a message instead of a traceback.
- **Measured**: a new resource at 0.06 fails (`new hub`), 0.049 passes, a 0.3-point rank shuffle
  passes, a truncated baseline fails cleanly, `accept --help` exits 2 and leaves the file untouched.
- **Lives in**: `bin/pi-percolate` (`WORSENED`, `NEW_HUB`, `accept`, `check`), `percolation/baseline.json`
  (reason field), this file.

## 2026-11-16 — 62% of the bill sat above a context ceiling that was never in force

- **What**: `pi-burn --drivers 7` put 62% of a $14/day burn in the `>250k` replayed-context band.
  `settings.json` declared a 248,576-token compaction ceiling for the default model, so the band
  was supposed to be impossible. The logged compactions fired at 676k–1.1M `tokensBefore`.
- **Cause**: the ceiling is a setting and the bill is a log, and nothing compared them. Hand-checking
  also found the first version of the check looked up `modelOverrides["deepseek/x"]` while
  settings.json keys them `openrouter/deepseek/x`, so it reported a 1,032,192 ceiling that no
  session could reach — a guard that could not fail.
- **Guard**: `bin/pi-burn --cap` resolves the override (exact key, then a suffix match) against
  `models-store.json`'s window, prints the effective ceiling and the calls/dollars above it, and
  **fails** when a compaction after `settings.json`'s mtime fired above 1.1× the ceiling; it says
  `unverified` (exit 0) until such a compaction is observed. It runs before the API-key check, so
  it is offline and writes no spend sample, and `pi-preflight` runs it as `cost cap`.
- **Measured**: `--cap 3` on 104 sessions → ceiling 248,576, 4,631 calls and $20.61 of replayed
  context above it, 8 compactions all before the setting, `guard unverified`. Fault cases: reserve 0
  → fail "no usable ceiling"; reserve > window → fail; truncated settings → fail with a message;
  a compaction in a fabricated session above the ceiling → exit 1 (and exit 0 under
  `TZ=America/New_York` only after the UTC epoch fix — `mktime(...) - timezone` shifted it an hour).
- **Lives in**: `bin/pi-burn` (`--cap`), `bin/pi-preflight` (`cost_cap`), this file.

## 2026-11-16 — the audit shipped an evidence pack with 24 defects, found by two testers in an hour

**What happened.** `skills/audit/scripts/window.py` (new) was written and self-tested in one pass,
then scanned the real tree successfully. A two-tester panel with disjoint lenses (boundaries+oracle;
faults+hostile-input) found 24 defects in it: a truncated ledger line made the whole ledger look
empty and the next `--record` appended onto the same broken line; `parse_when` read `2026`, `NaN`
and `inf` as epochs and traced back inside `money_section`; a failed `pi-cadence`/`pi-burn`/
`pi-delegate` read as a *real* finding (or as "every agent never dispatched"); `pi-preflight`
timing out produced a green-looking pack; uncaught crashes exited **1**, the same code as "suspects
found"; `score` never fired its REPEAT rule because it only compared *closed* pairs; a corrupt
`lenses.json` was silently overwritten with `{retire, double}`, deleting the roster.

**Cause.** Same shape as the audit's own five findings: the pack reported verdicts it could not
support — silence read as health, a tool failure read as a measurement, and an exit code that made
a crash indistinguishable from a discovery.

**Guard.** Every class is a case in `window.py selftest` (27 cases, 0.1 s, no network), run by
`pi-preflight` as **`audit pack`** on every publish, and mutation-checked: reintroducing the
closed-pairs REPEAT bug turns `score-repeat-on-second-unclosed-scan` red (verified on a /tmp copy).
Exit codes are now contractual: 0 clean, 1 suspects, 2 "could not produce an honest answer", with
`main()` converting an unexpected exception into 2 so a crash can never be read as a finding.
`append_ledger` never writes on top of a truncated tail; `read_ledger` counts bad lines instead of
erasing; a corrupt lens roster is refused rather than replaced; every instrument failure raises
`instrument:<name>-unreadable` instead of an empty section.

**Lives in**: `skills/audit/scripts/window.py` (`selftest`, `read_ledger`, `append_ledger`,
`parse_when`, `main`'s 0/1/2 exit contract), `bin/pi-preflight` (`audit_pack`, check name
`audit pack`), `skills/audit/SKILL.md` (the mutation rule), `skills/audit/lenses.json`.

**Lesson.** A self-test written by the same pass that wrote the code tests the author's assumptions.
A panel with a hostile lens found 24 defects in 10 minutes of wall-clock — and the *verifier* then
found one of the 27 selftest cases was theatre. Both are cheaper than the first wrong audit.

## 2026-11-17 — a 6-hourly session row re-opened for four days of unchanged work

**What happened.** The `frantic-queue` agenda row (6 h, p1, `session`) opened a full agent session to
triage the Frantic board. Three sessions in a row reported the same thing — 4 claimable bounties, all
`description=null`/`required_artifacts=[]`, wallet 0 USDC — and each closed the row; the row then went
overdue again (22 min at the last attempt) and the dispatcher re-opened it, until sessions started
refusing the row and the owner was asked to decide. Meanwhile `pi-frantic watch` re-queued #97 on
every poll: it is a `p-` *house rebate*, delivered by funding a posting, not by claiming one, so the
queue never emptied and every triage part-read dead work.

**Cause.** Two things the row could not see: (a) an agenda row whose work is *reading a feed* was
written as a session, so each poll paid ~$0.25 and 240 s for a report that a HTTP call answers; (b)
the "claimable" filter tested `work_status` and free slots but not *kind*, so a rebate posting looked
like work. A cadence that cannot make progress also has no way to say so — it just repeats.

**Guard.** `frantic-queue` is disabled; `frantic-watch` (6 h, `exec:pi-frantic watch --quiet`) polls
for free and queues only new claimable work, and `frantic-triage` (7 d, `session`) carries a written
claim rule in its notes — price ≥ 5× session cost, the contract or description names the acceptance
checks, delivery fits the 1 h claim window — so the honest "no claim" is a *conclusion* the row can
reach once a week instead of a session it rediscovers four times a day. `bin/pi-frantic watch` now
excludes `/v1/bounties/p-` posting ids from the queue and prunes them (verified: queue went from two
entries to one, #147, on the first run). PDSA cycle 40 holds the falsifier: if two weekly triages find
no claimable work, the row drops to monthly and earning effort moves to venue discovery (#99).

**Lives in**: `bin/pi-frantic` (`watch`'s two jq filters), agenda rows `frantic-watch`/`frantic-triage`,
`self-funding/FRANTIC.md` ("Decision 2026-11-17"), memory #256, `mem pdsa` cycle 40.

**Lesson.** If a scheduled row's job is to *check* something, make it an `exec` check and let only a
state change open a session. A session is a procurement of judgement; polling for it is how a feed
reader becomes four daily tokens sinks and a p1 strike.

## 2026-11-17 — a decision recorded four times, with nothing that would ever read it again

**What happened.** The earning-rail restructure (disable `frantic-queue`, add `frantic-watch`,
write a claim rule) was recorded in `self-funding/FRANTIC.md`, `INCIDENTS.md`, memory #256 and
`mem pdsa` cycle 40 — four copies, no canonical one. The falsifier ("two weekly triages with no
claim → drop to monthly") had a condition but no mechanism: nothing would read it, and the claim
rule itself is prose in an agenda row's notes, so a future session can ignore it without any check
failing. The cost figure that motivated the decision (~$0.25, 240 s per report) was an estimate
never measured from the logs.

**Cause.** The decision was handled as an *event* (measure, choose, write it down) rather than as a
*record with a lifecycle*. Nothing in the harness could answer "which decisions are open, and which
are past the date they were supposed to be re-measured?" — so the honest answer was "unknown", and
an unknown is how a decision quietly becomes folklore.

**Guard.** `DECISIONS.md` (protocol D1–D8, one canonical record per decision, others link) and
`bin/pi-decide`: `new` refuses a missing field, a non-date review, a guard that names no existing
path or command, and a falsifier with no date; `due` exits 1 on an open record past `review-by` and
runs as the `decisions` check in `pi-preflight`, so an un-re-measured decision blocks publish.
`skills/decide/SKILL.md` is the routing surface. Verified: selftest 9/9, both refusals exit 2,
`pi-preflight` reports `ok decisions: 1 open, none overdue`.

**Lives in**: `DECISIONS.md`, `bin/pi-decide`, `bin/pi-preflight` (`decisions`), `skills/decide/`,
memory #259, `mem pdsa` cycle 41.

**Lesson.** A decision is not finished when it is made; it is finished when the thing that would
prove it wrong has been measured. If the record cannot name a guard that runs and a date it will be
read, it is a wish with a timestamp.

## 2026-11-17 — the harness babysat its own jobs, and every session re-derived the same command

**What happened.** Measured over the session logs: 1,009 of 13,303 bash tool calls (7.6 %) contained
a `sleep`; 352 were `while ! …; do sleep …; done` watch loops, 45 were literally `sleep N; <check>`,
and the declared sleeps totalled ~84.8 h of requested wall clock. Separately, 49 of the 52 scripts in
`bin/` had no test and no selftest, so a procedure was re-improvised each session with different
flags and nothing compared two runs of the same intent.

**Cause.** Two habits with the same root: waiting was expressed as a *duration* rather than as an
*event*, and a procedure was treated as a *performance* rather than as an *artifact*. The kernel
already reports process exit (pidfd), file close/rename (inotify) and a unit's MainPID exit; the
subprocess and systemd primitives this tree already used (`subprocess.run(timeout=)`,
`systemd-run --wait`) were never the problem — the session's own loop was.

**Guard.** `bin/pi-wait` blocks on the event (pidfd poll, inotify with a `--stable` coalescer,
append-stream regex, MainPID, connect-backoff) and prints the event plus elapsed time, so a wait is
observable. `bin/pi-tool check` runs every pin twice and diffs the output, `pi-tool lint` fails a
`sleep` inside a loop or a `sleep N; <cmd>` (with a deliberate, greppable `pi-tool: allow <reason>`
opt-out), and `pi-tool new` scaffolds a tool with its contract and golden test. Both run as the
`tools` check in `pi-preflight`, so an unpinned tool or a new polling loop blocks publish. Verified:
`pi-wait --selftest` 10/10 (0.0 ms CPU per second waited); injecting
`while ! test -f /tmp/x; do sleep 5; done` into `bin/` makes `pi-tool lint` exit 1 and `pi-preflight`
report `FAIL tools`; the first `pi-tool check` found three real defects in existing selftests
(`pi-claim` printed a temp path, `pi-preflight` had no `--selftest` and the loose match ran live
checks, `pi-wait` printed elapsed times) — all normalised, none adjudicated by a model.

Blocking was only half the fix: a session that blocks is still occupied. `bin/pi-done` closes the
loop from the other side — `run` starts a detached transient user unit and returns in ~51 ms, and
systemd itself fires `pi-done-notify@<id>` through `OnSuccess=`/`OnFailure=` when the job ends, so
the completion *arrives* (`events/done.jsonl`, desktop, optionally a text and an agenda task)
instead of being asked for. Measured traps that shaped it: `%n` does not expand inside a transient
property (the notifier must be addressed by job id), the notifier inherits the *manager's*
environment rather than the caller's (so `PI_AGENT_DIR` cannot be passed through it), and `--collect`
unloads the unit at exit (so the job records its own rc before it dies, and the notifier reads that,
never `systemctl show`). Verified end to end: a 6 s job returned immediately and its ledger row
appeared 6.0 s later with no process watching it.

**Lives in**: `bin/pi-wait`, `bin/pi-done` (+ `~/.config/systemd/user/pi-done-notify@.service`),
`bin/pi-tool`, `tests/`, `bin/pi-preflight` (`tools`), agenda row `job-done`, `AGENTS.md`
(Engineering defaults), `research/event-driven-waits.md`,
`research/llm-to-deterministic-tools.md`, memory #270/#271/#273.

**Lesson.** Waiting is a question about *state*, so it should be answered by whoever changes the
state, not by asking again on a timer. And a procedure with no test is not owned by anyone: the
next session will write a slightly different one, and nothing will notice.

## 2026-11-17 — the text channel refused the owner at a cap that guarded nothing

**What happened.** Five messages in 40 minutes produced three identical texts that each read
"Not started yet: the hourly cap (6 background sessions) is spent; yours starts at the next slot" —
no waiting count, no time, indistinguishable from a stuck queue. The owner's reply: *"there doesn't
need to be an hourly cap that's really annoying and unnecessary (isn't it?)"*. Two more messages got
"a session is already running; yours is queued behind it". Meanwhile `due-busy` (a lock that was
held, so nothing ran) and `due-escalated` (a stop-trying marker) were counted against the same
MAX_PER_HOUR, and a scheduled `session:` row could take the slot the owner's message was waiting for.

**Cause.** Three failures stacked. (1) A *count* was standing in for *money*: measured on
`text/dispatch.jsonl`, a text session costs a median $0.012 and runs a median 66 s, so 6/h is
~$0.07/h while `pi-control cap text` ($1.00/24h, then at $0.42) binds ~14x further out — and it was
never the guard that tripped. (2) The refusal was a per-batch template, so N messages meant N copies
of a sentence that named neither the queue nor the clock ("yours starts at the next slot" is not a
time). (3) The ledger's rows and the "has anything started" question were conflated: bookkeeping
spent budget, and nothing ranked the owner above the schedule.

**Guard.** `rate_brake()` in `bin/pi-text` asks `pi-control cap text`: over → refuse with the number;
blind → the 6/h count applies (a broken controller must not brick the channel, and six sessions an
hour bounds unpriceable damage to cents); otherwise no refusal at all. `wait_notice()` sends at most
one "not started yet" per reason per 15 min, carrying the waiting count and the *clock time* the slot
opens, computed by `next_slot_s()` from the oldest in-window session; `describe_state()` turns every
internal code into that sentence. `SESSION_ROUTES` keeps `due-busy`/`due-escalated` out of the
counter. `cmd_dispatch_due` yields a tick while a text message was filed in the last 30 min
(`--force` overrides), and `pi-text check` fails when tasks wait over 90 min with no session opened
in the last hour (dead dispatcher, not busy one). Pinned by `tests/pi-text.sh` (12 checks, run twice
and diffed by `pi-tool check`): 3 real + 2 bookkeeping rows count as 3, the slot is a duration, a
repeat within the window is silent, a notice names the count and a clock time, due work defers and
`--force` does not. Verified live: the 03:20 tick's receipt read "6 messages waiting: a session is
already running, and the next one starts when it finishes. Answered in order — no need to resend."

**Lives in**: `bin/pi-text` (`rate_brake`, `spend_cap_state`, `wait_notice`, `describe_state`,
`next_slot_s`, `SESSION_ROUTES`, `cmd_dispatch_due`, `cmd_check`), `tests/pi-text.sh`, `AGENTS.md`
(Texts), `bin/pi-control` (`cap text`), memory #275.

**Lesson.** A rate limit is a claim about the scarce resource; when the resource is money, count
dollars. And a refusal is a message: if it cannot say how many are waiting and when the next one
starts, it is noise, and repeating it is the failure mode — one honest notice beats five statuses.

## INC-8 — the agenda fell behind because each tick filed a new p1 task (2026-11-17)

- **What happened**: `pi-agenda show` carried 37 open `job-done failed: 1 completion event(s) nobody has
  read` tasks and 7 `control-wake failed: wake cap-backstop: $26.72 over $12.00/24h`, one per tick since
  the previous night, while the machine had no overdue session work at all. `pi-agenda next` answered
  "due now: nothing" — the backlog was entirely self-made noise, and the owner's read was "the agenda is
  behind, so catch up".
- **Cause**: two rows fail *repeatedly and identically* by design. (1) `pi-done check` exits 1 until a
  session runs `pi-done seen`; until then every 15-min tick files another task. (2) `pi-control wake`
  exits 2 when a cap is over — over-cap means "refuse new work", which is the backstop working, not a
  broken probe, but the exec runner scored any non-zero as a failure (INC-7's class again). A third
  contributor: `route-inkling-check` had a relative `exec:delegation/route-heldout-check.sh`, so it could
  never run.
- **Guard**: `file_failure()` in `bin/pi-agenda` is the single path both callers (`tick --run`, `run <id>`)
  use: an open task for that ref is re-annotated with the newest detail instead of duplicated (same shape
  as the timer-failure dedupe). `pi-control wake` now exits 3 (`IDLE_EXIT`) when the only finding is an
  over-cap backstop and prints `over cap, nothing woken (idle)`; exit 2 stays for armed events. The row's
  command is absolute; AGENTS.md says behind-ness is caught up in the turn it is seen.
- **Measured**: three consecutive failing runs of a throwaway row (`exec:sh -c "echo boom; exit 1"`) left
  one open task (id 191) and `strikes=3`; `pi-agenda run control-wake` recorded `ok (idle (exit 3): …)`
  with `strikes=0` and filed nothing; `pi-agenda run job-done` → `ok`, `strikes=0`;
  `route-inkling-check` → `ok (inkling route 100% vs regex 41% on 22 held-out cases)`, `strikes=0`, and
  40 stale p1 tasks were dropped (37 job-done, 5 cap-backstop), leaving 2 real `tool-errors` ones.
- **Lives in**: `bin/pi-agenda` (`file_failure`), `bin/pi-control` (`cmd_wake`), `AGENTS.md` (agenda
  paragraph), agenda rows `route-inkling-check`/`control-wake`/`job-done`.
- **Lesson**: a row that strikes is a signal; a row that files the same p1 task every tick is the agenda
  reporting its own heartbeat as an emergency. Repeated identical failure means "re-annotate", never "file
  again" — and "behind" has to be measurable (strikes, unread events, unrunnable command), not felt.

## INC-9 — the same "Agenda is behind" digest was texted every 6 h (2026-11-17)

- **What happened**: the owner's 13:10 text (paraphrased: when the agenda is behind, catch up in that turn) was
  answered with a catch-up report; 30 min later they texted "This is a recurring problem look into it and
  fix it". The recurring artefact was the phone nudge: `text/outbox.jsonl` shows the body at
  2026-11-16T08:40:52Z and 2026-11-16T14:50:53Z byte-identical (`p1 due #86 cadence-measure failed`), and
  2026-11-17T03:30 / 09:40 differing only by one extra bug row.
- **Cause**: `cmd_tick --notify` paged on `late_session or stale_now or soon`, where `soon` is "a p1 due
  within 24 h" and `bugs_now` is every open bug. Those conditions are true for days at a time, so the only
  thing limiting repeats was the 6-hour `phone_nudge` throttle — the trigger never had to describe
  anything *new*. A chronic list therefore became wallpaper, and the owner could not tell a new problem
  from an old one.
- **Guard**: `phone_digest()` in `bin/pi-agenda` diffs the digest against `agenda/last-phone-digest.json`,
  the item list the owner already saw. New items text immediately and carry only the new lines (plus a
  `cleared: N` count); an unchanged list is silent until `PHONE_DIGEST_STALE` (24 h) and then says
  "Still open, unchanged for …"; a list that shrank says nothing. A bug that is also a p1 due tomorrow is
  one line, not two.
- **Measured**: `tests/pi-agenda.sh` (new, in the pinned suite) drives a stub `pi-text` in a temp
  `PI_AGENT_DIR`: new item → 1 message, identical → still 1, second new item → 2 with only the new line,
  shrink → unchanged. Seven assertions pass and two consecutive runs diff identical. On the live store,
  after seeding the digest with the current list, `pi-agenda tick --notify` left `text/outbox.jsonl`
  mtime unchanged (1794921262) and wrote no throttle stamp — no repeat.
- **Lives in**: `bin/pi-agenda` (`phone_digest`, `PHONE_DIGEST_STALE`), `tests/pi-agenda.sh`.
- **Lesson**: an alert must be a diff, not a state. If the trigger can be satisfied by a condition that
  persists, the message will repeat — dedupe against what the owner last saw, and let silence mean
  "nothing changed".

## INC-10 — a detached job could not find its own tools (2026-11-17)

- **What happened**: `pi-done run ... pi-delegate run ...` finished in 0.0 s with `bash: line 1:
  pi-delegate: command not found` (j43301298), and the retry with an absolute path died as "unit
  failed to start" (j76556415). The pergola gate work then had to be relaunched by hand.
- **Cause**: `systemd-run` units inherit the *manager's* environment, not the shell's, so PATH was
  `/usr/local/bin:/usr/bin:/bin`. `PI_AGENT_DIR` was already passed for exactly this reason; PATH
  was not.
- **Guard**: `pi-done run` now sets `--setenv=PATH=<agent bin>:<caller PATH>`. Verified by a real
  job whose tail reads `$HOME/.pi/agent/bin/pi-delegate` — the class cannot repeat for any
  pi tool, not just this one. `pi-done --selftest` still passes (20/20).
- **Lives in**: `bin/pi-done` (`cmd_run`).
- **Lesson**: a detached unit starts in a foreign environment; every path it needs by name has to be
  handed to it, and the guard is a real job's output, not the belief that it works.

## INC-11 — a cookie wall was reported as a wall for *me* (2026-11-17)

- **What happened**: the GitHub webhook was reported to the owner as "one 40 s step is left and it
  needs a real browser: GitHub refuses cookie-authenticated writes from curl", filed as task #209 and
  handed back. The owner answered "I am getting tired of hearing you hit an error and gave up."
- **Cause**: the 403 was real but it was a *cookie-auth* refusal, not a permission wall. The repo
  token already in `pi-secret github/token` carries `repo`, which covers repository hooks; the
  token path was never tried because the first attempt had used the browser's cookie jar.
- **Guard**: `bin/pi-github-watch setup` now creates-or-detects the hook through `api.github.com`
  first and only prints the form when no token exists (commit 2171faf). A credential-walled write is
  an API call, not a browser session — and a "needs a browser" claim has to name the credential it
  tried and why that credential cannot do it.
- **Verified**: hook 713197507 active with 6 event types; `POST .../hooks/713197507/pings` → 204 and
  GitHub's own `last_response` 200; the ping payload landed on the ntfy topic (8239 B) and the
  service consumed it.
- **Lives in**: `bin/pi-github-watch` (`setup`, `api_hook`).
- **Lesson**: "I could not" is a claim about a method, not a fact about the world. Before reporting
  it, enumerate the credentials and interfaces still untried — the second one usually works.
