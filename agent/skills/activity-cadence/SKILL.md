---
name: activity-cadence
description: Choose how often and at what clock a semi-automated account posts to a third-party service (GitHub pushes, issues, comments, mail, social APIs) so its history looks like an active human rather than a cron — measure peers first, then set rate, gap, burst and waking-hour gates. Use whenever a tool posts on a schedule the owner did not choose, when an account risks looking automated, or when someone asks to raise or lower a posting cap.
---

# Activity cadence — the clock is the fingerprint

One line: **a fixed minute is a confession; a plausible rate is not.** A cap answers "how many",
nothing answers "when", and services (and the humans reading a profile) notice both.

## Procedure

1. **Measure peers, never guess a cap.** For GitHub, commits carry the author's local UTC offset,
   so `commit.author.date` gives an hour histogram in *their* clock:
   `/repos/{o}/{r}/commits?since=...&per_page=100` over ~6 active repos, 180 days, group by
   author. Rate = commits/week while active (first→last commit), and separately for regulars
   (>=10 commits) so one-off patch contributors do not drag the median to zero.
2. **Condition on "active".** The median account is dormant (2% of a 290-account ID sample had
   any public event in 90 days). The peer to imitate is the regular contributor.
3. **Set four numbers, not one**: per-week cap, per-day burst cap, minimum gap, and a local-time
   window. Real baselines (2026-11, 1,869 commits): 70% of commits 08:00–20:00 local, 4%
   00:00–06:00, weekend 23%; regulars median 9.4 commits/week (p25 2.4, p75 15.4).
4. **Jitter the scheduler.** `OnCalendar=*-*-* 08..21:23` + `RandomizedDelaySec=1200` beats
   `Mon 05:37`; the gate in the tool does the refusing, the timer only wakes.
5. **A forced publish must not starve the routine ones.** Keep forced pushes in history but count
   the burst cap and the gap over all of them, so a bootstrap cannot silently eat the week.

## Where it lives here

`bin/pi-publish` (cap 5/7d, 2/24h, >=1.5h apart, 08:00-22:00 local) and
`~/.config/systemd/user/pi-publish.timer`; evidence and the falsifier in
`research/github-activity-cadence.md`. Re-measure when the service or the repo changes — the
numbers above are one platform, one season.
