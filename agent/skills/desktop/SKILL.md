---
name: desktop
description: Change the XFCE desktop safely — power/blank/sleep, panel indicators (battery, volume), autologin/autostart, notification sound. Use when you ask for a desktop setting, a taskbar indicator, "screen never turns off", or a session that survives logout/reboot.
---

# Desktop — XFCE settings that survive a restart

One line: **xfconf is the source of truth; the panel rewrites its own plugin `.rc` files, so edit
those only while the panel is stopped.**

## First, identify the session

```bash
echo "$XDG_CURRENT_DESKTOP / $XDG_SESSION_TYPE"      # expect XFCE / x11
xfconf-query -c xfce4-power-manager -l -v
xfconf-query -c xfce4-panel -l -v | head -40
xset q | sed -n '/Screen Saver/,/^$/p;/DPMS/,+3p'
```

If `DISPLAY` is unset in a shell, use `export DISPLAY=:0` (or `:0.0`).

## Screen never turns off on AC

Two layers both blank the screen: XFCE power manager and the X server.

```bash
export DISPLAY=:0
# XFCE: DPMS on AC off, blank/sleep/suspend/inactivity 0
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-enabled -n -t bool -s true
for prop in dpms-on-ac-sleep dpms-on-ac-off blank-on-ac inactivity-on-ac; do
  xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/$prop -n -t uint -s 0
done
# X server: kill the built-in 600 s blank
sudo tee /etc/X11/xorg.conf.d/10-no-blank.conf >/dev/null <<'EOF'
Section "ServerFlags"
    Option "BlankTime" "0"
EndSection
EOF
xset s off
# verify: timeout 0, Standby/Suspend/Off 0
xset q | grep -E 'timeout|Standby|Suspend|Off:|DPMS is'
```

Battery settings are left alone: DPMS still blanks on battery, which is the point. To apply the
xorg file without a reboot, `xset s off` is enough for the current session.

## Lid closed on AC: keep running (owner request, 2026-11-16)

Closing the lid must not suspend, hibernate or blank while plugged in. Blanking on AC was already
zero (above); the missing layer was the lid switch. **systemd-logind owns it**, and
xfce4-power-manager had grabbed it with a `handle-lid-switch` block inhibitor.

```bash
export DISPLAY=:0
# 1. logind decides: external power = ignore, battery = suspend
sudo tee /etc/systemd/logind.conf.d/50-lid-external-power.conf >/dev/null <<'EOF'
[Login]
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
HandleLidSwitch=suspend
LidSwitchIgnoreInhibited=yes
EOF
systemd-analyze cat-config systemd/logind.conf | grep -E 'HandleLid|LidSwitchIgnore'
# 2. xfpm hands the lid to logind (it then drops its inhibitor)
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/logind-handle-lid-switch -n -t bool -s true
sudo systemctl reload systemd-logind        # SIGHUP; sessions survive
systemd-inhibit --list | grep handle-lid-switch   # expect NO xfpm row
# 3. belt-and-braces if xfpm ever takes it back: AC = nothing, battery = suspend
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-ac -n -t uint -s 4
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-battery -n -t uint -s 1
```

**The enum is not 0-based by intuition.** `XfpmLidTriggerAction` (upstream
`common/xfpm-enum-glib.h`, 4.20 branch): `0` DPMS/switch-off-display, `1` suspend, `2` hibernate,
`3` lock screen, **`4` nothing**, `5` hybrid sleep, `6` shutdown. Writing `0` for "nothing"
turns the display off on lid close — read the enum, do not guess.

**Test it without touching the lid.** `lid-probe.py` (in this directory) creates a uinput device
with `EV_SW`/`SW_LID`, closes it, holds 12 s and reopens. logind logs `Lid closed.` / `Lid opened.`
and the `LidClosed` property on `org.freedesktop.login1.Manager` flips, so the event is genuinely
seen — a probe that does not flip that property proves nothing. Arm an RTC alarm first, so a wrong
config self-recovers instead of leaving the machine asleep:

