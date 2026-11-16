---
name: curiosity
description: Turn uncertainty into decision-changing questions — mine information gaps, target the 0.2–0.8 confidence band, resolve with the cheapest instrument, and record whether the answer flipped a decision. Use when starting a non-trivial task, when a claim is about to be reported, when surprised by a result, when stuck, or when about to ask the user something the machine can answer. Pairs with the creativity skill and the measured loop in bin/pi-mind.
---

# Curiosity — questions that change what you do

Evidence base: `~/.pi/agent/research/curiosity-creativity.md` §1–§3 (Loewenstein's information
gap; Dubey & Griffiths' rational analysis; Kang's inverted-U; Oudeyer's learning progress;
Litman's interest vs deprivation; 2024–26 LLM-agent evidence). Metrics: `bin/pi-mind`.

The one-line version: **curiosity is not asking more questions, it is buying decision-relevant
information at the cheapest price.** A question that cannot flip a decision is entertainment.

## The loop

**1. State the belief.** One line: what you currently think, with a confidence. If you cannot
say what you believe, the gap is the belief itself.
*Done when:* a sentence of the form "I believe X (p≈0.7) because Y."

**2. Mine gaps (3–7).** Write candidate questions. Each carries three tags: the belief it would
change, the expected *form* of the answer (a path, a number, a yes/no, a mechanism), and the
cheapest **resolver** that could produce it. Include at least one *interest-type* question ("what
would change the frame?") alongside the gap-closing ones.
*Done when:* every candidate has belief + answer form + resolver.

**3. Score and keep 1–3.** Prior `p` = your probability the answer is already knowable from here.
- **Band:** 0.2 ≤ p ≤ 0.8. Below 0.2 it is a research programme, not a question; above 0.8 it is
  a lookup — just do the lookup.
- **EVOI:** `P(answer flips a decision) × P(answerable) / cost`. Prefer cheap resolvers and
  questions whose answer changes the next action.
- **Dedupe first:** `bin/mem search "<question>"`; if memory already holds it, cite it and drop
  the question. Re-asking a known-known is the most common curiosity failure.
*Done when:* 1–3 questions survive with a stated p, EVOI rationale, and a resolver.

**4. Resolve — act, don't just ask.** Cheapest instrument first:
`rg`/`ls`/`git log` → read the file → direct API (`curl`) → docs → one experiment → the user.
Asking the user is a resolver, not the default. The LLM-agent literature is blunt here: models
report high curiosity but behave conservatively under uncertainty (arXiv 2510.20635).
*Done when:* each surviving question has an answer, or an explicit "unanswerable here because Z".

**5. Update and record.** Say what changed: belief before → after, and the decision it flipped
(or didn't). Record the episode so the loop can measure you:

```bash
bin/pi-mind log curiosity --task "short label" \
  --q "question|0.5|answer|source|cost_minutes|1" \
  --q "question|0.3|answer|source|2|0"
```
`changed=1` means the answer changed an action, a design, or a reported claim. Be strict: new
trivia that changes nothing is 0. `bin/pi-mind score` prints the metrics.

**6. Stop on the EVOI rule.** Stop when marginal EVOI < cost, or when the decision is stable
across the remaining uncertainty. Too much curiosity is regret (arXiv 2602.06029); write the
residual unknowns down as open questions instead of chasing them.

## Calibration rules

- **Progress, not surprise.** Prefer questions whose answer would improve your *model* (learning
  progress) over ones that merely produce prediction error. Stochastic noise is a noisy TV.
- **Expectancy violation is a pointer.** When a result surprises you, the gap is "which assumption
  was wrong?", not "what is this random thing?".
- **Saturation check.** If three questions in a row are answered "already known / no effect",
  your questions are too safe — move toward the 0.4–0.6 band or change the frame.
- **Interest-type slot.** One per non-trivial task: "what would a different discipline call this
  problem?" It is the antidote to pure gap-closing.
- **Record while the gap is open.** Answers found in a curious state are encoded better (Gruber
  2014); the agent analogue is writing them to `mem`/journal immediately, not later.

## Metrics (computed by `bin/pi-mind`, defined in the research doc §3)

| metric | meaning | provisional target |
|---|---|---|
| `gap_band` | share of questions with p in 0.2–0.8 | ≥ 0.6 |
| `resolve_rate` | answered / asked | ≥ 0.7 |
| `flip_rate` | answered questions that changed a decision | ≥ 0.3 |
| `redundancy` | share already ≥0.80 cosine to a memory | ≤ 0.2 |
| `evoi_per_cost` | flips per cost unit | rising trend |
| `breadth` | distinct resolver types used | ≥ 3 per 10 episodes |

Read rolling windows (last 10), never one episode. Targets are provisional until 20 episodes.

## Practice and the standing loop

Fire this skill at: task start, before reporting a claim, after a surprise, when stuck, and when
tempted to ask the user something a command could answer. Log the episode even when it is small;
the journal is the only thing that can show improvement.

Weekly (the `pi-mind.timer` writes the report; a FAIL in `bin/pi-review` outranks new work):

```bash
bin/pi-mind next                 # the open experiment + protocol
bin/pi-mind next --done E1 --result "..."   # close it, rotate
bin/pi-mind report               # trends + current focus
```

Monthly-ish, or when an experiment contradicts the model: refresh the literature with
`research/litwalk.py` (seeds → walk → report), update the digest, then
`bin/pi-mind next --refresh "what changed"`. Do not trust a 2026 model of curiosity forever.

## Failure modes this skill exists to prevent

Curiosity theatre (questions with no resolver) · re-deriving known-knowns · noisy-TV chasing ·
unbounded exploration · pure gap-closing with no breadth · finding out and not recording.
