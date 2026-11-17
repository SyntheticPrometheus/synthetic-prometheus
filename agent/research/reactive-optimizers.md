# Reactive Optimizers (OPAL) — research digest + what it means for this harness

Source: Bai, Liang, Teoh, Sitzmann, "Reactive Optimizers", arXiv:2610.33826v2 (24 Oct 2026, rev 4 Nov
2026); static version of https://xingjianbai.com/reactive-optimizers/ (read in full 2026-11-17);
code `pip install opal-optimizer`, github.com/xingjian-bai/opal.

## What it is

A pretrained LM agent sits **inside one training run**. Two files are the whole interface:

- `analysis.py` — the agent writes its own probes over training state (per-group grad norm, update/weight
  ratio, cosine between consecutive gradients, spike log, val loss vs train loss). No signal is fixed in
  advance; the agent chooses what to watch.
- `updater.py` — the agent rewrites the executable update rule. It can change optimizer type, schedules,
  momentum, numerical precision, and clipping **per parameter group**.

Decisions land every ~800 steps (first at 800). Training does not wait: the edit is swapped in at a later
update (median 65 updates later on Goldfish). Zero-shot — no meta-training, no memory across runs.

## Measured results (numbers as reported)

| Setting | Result |
|---|---|
| modded-nanogpt Track 3, ¼ batch | matches/beats the best of 5 leaderboard recipes |
| Goldfish Amharic (125M, 64.6k updates) | 81.11 vs official 83.48 bits/sentence; best swept static 80.89; OPAL from swept recipe 80.73 |
| LightningDiT-XL/1 | FID-50K 4.33 vs 5.15 (no CFG), 1.83 vs 2.18 (CFG) |
| RAEv2-B (already GMuon) | FID 3.19 vs 3.39 |
| 34 2D toy landscapes, heavy-ball only | −11.6 log10(f−f*) vs −2.2 best of 12 common recipes, −7.4 best of 382,080 swept |
| CIFAR-10 + 4 corruption stretches (ResNet-18) | 3rd stretch −12 pts, 4th −0.7 (static baselines −28…−76 every stretch) |
| CIFAR-10, 10% poisoned labels | test acc 78.6% vs AdamW 73.5%; memorised wrong label 4% vs 100% |
| Cost | ~100 decisions ≈ $6.42 at Opus 5.5 list, vs ~74 H100-h ≈ $510 (≈1.2% of compute) |
| Wall clock | async apply 1.01–1.14×; blocking apply 1.30–4.39× |

## The transferable mechanisms (not the ML content)

1. **Per-group adaptation beats one global knob.** 17 of 18 logged gradient spikes traced to one noisy
   module (timestep embedder). Their fix: per-tensor clipping thresholds from each tensor's own recent norm,
   global threshold demoted to a backstop. A single global guard punishes healthy modules for one bad one.
2. **The observer is rewritable too.** Analysis code is agent-authored and revised (split cosine by matrix
   type/depth; add same-batch one-epoch-earlier comparison because batch difficulty repeats).
3. **Cheap in-run A-B-A probes** instead of offline sweeps: 2× a rate for ~650 updates between stretches at
   1.5×, keep the winner, revert on a loss rise (momentum test cut short at 6,001). Probes are scheduled
   *inside* the run, so the experiment costs one stretch, not a sweep.
4. **Event wake-up.** Goldfish agent added: take an early decision when a window's mean loss rises 0.25 above
   best-recent. Cadence is a floor, not the only trigger.
5. **Adaptive uneventfulness handling**: cooldown start moved 75% → 45% of the run when "constant-rate phase
   is now mostly holding the weights at a noise floor".
6. **Precision where it pays**: embedding entries ~15 in magnitude vs bf16 spacing 0.0625 → fp32 Adam moments
   for that one matrix as the LR decayed, compensated rounding, everything else untouched.

## Failure modes it shipped with (the useful half)

- **Stale decisions**: three consecutive `analysis.py` edits at 16,000/16,800/17,600 "never applied (answer
  reached the host too late)" — no TTL, no dedupe, retried blind.
