---
name: fit-structural-model
description: Fit an unobserved-components (structural time series) model so a noise decomposition becomes parameters with confidence intervals — observation noise, level disturbance, slope, seasonal — and test whether a component exists at all. Use when a trend needs an interval rather than a slope, when "is there really drift here" needs an answer, when the series has gaps, when the level must be separated from the noise with uncertainty attached, and when an offline analysis has to become an online detector.
---

# Fitting the decomposition instead of reading it

`analyze-noise` reads a decomposition off the geometry of a curve: a −1/2 segment
is white, a +1/2 segment is random walk, and the knee is where one takes over.
That is fast, assumption-light, and gives you no standard errors, no hypothesis
test, and no estimate of the underlying level.

A structural model fits the same decomposition as **parameters**. The trade is
explicit: you assume a linear Gaussian state space form, and in exchange every
component comes back with an interval you can test and difference.

**Fit a model only when the curve was not enough.** Most questions do not need one.

| Fit when | Because |
| --- | --- |
| a trend needs a confidence interval | a slope read off a log-log plot has none |
| "does this component exist at all" needs an answer | the curve cannot test a hypothesis |
| the series has gaps | the Kalman filter handles missing observations natively — no interpolation, no zero-fill |
| the level must be separated from the noise | smoothed states come with uncertainty bands |
| the analysis has to run online afterwards | fit once offline, then run O(1) per sample (step 6) |

**Do not fit when** the curve already answered it, when you have fewer than a few
thousand points (variance components are weakly identified and the fit will
report precision it does not have), or when the structure is non-linear or the
noise multiplicative — a log transform first, or a different model.

## Step 1 — Start with the smallest model that could be true

Local level → local linear trend → add a seasonal only if you have already
identified a period (from `attribute-perturbation` step 3, not by assumption).
Every added component costs identifiability, and an over-specified model does not
announce itself — it quietly splits one real component across two fitted ones.

`references/components.md` has the state space forms and which noise colour each
disturbance produces.

## Step 2 — Fit, and expect variances to pile up at zero

Maximum likelihood for variance components sits on a boundary, and it lands there
often. Fitting a local linear trend to data with no slope component returns
`sigma2.trend = 1.0e-12` — numerically zero.

**That is the estimator working correctly, not a bug.** But a zero is not a
hypothesis test, and standard errors computed at a boundary are invalid. Step 5
is how you actually test it.

## Step 3 — The innovations must be white

**Run `analyze-noise` on the standardized one-step prediction errors.** This is
the adequacy check, and it is the tightest one available: a correctly specified
model converts all the structure into white innovations of unit variance.

Checked on local level data whose raw ADEV slope is +0.034 — visibly structured —
the fitted model's innovations come back at slope **−0.501** with variance
**1.000**. If your innovations are not white, the model has not captured the
structure and every parameter in step 5 is describing the wrong thing. Do not
proceed; add the missing component or drop back to the curve.

## Step 4 — Cross-check against the Allan curve

For a local level model the two analyses predict each other exactly, so they must
agree. With `q = σ²_level / σ²_irregular`:

```
τ_min  = τ₀ · √(3/q)                  the minimum of the Allan curve
ADEV_min = √( 2·σ²_irregular·√(q/3) )    its value there
```

Checked across four decades of `q`, dense τ grid:

| q | τ_min predicted | τ_min measured | ADEV_min predicted | ADEV_min measured |
| --- | --- | --- | --- | --- |
| 2.93e-3 | 32 | 33 | 0.2500 | 0.2482 |
| 3.00e-4 | 100 | 101 | 0.1414 | 0.1444 |
| 3.00e-5 | 316 | 308 | 0.0796 | 0.0796 |
| 3.00e-6 | 1000 | 942 | — | — |

**If the fitted `q` and the measured curve disagree, one of them is wrong and you
do not yet know which.** Usually it is an unmodelled component, a changepoint
inside the window, or a τ range read off the tail. Resolve it before reporting
either. The drift at the largest τ above is the curve being genuinely flat near
its minimum — the argmin wanders where the curvature is small, which is also why
τ_min should be quoted as a range.

## Step 5 — Test whether a component exists, properly

A likelihood ratio test against χ²₁ is **wrong here** because the null sits on the
boundary of the parameter space. Three options, in order of preference:

1. **Use the purpose-built test.** For "is the level constant" (σ²_level = 0) in a
   local level model, the locally best invariant test *is* the KPSS statistic,
   with its own tabulated critical values. Use it rather than inventing one.
2. **Parametric bootstrap.** Simulate from the fitted restricted model, refit both
   models on each replicate, and build the null distribution of the LR statistic
   empirically. Always valid, and cheap enough at tier 3.
3. **Boundary-corrected LR**, as a last resort: for a single variance component
   the asymptotic null is a 50:50 mixture of χ²₀ and χ²₁, so the p-value is half
   the naive χ²₁ value. Treat this as a rule of thumb — the asymptotics are
   unreliable when a nonstationary component is involved.

Never report "the variance estimate was zero, so the component is absent."

## Step 6 — Fit offline, run online

This is the one technique in the library that spans tiers. Fitting is iterative
and belongs in tier 3, but **once the parameters are fixed the Kalman filter has
a steady state**, and for the local level model that steady state is an EWMA:

```
P = (q + √(q² + 4q)) / 2          K = P / (P + 1)
level ← level + K · (y − level)
```

Two floats of state and one multiply-add per sample. Checked against the full
filter at four values of `q`: the analytic `K` matches the converged Kalman gain
to six decimals, and the EWMA reproduces the filtered state to ~1e-8.

So the deployment is: fit on a recording (tier 3), ship `K` (tier 1), and watch
the standardized innovations on the node — CUSUM over them is O(1) and fires when
the series stops matching the model it was fitted to. `references/online-filter.md`
has the recursion, what to monitor, and when a refit is due.

## Step 7 — Report

State: the model form and why that one, the fitted variances with intervals,
which components were tested and by which test, the innovation check (slope and
variance), the Allan cross-check, and the data span. A structural model produces
confident-looking parameters for a badly specified form, so **the innovation
check is not optional in the write-up** — it is what makes the rest readable.

## Never

- **Never report parameters from a model whose innovations are not white.**
- **Never read "variance estimated as zero" as "component absent."** It is a
  boundary artifact until a proper test says otherwise.
- **Never use a naive χ²₁ LR test on a variance component.**
- **Never add components until the fit looks good.** Each one costs
  identifiability, and an over-specified model splits one real effect in two.
- **Never fit across a changepoint.** Segment first — `attribute-perturbation`
  step 1 — or the model will absorb a step into the level disturbance and report
  drift that is really one jump.
- **Never let the fitted model's forecasts become a reported measurement.** The
  same rule as every other model in this library: a pointer, not a number.
