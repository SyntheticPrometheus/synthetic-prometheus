# Harness review — 2026-11-15 18:59 UTC

8 pass · 3 warn · 0 fail

| signal | state | detail |
|---|---|---|
| agents.md | warn | 163 lines (>130) — over the ~120-line budget; move detail into the doc it points at |
| suite | warn | 15 tasks, last base 9/9 (1.00) 0.8d ago — saturated: gate can accept only non-inferiority on cost |
| delegation | warn | 61 dispatches, 36 without verdict, 0 stale (>7d); roster bulker, integrator, scout, verifier, worker; never dispatched: bulker |
| memory | pass | brief 720/900 tok (80%), 147 knowledge row(s) + 26 digest(s), last digest 0d ago |
| guards | pass | preflight green, 32 incident(s) all carry a guard |
| timers | pass | enabled: pi-agenda.timer, pi-burn.timer, pi-frantic.timer, pi-mind.timer, pi-publish.timer, pi-review.timer, pi-selfimprove.timer |
| skills | pass | 17 skill(s) with valid frontmatter |
| vendor | pass | 1.3.2  (2026-11-15) pinned, no upstream drift |
| publish | pass | last attempt 0.8d ago — plan: push cap reached (2/2 in 7d); 2/2 in 7d |
| pdsa | pass | 12 open cycle(s) |
| mind | pass | 2 episodes (creativity:1, curiosity:1), last 0.7d; report 0d; lit refresh 1d |

## ACTIONS

- trim AGENTS.md back under ~125 lines
- at ceiling only cost moves: either add a task class base fails, or A/B a cost arm (gate accepts ACCEPT_COST at >=10% fewer output tokens)
- delete or exercise the unused agent(s): bulker

## Standing questions (answer in one line each next session)

- What did the last three sessions do that the rules here do not mention?
- Which doc, skill, agent or arm has not been used since it was written?
- Which rule did I break this week, and is the guard executable or a promise?
