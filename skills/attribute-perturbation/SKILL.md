---
name: attribute-perturbation
description: Find what is driving a perturbation in a measurement — when it started, whether it is periodic, which other metric moves with it, and at what timescale — without manufacturing a correlation out of autocorrelated data. Use when a run is anomalous and the cause is unknown, when a metric has to be matched against candidate confounders, when a periodic artifact needs identifying, and before quoting any cross-metric correlation or calling one signal stronger than another.
---

# Attributing a perturbation

`analyze-noise` characterizes one series against itself. This one asks the next
question: **what is it moving with, and on what timescale.** The order below is
not decoration — each step invalidates the next one if it is skipped, and the
two most common failures in this work are computing a statistic across a regime
boundary and correlating two red-noise series without prewhitening.

Both of those produce confident numbers. Neither produces an error.

## Step 1 — Bound the perturbation in time before computing anything

**A mean computed across a regime boundary measures neither regime.** Segment
first, then work within segments.

Use changepoint detection over mean *and* variance — PELT is the usual choice
(`ruptures`, BSD-2-Clause). This is not the CUSUM in `detect_anomalies`: CUSUM is
a detector tuned for a shift size you nominate, PELT segments a whole record and
estimates how many changes there were.

What it most often finds, in order of how much time it saves:

- a warmup you failed to exclude from the measured window;
- a step where a background job started or a cache finished filling;
- that "the perturbation" is two changes, not one.

Penalty choice decides the segment count and there is no universal value. Tune it
on a recording you know is clean — the penalty that yields zero changepoints
there is the floor for the one you are investigating.

## Step 2 — Characterize the target alone first

Run `analyze-noise` on the perturbed series before looking at any other metric.
It decides how the rest of this skill has to be done:

| What the curve shows | What it means for the next steps |
| --- | --- |
| white (−1/2 throughout) | correlations can be read directly; ordinary significance bands apply |
| flicker or redder | **every cross-correlation from here needs prewhitening** (step 4), and naive bands are worthless |
| a null pattern | there is a periodic component — identify it (step 3) before hunting a confounder, or it will distort everything around it |
| still rising at your τ | there is no stationary mean; segment harder or report the trend |

## Step 3 — Test for periodic components, do not eyeball them

Against a 1/f background, periodogram peaks always look impressive. Some of them
are.

Use a **multitaper spectrum with Thomson's harmonic F-test**, which gives a
p-value for a sinusoidal line against the local colored background rather than
against a flat one. For gapped or unevenly sampled data use **Lomb–Scargle**,
which is the honest tool where `analyze-noise` tells you to split the series.

A confirmed line is worth more than any correlation you could compute: a period
usually names the mechanism outright (a scrape interval, a GC cycle, log
rotation, an autoscaler, a fan or power cycle).
`${CLAUDE_SKILL_DIR}/references/spectral.md` has the parameters, the test, and
the code.

## Step 4 — Prewhiten before every cross-correlation

**Two independent series that are each autocorrelated produce large, confident
cross-correlations.** Fit an AR model to one series, apply *the same* filter to
both, then correlate (the Box–Jenkins procedure).

Independent AR(1) pairs, n = 4000, largest |CCF| over ±200 lags, mean of 30 trials:

| φ | raw | prewhitened |
| --- | --- | --- |
| 0.0 | 0.051 | 0.051 |
| 0.9 | **0.122** | 0.051 |
| 0.98 | **0.197** | 0.051 |

Nothing connects those series. At φ = 0.98 the raw scan reports a correlation of
0.2 — publishable-looking, entirely an artifact of the autocorrelation, and
prewhitening removes it completely at every φ.

Two more traps in the same step:

- **The ±2/√n band is per lag.** Scan 400 lags and you will cross it by chance;
  above, white-noise pairs still hit 0.051 against a nominal band of 0.032.
  Correct for the number of lags scanned, or nominate the lag in advance.
- **A lag is not a direction.** Sampling skew, differing filter delays, and a
  shared driver with different response times all produce a lag.

## Step 5 — Resolve the coupling by timescale

Correlation gives one number for a relationship that is usually frequency
dependent. **Magnitude-squared coherence** says at which timescales two signals
are linearly related, and the phase says the lead/lag at each. This is the
multivariate counterpart of putting two Allan curves on one axis, and it is the
defensible form of "this signal is stronger than that one *here*".

**Coherence is biased upward by 1/K for K segments**, and it is a hard floor, not
a tendency. Measured on independent white series:

| segments K | mean coherence under the null |
| --- | --- |
| 2 | 0.501 |
| 8 | 0.126 |
| 32 | 0.031 |
| 128 | 0.008 |

With 8 Welch segments, uncorrelated signals show coherence 0.125. **Never report
a coherence without saying how many segments produced it**, and never read one
computed from fewer than about 16. `${CLAUDE_SKILL_DIR}/references/spectral.md`
has the segment-count tradeoff and the null threshold to compare against.

## Step 6 — Screen many metrics without testing many metrics

A recording carries hundreds of series and testing each against the target is a
multiple-comparisons machine. Narrow first:

- **PCA over the standardized metrics.** The first component is usually "the
  machine got busy"; project it out and look at what survives. A candidate that
  only loads on PC1 is telling you about load, not about your change.
- **Compare Allan curves rather than values.** A confounder that matters shares
  a knee with the target. This costs one curve per candidate and no significance
  test at all.
- **Rank, then test a handful.** Carry at most a few candidates into steps 4–5,
  chosen before you look at their p-values.

`${CLAUDE_SKILL_DIR}/references/coupling.md` has the screening code and the
partial-correlation form for controlling a third metric.

## Step 7 — Stop before causality

Granger causality and transfer entropy are directional, and both assume no
unobserved common cause. **On a shared machine an unobserved common cause is the
default state of the world.** Use them to rank hypotheses; never quote one as
evidence that A caused B.

What actually settles it is an intervention: pin the suspected variable, remove
it, or interleave against it, and see whether the perturbation follows. One
successful intervention outweighs every statistic above.

## Step 8 — Report

State: the segmentation and its penalty, which series and which segment, whether
prewhitening was applied and what filter, the lag range scanned and the
correction for it, the segment count behind any coherence, and the candidates you
screened out. Then separate what you measured from what you infer, and name the
intervention that would confirm it.

## Never

- **Never compute a statistic across a changepoint.** Segment first.
- **Never cross-correlate red-noise series without prewhitening.** The table in
  step 4 is what you will otherwise report.
- **Never quote a coherence without its segment count**, and never one below the
  1/K floor.
- **Never scan lags and report the best one at its per-lag significance.**
- **Never promote a lag to a direction, or a correlation to a cause.**
- **Never test every metric in the recording.** Screen, then test a few.
- **Never let a model's output stand in for a measurement.** A forecast residual
  or an anomaly score points at a metric worth opening; it is not a finding. See
  `${CLAUDE_SKILL_DIR}/references/further-techniques.md` for where those models
  earn their place and where they do not.
