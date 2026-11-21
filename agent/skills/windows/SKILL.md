---
name: windows
description: Tile the windows a session is working with before capturing anything, so screenshots show the work instead of one corner of it. Use whenever a session opens a window, drives two or more windows at once, takes a screenshot to check its own work or show you, or when a window is "missing", maximized, overlapping, off-screen, or the desktop layout looks wrong.
---

# Windows — tile, verify, capture, name them

One line: **`bin/pi-shot` is the screenshot command; it tiles first and says what is in the frame.**

The failure this prevents: a session opens a browser and a terminal, screenshots the root window,
and reports "the page shows X" while the page is 95% hidden behind a maximized terminal. The picture
is evidence only if the session knows what it contains.

## The protocol

1. **Before any claim about the screen, tile.** `bin/pi-shot --note "<why>"` runs `bin/pi-tile`,
   captures the whole work area, downscales it, and prints every window with its rect. Read that
   table, not the raw pixels, to know what is visible.
2. **A window you opened is a window you place.** After launching anything (`pi-firefox`, a terminal,
   a test window, a dialog that must stay put), run `bin/pi-tile` once the window is mapped. The
   desktop never drifts into "one window on top of another".
3. **One window per shot only for detail.** `pi-shot --window <ID>` frames it full-screen; that is
   for reading exact pixels/text, and the reply must say it is a detail shot of one window.
4. **Exclude on purpose, not by accident.** `bin/pi-tile --park <ID>` moves a window to desktop 1:
   pergola drops it from the layout, so the *rest* re-tile evenly. `--unpark` brings it back.
   Floating a window does **not** remove it — `arrange` tiles floating windows too.
5. **Verify before you capture.** `pi-tile status` classifies every managed window as `shown`,
   `MAXIMIZED`, `OFF-SCREEN` or `FLOATING`; `pi-shot --expect N` exits 4 when the shot lost windows.
6. **"Make it a grid" is `pi-tile grid`, and the shape is verified, not hoped for.** `arrange` is a
   balanced fractal tree: four panels happen to come out 2×2 (mid = n/2, alternating axis), three
   come out half column + split, five come out ragged. `pi-tile grid` adds the check `tile` cannot
   do — one window per cell, no overlaps, equal areas, union covers the work area — so a grid claim
   is a measurement (`~/.local/state/pi-win/events.jsonl`, `"event": "grid"`). Your own key
   for it is **Super+g** (xfconf `/commands/custom/<Super>g`, `--quiet --notify`).
   If a window is not in the log, it is not in the shot, and the reply must not imply it is.

## Lifecycle: open → tile → name → close

Use `bin/pi-term` for every window this session opens for work; it enforces the lifecycle instead of
relying on memory.

```sh
pi-term --name build --exec "cargo test --workspace"   # tiled window, closes when the test ends
pi-term --name review --cwd ~/proj "review the parser"  # tiled pi chat, closes when pi exits
pi-term --tmux --name soak --exec "./soak.sh"           # no window; session dies with the command
pi-term --list                                         # what is open, age, target, orphans
pi-term --close review                                 # idle chat, work already captured
pi-term --reap                                         # gone/expired targets + dead pi-* sessions
```

- **Tiled on open**: `pi-term` waits for the window to map and runs `pi-tile`, so a new window never
  lands on top of the others. `--no-tile` exists only for a deliberate exception.
- **Named**: title is `pi: <name>: <task>`; that is the handle in `pergola list`, `wmctrl`, and the
  registry (`~/.local/state/pi-win/terms.jsonl`).
- **Self-labelled**: a plain `pi` window titles itself `Terminal - π - <topic> - <cwd>`
  (`extensions/session-title.ts`: `/topic <text>`, else `/name`, else the first user message; a
  braille frame while the agent works). `xfce4-terminal --title=` is a *static* title and freezes
  it, so launch with no `--title` — the autostart entry and `pi-attach` rely on that, and
  `~/.tmux.conf` forwards `#{pane_title}` (`set-titles on`) so a tmux-attached window is labelled too.
- **Closed by default**: the terminal exits with its command; `--keep` is explicit and must be
  justified in the report. A `pi-*` tmux session whose pane is no longer `pi` is an orphan.
- **Reaped**: the 6 h `window-reap` agenda row runs `pi-term --reap`; `pi-preflight` check `windows`
  fails on an orphan or a target older than the 12 h TTL. A forgotten window is a red check.
