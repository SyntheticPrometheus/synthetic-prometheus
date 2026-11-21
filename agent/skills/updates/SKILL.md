---
name: updates
description: Keep this Arch host and pi itself current with a protocol that runs — the weekly `updates` agenda row applies detached (snap-pac snapshot first, reboot marker after), `bin/pi-update check` measures what is pending and how long it has waited, and `pi-preflight` blocks on a stale protocol, an aging reboot marker or an unmerged .pacnew. Use when updating the system or pi, when asked whether the machine is current, before a reboot decision, or when an upgrade failed and needs a rollback.
---

# Updates — the machine and the harness, on a clock

Measured 2026-11-20: last full `pacman -Syu` was 6 days old with 54 packages pending (glibc,
firefox, the kernel), and pi was 1.5.2 while npm published 1.6.0. Nothing would have noticed — no
agenda row, no check. A protocol that depends on remembering is not a protocol.

Three parts, each one a thing that runs:

| part | what it does | where it lives |
|---|---|---|
| `bin/pi-update check` | fresh sync dbs in a throw-away dbpath, pending counts, pi vs npm, age | interactive + `--json` |
| `bin/pi-update apply --detach` | the real upgrade, as a detached `pi-done` job | `updates` agenda row, weekly |
| `bin/pi-update status` | offline state/markers, exit 1 on attention | `pi-preflight` (`updates`) |
| `tests/pi-update.sh` | pins the decision logic against a fake root | `pi-tool check` |

## The weekly row (automatic)

```
pi-update apply --detach --quiet          # row `updates`, 1w
```

It starts `pi-done run --title 'updates: apply' --phone`, which means: the upgrade outlives the
shell, `OnFailure` writes `events/done.jsonl`, and you get one text saying how it went.
`pi-done check` (the `job-done` row and preflight `completions`) fails on an unseen failure, so a
broken upgrade is not a silent one.

Inside, in this order:

1. **Preconditions** — passwordless sudo, ≥5 GiB free, no `db.lck`. Any failure is a named step,
   not a half-run.
2. **snap-pac** writes the pre/post btrfs snapshot around the transaction automatically (`snapper`
   config `root`, hook `05-snap-pac-pre.hook`). The snapshot numbers land in
   `updates/state.json` as `snapshot_pre`/`snapshot_post`.
3. **`sudo pacman -Syu --noconfirm`** — never `pacman -Sy <pkg>`, which is the partial upgrade that
   breaks an Arch box. If the first attempt dies on a PGP signature, the one sanctioned retry is
   `pacman -Sy --noconfirm archlinux-keyring` and then `-Syu` again.
4. **`paru -Sua --noconfirm`** for the foreign packages (currently `paru-bin`, `paru-bin-debug`).
5. **pi** — `pi update --extensions` and `--models` as the user, then **`sudo pi update self`**
   (the managed install is under `/root/.pi/agent/install`), then verify `pi --version`. Release
   directories are never pruned: rollback needs them.
6. **Aftermath** — kernel changed → `updates/REBOOT-REQUIRED` marker + a priority-2 task; new
   `.pacnew` files → `updates/PACNEW.txt` + one task (never auto-merged); everything → one line in
   `events/update.jsonl` and `updates/state.json`, plus a 5-file log cap in `updates/apply-*.log`.

## What `check` treats as overdue

Arch is always pending *something*, so "pending > 0" is not the alarm — it is the information.
`check` exits 1 only on:

- no **successful apply** (or full upgrade) for `--max-age-days` (default 14);
- `REBOOT-REQUIRED` older than 3 days (the task it files is due after 2, so it nudges first);
- a `.pacnew` older than 7 days;
- pi behind npm for 7 days (counted from first sighting, so a Saturday release does not fire);
- a running kernel older than the installed one.

`--strict` exits 1 on any pending package. `status` uses the same rules offline with a 30-day
default, which is what `pi-preflight` calls.

## Reading it

```
pi-update check                 # system / aur / pi / pacnew / reboot + ATTENTION lines
pi-update status                # offline: last apply, pi versions, marker
pi-update log -n 20             # events/update.jsonl
pi-update apply --pi-only --yes  # just the harness (extensions, catalogs, pi self)
pi-update apply --system-only --yes
```

## Rollback

```
pi-update rollback                 # prints the two ladders, runs neither
sudo snapper -c root undochange <pre>..<post>   # live system, same btrfs root
# boot menu: GRUB snapshot entries -> boot the pacman (pre) snapshot -> snapper rollback
pi-update rollback pi 1.5.2        # point the managed install at a release still on disk
```

A system rollback is a boot-time decision: the tool prints the command and the menu path instead
of running it. `rollback pi` writes `current-version` only, and says so.

## Rules that are not negotiable

- **Never `pacman -Sy <pkg>`** — sync + single install is a partial upgrade. The check's throw-away
  `--dbpath` exists so that inspecting updates cannot leave the real database half-synced.
- **Never update pi from inside a long session's critical path**: `apply` detaches for this reason,
  and the running process keeps its loaded release. A pi update applies to the *next* session.
- **Never auto-merge a `.pacnew`** or reboot. Both are decisions with your data in them.
- **A failed apply files a priority-1 task** and leaves its log; a kernel change leaves a marker that
  `pi-preflight` reads.

## When an upgrade breaks something

1. `pi-update log -n 5` and the newest `updates/apply-*.log` — which step, which rc.
2. `sudo snapper -c root list | tail` — the pacman pre/post pair from that run.
3. Live rollback `sudo snapper -c root undochange <pre>..<post>`, or boot the snapshot and
   `sudo snapper rollback`.
4. `pi-update rollback pi <previous>` if only the harness moved.
5. File the incident in `INCIDENTS.md` with the guard that should have caught it, then add that
   guard to `bin/pi-update` (its `--selftest`) rather than to a note.