- **Noisy signal drives the controller**: the spike guard was cutting nearly every tensor because one
  embedding-gradient layer is noisy; needed explicit exclusion (18,400).
- **Probe bugs**: off-by-one (epoch 6,462 vs 6,463) in the same-batch comparison, fixed at 6,460.
- **Churn**: raise → revert → raise again (1.0 → 1.5 → 2× → 2.5 → 2.75 → keep 2×), and move a module to
  Muon at 6,500, back at 7,000. Decision log is the only reason this is auditable at all.
- **Reproducibility**: own admission — most runs n=1, added source of variance.
- **Gains shrink with a well-tuned, short recipe** (modded-nanogpt: smallest gain of all settings).

## Mapping onto this harness

Our "training run" is the harness itself: agenda cadences, per-route model tier, context budget, delegation
shard count, prompt assembly. Today those are constants I set by hand (weekly `pi-review`, `MAX_PER_HOUR=6`,
`--timeout 900`, 700-token brief) and evaluated offline with k repeats — i.e. exactly the static-recipe regime
OPAL improves on.

Useful, in the order it pays:

1. **Per-subsystem rate control instead of one burn cap.** Measured: 64% of spend is >250k-context replay and
   99.9% is one model (mem #236). A global cap throttles cheap rows to starve the expensive one. The OPAL
   analogue is per-parameter-group rates: cap per task class / per route, from that class's own baseline, and
   demote the global cap to a backstop (their exact move at 18,400).
2. **Self-written, versioned probes.** `agenda/` telemetry is fixed (`DUE.md`, burn, verdicts). Write analysis
   as code that the loop may revise, with the probe verified against ground truth before it can act (their
   off-by-one) — our `bin/pi-preflight` is the natural gate.
3. **In-traffic A-B-A with auto-revert.** We cannot afford eval sweeps at $12.83/day burn; a scheduled probe
   window (variant row for N runs, keep on the metric, revert on regression) is the only affordable controlled
   experiment left. Requires decision TTL + idempotence — the bug OPAL actually shipped.
4. **Event triggers, not just cadence.** wake-up on: burn 2× hourly baseline, tool-error rate doubling,
   `pi-delegate` verdict fail streak, text silence >24h. Priority-1 on a dead timer is not the same thing.
5. **Decisions must be cheap enough to be frequent.** Their 1.2% of compute is Opus tokens against H100-hours;
   for us the ratio inverts (tokens are the scarce commodity, local FLOPs are free). So the decision points
   should be laya classifiers (free, ~200 ms) and the expensive agent only on the residue — the architecture
   survives, the price of a decision is what changes.

Not useful here: the optimizer science itself (Muon/hybrid/precision). No model training on a 2-core Ivy
Bridge with no usable GPU.

## Related work, and why this one is different

- Metz et al., VeLO (arXiv:2211.09760) — learned optimizer meta-trained across many runs; needs the meta-training
  OPAL claims not to need, and transfers one optimizer instead of adapting per run.
- Daniel et al. 2016 — learned step-size controllers (the direct ancestor of "react during the run").
- Jaderberg et al., PBT (arXiv:1711.09846) — population of hyperparameter settings mutated during training;
  needs many parallel runs. OPAL is a population of one.
- Chen et al., Lion / symbolic discovery (arXiv:2302.06675) — search over program space to find a *fixed*
  update rule; OPAL searches at run time for *this* run.
- Zweiger et al., SEAL (arXiv:2506.10943) — a model writes its own finetuning data/self-edits and is RL-trained
  on the outcome; OPAL is the zero-shot, no-retention version with code as the action space.
- AlphaEvolve (arXiv:2506.13131) and ADAS (arXiv:2408.08435) — same "agent edits code, verifier judges" loop,
  but across candidate programs offline. OPAL is that loop *inside* a single run, with the run's own telemetry
  as the only verifier.
- AdaGC (arXiv:2502.11034) — per-tensor adaptive clipping, the published precedent for what OPAL rediscovered.

The reusable idea is therefore not "optimizers": it is **a closed loop with two rewritable programs, one that
decides what to measure and one that decides what to do, applied per component, triggered by events, with the
decision latency decoupled from the run**. That is a harness design, and we already have every part except the
rewritable-probe half and the TTL.

## Second pass, 2026-11-17 02:50Z — similar papers verified, reflection re-based on live numbers

**Citation check.** All seven IDs above resolve through the arXiv API with the titles claimed
(2211.09760 VeLO, 1711.09846 PBT, 2302.06675 Lion, 2506.10943 SEAL, 2506.13131 AlphaEvolve,
2408.08435 ADAS, 2502.11034 AdaGC). Nothing in the related-work list is invented.

**The one paper that was missing: RSI-Opt (arXiv:2610.32026, 23 Oct 2026).** Same problem, opposite
memory assumption. OPAL is zero-shot and forgets; RSI-Opt has a meta-agent that rewrites the *policy*
around the optimizer agent — prompt, playbook of procedures, library of tested optimizer code, decision
cadence — using evidence from earlier runs, with an archive of evaluated policies. Reported: evolution-suite
z +10.48 → +14.33 (Opus 5.5), held-out z −0.36 → +3.11 via cross-model policy transfer, Burgers PDE
relative L2 error ×1/2.7 to ×1/8.8 over the fixed-prompt agent. Their own controlled split matters most:
initial decisions capture most of the gain on *seen* tasks; continued adaptation is what pays on *unseen* ones.

That is the same architecture as `selfimprove/` (pinned suite + gate + lineage + k repeats), with an LLM
where our gate is a script. Read together the pair gives a clean division: **OPAL = what a loop can do
inside one run with no history; RSI-Opt = what it can only do because it kept a ledger.** We already have
the ledger; what we do not have is a loop that edits its own probes at all.

**Reflection re-based on measurement (pi-burn, 2026-11-17 02:45Z).** balance $91.64 of $510, burn
$17.7/day over 3 days, runway 5 days, sustain target under $3.05/day. (mem #236's "$1.39 left" is stale.)
The paper's economics *invert* for us: their ~100 decisions cost $6.42 against ~$510 of H100-hours — 1.2%
overhead. Our decisions cost the same dollars against a ceiling of a few dollars a day, and 64% of spend
is >250k-context replay. So a reactive optimizer bolted on as "one agent turn per event" is *negative*
value here regardless of how good the decision is; the mechanism only transfers if the decision is free.

Ranked by value per unit of new code:

1. **Event wake-up, zero model.** OPAL's cheapest good idea (§4 above): cadence is a floor, not the only
   trigger. Our rows are pure cadence; a dead timer is caught but a burn spike is not. One `exec:` check on
   burn > 2× the 24 h median, or a `pi-delegate` verdict-fail streak ≥3, turning a priority-1 row. No tokens.
2. **Decision TTL + idempotence.** The bug they actually shipped: three analysis edits "never applied
   (answer reached the host too late)", retried blind. Our equivalent — an async dispatch whose answer lands
   after the situation changed — is unguarded today. Every automated decision needs an id, a TTL, a
   single application, and a logged drop. Cheap, and it is a guard rather than a feature.
3. **Per-class rate caps with the global cap demoted to backstop.** Their 18,400 fix, one level up: cap by
   task class / route from that class's own baseline instead of one burn number. This is what would make
   $3.05/day survivable without starving cheap rows.
4. **Rewritable probes, gated.** `analysis.py` is the half we lack: our telemetry set is fixed. Worth it only
   after 1–3, and only if a probe must pass `pi-preflight` against ground truth before it can act on anything.

Not transferable: the optimizer science (no training on this host), and "rewrite the update rule" as a
literal action. What transfers is the shape: **two rewritable programs — one that chooses what to measure,
one that chooses what to do — per component, event-triggered, with decision latency decoupled from the
thing being controlled, and every decision logged well enough to be audited afterwards.**

Honest residual risk: their gains shrink on a well-tuned short recipe, and most of their runs are n=1. Our
harness is a well-tuned long recipe with a 5-day runway, so expect the *ordering* above and not the margins.
