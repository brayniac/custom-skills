# Model forms and what each disturbance is

## The forms

**Local level** (random walk plus noise) — two variances:

```
y_t = μ_t + ε_t          ε_t ~ N(0, σ²_ε)     irregular / observation noise
μ_t = μ_{t-1} + η_t      η_t ~ N(0, σ²_η)     level disturbance
```

**Local linear trend** — adds a stochastic slope:

```
y_t = μ_t + ε_t
μ_t = μ_{t-1} + β_{t-1} + η_t
β_t = β_{t-1} + ζ_t      ζ_t ~ N(0, σ²_ζ)     slope disturbance
```

Special cases worth naming, because they are what you usually want:

| σ²_η | σ²_ζ | Form | Means |
| --- | --- | --- | --- |
| 0 | 0 | deterministic constant + noise | a fixed level; the classical i.i.d. case |
| >0 | 0 | local level | the level wanders, no persistent direction |
| 0 | >0 | smooth trend (integrated random walk) | direction changes slowly; a bending curve |
| >0 | >0 | full local linear trend | both; hardest to identify, needs the most data |

Add a **seasonal** only for a period you have already identified. Dummy-variable
and trigonometric forms both exist; trigonometric is better when only the first
few harmonics matter, which is the usual case for a machine cycle.

## What each disturbance is, in noise-colour terms

The mapping is why fitting this model is the parametric counterpart to reading an
Allan curve:

| Component | Contributes | ADEV slope of that contribution |
| --- | --- | --- |
| irregular `σ²_ε` | white FM | −1/2 |
| level `σ²_η` | random walk FM | +1/2 |
| slope `σ²_ζ` | integrated random walk (flicker walk territory) | +3/2 |
| deterministic drift | ramp | +1 |

Two AVAR constants make this exact, both verified directly:

```
AVAR_white(τ)  = σ²_ε · τ₀/τ          measured 4.000 for σ²_ε = 4
AVAR_rwalk(τ)  = σ²_η · τ/(3τ₀)       measured 0.2507 for step variance 0.25
```

Summing them (Allan variances add) gives the local level model's whole curve, and
minimising it gives the identity in the skill's step 4:

```
AVAR(τ) = σ²_ε·τ₀/τ + σ²_η·τ/(3τ₀)
τ_min   = τ₀·√(3/q)                     q = σ²_η/σ²_ε
AVAR_min = 2·σ²_ε·√(q/3)
```

**Both terms are equal at the minimum** — that is what a minimum of a sum of a
falling and a rising power law means, and it is a useful sanity check when you
compute one by hand.

## Fitting

```python
import numpy as np, statsmodels.api as sm          # statsmodels is BSD-3

res = sm.tsa.UnobservedComponents(y, 'local level').fit(disp=0)
# forms: 'local level', 'local linear trend', 'smooth trend',
#        add seasonal=<period> and/or freq_seasonal=[...]

print(res.summary())
q = res.params[1] / res.params[0]                   # sigma2.level / sigma2.irregular
tau_min = np.sqrt(3.0 / q)                          # cross-check against the curve

level = res.smoothed_state[0]                       # the estimated level
innov = res.filter_results.standardized_forecasts_error[0]
```

Missing data: pass `np.nan` for gaps. The filter skips them correctly, which is
the one place this beats every other technique in the library — `analyze-noise`
tells you to split the series at a gap, and this does not have to. Checked: 700
NaNs punched into a 200,000-point series recover `q = 2.996e-4` against a true
3.0e-4, converging normally.

Recovery on 60k points from a known local level process landed within about 10%
on `q` across three decades. That is the realistic precision; do not quote a
fitted variance to three significant figures off a short record.

## Identifiability, concretely

The variance components trade off against each other, and the likelihood surface
is flat along that trade for short series. Symptoms:

- a variance pinned at exactly zero (see the boundary discussion in the skill);
- wildly different parameters from different starting values;
- a fitted `q` that disagrees with the Allan curve's `τ_min`.

**The Allan cross-check is the cheapest identifiability diagnostic you have.**
Two estimators with different failure modes agreeing is worth more than either
one's standard errors.

## The boundary

Fitting a local linear trend to data generated with no slope component returns:

```
sigma2.irregular   7.568e-01
sigma2.level       1.314e-03
sigma2.trend       1.016e-12      <- pinned at the boundary
```

The estimator is right and the model is over-specified. What you must not do is
report "slope variance is zero, therefore there is no slope" — that is a boundary
artifact, and the test for it is in the skill's step 5 (KPSS for the level case,
parametric bootstrap in general).
