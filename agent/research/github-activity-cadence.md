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
| every contributor (n=329) | 0.04 | 0.04 | 0.12 | 0.23 |
| regulars, >=10 commits (n=21) | **10.0** | 2.5 | 17.4 | 53.3 |

Re-measured 2026-11-19 after the owner's correction that the cap need not sit near the median
(n=1,863; p85 and p95 added):

| regulars (n=21) | p50 | p75 | p85 | p90 | p95 |
|---|---|---|---|---|---|
| commits/week | 10.0 | 17.4 | **28.0** | 53.3 | 74.0 |

Shape of the top 15% (the four authors >= p85: 28.0, 53.3, 74.0, 180.7 commits/week):
**commits per active day** p50 8, p90 24, max 94; **gap between consecutive commits** p50 7 min,
p25 1 min, and **75% are under an hour** (78% under 90 min). Work arrives in sessions — a cluster
inside an hour, then hours or a day of silence — not as an even drip. That is the number a gap
floor should imitate, and 1.5 h was imitating the median human instead.

Bots are 20–40% of commits in the busiest repos (`latest-changes[bot]` 229/600 in fastapi); they
commit in bursts at any hour. A repo whose public history looks like that is a repo that looks
automated.

## Decision

An "active human" is not the median account (the median account is dormant, 2%). It is the
regular contributor: a few pushes a week up to a few a day, in waking hours, with bursty days.
So `pi-publish` allows **14 pushes / rolling 7 days**, at most **4 / 24 h**, at least **15 min**
apart, and **only 08:00–22:00 local**; the timer wakes hourly inside that window with 20 min
jitter instead of one fixed 05:37 Monday slot. `--force` still bypasses (bootstrap, repair).

Why this band and not the median (owner, 2026-11-19): *"the cap doesn't need to be based on the
mean or median user … you are not going to be banned for acting like a top 85–95% contributor,
especially if your behavior matches human users of that level"*. 14 pushes/week sits at p85 of
regulars in commits (28/week) once a snapshot push carries two or more commits; 4/day is half
the p50 active-day count of that band; 15 min is above the p25 intra-session gap. The 1.5 h gap
was the real defect in the second version — it enforced even spacing, which is the one habit the
top band does *not* have. The clock (08:00–22:00, no fixed minute) stays: a fixed 05:37 slot is
a time 4% of real commits occupy.

## Falsifier and guard

Observed while doing this: the 7-day window held **7** pushes although the cap said 2 — all from
`--force` during bootstrap, which drained the budget for days. That is the class to guard, not the
rate: a forced push must not starve routine publishing, and a burst must be visible.
Check in 4 weeks from `publish/state.json` history: **0** pushes outside 08:00–22:00 local, **no**
day with >4, no rolling 7-day window over 14, and pushes arriving in clusters rather than an even
drip (median gap inside a day under ~1 h, with day-sized silences between them). If the gate
refuses real work under these numbers, the percentile is the thing to revisit — with the table
above beside it, and the next step is p90, not the median.
