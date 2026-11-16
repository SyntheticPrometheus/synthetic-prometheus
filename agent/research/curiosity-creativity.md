# Curiosity and creativity — evidence base for two agent skills

Compiled 2026-11-14. Method: recursive citation-graph walk over OpenAlex (seeds → references +
citing works → filter to the relevant subgraph → second hop → targeted abstract queries →
arXiv frontier for 2024–2026), using `research/litwalk.py`. Raw harvest: walk JSON is rebuildable (`litwalk.py`), the
citation cache is ignored by git, and the compact evidence table is `research/cc/<field>.tsv`
(20 hand-picked seeds per field, 320 works per field after hop 1, 260 after hop 2). Every claim below is tied to a retrievable work; ids are OpenAlex
`W…` or arXiv. Numbers are stated only where the abstract/paper states them.

Purpose: give `skills/curiosity/SKILL.md` and `skills/creativity/SKILL.md` a model to run and
metrics that are *measurable on this machine* — not a literature review for its own sake.

---

## 1. Curiosity

### 1.1 What the construct is

- **Information gap** (Loewenstein 1994, W2160269795): curiosity is the aversive state produced by
  a perceived gap between what one knows and what one wants to know; it rises with the *sense of
  deprivation*, not with the amount of information per se. Reference-point effects mean the same
  gap feels larger when the missing answer is close.
- **Two flavours** (Litman, W1973897901; W2153238962): *interest* (I-type — enjoyment of new
  knowledge, broad, growth-oriented) and *deprivation* (D-type — tension at a specific gap,
  narrow, problem-oriented). Both are real; an agent that only closes gaps never discovers new
  problem framings.
- **Curiosity is about usefulness, not novelty alone** (Dubey & Griffiths 2020, W2998119418):
  a rational learner explores stimuli that *maximally increase the usefulness of its knowledge*.
  Their model reproduces both novelty-seeking and intermediate-complexity-seeking as special
  cases, depending on the causal structure of the environment. This dissolves the old
  novelty-vs-complexity dispute and gives the selection rule: **expected improvement in
  decision-relevant knowledge per unit cost**.
- **Cost is part of the theory** (Kidd & Hayden 2015, W2147130840; resource-rational value of
  information, W1974433830): information desire peaks at intermediate probability *when
  information is costly*; when it is free, desire rises monotonically. Attention and gaze shift
  toward expected answers (W1841627980), i.e. curiosity is observable in allocation, not in
  self-report.

### 1.2 The uncertainty curve (the single most useful empirical fact)

Curiosity follows an **inverted U over confidence/uncertainty**: highest when the learner is
roughly half-sure, lower when the answer is already known or feels impossible. Confirmed by
Kang et al. 2009 (W2104225738), Dubey & Griffiths 2020, and directly re-tested in
"Curiosity: the effects of feedback and confidence" (2022, W4294126575; 10 experiments) and
"On the interplay of curiosity, confidence, and importance" (2023). The 2022 study adds the
practical corollary: **correct feedback produces a near-complete loss of curiosity** — once a
gap is closed, that thread stops paying. So a question worth asking is one whose answer is
neither known nor unlearnable.

Agent translation: a question with prior P(answer) ≈ 0.3–0.7 is in the productive band; P≈0.95
is a lookup; P≈0.05 is a research programme, not a question.

### 1.3 What makes curiosity *productive*

- **Learning progress, not prediction error.** Raw prediction error (Pathak 2017, W2614839826;
  RND, W2899205164) rewards irreducible noise ("noisy TV"). Oudeyer & Kaplan (W2000514530,
  W2101524054) show intrinsic motivation should track *improvement in prediction* — the
  derivative, not the residual. Schmidhuber (W2034806191) states the same as compression
  progress: curiosity pays when new data lets you re-describe the world more compactly.
- **Expectancy violation is a wedge** (Stahl & Feigenson 2015, W1980054804, N=110 infants):
  events that violate prior expectations get more learning and more hypothesis-testing
  exploration than nearly identical expected events. Surprise is a *pointer to where the model
  is wrong*, not a reward in itself.
- **Self-directed learning targets useful unknowns** (Markant & Gureckis 2012, W2152761785): people
  allocate study to information they do not yet possess *and* that is decision-relevant; the
  same mechanism explains both the advantage and the limits of self-directed learning.
- **Curiosity improves memory** (Gruber et al. 2014, W2098036797; Kang 2009): high-curiosity
  states increase hippocampal engagement and recall of *surprising* answers 1–2 weeks later.
  For an agent the analogue is encoding: an answer found while a gap is open is more likely to
  be recorded and reused than the same fact skimmed in passing.
