# Slopes, colors, and what they implicate

## The identification table

`S_y(f) ∝ f^α` is the one-sided power spectral density of the *sampled quantity*
(a rate or a level, not an accumulation). Allan variance goes as `τ^μ` with
`μ = −α − 1`; the deviation is the square root, so the ADEV slope on log-log is
`μ/2`.

| α | Name | AVAR τ^μ | **ADEV slope** | MDEV slope | HDEV slope |
| --- | --- | --- | --- | --- | --- |
| +2 | white PM | τ^-2 | −1 | **−3/2** | −1 |
| +1 | flicker PM | ~τ^-2 | −1 | **−1** | −1 |
| 0 | white FM | τ^-1 | −1/2 | −1/2 | −1/2 |
| −1 | flicker FM | τ^0 | **0** | 0 | 0 |
| −2 | random walk FM | τ^+1 | +1/2 | +1/2 | +1/2 |
| −3 | flicker walk FM | — | *diverges* | — | +1 |
| −4 | random run FM | — | *diverges* | — | +3/2 |
| — | linear drift | τ^+2 | +1 | +1 | **0** (rejected) |

Three consequences worth holding onto:

- **ADEV cannot separate white PM from flicker PM.** Both give −1. Compute MDEV
  when the fast end slopes at −1 and you need to know which; the split is −3/2
  versus −1.
- **ADEV cannot distinguish drift from noise redder than random walk.** Both
  climb. Hadamard is the discriminator: it rejects linear drift outright, so a
  τ^+1 rise in ADEV that flattens in HDEV was drift, and one that stays at +1 in
  HDEV is flicker walk.
- **Hadamard and Allan share slopes for α ≥ −2.** They agree exactly for white
  FM and differ by a modest constant elsewhere, so read slopes from either, but
  quote the standard coefficients from ADEV.

## Reading coefficients off the fitted lines

Fit the straight segment, extend it, and read its value at the fixed τ below.
These are the IMU/clock conventions and they transfer to any rate-like series;
the units are the series' own units unless noted.

| Coefficient | Segment | Fitted line | Read at |
| --- | --- | --- | --- |
| Quantization **Q** | −1 | σ(τ) = √3·Q/τ | τ = √3 |
| Random walk **N** (angle/velocity/"ARW") | −1/2 | σ(τ) = N/√τ | τ = 1 |
| Bias instability **B** | 0 (the minimum) | σ_min = 0.664·B | the minimum itself |
| Rate random walk **K** | +1/2 | σ(τ) = K·√(τ/3) | τ = 3 |
| Drift ramp **R** | +1 | σ(τ) = R·τ/√2 | τ = √2 |

**B is the floor's meaning, not the floor's value** — the minimum of the curve
is `0.664·B`, and it is the practical answer to "what is the best this can
resolve in one sitting". The τ at that minimum is the optimal averaging time.

## Periodic components

A sinusoidal component of amplitude A and period T₀ contributes

```
σ²(τ) = A² · sin⁴(π τ / T₀) / (π τ / T₀)²
```

so the signature is unmistakable once you know it:

- **Deep nulls at τ = T₀, 2T₀, 3T₀ …** — the crisp reading. First null is the
  period.
- A local peak just before the first null, at **τ ≈ 0.37·T₀**.
- On a log-log plot with other noise present, this looks like a scalloped bump
  riding on the baseline curve rather than clean zeros.

A bump you cannot place is worth chasing before any slope-fitting: a periodic
confounder crossing your τ range distorts the segments on either side of it.

## Mixed processes

**Allan variances add** for independent contributions. So the observed curve is
the sum, in variance, of every process present, and a knee is a crossover from
one dominating to the next. Fit segments, never one global slope. If two
processes are within a factor of two of each other, there is no clean segment
between their knees — say the region is mixed rather than inventing an exponent.

## What each color implicates

The color narrows the search to a class of mechanism and a timescale. It never
names the component.

| Color | Timescale story | Suspects in a system | Suspects on an instrument |
| --- | --- | --- | --- |
| white PM | none — per sample, non-accumulating | timer granularity, counter quantization, rounding in the exporter | ADC quantization, readout noise |
| flicker PM | short, weakly correlated | sampling path jitter, correlated scheduling delay | correlated electronics jitter |
| white FM | independent interval to interval | independent arrivals, queueing, genuinely random work | thermal/Johnson noise, shot noise |
| flicker FM | many overlapping timescales, no single one | contention, frequency scaling, background daemons, allocator and page-cache state, JIT/branch-predictor warmth, co-tenants | 1/f device noise, flicker in the oscillator |
| random walk FM | slow, accumulating | temperature ramp, memory leak, fragmentation, cache filling, queue depth wandering, clock drift | temperature-driven bias walk, aging |
| drift | monotone, deterministic | thermal throttling ramp, a growing dataset, a warming machine, a filling disk | linear bias ramp, warm-up |
| periodic | one exact timescale | cron, GC, log rotation, autoscaler, rebalancer, fan or power cycling, telemetry scrape | dither, mains hum, chopper |

**Flicker and redder are the ones that break experiments**, because both defeat
`1/√N` and both make A-then-B comparisons compare epochs. When you find either,
the fix is structural — interleave, shorten the window to τ at the minimum, or
control the drifting variable — never "collect more samples".
