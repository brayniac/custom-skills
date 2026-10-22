# How many independent samples you actually have

The Allan curve says whether a stable error bar *exists*. This says what it is.

Three routes compute the same quantity from different directions. **Run at least
two and check they agree** — when they disagree, one of them is being applied
outside its assumptions, and that is worth knowing before you quote a number.

## Route 1 — Integrated autocorrelation time

For a stationary series, the variance of the mean is inflated by the
autocorrelation:

```
Var(x̄) = (σ² / N) · τ_int        τ_int = 1 + 2 Σ_{k≥1} ρ(k)        N_eff = N / τ_int
```

`τ_int` is the inflation factor and `N_eff` is the honest sample count. White
noise gives `τ_int = 1`; an AR(1) with coefficient φ gives `(1+φ)/(1−φ)`, so
φ = 0.95 means 4% of your samples are doing the work.

**Never sum the whole ACF.** The tail is pure estimation noise and adding it in
makes `τ_int` a random walk in `k`. Truncate:

- **Sokal automatic windowing** — take the smallest window `W` with `W ≥ c·τ_int(W)`,
  conventionally `c = 5`. Simple, and what the code below does.
- **Geyer initial positive sequence** — sum adjacent lag pairs `Γ_m = ρ(2m) + ρ(2m+1)`
  and stop at the first `Γ_m ≤ 0`. More conservative; prefer it when ρ goes negative.

You need `N ≫ τ_int` for either to mean anything — **at least 50·τ_int**, and if
the window runs off the end of the series, the answer is "the run was too short",
not a number.

## Route 2 — Blocking

Average adjacent pairs, re-estimate the standard error from the block means,
double the block size, repeat (Flyvbjerg–Petersen). The estimate rises as blocks
absorb the correlation, then **plateaus once adjacent blocks are independent**.
The plateau is your standard error.

**No plateau means no error bar.** That is the same finding as an Allan curve
that never bottoms out, arrived at independently.

## Route 3 — Straight off the Allan curve

If you already computed the curve, you already have the answer:

```
SE(x̄) ≈ ADEV(τ) / √(T/τ)          for any τ past the knee
```

This holds because `AVAR(τ) = Var(ȳ_τ) − Cov(ȳ_i, ȳ_{i+1})`: the Allan variance
is the variance of a block mean minus the covariance of adjacent blocks. Where
blocking plateaus, that covariance has vanished, and the two estimators coincide.
**Allan differences adjacent blocks (which kills drift); blocking takes their
variance (which does not).** That is the whole difference between them, and it is
why Allan is the diagnostic and blocking is the error bar.

## Checked

AR(1) series, N = 2²⁰, three correlation strengths:

| φ | τ_int theory | τ_int estimated | SE theory | SE blocking | SE via ADEV |
| --- | --- | --- | --- | --- | --- |
| 0.0 | 1.00 | 1.00 | 0.00098 | 0.00080 | 0.00078 |
| 0.8 | 9.00 | 8.97 | 0.00293 | 0.00318 | 0.00306 |
| 0.95 | 39.00 | 37.70 | 0.00609 | 0.00540 | 0.00590 |

Agreement to within each estimator's own sampling error, across two orders of
magnitude of correlation. If your three routes spread wider than this, something
is nonstationary.

## Implementation

```python
import numpy as np

def tau_int(y, c=5.0):
    """Integrated autocorrelation time, Sokal automatic windowing.
    Returns (tau_int, window). Raises if the series is too short."""
    y = np.asarray(y, float); y = y - y.mean(); n = len(y)
    f = np.fft.rfft(y, 2 * n)
    acov = np.fft.irfft(f * np.conj(f))[:n].real / n
    rho = acov / acov[0]
    for W in range(1, n):
        t = 1.0 + 2.0 * rho[1:W + 1].sum()
        if W >= c * t:
            return t, W
    raise ValueError("no window: series too short for its own correlation time")

def n_eff(y):
    return len(y) / tau_int(y)[0]

def blocking(y, min_blocks=16):
    """[(block_size, standard_error_of_the_mean)] as blocks double.
    Read the plateau; if there isn't one, there is no error bar."""
    y = np.asarray(y, float); out = []; b = 1
    while len(y) // b >= min_blocks:
        nb = len(y) // b
        bm = y[:nb * b].reshape(nb, b).mean(axis=1)
        out.append((b, bm.std(ddof=1) / np.sqrt(nb)))
        b *= 2
    return out

def se_from_adev(dev_at_tau, tau, total_duration):
    """Route 3. Use a tau past the knee of the curve."""
    return dev_at_tau / np.sqrt(total_duration / tau)
```

Self-test: an AR(1) with known φ must recover `τ_int = (1+φ)/(1−φ)` and all three
routes must agree. White noise must give `τ_int = 1`; if it does not, the ACF
normalisation is wrong.

## Reporting

**Quote `N_eff` beside `N`.** "12,000 samples" and "12,000 samples, 340 effective"
lead to different decisions, and only the second one is a fact about the system.

## Where this does not apply

`τ_int` and blocking both assume a stationary mean. **If the Allan curve is still
rising at the τ you care about, there is no stationary mean to put an error bar
on**, and both routes will return a confident number anyway. Fix the drift,
shorten the window to the knee, or report the trend instead of a mean.