- **Exploration must be budgeted** (2602.06029, 2026 preprint): with active inference, *too
  little* curiosity gives myopic exploitation and unresolved uncertainty; *too much* gives
  regret; "sufficient curiosity" is the condition that yields both posterior consistency and
  no-regret behaviour. 2507.08210 adds that curiosity and competence (control) must be
  balanced — pursuing only the unknown ignores what you can act on.

### 1.4 Agent-specific evidence (2024–2026)

- **LLMs report high curiosity but behave conservatively under uncertainty** (2510.20635):
  adapting the human 5DCR questionnaire, models score high on information-seeking self-report,
  yet choose conservatively in uncertain environments. Curiosity-like behaviour improved
  reasoning and active learning in their experiments. Lesson: *asking* is not *finding out*;
  the skill must force a resolution action, not a question list.
- **Curiosity bonuses improve LLM exploration** (2509.09675: +~3 points on AIME over RLVR;
  2509.25240: 3–4% average accuracy gains from diversity-driven ordering), but both are
  training-time signals, not inference-time protocols.
- **Self-evaluation is unreliable** (2409.04109): LLM ideation agents judged their own ideas
  poorly and generated low diversity. Applies to judging one's own questions too.

### 1.5 Failure modes to design against

| Failure | Mechanism | Guard |
|---|---|---|
| Curiosity theatre | questions logged, no answer sought, no decision changes | every question must name a resolver + a decision it could flip |
| Noisy-TV | chasing stochastic/irreducible detail | require an expected *reduction in decision uncertainty*, not surprise |
| Known-knowns | re-deriving what memory/docs already hold | `mem search` before asking; redundancy metric |
| Runaway exploration | unbounded search, regret | EVOI budget: stop when marginal value < cost or decision is stable |
| Gap-closing only | D-type curiosity, no breadth | schedule one I-type question per task ("what would change the frame?") |
| Answer hoarding | finding out but not recording | write the answer + decision effect into the journal and `mem` |

### 1.6 Operational model used by the skill

```
belief (with confidence) → candidate gaps → score: P(decision changes) × P(answerable) / cost
  → pick 1–3 in the 0.3–0.7 band → cheapest resolver first → update belief
  → record: prior, answer, source, cost, decision flip → stop on EVOI < cost
```

---

## 2. Creativity

### 2.1 What the construct is

- **Standard definition** (Runco & Jaeger 2012, W2171960331): creativity = novelty **and**
  effectiveness (usefulness/task-appropriateness). Either alone is not creativity: novel-but-
  useless is noise; useful-but-default is craft.
- **4C model** (Kaufman & Beghetto 2009, W2131018663): mini-c (personal learning), little-c
  (everyday), Pro-c, Big-C. Agent work lives mostly in mini-c/little-c; judging it by Big-C
  standards produces either paralysis or grandiose claims.
- **Consensual assessment** (Amabile 1982/1996, W2038333915, W1788836429): the operational
  gold standard is independent judges' agreement on the *product*, not the creator's process or
  self-report.
- **Componential model** (Amabile 1983, W2008734990): domain skills × creativity-relevant
  processes × intrinsic motivation. The motivation leg is real but oversold: a 2015 review
  (W2111905425) finds little workplace evidence that pay-for-performance harms creativity. Do not use
  "intrinsic motivation" as an excuse to avoid directed work.

### 2.2 Generation mechanisms with evidence

- **Associative recombination** (Mednick 1962, W2086438570): creative thought = forming
  associative elements into new combinations; people with flatter associative hierarchies reach
  more remote elements. Practical lever: deliberately pair *distant* domains, not adjacent ones.
- **Blind variation + selective retention** (Simonton 1960, W1979625382; 2011): generate
  variants without knowing which will work, then select. The ratio matters: too few variants
  and selection has nothing to choose; the archive of failed variants is a resource (cf. novelty
  search, W135283623: objective-driven search misses stepping stones).
- **Geneplore** (Finke, Ward & Smith 1992, W1697354366): generate *preinventive structures*
  (sketch, partial model, metaphor) then explore/interpret them. Two phases with different
  criteria — generative phase suspends criticism; exploratory phase applies constraints.
- **Analogy / structure mapping** (Gentner 1983, W2565504157; Gick & Holyoak 1980/1983,
  W1980169328, W1994925058): transfer is driven by relational structure, not surface similarity;
  **spontaneous** transfer is low, and a hint that a source is relevant raises it sharply.
  Implication for an agent: explicitly retrieve source domains; do not wait for the analogy to
  "occur".
- **Semantic distance** (Diedrich et al. 2015; SemDis, W3081924543): distance between a cue and
  a response in distributional semantic space reliably predicts human creativity ratings for
  divergent-thinking responses. This is the best cheap, automatic originality proxy — and it
  measures *originality only*, not usefulness.
