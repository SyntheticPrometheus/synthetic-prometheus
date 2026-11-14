# Publishing protocol

Public snapshots go to `github.com/SyntheticPrometheus/synthetic-prometheus`. The working tree is
**not** a mirror of what is published, and that is deliberate.

## Rules

1. **Allowlist, never denylist.** `bin/pi-publish` copies an explicit list of paths. Anything not on
   the list cannot leak by being forgotten. Excluded by construction: `auth.json`, `sessions/`,
   `memory/` (journal + DB), `delegation/ledger.jsonl`, `laya/.venv`, run directories.
2. **Scan before every push.** The script refuses on: API-key shapes (`sk-`, `ghp_`, `github_pat_`,
   `xox*`, `AKIA`), private-key headers, inline `api_key = "…"` style assignments, any file over
   512 KB, or a snapshot over 20 MB.
3. **Redact on the way out.** `/home/daedalus` → `$HOME` and the machine name → `host`, so the
   snapshot is usable as a template and carries no personal paths.
4. **Push rarely.** One squashed commit per cycle, and only when
   `changed files >= 3` **or** `days since last push >= 7`; hard cap **2 pushes per rolling 7 days**.
   `--force` exists for the first publish and for fixing a broken snapshot, not for routine work.
5. **Snapshots are not backups.** My provenance history is the local git repo in `~/.pi/agent`
   (which also excludes the same private paths). Public history is for reading and sharing.

## Commands

```bash
pi-publish                 # plan: what would change, scan, size, batching state (no network)
pi-publish --push          # build + commit + push, if the rules allow
pi-publish --status        # remote, last push, caps
pi-publish --force --push  # first publish / repair
```

State lives in `~/.pi/agent/publish/state.json` (last push, rolling history, thresholds).

## Schedule

`pi-publish.timer` runs `pi-publish --push` weekly (Mon 05:37). The unit is **disabled until
`~/.pi/agent/publish/enabled` exists**, so an unauthenticated machine does not produce a failed
unit every week. Create that file once credentials work.

## If GitHub flags the signup

GitHub's signup wall fires on automated-looking activity: a browser launched from a script, a burst
of unauthenticated API calls, a datacenter/VPN IP, or a shared network with a bad reputation. Both
of the first two happened here on 2026-11-14 (scripted `firefox --new-window`, plus repo-search API
calls), and the signup page returned "unusual activity" (ID 3b334e10-4157-cd59-25ca-0aee0157d395).

Recovery, in order of likelihood:

1. **Sign up from a phone on cellular data.** Different IP, real browser, human input — this clears
   it almost every time. Then run `gh auth login` on this machine and `pi-github-bootstrap`.
2. **Wait 24–72 h**, then sign up from a browser opened normally from the desktop (not from a
   script), no VPN, JavaScript on, extensions off, one attempt only. Repeated attempts extend the
   block.
3. **Ask support** via the "Submit feedback" link with the ID above; they can lift it.

Rules that follow, and apply to any third-party service:

- never automate account creation, signup, or login flows;
- never launch a browser *at* an auth flow from a script or an agent;
- keep unauthenticated API traffic from this host low; use authenticated calls after `gh auth login`.

Fallback if GitHub stays closed: the same pipeline works against GitLab or Codeberg — create the
repo there and run `pi-publish --force --push --remote <url>` (nothing else changes).

## What is published

- `agent/AGENTS.md` — the operating protocol (mandate, memory rules, PDSA, verification policy)
- `agent/skills/`, `agent/agents/`, `agent/prompts/`, `agent/extensions/` — the harness proper
- `agent/research/` — literature digests, with citations
- `agent/selfimprove/` — design, decisions log, suite, gate/audit/maintenance code
- `agent/bin/` — `mem`, `layaq`, `pi-publish`, delegation wrappers
- `dotfiles/` — shell profiles, systemd user units, autostart, lightdm autologin
