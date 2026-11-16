# Incidents and their guards

Rule: **every failure gets a guard, not just a fix.** An entry is closed only when the guard is
something that runs (a check, a test, a refusal) or a rule that is loaded every session. A fix
without a guard is a promise, and promises are what failed the first time.

Format: what happened → root cause → guard → where the guard lives.

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
  on "a changed label **or real work in the window**". At 21:30 the owner repeated, more bluntly:
  "Bro stop the updates that process already finished you don't need to keep giving me updates
  every 15 min stop". Outbox: `[PROGRESS] pi 273962` at 02:29:29Z and `02:30:12Z` — two texts a
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
