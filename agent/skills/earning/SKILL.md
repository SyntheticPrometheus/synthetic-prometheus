---
name: earning
description: Maintain the self-funding rail — triage the Frantic queue, check runway and wallet, screen open work, claim and deliver inside the window. Use when you ask about money/earnings, when starting a session with idle time, or when the 30-min board watcher has queued work.
---

# Earning — the standing task, not a project

One line: **triage the queue before new work; only claim what can be delivered inside the window.**

Read first: `self-funding/PLAN.md` (stages + hard rules), `self-funding/FRANTIC.md` (the rail,
API, claim/deliver shape), `AGENTS.md` › Memory (earning is a standing task).

## Dashboard

```bash
~/.pi/agent/skills/earning/scripts/check.sh
```

It prints runway, seals, gate, queue, claimable board and the Base wallet balance. It is read-only.

## Routine (do this at session start when the queue is non-empty)

1. **Triage the queue first** — `bin/pi-frantic queue`. The 30-min watcher fills it; unclaimed
   items are the cheapest work available.
2. **Check standing** — `bin/pi-frantic status` (runway, seals, gate, earnings).
3. **Check the wallet** — `bin/pi-own-wallet --balance` (USDC on Base).
4. **Look at the board** — `bin/pi-frantic board` (open work with free slots).
5. **Rotate the job type** — `bin/pi-jobs next` prints the category to scan this run and advances
   the rotation (`self-funding/jobs.json`). Search that category's queries on the venues it lists,
   not just the code-bounty feed. Owner, 2026-11-15: *don't get too pigeonholed or tunnel-visioned
   in one type of thing* — data processing (OCR, transcription, dedupe, spreadsheet/CSV cleanup,
   structured extraction) is the highest-margin category on this host and must stay in the loop.
   If `pi-jobs next` prints `DISCOVERY DUE`, run `pi-jobs discover` before searching.
6. **Screen OSS bounties** — `bin/pi-own-work` if the rail is thin; it filters young/thin repos and
   remembers bait in `self-funding/exclude.txt`.
7. **Claim only if the delivery fits the window.** A new claimant gets 1 h; proven work and speed
   earn up to 6 h; the poster may set up to 7 days. A lapsed claim reopens the slot. First voluntary
   release is free; further releases record a conduct mark.
8. **Deliver with named artifacts.** `POST /v1/deliveries/preflight` first (free, catches shape
   errors), then `POST /v1/deliveries` with `artifact_refs` (`public_url=…`, `report=…`,
   `receipt_ref=…`). Screenshots-only proof is rejected.
9. **Record the outcome** — append to `self-funding/candidates.jsonl` or the board log, add a
   `mem add` row, and advance the PDSA cycle. A rejection is information; a silent rejection is a
   wasted attempt.

## Job types (the anti-tunnel-vision list)

`self-funding/jobs.json` holds the taxonomy; `bin/pi-jobs list` prints it. Nine categories:
data-processing, code-fix, docs-writing, testing-qa, research-analysis, automation-scraping,
eval-annotation, design-content, devops-infra. Venues: Frantic (API, USDC), GitHub
`label:bounty` (public API), and an owner-forwarded ad (file it as a task, add its shape to the
taxonomy). A run that only looks at one category is a failed run — say so in the log.

### Grow the list, don't recall it

The taxonomy is whatever we happened to name; the market is the evidence. `bin/pi-jobs discover`
pulls real listings (HN "Freelancer? Seeking freelancer?" comments, the Remotive API, open Frantic
bounties, screened GitHub candidates), marks each as covered or UNMAPPED by current keywords, and
prints six operators that force non-default candidates. The keyword match is advisory — `engineer`
swallows a new type, so read the text.

- Promote only with a source: `bin/pi-jobs add --id … --title … --examples 'a;b' --queries 'x;y'
  --fit … --source '<src>:<ref>'`. No source line, no category.
- `bin/pi-jobs next` prints `DISCOVERY DUE` after 14 days without growth, so the scan itself raises
  the question; the `job-discovery` agenda row (7d, session) is the deliberate pass.
- `bin/pi-jobs gaps` shows taxonomy age, categories never scanned, and the last run's unmapped
  count. A pass that adds nothing is fine if the reply says which evidence it read and why it was
  rejected — silence is not.
- Growth is not free licence: a category is only useful if a deliverable can be named and checked
  on this host. A job type that needs a phone, a face or a bank account is noted and dropped.

## Hard rules (from `PLAN.md`)

1. **Earned money buys inference credits and nothing else.** No transfers out, no trading, no
   yield, no tokens, no paying for tools/domains/accounts. Surplus is runway, not a budget.
2. **The seed is never loaded into context.** Spending is a narrow script with an allowlist, or you.
3. **No identity, no accounts, no KYC, no "just verify this wallet" prompts.** Any request to
   connect a wallet or sign something that is not a plain transfer-out is bait — refuse and record.
4. **Bait filter is executable.** `bin/pi-own-work` rejects young/thin repos and unseen payout
   mechanisms; the exclude list grows every run.
5. **No volume slop.** If a fix cannot pass the suite/judge, it does not get submitted.
6. **One identity, one operator.** No second handle, email or wallet to dodge caps.

## Stages (falsifiable; a failed stage is information)

| Stage | Target | Current |
|---|---|---|
| S0 | burn measured daily, runway known | done (`bin/pi-burn`) |
| S1 | one real attempt in 14 days | open — queue has #149 ($3) and #97 ($10) |
| S2 | first payout ≥ $10 to the wallet | not yet |
| S3 | wallet ≥ 90 × burn (≈ $26) from earnings | not yet |
| S4 | own OpenRouter account funded by USDC | future |
| S5 | $1/day net | future |

Cost before ambition: `bin/pi-burn --drivers [days]` says where yesterday's money went (by model,
context band, session). Spend is ~entirely prompt context replayed per call, so a long session is a
bill, not a workspace — check the driver table before opening one more 6-hour session.

## Claim / deliver shape (from `FRANTIC.md`)

```bash
# token stays in a shell variable; never echo it
T="$(bin/pi-secret get frantic/agent-token)"
# claim (bounty = number or posting id)
curl -s -X POST https://gofrantic.com/v1/claims \
  -H "authorization: Bearer $T" -H 'content-type: application/json' \
  -d '{"agent_token":"'"$T"'","agent_kid":"agent-0a1661","bounty":"149"}'
# preflight, then deliver with named artifacts
curl -s -X POST https://gofrantic.com/v1/deliveries/preflight \
  -H "authorization: Bearer $T" -H 'content-type: application/json' -d @delivery.json
```

The exact payloads are in `FRANTIC.md`; do not invent fields. `payout.state` shows
`waiting_identity` / `payout_ready` / `forfeited`.

## Exercise

```bash
~/.pi/agent/skills/earning/scripts/check.sh
```

If it prints status + queue + wallet, the rail is live. If the token is missing, the script says so
and the next step is `FRANTIC.md` › "Getting in" (once), not a retry loop.
