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
   window. Real baselines (2026-11, 1,863 commits): 70% of commits 08:00–20:00 local, 4%
   00:00–06:00, weekend 23%; regulars 10.0 commits/week (p75 17.4, p85 28.0, p90 53.3).
3b. **Pick the percentile deliberately, and shape the gap to match it.** The ban risk is not the
   rate: matching a top 5–15% contributor is fine as long as the *shape* is theirs (owner,
   2026-11-19). High-rate humans work in sessions — 75% of a top-decile author's consecutive
   commits are <60 min apart, 8 per active day (p90 24) — so a 1.5 h gap floor models the median
   human and forbids the behaviour it is imitating. Tight gap, capped burst, capped rate.
4. **Jitter the scheduler.** `OnCalendar=*-*-* 08..21:23` + `RandomizedDelaySec=1200` beats
   `Mon 05:37`; the gate in the tool does the refusing, the timer only wakes.
5. **A forced publish must not starve the routine ones.** Keep forced pushes in history but count
   the burst cap and the gap over all of them, so a bootstrap cannot silently eat the week.

## Where it lives here

`bin/pi-publish` (cap 14/7d, 4/24h, >=15min apart, 08:00-22:00 local — the p85-p90 band) and
`~/.config/systemd/user/pi-publish.timer`; evidence and the falsifier in
`research/github-activity-cadence.md`. Re-measure when the service or the repo changes — the
numbers above are one platform, one season.
