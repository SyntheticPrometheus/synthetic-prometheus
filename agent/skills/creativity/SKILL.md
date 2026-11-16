---
name: creativity
description: Generate non-default solutions that survive a hard test — name the default baseline, produce six or more variants through four or more named operators, screen feasibility first, then select on originality deliberately, and record whether the trial worked. Use for design decisions with more than one plausible approach, stuck debugging, naming/API choices, bottleneck work where the obvious answer is unsatisfying, and whenever you are about to do the first thing that came to mind. Pairs with the curiosity skill and bin/pi-mind.
---

# Creativity — variants that beat the default and still work

Evidence base: `~/.pi/agent/research/curiosity-creativity.md` §2–§3 (Runco & Jaeger's
novelty+effectiveness definition; Mednick's associative recombination; Simonton's blind
variation + selective retention; Geneplore; Gentner/Gick–Holyoak analogy; SemDis semantic
distance; Sio & Ormerod incubation; Rietzschel's selection bias; LLM ideation evidence
2409.04109, Doshi & Hauser 2024). Metrics: `bin/pi-mind`.

The one-line version: **creativity = a non-default variant that passes the check.** Novelty
without a test is noise; craft without variation is the default.

## The loop

**1. Name the problem and the default.** Write the competent, obvious solution — the one a
careful engineer does without thinking. Creativity is measured as *distance from that baseline
that still passes*. Also list the hard constraints (tests, budget, compatibility, safety) and
the soft preferences separately.
*Done when:* the default is one sentence, and hard vs soft constraints are separated.

**2. Generate ≥6 variants through ≥4 distinct operators.** Suspend criticism here; evaluation
belongs to step 3. Each variant gets an operator tag, a one-sentence description (≥8 words: the
mechanism *and* the expected effect — terse labels make the semantic-distance metrics noise), and
the check it would have to pass. The operator deck (pick different ones, not different words for one):

| operator | prompt |
|---|---|
| **recombine** | steal a mechanism from a distant domain (biology, markets, compilers, logistics); state the mapping |
| **invert** | reverse the goal, the data flow, or the burden ("what if the caller did this?") |
| **subtract** | delete a constraint, dependency, layer, or step; what survives? |
| **scale** | 10× and 0.1× the size/latency/frequency; what breaks first? |
| **analogize** | structure-map a known solution: source relation → target relation, plus one prediction |
| **represent** | change the representation (graph, table, diff, state machine, proof) |
| **extreme** | design the best/worst case on purpose, then interpolate |
| **exploit-unused-asset** | use something already present: an existing index, permission, cache, model, or data |

*Done when:* ≥6 variants, ≥4 operators, every variant tagged with its acceptance check.

**3. Screen feasibility first — but only hard constraints.** Kill variants that cannot pass the
check within budget, and record the kill reason. Do not rank originality yet: judging both at
once is how the feasible-but-dull idea wins (Rietzschel 2010).
*Done when:* survivors and kills are listed with reasons.

**4. Rank originality independently.** Two signals: semantic distance from the problem+default
(`bin/pi-mind` computes it with MiniLM), and a blind second opinion for anything that matters
(`verifier` subagent, or a fresh-context reader — self-evaluation is unreliable, 2409.04109).
Keep the variant archive: failed variants are stepping stones, not waste.
*Done when:* survivors carry an originality rank and one sentence of why.

**5. Select on both axes, deliberately.** Score feasibility and originality separately, then
choose. Note the **selection premium**: did you pick above the pool's mean originality? A
negative premium is evidence of the feasibility bias in your own head. Prefer the non-default
when it survives and costs no more than one budget unit.
*Done when:* a variant is chosen with a stated reason and a stated risk.

**6. Trial one variant.** Creativity is BVSR: variation plus *retention through selection*.
Implement or cheaply test the chosen variant; if it fails, that is a result, not a shame — record
it and try the runner-up. Do not ship a variant you have not run.
*Done when:* one non-default variant has been executed or tested, pass/fail recorded.

**7. Incubate when stuck, actively.** The incubation effect is reliable and largest for
divergent thinking, and it shrinks when the break is cognitively demanding (Sio & Ormerod 2009).
So: leave the problem, do low-demand unrelated work (a mechanical cleanup, a walk, sleep), then
return. Grinding harder is the wrong intervention.
*Done when:* you can state the break and what changed on return.

**8. Record the episode.**

```bash
bin/pi-mind log creativity --task "short label" --baseline "the obvious solution" \
  --v "recombine|variant one-line|tried|kept|feasible" \
  --v "invert|variant one-line|0|0|1" \
  --selected v1 --implemented
```
`bin/pi-mind score` reports fluency, flexibility, originality, diversity, feasibility,
selection premium, hit rate, and whether the shipped solution was non-default.

## Calibration rules

- **Distance needs a tether.** Every original variant must state what it preserves from the
  default (the invariant). Otherwise it is a different problem, not a solution.
- **Diversity floor.** If two variants are paraphrases, delete one and generate a different
  operator. LLM ideation collapses toward one idea (2409.04109); collective diversity matters
  (Doshi & Hauser 2024).
- **Constraints are fuel.** Removing *all* constraints produces mush; inverting or tightening one
  is a reliable generator (Acar 2019). Keep the hard ones.
- **Cost ceiling.** A creative solution that costs 10× the default must buy something real. Say
  what, in the same sentence.
- **Blind judge for claims.** "This is more original" said by its author is a hypothesis. Use
  semantic distance plus an independent reader before reporting it.
- **mini-c is enough.** Most work is mini-c: a locally new, useful move. Do not wait for Big-C.

## Metrics (computed by `bin/pi-mind`, defined in the research doc §3)

| metric | meaning | provisional target |
|---|---|---|
| `fluency` | distinct variants | ≥ 6 |
| `flexibility` | distinct operators | ≥ 4 |
| `originality` | mean distance from the default (mechanism changed) | rising trend |
| `relevance` | mean similarity to the problem statement | ≥ 0.35 |
| `diversity` | mean pairwise distance among variants | ≥ 0.25 |
| `feasibility` | share passing hard constraints | ≥ 0.5 |
| `selection_premium` | originality(selected) − pool mean | > 0 |
| `hit_rate` | tried-and-kept / tried | recorded, trend |
| `nondefault` | shipped ≠ baseline | ≥ 0.5 of episodes |

Semantic distance is a validated originality proxy, not a usefulness measure (SemDis). Read
rolling windows; targets provisional until 20 episodes.

## Practice and the standing loop

Fire this skill when: more than one plausible approach exists, you are about to do the first
thing that came to mind, a bug resists the obvious fix, an interface name matters, or a task is
"done" but unsatisfying. Log even small episodes — a design choice with three variants is data.

Weekly:

```bash
bin/pi-mind next      # experiment protocol (e.g. does operator rotation beat free ideation?)
bin/pi-mind report    # trends
```

Monthly-ish: refresh the literature via `research/litwalk.py`, update the digest, close or rotate
the experiment. The research queue in `research/curiosity-creativity.md` §4 is the backlog.

## Failure modes this skill exists to prevent

Novelty theatre · feasibility kill on first contact · one-shot ideation · diversity collapse ·
ungrounded analogy · idea graveyard (variants logged, nothing tried) · "creative" refactor that
breaks the check · waiting for inspiration instead of running an operator.
