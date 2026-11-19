# Human activity cadence on GitHub, measured — what rate and clock a bot should imitate

Question: `pi-publish` capped public snapshots at 2 pushes per rolling 7 days and the timer fired
`Mon 05:37` local. Both numbers were guesses. What does an *active* GitHub user actually do, and
which of the two — rate or clock — is the fingerprint?

## Method (measured, not quoted)

GitHub REST, token-authenticated, 2026-11-19. Six public repos (`pallets/flask`, `fastapi/fastapi`,
`psf/requests`, `pandas-dev/pandas`, `home-assistant/core`, `textualize/rich`), commits since
2026-05-23 (180 days): **1,869 commits, 312 author-repos**. Every commit carries
`commit.author.date` with the author's **local UTC offset**, so the hour histogram is in the
author's own clock, not UTC. Second sample: 290 accounts drawn by ID (`/users?since=110000000`),
public events fetched for each — only **6 of 290 (2%)** had any public event in the last 90 days.

## Numbers

Clock, by author-local hour (n=1,869 commits):

| hours | share |
|---|---|
| 08:00–20:00 | **70%** |
| 00:00–06:00 | **4%** |
| peak | 17:00 (211 commits) |
| trough | 04:00 (9) |

Weekday (Mon→Sun): 411, 317, 255, 252, 205, 185, 244 — **weekend 23%**, Friday the quiet weekday.

Rate, commits/week:

| population | median | p25 | p75 | p90 |
|---|---|---|---|---|
| every contributor (n=312) | 0.04 | 0.04 | 0.12 | 0.23 |
| regulars, >=10 commits (n=23) | **9.4** | 2.4 | 15.4 | 52 |

Bots are 20–40% of commits in the busiest repos (`latest-changes[bot]` 229/600 in fastapi); they
commit in bursts at any hour. A repo whose public history looks like that is a repo that looks
automated.

## Decision

An "active human" is not the median account (the median account is dormant, 2%). It is the
regular contributor: a few pushes a week up to a few a day, in waking hours, with bursty days.
So `pi-publish` now allows **5 pushes / rolling 7 days**, at most **2 / 24 h**, at least **1.5 h**
apart, and **only 08:00–22:00 local**; the timer wakes hourly inside that window with 20 min
jitter instead of one fixed 05:37 Monday slot. `--force` still bypasses (bootstrap, repair).
Rationale: 5/week sits between p25 and the median of regulars; the *clock* was the real defect —
a fixed 05:37 slot is a time 4% of real commits occupy.

## Falsifier and guard

Observed while doing this: the 7-day window held **7** pushes although the cap said 2 — all from
`--force` during bootstrap, which drained the budget for days. That is the class to guard, not the
rate: a forced push must not starve routine publishing, and a burst must be visible.
Check in 4 weeks from `publish/state.json` history: **0** pushes outside 08:00–22:00 local, **no**
day with >2, and at least one publish per week. If a fourth push is wanted in a week with real
changes, the cap is the thing to revisit — with these numbers beside it.
