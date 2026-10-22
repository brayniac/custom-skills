# What travels between metric sources, and what does not

All numbers below are from synthetic series run through this library's own shipped
code. **They probe the estimators, not any real telemetry pipeline** — see the
preconditions at the bottom, which bite harder than any of this.

## Slopes travel, unconditionally

ADEV slope on i.i.d. series, true answer −0.500, N = 200,000, 15 trials each:

| marginal | median slope | sd |
| --- | --- | --- |
| gaussian | −0.501 | 0.007 |
| exponential | −0.503 | 0.009 |
| lognormal σ=1 | −0.504 | 0.011 |
| lognormal σ=2 | −0.499 | 0.008 |
| student-t df=3 | −0.498 | 0.008 |
| **student-t df=1.5** (infinite variance) | −0.498 | 0.011 |
| **pareto α=1.5** (infinite variance) | −0.496 | 0.008 |
| bernoulli p=0.01 (sparse) | −0.502 | 0.010 |
| quantized to 4 levels | −0.505 | 0.008 |
| clipped to [0,1] | −0.503 | 0.010 |

The slope reads correctly **even where the variance does not exist**, because it
is a ratio across τ and the amplitude pathology divides out of both ends.

Also unconditional: the `W1/|Δmean|` ratio (exactly 1.0000 across ns, µs, s and a
×1e6 rescaling), coherence's `1/K` null floor, and the prewhitened CCF band
(0.051 at every φ).

## Magnitudes do not travel

Same estimator, the ADEV *value* at τ = 1, across 15 trials:

| marginal | relative IQR | max/min |
| --- | --- | --- |
| gaussian | 0.00 | 1.0 |
| student-t df=3 | 0.02 | 1.0 |
| lognormal σ=2 | 0.10 | 1.4 |
| student-t df=1.5 | 0.40 | 3.8 |
| pareto α=1.5 | **1.17** | **4.5** |

So on a heavy-tailed metric the classification is solid while **τ_min and the
floor — the things you actually decide on — vary 4.5× between runs of the
identical process.**

## Why: the moment order of the statistic

This is the rule that predicts the rest. The sampling distribution of a statistic
depends on moments *above* the one it estimates, so tail weight leaks in at a rate
set by the statistic's order.

| Statistic | Order | Null shape across sources (q95/q50) |
| --- | --- | --- |
| slope (ratio of second moments across τ) | pivotal | no dependence at all |
| W1 (first moment) | 1st | 1.66 – 2.02 for every finite-variance source |
| ADEV magnitude (variance-like) | 2nd | 1.01, 1.02, 1.04, 1.34, 1.65, **4.03** |

That last row is gaussian, exponential, lognormal σ=1, pareto α=2.5, lognormal
σ=2, pareto α=1.5 in order. A variance-like statistic's null depends on the
marginal's *kurtosis*, which is why it cannot be calibrated once and reused.

**Design rule: studentize.** Every zero-shot-portable thing in this library is a
ratio of like quantities.

## Robustness to the mess in real telemetry

**Outliers.** τ_min with a true knee at 100 (dense grid, baseline reads 112):

| contamination | τ_min |
| --- | --- |
| none | 112 |
| 20σ spikes at 1e-5, 1e-4, 1e-3 | 112, 112, 112 |
| 100σ spikes at 1e-4 | 146 |
| 100σ spikes at 1e-3 | **321** |

Unmoved by ordinary outliers at any rate tested; breaks only when the spikes
carry more variance than the signal.

**Record length.** ADEV slope, true −0.500:

| N | median | sd | octaves |
| --- | --- | --- | --- |
| 300 | −0.512 | 0.063 | 5 |
| 1,000 | −0.508 | 0.025 | 7 |
| 10,000 | −0.506 | 0.016 | 10 |
| 100,000 | −0.503 | 0.010 | 14 |

**Classification works from ~1000 points.** Separating adjacent noise types
(−1/2 from −0.4) needs 10⁴ or more. There is a small negative bias at short N.

**Distributional versus variance-based, on a null comparison.** Run-to-run spread
of an A-vs-A statistic (max/min over 15 pairs):

| source | W1 | \|Δstd\| |
| --- | --- | --- |
| lognormal σ=1 | 2.5 | 10.7 |
| lognormal σ=2 | 2.9 | 88.7 |
| pareto α=1.2 | 15.1 | 430.6 |
| pareto α=1.5 | 67.3 | **2233.9** |

W1 degrades gracefully where variance-based statistics degrade catastrophically —
roughly 30× better on the worst case. **But 67× is still not a shippable
threshold.** For α < 2 tails, prefer the distributional tools *and* accept that
the null needs many runs.

## Preconditions beat parameters

None of the above rescues a series that was assembled wrong, and these are facts
about a pipeline to verify rather than knobs to tune:

- a rate, not a cumulative counter (every colour reads one shade too red);
- uniform τ₀, with dead time accounted for;
- no zero-filled or forward-filled gaps (a step reads as random walk);
- segmented before any statistic is computed.

Hazards that synthetic data cannot reproduce and that are worth checking per
source: coordinated omission, agent-side pre-aggregation, and
scheduler-induced bimodality.
