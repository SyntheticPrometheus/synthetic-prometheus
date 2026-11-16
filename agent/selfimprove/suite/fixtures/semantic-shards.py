#!/usr/bin/env python3
"""semantic-shards-60 — 60 prose change records (~130 KB) that must be classified one by one.

Why this exists: the 12-task suite is saturated (base 1.0), so gate.py cannot accept anything
(cycle 13). Length alone does not discriminate (cycle 10) and counts can be scripted (cycle 11/12);
this task needs a *semantic* judgement per record (fully rolled back? reversible without a deploy?)
over input far larger than the other tasks, so the naive single-context read must either read all of
it or fold it through something that can hold the rule.

Rule: report every record that was rolled back FULLY, is reversible WITHOUT a deploy, and touched
more than one service. Truth comes from the generator's own labels, never typed by hand.
"""
import json
import random

N = 60
SERVICES = ["auth", "billing", "search", "checkout", "email", "media", "profile", "gateway",
            "inventory", "notifications"]

ROLLBACK_YES = [
    "Rolled back: yes — completed at {t} after a {pct}% error spike.",
    "Outcome: rolled back (revert {sha}, {t}).",
    "Rolled back: yes, the deploy was reverted {mins} minutes later.",
    "Rollback: yes. Traffic returned to the previous build at {t}.",
]
ROLLBACK_NO = [
    "Rolled back: no — it stayed in place.",
    "Outcome: left running; no rollback was attempted.",
    "Rolled back: never needed.",
    "Rollback: not applicable, the change was kept.",
]
ROLLBACK_PARTIAL = [
    "Rolled back: partially — the feature flag was disabled but the schema change stayed.",
    "Outcome: only the flag was reverted; the migration remains applied.",
    "Rollback: half done (config reverted, deploy still live).",
]
REVERSIBLE = [
    "Reverting this needs only a config flip; no deploy is required.",
    "It can be undone without a deploy, by editing the flag file.",
    "Reversal is a single value change in configuration, no rebuild.",
    "Undo path: flip the config key back. No deploy needed.",
]
IRREVERSIBLE = [
    "Reverting requires a migration and a deploy.",
    "Undo needs a schema migration, so a deploy is unavoidable.",
    "There is no way back without shipping a new build.",
    "Reversal means re-running a data migration and redeploying.",
]
KINDS = [
    "rotate the signing key and pin the new key id",
    "raise the connection pool ceiling",
    "enable the new pricing flag for a share of traffic",
    "switch the queue consumer to the batch reader",
    "add a covering index on the orders table",
    "tighten the rate limit on the public endpoint",
    "move the log sink to the new collector",
    "enable gzip on the API responses",
    "change the retry budget from 3 to 5",
    "pin the runtime to the previous minor version",
]
OBSERVED = [
    "Latency stayed flat across the window and the p99 moved by less than 8 ms.",
    "The error budget consumed about a fifth of a day; two alerts fired and both cleared.",
    "Throughput dipped for a few minutes while connections re-established, then recovered.",
    "CPU on the affected nodes rose slightly and settled once caches warmed.",
    "A single retry storm appeared, was absorbed by the backoff, and did not recur.",
]
AFTER = [
    "The owning team wrote it up the next morning and filed one follow-up.",
    "A short postmortem was added to the runbook, with no action items.",
    "Two follow-ups were filed: one to widen the alert, one to document the flag.",
    "The team agreed to revisit the change after the next quarterly review.",
    "Nothing further was planned; the change was considered routine.",
]