- **Cap two visible windows.** More is a queue; close or hand off first.
- **Shoot before you close.** A window is evidence only while it exists and is tiled; after closing,
  cite `win-log.jsonl`, not the window.

## Decision table

| Situation | Do |
|---|---|
| 1 window, need the content | `pergola frame-window` (or `pi-shot --window ID`) |
| 2 windows | `pi-shot` — `arrange` gives two equal columns |
| 4 windows, wants a grid | `pi-tile grid` — tiles, then *proves* 2×2 (exit 3 + PROBLEM when not) |
| 3–4 windows, general | `pi-shot` — balanced tree: half column + half split, or a 2×2 grid |
| 5+ windows | `pi-shot`, then `pergola zoom-in` if only one group matters |
| a window must not appear | `pi-tile --park ID` before the shot |
| two pi sessions share the screen | tile immediately before capture; the other session re-arranges too |
| layout looks wrong | `pi-tile status`, then `pergola tree` / `pergola rects` |

## Pitfalls (each one cost a session once)

- **A maximized window ignores `_NET_MOVERESIZE_WINDOW`** (xfwm4). `arrange` reports success and the
  window squats over the tiles at 1600 wide. `pi-tile` removes the maximized state first, waits for
  it to clear, and fails loudly if it did not.
- **The work area is not the display.** With a 27 px top panel the display is 1600×900 but
  `_NET_WORKAREA` is 1600×873 at y=27. Laying out against the display pushes the bottom 27 px of
  every window off-screen. `pi-tile` and `pergola 0.1.1+` use the work area.
- **The work area is not the workspace either.** Nothing may test `desktop == 0`: work runs on
  workspace index 2 here, and that literal made `pi-tile` report a tiled 2×2 as `0/4 parked` and
  `pi-shot` log *0 windows in shot* with exit 0. `pi-tile` uses `current_desktop()` (`wmctrl -d`)
  and `pi-shot` refuses a blind shot with exit 4 — if you see that refusal, believe it.
- **`--park` is checked after the tile, not before.** pergola 0.4.0-dev re-homes a floating panel
  on reconcile, so a park that did not stick now fails the run (`did not park …`, exit 3) instead
  of printing a desktop number nobody reached (bug #114).
- **Terminals snap their size** to `WM_NORMAL_HINTS` increments (10×23 here), so a tile is expected
  to be a few pixels short of its rect. Compare with the increment as tolerance, never exact.
- **`arrange` includes floating windows and every managed window**, so "show only these three" is
  done by parking the others on another desktop — the only exclusion that still tiles equally.
- **Docking is not equal tiling.** `dock left/right` keeps the `desktop` leaf in the split (panels
  end up at ¼ width); `arrange` with `desktop_share: 0` is the equal-area primitive.
- **The overlay is drawn into the root window**, so pergola's structure borders appear in every
  capture. That is useful; `pergola overlay off` for a clean image.
- **A tile that matches its own rect can still not be a grid.** Per-window verification says
  "this window took its tile"; a half column, a squatter over two cells and a ragged 5-window
  layout all pass that and still look wrong. Use `pi-tile grid` when the *shape* is the claim.
- **Unmanaged ≠ absent.** A window pergola has not adopted lists as `unmanaged`: run `pi-tile` again
  (adoption happens on the next reconcile).

## Measurement

`~/.local/state/pi-win/events.jsonl` (tile/park) and `~/.pi/agent/win-log.jsonl` (every shot, with the
windows in it) make the protocol falsifiable:

```bash
pi-shot --stats        # shots, how many windows each showed, share with >= 2
```

Target: a shot taken while ≥2 windows were in play shows ≥2; a shot that shows one has `--window` in
its command line or a `--note` saying why. A session that batches two windows and reports from a
one-window screenshot is the bug this skill exists to catch.

## What not to do

- Do not capture `import -window root` directly for a multi-window claim — use `pi-shot`.
- Do not close or park a window just to make the layout look tidy; park only what the shot must omit.
- Do not trust `wmctrl -l` as the window list (it shows panels and unmanaged windows); `pi-tile
  status` is the managed view.
- Do not fight a parallel session's layout: tile, capture within the same second, report what the
  log says. If the other session re-tiled first, your `--expect` will catch the difference.
