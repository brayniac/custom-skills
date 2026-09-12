# Shipping a fitted model to the node

Fitting is tier 3. **Running a fitted model is tier 1** — this is the only
technique in the library that legitimately spans both, and it is worth knowing
because it turns an offline analysis into a detector that costs nothing.

## The steady state

Once the parameters are fixed, the Kalman filter's covariance recursion converges
and the gain stops changing. For the local level model with
`q = σ²_level / σ²_irregular` the fixed point of the Riccati equation is closed
form:

```
P = (q + √(q² + 4q)) / 2            steady-state prior variance, in units of σ²_ε
K = P / (P + 1)                     steady-state Kalman gain
```

and the filter collapses to an EWMA:

```
level ← level + K·(y − level)
```

Two floats of state, one multiply-add per sample, no allocation. Checked against
the full time-varying filter:

| q | K analytic | K from the filter | EWMA vs Kalman, max abs diff |
| --- | --- | --- | --- |
| 1e-1 | 0.270156 | 0.270156 | 2.6e-9 |
| 1e-2 | 0.095125 | 0.095125 | 1.5e-8 |
| 1e-3 | 0.031127 | 0.031127 | 7.8e-8 |
| 1e-4 | 0.009950 | 0.009950 | 4.6e-7 |

So "fit a structural model" and "pick an EWMA smoothing factor" are the same
decision — **the fit is how you stop guessing α.** An EWMA whose α was chosen by
feel is a local level model with an unexamined `q`.

Transients: the recursion needs a burn-in before the gain assumption holds.
Discard the first few `1/K` samples, or seed `level` with a known-good mean.

## What to monitor

Do not monitor the level. Monitor the **standardized innovations**:

```
e = (y − level) / s          s = √(σ²_ε·(P + 1))      the one-step prediction sd
```

Under the model these are white with unit variance — which is exactly the
property the skill's step 3 verified on the fitted record. So the online test is
a test of *continued* agreement with the model, and it catches everything the
model did not predict, rather than only the things you thought to threshold.

Verified: the recursion above reproduces statsmodels' own standardized
innovations with a correlation of 1.000000 and variance 1.000, so the closed-form
`s` is exact and you do not need the library at runtime.

Two O(1) detectors over `e`, both tier 1:

- **CUSUM** for a persistent shift: `S⁺ ← max(0, S⁺ + e − k)`, fire at `S⁺ > h`.
  Take `k ≈ δ/2` for a shift of `δ` standard deviations you want to catch.
- **Running variance of `e`** for a change in noise amplitude rather than level —
  the "it got noisier, not slower" case a level detector misses entirely.

### Choosing h, with measured numbers

**The mean run length to a false alarm is not the number you want.** ARL0 is
close to geometric, so false alarms are roughly memoryless and arrive early far
more often than a mean suggests. Quote instead:

```
P(false alarm within N samples) ≈ 1 − exp(−N / ARL0)
```

Measured over 2000 chains of unit-variance white innovations:

| k | h | median ARL0 | mean ARL0 | samples to detect a 0.5σ shift |
| --- | --- | --- | --- | --- |
| 0.25 | 20 | 223,590 | 311,488 | 69 |
| 0.25 | 30 | >4e6 (cap) | 3,817,082 | 110 |
| 0.25 | 40 | >4e6 (cap) | 3,996,700 | 147 |
| 0.5 | 8 | 12,886 | 18,697 | 65 |
| 0.5 | 12 | 700,019 | 986,420 | 134 |
| 0.5 | 16 | >4e6 (cap) | 3,862,283 | 234 |

Worked: `k = 0.25, h = 20` over a 150,000-sample run gives
`1 − exp(−150000/311488) ≈ 38%` chance of firing with nothing wrong. Going to
`h = 30` drops that to about 4% and costs 110 samples instead of 69 to catch a
0.5σ shift — **a 12× better false-alarm rate for 1.6× the detection delay.**

That first setting is not a strawman; it is what this reference was drafted with,
and it false-alarmed at sample 21,246 of a run whose injected step was at 150,000.
**Calibrate `h` against the run length you will actually observe**, on
model-conforming data, before shipping it.

The table above is usable across sources only because the innovations are
standardized — a correctly fitted model makes the null universal, which is the
whole point of monitoring `e` rather than `y`. For any statistic that has *not*
been studentized that way, the threshold is source-specific and
`calibrate-to-source` is how to derive it.

Both detectors are in the tier-1 table in `measure-performance`'s
`analysis-placement.md`.

## When the model needs refitting

A detector that fires constantly is not detecting; it has been deployed past its
validity. Refit when:

- the innovation variance drifts away from 1 and stays there — the noise
  amplitude changed, so `q` is stale;
- the innovations stop being white (run `analyze-noise` on a captured window);
- the workload, hardware, or configuration changed. **A model fitted on hv01 does
  not transfer to hv02** for the same reason a measurement does not.

Carry the fit's provenance with `K` — which recording, which host, which span.
A bare smoothing constant in a config file, six months on, is indistinguishable
from a guess.

## What this does not become

The filter produces a one-step prediction. **That is not a measurement**, and the
level estimate is not a reported number: it is a model's view of the series, with
all the assumptions in the skill's step 1 baked in. It points at a window worth
opening. The number in the report comes from the recording.