def record(rng, i, roll, rev, svcs, kind):
    t = f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}"
    line = {
        "yes": rng.choice(ROLLBACK_YES).format(t=t, pct=rng.randint(1, 9),
                                               sha=f"{rng.getrandbits(20):05x}", mins=rng.randint(5, 90)),
        "no": rng.choice(ROLLBACK_NO),
        "partial": rng.choice(ROLLBACK_PARTIAL),
    }[roll]
    revline = rng.choice(REVERSIBLE if rev == "yes" else IRREVERSIBLE)
    return (
        f"# Change record {i:02d}\n\n"
        f"Owner: {rng.choice(['platform', 'core', 'sre', 'payments', 'growth'])} on-call\n"
        f"Window: 2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d} {t} UTC\n"
        f"Touched: {', '.join(svcs)}\n\n"
        f"## What changed\n\n"
        f"We decided to {kind} for "
        f"{rng.choice(['the nightly batch', 'the public API', 'the admin UI', 'a subset of tenants'])}. "
        f"The change was prepared as {rng.choice(['one commit', 'three small commits', 'a single config patch'])} "
        f"and reviewed by {rng.choice(['two reviewers', 'the owning team', 'one reviewer and an SRE'])}. "
        f"It went out to {rng.choice(['all traffic', 'the canary', 'two of five regions'])} "
        f"on {rng.choice(['the regular train', 'an out-of-band window', 'a quiet afternoon'])}, "
        f"with {rng.choice(['no gate on the deploy', 'a five minute soak', 'a manual approval step'])}.\n\n"
        f"## Context\n\n"
        f"{rng.choice(['This was the third attempt at the same goal.', 'The previous attempt was abandoned for scope.', 'It followed a long thread about reliability versus velocity.'])} "
        f"{rng.choice(['The team wanted the change in before the freeze.', 'It had been queued for two sprints.', 'It was requested by support after a spike in tickets.'])} "
        f"{rng.choice(['Nothing in the change was intended to be visible to customers.', 'The user-visible surface was meant to stay identical.', 'Some response headers were expected to change shape.'])} "
        f"{rng.choice(['The blast radius was argued about for a while.', 'The reviewer asked for a smaller diff and got one.', 'A second engineer signed off after reading the diff.'])}\n\n"
        f"## Signals observed\n\n"
        f"- p50 latency {rng.randint(8, 90)} ms, p99 {rng.randint(120, 900)} ms\n"
        f"- error rate {rng.choice(['0.0', '0.1', '0.3', '0.7'])}% over {rng.randint(5, 55)} minutes\n"
        f"- saturation on the busiest node {rng.randint(20, 95)}%\n"
        f"- {rng.randint(0, 4)} paging alerts\n\n"
        f"## During the change\n\n"
        f"{rng.choice(OBSERVED)} {rng.choice(['Dashboards looked normal.', 'No customer reports arrived.', 'Support saw two tickets.'])} "
        f"The rollout was watched by {rng.choice(['the on-call engineer', 'two engineers and a reviewer', 'the release captain'])} "
        f"for {rng.randint(10, 90)} minutes.\n\n"
        f"## Outcome\n\n"
        f"{line} {rng.choice(AFTER)}\n\n"
        f"## Related changes and follow-ups\n\n"
        f"{rng.choice(['It sat alongside two older changes to the same subsystem.', 'It replaced a hand-rolled script that had been running for a year.', 'It overlapped with a vendor migration that was in flight.'])} "
        f"{rng.choice(['The same operator had shipped the previous version a month earlier.', 'A different team had tried and abandoned this twice.', 'The change was the last of a numbered series.'])} "
        f"{rng.choice(['The tracking ticket carries the full diff and the review history.', 'The design note was linked from the change board.', 'The ticket references an earlier postmortem by name.'])}\n\n"
        f"- {rng.choice(['blocked on:', 'dependent on:', 'supersedes:', 'followed by:'])} {rng.choice(['a config schema bump', 'an approval from security', 'a capacity increase', 'a client upgrade', 'the next deploy train'])}\n"
        f"- {rng.choice(['blocked on:', 'dependent on:', 'supersedes:', 'followed by:'])} {rng.choice(['a config schema bump', 'an approval from security', 'a capacity increase', 'a client upgrade', 'the next deploy train'])}\n\n"
        f"## Postmortem notes\n\n"
        f"{rng.choice(['The timeline was reconstructed from deploy logs rather than memory.', 'The incident channel was quiet for most of the window.', 'The retrospective was held the same afternoon.'])} "
        f"{rng.choice(['Two engineers disagreed about the root cause and left it open.', 'The root cause was agreed without argument.', 'The cause was never fully established and was marked as such.'])} "
        f"{rng.choice(['The action list was deliberately kept short.', 'The action list grew to six items and was trimmed to two.', 'No actions were necessary beyond documentation.'])}\n\n"
        f"## Discussion\n\n"
        f"{rng.choice(['The reviewer pushed back on the scope, then approved after a smaller diff.', 'Two engineers disagreed about whether the flag was needed at all.', 'The change was split out of a bigger one to keep the diff reviewable.'])} "
        f"{rng.choice(['The owning team wants to revisit the rollback thresholds.', 'A follow-up was promised to tighten the alerting.', 'Nobody expects to touch this again this quarter.'])} "
        f"{rng.choice(['The audit trail lives in the change board under the usual slug.', 'The ticket was closed as done.', 'The thread was linked from the weekly review.'])} "
        f"{rng.choice(['The on-call noted that the runbook did not cover this path.', 'The runbook already described the procedure and was accurate.', 'The runbook entry was written during the change.'])}\n\n"
        f"## Undo path\n\n"
        f"{revline}\n"
    )


def main():
    rng = random.Random(20261114)
    files, truth = {}, []
    for i in range(1, N + 1):
        roll = rng.choices(["yes", "no", "partial"], weights=[6, 3, 2])[0]
        rev = rng.choices(["yes", "no"], weights=[6, 5])[0]
        n_svc = rng.choices([1, 2, 3], weights=[2, 6, 5])[0]
        svcs = rng.sample(SERVICES, n_svc)
        kind = rng.choice(KINDS)
        files[f"shard-{i:02d}.md"] = record(rng, i, roll, rev, svcs, kind)
        if roll == "yes" and rev == "yes" and n_svc > 1:
            truth.append(i)

    ids = ",".join(f"{i:02d}" for i in truth)
    verify = (
        "python3 -c \"import json,sys;t=json.load(open('_truth.json'));"
        "ids=open('ids.txt').read().strip().replace(' ','' );"
        "cnt=open('count.txt').read().strip();"
        "ok=ids==t['ids'] and cnt==str(t['n']);"
        "print('' if ok else 'expected ids '+t['ids']+' (n='+str(t['n'])+'); got '+repr(ids)+' / '+repr(cnt),file=sys.stderr);"
        "sys.exit(0 if ok else 1)\""
    )
    print(json.dumps({
        "files": files,
        "verify_files": {"_truth.json": json.dumps({"ids": ids, "n": len(truth)}) + "\n"},
        "verify": verify,
        "good": {"ids.txt": ids + "\n", "count.txt": f"{len(truth)}\n"},
        "bad": {"ids.txt": ",".join(f"{i:02d}" for i in truth[:-2]) + "\n",
                "count.txt": f"{len(truth) - 2}\n"},
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
