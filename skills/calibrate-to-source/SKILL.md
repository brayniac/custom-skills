---
name: calibrate-to-source
description: Decide whether an analysis carries to a new metric or environment unchanged, and when it does not, derive the threshold it needs from A-vs-A runs you are already producing. Use before reusing any threshold, floor, or detector setting across metrics, hosts, or builds; when an analysis validated on one source is about to be pointed at another; and whenever a number is about to be written into a config file as if it were universal.
---

# Making an analysis portable

A decision procedure needs three things: a statistic, a null distribution for it,
and a threshold. The statistic can be universal. The threshold follows from the
null mechanically. **So the null is the only irreducibly source-specific part —
and a null is a fact about the source, not about the algorithm.** No procedure
supplies it from outside.

That is the whole problem, and it is smaller than it sounds: what has to be
learned is usually **one scalar**, and you get to choose where it enters.

## Step 1 — Check whether there is anything to calibrate

Many statistics are pivotal: their null does not depend on the unknowns. Those
carry to a new source unchanged and need nothing.

| Carries unchanged | Needs a local null |
| --- | --- |
| ADEV/HDEV **slope** — verified −0.496 to −0.505 across ten marginals including infinite-variance ones | ADEV **magnitude**, τ_min, the floor |
| `W1/\|Δmean\|` ratio and the quantile-band shares | W1 **magnitude** |
| coherence's `1/K` null floor | CUSUM `h`, PELT penalty |
| prewhitened CCF band | anything with "threshold" in its name |

**If your reading is a slope, a ratio, or a share, stop here.** The
`${CLAUDE_SKILL_DIR}/references/portability.md` table says what was tested and
how far it holds.

## Step 2 — Say what precision the number needs

This decides the route, and getting it backwards is the main way calibration
becomes expensive for no reason.

- **A detector threshold** tolerates ~10%. Take the cheap route.
- **A reported error bar** does not. Measure it.
- **A rare-event threshold** (99.9th percentile and beyond) is the expensive case
  and usually the wrong requirement — see step 6.

## Step 3 — Harvest the A-vs-A pairs you are already making

**Do not run new experiments for this.** `measure-performance` step 5 already
requires interleaved runs of the same configuration; four runs a side gives six
A-vs-A pairs, and those pairs *are* the null. Most labs compute them and throw
them away.

Compute your statistic between same-configuration runs, not within a run. **Never
bootstrap within a run to stand in for this** — correlated samples make that null
far too tight, the same failure as `1/√N`.

## Step 4 — Estimate the scale

The median of the A-vs-A values. This is the one number that is genuinely
source-specific, and it moves a lot: across seven sources the median W1 spanned
**560×** while the null's shape stayed inside 1.66–2.02.

Medians converge fast — 3 pairs gets ~14%, 10 gets ~7%, 50 gets ~3%.

## Step 5 — Turn the scale into a threshold

Two routes, and the choice is governed by how many pairs you have:

| Pairs | Use | Expected error |
| --- | --- | --- |
| < 10 | `median × 1.8` (the universal shape factor) | ~10% for finite-variance sources, and it **never improves** |
| ≥ 20 | the measured q95 directly | ~10% at 20 pairs, ~6% at 50, ~2% at 300 |

The constant is a bias, not a variance: more data cannot fix a shape factor that
is wrong for your source. The measured quantile converges but is noisier than the
constant's bias below about ten pairs. **Report which route you used.**

## Step 6 — Do not buy a rare-event threshold you do not need

You cannot estimate a quantile past roughly `1 − 1/k` from `k` pairs, and useful
precision wants ten times that. A 99.9th-percentile threshold measured directly
needs thousands of pairs — which no interleaving protocol produces as a
byproduct, and which is where "light" becomes "heavy".

Loosen the requirement first: a detector firing once a week is two orders of
magnitude cheaper to calibrate than one firing once a year, and is usually what
was actually wanted. Only if the rare-event threshold is genuinely required,
extrapolate with a generalized Pareto fit to the null's tail — and say that you
did, because it trades a sampling problem for a parametric assumption.

## Step 7 — Use the shape factor as a free diagnostic

Because the shape is stable for finite-variance sources, **a shape factor far
outside 1.7–2.0 is itself a finding.** Pareto α=1.5 announces itself at 3.17
before any other analysis has run.

A `q95/q50` above ~2.5 means: expect unstable magnitudes, expect to need many more
runs, and prefer the distributional tools (`compare-distributions`) over the
variance-based ones (`analyze-noise` magnitudes, blocking, structural models).

## Step 8 — Know when it goes stale, and record where it came from

Recalibrate when the host, image, workload or configuration changed; when a
deployed model's innovation variance drifts off 1 and stays there; or when the
Allan curve is still rising at your τ — **in which case the null you just measured
is already stale**, and the fix is a shorter window or a controlled variable, not
more calibration.

Carry provenance with every threshold: which source, how many pairs, which route.
A bare constant in a config file is indistinguishable from a guess six months on.

## Never

- **Never move a magnitude or a threshold between metrics or hosts.** Move the
  procedure that derives it. The scale varied 560× across sources that share a
  shape factor.
- **Never bootstrap within a run** to substitute for A-vs-A pairs.
- **Never let more data "fix" a universal constant.** It is a bias floor.
- **Never calibrate a source whose null is drifting** and call the result a
  threshold.
- **Never assume a shape factor outside 1.7–2.0 is noise.** It is the source
  telling you it has pathological tails.
- **Never treat the tables here as a substitute for measuring your own source.**
  They are synthetic, and they bound what the estimators do — not what your
  pipeline does.