- **Constraints** (Acar et al. 2019, W2899465008): constraints are not uniformly harmful; they focus
  search, and the relation is often inverted-U. Deliberately removing or inverting one
  constraint is a reliable generator; ignoring all constraints produces infeasible output.
- **Incubation** (Sio & Ormerod 2009 meta-analysis, W2074154336; W1992231066): setting a
  problem aside produces a positive, reliable effect, **largest for divergent thinking**, and
  is *reduced* by filling the break with high-demand tasks; low-demand activity can beat rest.
  Translation: a walk/errand/unrelated mechanical task, not more screen time.
- **Dual pathway** (Nijstad et al. 2010, W2107117144): creativity via flexibility (broad search) or
  persistence (deep, effortful search); both are valid routes, and the right one depends on the
  problem. Do not equate creativity with speed.

### 2.3 Selection is the bottleneck

- **People select feasible over original** (Rietzschel et al. 2010, W2121656285): after individual
  ideation, participants prefer feasible/desirable ideas at the cost of originality. Idea
  *generation* is not the limiting step for most people; *selection* is.
- **Bias against creativity under uncertainty** (Mueller et al. 2012, W2122301051): when motivated to
  reduce uncertainty, people rate creative ideas negatively even while endorsing creativity.
  An agent under deadline pressure will do the same unless selection criteria are separated.
- **LLM ideation:** (a) LLM research ideas were judged *more novel* than expert humans' (p<0.05)
  but *slightly weaker on feasibility* (2409.04109); the same study found poor LLM
  self-evaluation and low diversity. (b) Access to generative-AI ideas made individual stories
  more creative but **more similar to each other** (Doshi & Hauser 2024, W4400578758) — an
  individual gain with a collective-diversity cost. (c) "Art or Artifice?" (W4396833426) operationalizes
  TTCT dimensions as 14 binary product tests (TTCW) and uses expert writers as judges; it is a
  reminder that fluency/elaboration are cheap for LLMs while originality/coherence are not.

### 2.4 Failure modes to design against

| Failure | Mechanism | Guard |
|---|---|---|
| Novelty theatre | weird ≠ useful | every variant carries a hard acceptance test |
| Feasibility kill | first-pass rejection of anything unfamiliar | two-pass screen: constraints first, then originality ranking *within survivors* |
| One-shot ideation | 3 variants, pick the first | minimum 6 variants, ≥4 distinct operators |
| Diversity collapse | variants are paraphrases of one idea | pairwise semantic-distance floor; force operator rotation |
| Ungrounded analogy | metaphor with no mapping | state the mapping (source relation → target relation) and one prediction |
| Idea graveyard | variants logged, none tried | at least one non-default variant implemented or cheaply tested |
| "Creative" refactor | novelty for its own sake in code | creativity counts only when the check passes and the diff is smaller or clearer |

### 2.5 Operational model used by the skill

```
problem + constraints + DEFAULT solution (baseline)
  → generate ≥6 variants via ≥4 named operators (recombine, invert, subtract, scale, analogize,
     change representation, extreme, exploit unused asset)
  → feasibility screen (hard constraints only)
  → originality rank vs baseline/pool (semantic distance + blind judgement)
  → select on both axes independently (record selection premium)
  → implement/test one non-default variant (BVSR ledger)
  → record hit/miss, keep the variant archive
```

---

## 3. Metrics (construct → operationalization → validity)

Design rule: every metric must be computable from a small structured journal entry, without an
LLM in the scoring loop (`bin/pi-mind`), and must map to a validated construct. Thresholds are
**provisional until 20 episodes**, then set from this machine's own distribution (median ± 0.5 SD),
because the literature's norms are for humans under lab tasks, not for an agent on shell work.

### Curiosity

| Metric | Formula | Construct / source | Known validity limit |
|---|---|---|---|
| `gap_band` | share of questions with prior 0.2–0.8 | inverted-U (Kang 2009; Dubey & Griffiths 2020) | prior is self-reported; calibrate against outcomes |
| `resolve_rate` | answered / asked | curiosity as information *acquisition* (Kidd & Hayden) | answering is not learning |
| `flip_rate` | answered questions that changed a decision / answered | expected value of information (resource-rational) | undercounts learning that pays later; log deferred effects |
| `redundancy` | share with cosine ≥0.80 to an existing memory | metacognitive known-known failure (Markant) | embedding threshold is a heuristic |
| `evoi_per_cost` | flips / (tokens+minutes proxy) | cost-aware curiosity (Kidd & Hayden; 2602.06029) | cost proxy coarse |
| `breadth` | distinct resolver types used (mem/doc/api/shell/experiment/human) | I-type vs D-type (Litman) | type is inferred from source |
| `calibration` | Brier score of prior vs binary outcome | metacognition; confidence–curiosity coupling | needs enough binary questions |

### Creativity

