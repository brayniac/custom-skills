# Computing the curve

## Preparing the series

The estimators below assume a **uniformly sampled, rate-like, gap-free** series
`y[0..N-1]` with sampling interval τ₀. Everything that goes wrong here is silent.

- **Counters → rates.** Differentiate first (`rate()` in PromQL, `np.diff` on a
  raw counter). Feeding cumulative values shifts every slope by +1 and yields a
  plausible-looking plot of the wrong thing.
- **Events → bins.** Bin into fixed τ₀ windows and take the statistic the
  question is about. Analyzing the ADEV of a p99 series is legitimate; just say
  so, because the coefficients then describe the p99, not the distribution.
- **Dead time.** Gaps between measurement windows (a sampler that measures for
  0.5 s every 2 s) bias the result, and the classical bias functions that
  correct for it are worse than fixing the sampler. Prefer contiguous sampling.
- **Gaps.** Split the series and analyze the pieces, or use a gap-aware
  implementation. Never zero-fill or forward-fill: the step reads as random walk.
- **Do not detrend by reflex.** Removing a linear trend before ADEV destroys the
  evidence that the trend was there. Compute both ADEV and HDEV instead; the
  difference between them *is* the drift measurement.

## The estimators

With phase `x[k] = τ₀·Σ_{i<k} y[i]` (so `x` has `N+1` points), averaging factor
`m`, and `τ = m·τ₀`:

**Overlapping Allan** — the default.

```
σ²(τ) = 1 / (2 m²τ₀² (N−2m+1)) · Σ_j (x[j+2m] − 2x[j+m] + x[j])²
```

**Overlapping Hadamard** — drift-immune, converges to α = −4.

```
σ²_H(τ) = 1 / (6 m²τ₀² (N−3m+1)) · Σ_j (x[j+3m] − 3x[j+2m] + 3x[j+m] − x[j])²
```

**Modified Allan** — splits white PM from flicker PM at the fast end.

```
σ²_mod(τ) = 1 / (2 m⁴τ₀² (N−3m+2)) · Σ_j ( Σ_{i=j}^{j+m−1} (x[i+2m] − 2x[i+m] + x[i]) )²
```

Use **octave-spaced m** (1, 2, 4, 8, …) unless you need a denser grid for a slope
fit; denser τ points are not independent and do not add information.

## How far out to trust it

The number of independent estimates at averaging factor `m` is about `N/m`, and
the fractional 1σ uncertainty on the deviation is roughly

```
σ_ADEV / ADEV ≈ 1 / √(2 (N/m − 1))
```

| N/m | fractional uncertainty | verdict |
| --- | --- | --- |
| 100 | ~7% | solid |
| 30 | ~13% | usable for a slope |
| 10 | ~24% | one point, not a segment |
| 3 | ~50% | decoration |

Overlapping improves on this at small `m` and barely at large `m`, so treat the
formula as the honest bound. **Cap τ at N/10 clusters** (`m ≤ N/10`) for anything
you intend to fit, and never fit through the last few points. If long τ genuinely
matters, the fix is a longer run — or Total/Theo1 estimators if your tooling has
them, which buy roughly a factor of two in usable τ, not an order of magnitude.

## A reference implementation

Short enough to paste, and correct in the places that are easy to get wrong
(the `+1` in each denominator, the `m⁴` in MDEV).

```python
import numpy as np

def _phase(y, tau0):
    y = np.asarray(y, dtype=float)
    return np.concatenate(([0.0], np.cumsum(y))) * tau0   # N+1 points

def _octaves(n, frac=10):
    m, out = 1, []
    while m <= max(1, n // frac):
        out.append(m)
        m *= 2
    return out

def stability(y, tau0=1.0, kind="adev", ms=None):
    """(taus, devs, n_indep) for kind in {'adev','hdev','mdev'}.
    y: uniformly sampled, rate-like, gap-free."""
    x = _phase(y, tau0)
    n = len(y)
    ms = ms or _octaves(n)
    taus, devs, dof = [], [], []
    for m in ms:
        if kind == "adev":
            d = x[2*m:] - 2*x[m:-m] + x[:-2*m]
            k = len(d)                                    # N - 2m + 1
            if k < 1: continue
            var = np.sum(d**2) / (2 * (m*tau0)**2 * k)
        elif kind == "hdev":
            d = x[3*m:] - 3*x[2*m:-m] + 3*x[m:-2*m] - x[:-3*m]
            k = len(d)                                    # N - 3m + 1
            if k < 1: continue
            var = np.sum(d**2) / (6 * (m*tau0)**2 * k)
        elif kind == "mdev":
            d = x[2*m:] - 2*x[m:-m] + x[:-2*m]
            s = np.convolve(d, np.ones(m), mode="valid")  # N - 3m + 2
            if len(s) < 1: continue
            var = np.sum(s**2) / (2 * m**4 * tau0**2 * len(s))
        else:
            raise ValueError(kind)
        taus.append(m * tau0); devs.append(np.sqrt(var)); dof.append(n // m)
    return np.array(taus), np.array(devs), np.array(dof)

def slope(taus, devs, lo, hi):
    """Log-log slope fitted over lo <= tau <= hi."""
    sel = (taus >= lo) & (taus <= hi)
    if sel.sum() < 3:
        raise ValueError("fit at least 3 points, over at least a decade")
    return np.polyfit(np.log10(taus[sel]), np.log10(devs[sel]), 1)[0]
```

`allantools` is the maintained library and the results should agree to floating
point — but it is **LGPL-3.0**, where NumPy and SciPy are BSD-3. Cross-check
against it once, then keep the implementation above if the licence matters to the
project you are working in.

## Self-test before you believe a plot

Run these three and check the slopes. An implementation that fails any of them
will still produce a confident-looking curve for real data.

```python
rng = np.random.default_rng(0)
w = rng.standard_normal(100_000)

t, d, _ = stability(w)                      # white FM
assert abs(slope(t, d, t[0], t[-1]) + 0.5) < 0.05

t, d, _ = stability(np.cumsum(w))           # random walk FM
assert abs(slope(t, d, t[0], t[-1]) - 0.5) < 0.05

ramp = w + 1e-3 * np.arange(len(w))         # drift buried in white noise
ta, da, _ = stability(ramp, kind="adev")
th, dh, _ = stability(ramp, kind="hdev")
# adev turns up toward +1 at long tau; hdev stays near -1/2. That gap is the drift.
```

Then add a known sinusoid and confirm the null lands at its period — that is the
check that your τ axis is in real units and not in samples.

## Plotting

Log-log on both axes, τ on x. Draw the reference slopes (−1, −1/2, 0, +1/2, +1)
as faint guides; identification is comparison against those lines, not eyeballing
a curve. Mark the minimum and its τ. Show error bars, or at least stop the curve
where `N/m` drops below 10 — an unmarked tail is an invitation to over-read it.