```bash
sudo sh -c 'echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +180 > /sys/class/rtc/rtc0/wakealarm'
timeout 60 sudo python3 ~/.pi/agent/skills/desktop/lid-probe.py
cat /proc/sys/kernel/random/boot_id; journalctl --since -2min | grep -i lid   # same boot id + 'Lid closed.' = pass
sudo sh -c 'echo 0 > /sys/class/rtc/rtc0/wakealarm'
```

Measured 2026-11-16 on AC: `Lid closed.` at 13:25:15, `Lid opened.` at 13:25:27, uptime and boot
id unchanged, session `State=active`, `xset q` timeouts still 0. On battery the default suspend
is untouched, which is the point.

## Panel indicators (battery, volume)

The panel stores plugin ids in `/panels/panel-1/plugin-ids`; each plugin is a string under
`/plugins/plugin-N`. Add the plugin, insert its id in the array, restart the panel.

Battery:
```bash
sudo pacman -S --noconfirm --needed xfce4-battery-plugin
xfconf-query -c xfce4-panel -p /plugins/plugin-19 -n -t string -s battery
# insert 19 after the systray (example order; read the current array first)
xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids -t int \
  -s 1 -s 2 -s 3 -s 4 -s 5 -s 6 -s 19 -s 7 -s 8 -s 9 -s 10
xfce4-panel -r
pgrep -a xfce4-panel || nohup xfce4-panel --disable-wm-check >/tmp/panel.log 2>&1 &
```

Volume:
```bash
sudo pacman -S --noconfirm --needed xfce4-pulseaudio-plugin
xfconf-query -c xfce4-panel -p /plugins/plugin-20 -n -t string -s pulseaudio
# insert 20 after the systray, before battery/clock; read the current array first
xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids -t int \
  -s 1 -s 2 -s 3 -s 4 -s 5 -s 6 -s 20 -s 19 -s 7 -s 8 -s 9 -s 10
xfce4-panel -r
pgrep -a xfce4-panel || nohup xfce4-panel --disable-wm-check >/tmp/panel.log 2>&1 &
```

**Gotchas (measured):**
- **Writing the `plugin-ids` array needs one `-t int` per value.** xfconf 4.20 rejects a single
  `-t int -s 1 -s 2 -s 3` with *"There are 3 new values, but only 1 types could be determined"*;
  the form that works is `-t int -s 1 -t int -s 2 …`. (The older one-`-t` form in this file never
  ran.)
- **Set a plugin property and restart the panel too quickly and the restart clobbers it**: `-r`
  makes the panel save its in-memory config on the way out, so a write it had not yet observed is
  overwritten with the old value. Write, confirm with `xfconf-query -p …`, *then* restart.
- `xfce4-panel -r` can leave **no panel running**. Always `pgrep -a xfce4-panel` after a restart;
  if it is gone, start it with `nohup xfce4-panel --disable-wm-check &`.
- The battery plugin's `~/.config/xfce4/panel/battery-19.rc` is rewritten from the running panel's
  memory and ignores xfconf settings under `/plugins/plugin-19/*`. Edit it only while the panel is
  stopped (`xfce4-panel -q`, edit, start), then verify with a screenshot.
- Screenshots: `ffmpeg -f x11grab -video_size 1600x60 -i :0.0+0,0 -frames:v 1 /tmp/panel.png`
  (no `scrot`/`import` on this host).
- **A new keyboard shortcut is not live until `xfsettingsd --replace`.** Custom commands live in
  `xfce4-keyboard-shortcuts` at `/commands/custom/<Super>g` (write with `-n -t string -s "cmd"`);
  `xfconf-query -lv` shows it immediately and the key still does nothing, because xfsettingsd
  bound the old set at start. Measured 2026-11-16: the Super+g grid shortcut fired only after the
  replace, then produced the expected `grid` event on the first press. Verify a shortcut by pressing
  it over a throwaway window (`xfce4-terminal --command "sh -c 'cat >/dev/null'"`), never over a
  chat terminal where a stray keystroke lands as prompt text.