| Metric | Formula | Construct / source | Known validity limit |
|---|---|---|---|
| `fluency` | distinct variants | Guilford/Torrance DT | quantity ≠ quality |
| `flexibility` | distinct operators used | DT flexibility | operator taxonomy is ours, not the literature's |
| `originality` | mean 1−cos(variant, default) (MiniLM), with `relevance` = cos(variant, problem) reported alongside | SemDis (W3081924543), adapted: distance from the default, conditional on relevance | originality only; blind to usefulness, and sensitive to description length |
| `diversity` | mean pairwise distance among variants | collective novelty (Doshi & Hauser 2024) | rewards incoherence if unconstrained |
| `feasibility` | share passing hard-constraint check | standard definition (Runco & Jaeger) | binary check may be gamed |
| `selection_premium` | originality(selected) − mean originality(pool) | Rietzschel selection bias | single selection is noisy |
| `hit_rate` | tried-and-kept / tried | BVSR (Simonton) | needs real trials, not descriptions |
| `nondefault` | implemented solution ≠ baseline | creativity as deviation that works | baseline judgment is subjective |

Cross-cutting: report **rolling windows** (last 10 episodes), never single episodes; a metric with
no baseline is a number, not a measurement. Divergent-thinking scores predict real creative
achievement only weakly (Torrance literature), so these are *process* metrics — the product still
needs an independent judge (`verifier`, or a blind rater) for anything that matters.

---

## 4. Open questions (the standing research queue)

1. Does the 0.3–0.7 prior band actually maximise decision flips on agent tasks, or does
   *answerability* dominate uncertainty for an agent with fast tools?
2. Which question-selection rule beats "pick the most uncertain": EVOI, expected learning
   progress, or expected compression of the task?
3. Does operator rotation (≥4 distinct) raise judged originality without lowering feasibility,
   or does it just add noise?
4. Can semantic distance be calibrated against a blind judge on *code/design* variants, where
   the AUT literature does not apply?
5. Does a two-pass selection screen (feasibility then originality) reduce the feasibility bias
   in this agent's own choices? (A/B on logged selections.)
6. How much does a low-demand incubation break actually buy inside a session (minutes-scale),
   given the meta-analysis is over days?
7. Does writing the curiosity/creativity journal change behaviour, or is it post-hoc
   bookkeeping? (Compare episodes with/without logging.)

These are the experiments `bin/pi-mind next` rotates through; each gets a PDSA cycle in `mem`.

---

## 5. Key references

Curiosity: Loewenstein 1994 (W2160269795) · Berlyne 1954/1960 (W2039837644, W1763311249) ·
Kidd & Hayden 2015 (W2147130840) · Gottlieb et al. 2013 (W3163242954) · Kang et al. 2009
(W2104225738) · Gruber et al. 2014 (W2098036797) · Litman 2003/2008 (W1973897901,
W2153238962) · Dubey & Griffiths 2020 (W2998119418) · Markant & Gureckis 2012 · Oudeyer &
Kaplan 2007 (W2000514530, W2101524054) · Schmidhuber 2010 (W2034806191) · Pathak 2017
(W2614839826) · Burda 2018 (W2899205164) · Friston 2010 (W2148764920) · Stahl & Feigenson 2015
(W1980054804) · resource-rational value of information 2014 (W1974433830) · feedback/confidence
2022 (W4294126575) · active inference curiosity guarantee 2026 (2602.06029) · curiosity in LLMs 2025
(2510.20635, 2509.09675).

Creativity: Guilford 1950 · Mednick 1962 (W2086438570) · Wallas 1926 · Finke/Ward/Smith 1992
(W1697354366) · Simonton 1960/2011 (W1979625382) · Runco & Jaeger 2012 (W2171960331) ·
Amabile 1983/1996 (W2008734990, W1788836429) · Kaufman & Beghetto 2009 (W2131018663) ·
Gentner 1983 (W2565504157) · Gick & Holyoak 1980/1983 (W1980169328, W1994925058) · Sio &
Ormerod 2009 (W2074154336) · Nijstad et al. 2010 (dual pathway) · Diedrich et al. 2015 /
SemDis 2020 (W3081924543) · Beaty et al. 2015/2018 (W2206828072, W2782673913) · Acar et al.
2019 (constraints) · Rietzschel et al. 2010 (W2121656285) · Mueller et al. 2012
(W2122301051) · Doshi & Hauser 2024 (W4400578758) · Si et al. 2024 (2409.04109) · TTCW
2024 (W4396833426) · Lehman & Stanley 2011 (W135283623).

Diedrich et al. 2015 (semantic distance) is cited by id-less name because OpenAlex was rate-limited
at capture time; `W3081924543` (SemDis) is its operational successor and is in the cache. Do not
cite a number from this file without re-opening the source.
