# synthetic-prometheus

The working harness and dotfiles of an unattended coding agent on a single Arch Linux machine:
prose protocol (`agent/AGENTS.md`), skills, the subagent roster, and a measured
self-improvement loop (`agent/selfimprove`) whose design and evidence live next to the code.

Published as periodic snapshots, not a mirror of the working tree — one squashed commit per cycle,
only when there is something worth reading. Secrets, sessions and personal memory are excluded by
an explicit allowlist; see `PUBLISHING.md`.

- `agent/` — harness: AGENTS.md, agents/, skills/, prompts/, extensions/, bin/, research/,
  selfimprove/ (design, decisions, suite, gate, audit, maintenance)
- `dotfiles/` — shell, systemd user units, autostart, lightdm autologin
- files: 193 · snapshot: 2026-11-19

Research behind the loop: `agent/research/self-improving-harnesses.md`.
