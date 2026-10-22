# Coupling in the time domain

## Prewhitening (Box–Jenkins)

The procedure, in the order that matters:

1. Fit an AR model to the **target** series `a` (order by AIC, or AR(1) if the
   ACF decays cleanly). Call the fitted filter `Φ`.
2. Apply **the same filter `Φ`** to both `a` and the candidate `b`. Not a filter
   fitted separately to each — the same one. Filtering each series by its own
   model destroys the cross-structure you are looking for.
3. Cross-correlate the two residual series.
4. Report lags in the original units; the filter shifts nothing, but it does eat
   `order` samples off the front.

```python
import numpy as np

def ar_fit(y, order=1):
    """Least-squares AR coefficients (no intercept; y should be centered)."""
    y = np.asarray(y, float) - np.mean(y)
    X = np.column_stack([y[order - 1 - k: len(y) - 1 - k] for k in range(order)])
    return np.linalg.lstsq(X, y[order:], rcond=None)[0]

def ar_filter(y, phi):
    """Apply 1 - phi(B): returns the innovation series, len(y) - order."""
    y = np.asarray(y, float) - np.mean(y); o = len(phi)
    out = y[o:].copy()
    for k, c in enumerate(phi):
        out = out - c * y[o - 1 - k: len(y) - 1 - k]
    return out

def prewhitened_ccf(a, b, order=1, maxlag=200):
    """(lags, ccf) with the target's AR filter applied to BOTH series."""
    phi = ar_fit(a, order)
    ra, rb = ar_filter(a, phi), ar_filter(b, phi)
    ra = (ra - ra.mean()) / ra.std(); rb = (rb - rb.mean()) / rb.std()
    n = len(ra); lags = np.arange(-maxlag, maxlag + 1); out = []
    for L in lags:
        out.append(np.dot(ra[L:], rb[:n - L]) / (n - L) if L >= 0
                   else np.dot(ra[:n + L], rb[-L:]) / (n + L))
    return lags, np.array(out)
```

### Which way the lag points

Checked, not assumed: with the convention above, a peak at **negative** lag means
the target `a` leads the candidate `b`. Injecting `b[t] = 0.6·a[t−17] + noise`
into two φ = 0.95 series recovers lag −17 with a peak CCF of 0.601.

Get this backwards and you will attribute a perturbation to its own consequence,
so re-derive it on synthetic data rather than trusting any convention — including
this one — after editing the loop.

The helpers were checked the rest of the way too: `ar_fit` recovers φ = 0.5 and
0.9 to four figures; `partial_corr` takes a shared-driver pair from a raw
correlation of 0.803 to 0.001 given the driver; `pc1_residuals` takes five
load-driven metrics from mean |corr| 0.958 with load to 0.001.

## Significance, honestly

The familiar `±2/√n` band is **per lag**. Scanning a window of `L` lags and
reporting the largest is a maximum over `L` correlated tests.

Measured on independent series, n = 4000, largest |CCF| over ±200 lags:

| φ of both series | raw scan | prewhitened scan | nominal per-lag band |
| --- | --- | --- | --- |
| 0.0 | 0.051 | 0.051 | 0.032 |
| 0.9 | 0.122 | 0.051 | 0.032 |
| 0.98 | 0.197 | 0.051 | 0.032 |

Two separate effects, and you need both fixes:

- **Autocorrelation** inflates the raw scan (0.032 → 0.197). Prewhitening fixes
  this completely, at every φ.
- **Scanning** inflates it further (0.032 → 0.051) even after prewhitening, for
  white series with nothing to find. Correct for the lag count, or — better —
  **nominate the lag range before you look**, from a mechanism you can name.

## Partial correlation

To ask whether `b` explains anything about `a` beyond what `c` already explains,
regress both on `c` and correlate the residuals:

```python
def partial_corr(a, b, c):
    def resid(y, x):
        X = np.column_stack([np.ones(len(x)), x])
        return y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
    return np.corrcoef(resid(a, c), resid(b, c))[0, 1]
```

On a shared machine the `c` worth controlling for is usually overall load. Its
frequency-resolved counterpart is partial coherence.

## Screening many metrics

```python
def screen(target, candidates, order=1, maxlag=200):
    """Rank candidates by peak prewhitened |CCF|. Ranking only — the p-values
    that come out of a scan like this are not usable as p-values."""
    scored = []
    for name, y in candidates.items():
        lags, c = prewhitened_ccf(target, y, order, maxlag)
        i = int(np.argmax(np.abs(c)))
        scored.append((name, float(c[i]), int(lags[i])))
    return sorted(scored, key=lambda r: -abs(r[1]))
```

**Use the ranking to choose a handful, then test those properly.** A screen over
300 metrics that reports its own best hit as significant has tested 300
hypotheses and corrected for none.

### PCA first

Standardize every metric, take the principal components, and look at the
loadings. In a machine recording the first component is almost always "the
machine got busy" — it captures anything driven by overall load. Project it out
and rerun the screen: a candidate that survives is telling you something specific,
and one that does not was telling you about load.

```python
def pc1_residuals(M):
    """M: (n_samples, n_metrics), standardized. Returns M with PC1 removed."""
    M = (M - M.mean(0)) / M.std(0)
    U, S, Vt = np.linalg.svd(M, full_matrices=False)
    return M - np.outer(U[:, 0] * S[0], Vt[0])
```

## Granger causality and transfer entropy

Both are directional; neither is causal in the sense you want. Granger asks
whether `b`'s past improves a linear prediction of `a` beyond `a`'s own past, and
transfer entropy asks the same without the linearity assumption. **Both assume no
unobserved common cause.** On a shared machine — shared caches, shared memory
bandwidth, shared thermal envelope, a shared scheduler — an unobserved common
cause is the normal state of the world, not an edge case.

They are also sensitive to sampling rate relative to the true coupling delay: a
coupling faster than τ₀ shows up as instantaneous and gets attributed to whichever
series happens to lead by rounding.

Use them to rank hypotheses. The thing that settles the question is an
intervention — pin it, remove it, or interleave against it, and watch whether the
perturbation follows.