- **A stale notification pile is a desktop state, not a bug to ignore.** `wmctrl -l | awk
  '/xfce4-notifyd/{print $1}'` then `wmctrl -ic` each id clears the popups (`CloseNotification`
  needs ids nobody published; killing xfce4-notifyd replays nothing but leaves the popups).

## Autologin + a terminal that resumes the pi session

```bash
# 1. lightdm autologin (survives reboot)
sudo mkdir -p /etc/lightdm/lightdm.conf.d
sudo tee /etc/lightdm/lightdm.conf.d/50-autologin.conf >/dev/null <<'EOF'
[Seat:*]
autologin-user=host
autologin-user-timeout=0
autologin-session=xfce
EOF

# 2. autostart a terminal attached to tmux session 'pi'
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/pi-terminal.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=pi session
Exec=xfce4-terminal --title=pi --geometry=120x40 --command=$HOME/.pi/agent/bin/pi-attach
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

# 3. linger so user timers run without a login
loginctl enable-linger host
```

`bin/pi-attach` attaches to tmux `pi` or creates it with `pi --continue`. Verify:
`bash -n bin/pi-attach`, `desktop-file-validate ~/.config/autostart/pi-terminal.desktop`,
`systemctl is-enabled lightdm`.

## Notification sound (pi replies)

`~/.pi/agent/extensions/notify.ts` calls `notify-send` when a TUI run settles and then plays
`/usr/share/sounds/freedesktop/stereo/complete.oga` with `paplay` (honours sink volume/mute).
Requires `xfce4-notifyd` and `paplay`:

```bash
sudo pacman -S --noconfirm --needed xfce4-notifyd
pacman -Qq | grep -E 'xfce4-notifyd|pulseaudio|pipewire'
paplay /usr/share/sounds/freedesktop/stereo/complete.oga
```

`PI_NOTIFY_SOUND=/path/to.oga` overrides; `PI_NOTIFY_SOUND=0` mutes only the chime.

## Appearances: the rice has a script, not a chat

`~/.local/bin/pi-rice apply|revert [TS]|status` owns every look-and-feel value: Adwaita-dark GTK,
Papirus-Dark icons, Inter/JetBrains Mono, a hand-tinted Tokyo-Night xfwm4 theme, a generated
gradient wallpaper and a translucent panel. `apply` saves the previous value of every property it
touches under `~/.local/state/pi-rice/backup-*/previous.txt` before writing, so `revert` is exact
(round-trip verified 2026-11-15). Never hand-set these keys in a session: change the script, apply,
and say what the screenshot shows — `bin/rice-showcase` is the demo content for that screenshot.

Two measured traps:

- **xfce4-terminal 1.2 migrated to Xfconf.** `~/.config/xfce4/terminal/terminalrc` is *ignored*
  ("settings have been migrated to Xfconf"). Settings are channel `xfce4-terminal` — `color-palette`
  must be ONE semicolon-separated string, never a 16-element array (that renders 16 empty swatches);
  a new window takes the change, windows already open keep theirs.
- **Two WMs on `:0` make windows exist without drawing.** If a screenshot drops windows that
  `pi-tile status` calls `shown`, count `pgrep -af "^xfwm4 "`; more than one (excluding nested
  `--display :70` test servers) means a stale WM displaced the real one. One `xfwm4 --replace`
  fixes it, and `pi-preflight` check `windows` now fails on that state.

## What the machine is doing: four indicators, three windows

`bin/pi-bg` reports from live sources only, and the panel shows four of its views as genmon
plugins on `panel-1` (`period = 5`, panel order `1 2 3 4 5 6 20 24 19 21 22 23 7 8 9 10` —
volume, mem, battery, then bg/fg/due):

