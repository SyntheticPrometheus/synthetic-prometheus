# Harness review — 2026-11-20 14:04 UTC

8 pass · 2 warn · 2 fail

| signal | state | detail |
|---|---|---|
| agents.md | fail | 188 lines, 1 referenced path(s) missing: tests/NAME.sh |
| replay | pass | full-stack replay catches a regression arm-only misses |
| suite | pass | 17 tasks, last base 0/6 (0.00) on 6/17 tasks 0.4d ago — uncovered: stale-cache, long-reports, log-fanout, chain-12 … |
| delegation | pass | 179 dispatches, 96 without verdict, 0 stale (>7d); roster bulker, debator, integrator, redteam, scout, tester, verifier, worker |
| memory | warn | brief 1030/1100 tok (94%), 298 knowledge row(s) + 32 digest(s), last digest 3d ago; cut KEY LESSONS / PREFERENCES 4/10; RECENT 5/8; OPEN PDSA 1/2 — working set is full (sections are cutting rows, listed above) |
| guards | fail | pi-preflight failing: Command '('$HOME/.pi/agent/bin/pi-preflight', '--quiet')' timed out after 120 seconds |
| timers | pass | enabled: pi-agenda.timer, pi-burn.timer, pi-frantic.timer, pi-mind.timer, pi-publish.timer, pi-review.timer, pi-selfimprove.timer |
| skills | pass | 22 skill(s) with valid frontmatter |
| vendor | warn | 4 new commit(s), head abeeaf95660b, version 1.3.2 |
| publish | pass | last attempt 0.0d ago — pushed: 2 file(s), 1885 KB; 13/2 in 7d |
| pdsa | pass | 21 open cycle(s) |
| mind | pass | 2 episodes (creativity:1, curiosity:1), last 5.5d; report 5d; lit refresh 6d |

## ACTIONS

- fix or drop the dangling reference(s): tests/NAME.sh
- mem consolidate --digest, or archive what no longer matters
- fix the failing preflight check before anything else
- bin/pi-skills update --dry-run, then follow upstream/PROTOCOL.md

## Standing questions (answer in one line each next session)

- What did the last three sessions do that the rules here do not mention?
- Which doc, skill, agent or arm has not been used since it was written?
- Which rule did I break this week, and is the guard executable or a promise?