| plugin | command | shows | click |
|---|---|---|---|
| 24 | `pi-bg --panel mem` | host RAM in use (`total - MemAvailable`, amber ≥75 %, red ≥90 %), tooltip with the top 6 processes by RSS; read straight from `/proc`, so it costs 0.13 s and not the 0.85 s background snapshot | **Memory** window (`pi-mem-view`) |
| 21 | `pi-bg --panel bg` | every background thing: text-dispatch sessions, other live `pi` sessions, `pi-term` targets, work units (`pi-*`, `local-*`, `llama-*`, `pergola`), and known job processes (`local-batch`, `cargo`, `llama-server`…) | **Runtime** window (`pi-bg --watch`) |
| 22 | `pi-bg --panel fg` | the active window and every process that is the *foreground* process group of a desktop tty (`pgrp == tpgid` in `/proc/<pid>/stat`, shells excluded) | — |
| 23 | `pi-bg --panel due` | overdue agenda obligations + overdue tasks; warning icon when non-zero | **Agenda** window (`pi-agenda-view`) |

All three windows are `pi-term --keep`-free: they page (`less`) and the window closes when you
quit. `.desktop` entries in `~/.local/share/applications/`: **Agenda — due and overdue**,
**Runtime — what is running**, **Memory — what is holding the RAM**.

**The click tag is `<txtclick>`, and the click must open its own window.** genmon 4.3.0 executes
`<txtclick>`/`<iconclick>` and silently ignores a bare `<click>`, and it runs the command with no
terminal. Both were wrong here: every indicator advertised a click that had never fired, and the
targets were bare views that would have printed into nowhere anyway. So each click is
`pi-term --name <slug> --exec <view>`: it fires and it has somewhere to draw.

**Memory numbers that matter:** `MemFree` counts page cache and reads a 44 %-used machine as full;
`MemAvailable` is what new work can actually have, so that is what the indicator shows. `--mem`
lists `VmRSS` from `/proc/<pid>/statm` (identical to `VmRSS` in `status`, 27 ms vs 92 ms for 230
processes — the panel builds this tooltip every 5 s). Verify a change with `pi-bg --panel mem`, a
hover screenshot for the tooltip, and a click test: `xdotool mousemove <x> 14 click 1`, then
`pi-term --list` must show the window as `open`.

Two rules the code enforces, both learned by getting them wrong: a process's display is read from
`--display` or `/proc/<pid>/environ` (test sandboxes on `:78/:79` are not desktop work), and a
finished job must never be reported as running (`/proc/<pid>` is checked, so no ghost rows).

```bash
pi-bg            # "1 bg — #52 text-dispatch 87s"
pi-bg --panel    # <txt>1 bg</txt><tool>…</tool>  (what genmon reads)
pi-bg --json     # for scripts; --watch for a live terminal view
```

Verify a change to it the way any other visual change is verified: `pi-bg` says N, then grab the
panel (`ffmpeg -f x11grab -video_size 1600x40 -i :0.0+0,0`). An indicator that reports a ghost (a
dead pid, a finished dispatch) is worse than none — `pi-bg` checks `/proc/<pid>` for exactly that.

## Verify, then record

- `xset q` for blank/DPMS.
- `pgrep -a xfce4-panel` after any panel restart.
- A screenshot for a visual change.
- `mem add` the durable fact (panel layout, plugin ids, gotchas) and, if the change guards a
  failure, add an `INCIDENTS.md` entry.

## Exercise

```bash
xfconf-query -c xfce4-power-manager -l -v | head
xfconf-query -c xfce4-panel -l -v | head
xset q | grep -E 'timeout|DPMS is'
```

If those print the current settings, the skill's read path is live. Do not change a setting without
reading it first.

## Window layout is not a desktop setting

Tiling lives in `skills/windows` (`bin/pi-tile`, `bin/pi-shot`), not here: pergola is a layer inside
xfwm4, so a "window" question is a pergola command (`pergola list|rects|arrange`), never an xfconf
key. Screenshots go through `bin/pi-shot` so they show more than one window.
