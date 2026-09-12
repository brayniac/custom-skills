# What calibration costs

## The null's scale is source-specific; its shape is nearly not

A-vs-A null of W1, 400 pairs per source, N = 50,000 each:

| source | median W1 | q95/q50 | q99/q50 | q99.9/q50 |
| --- | --- | --- | --- | --- |
| gaussian | 7.5 | 1.75 | 2.06 | 2.59 |
| exponential | 72.2 | 1.85 | 2.24 | 2.81 |
| lognormal σ=1 | 181.3 | 1.66 | 1.90 | 2.22 |
| lognormal σ=2 | 4208.4 | 1.78 | 2.22 | 2.85 |
| pareto α=2.5 | 129.6 | 1.83 | 2.32 | 4.82 |
| bimodal 90/10 | 2477.8 | 2.02 | 2.46 | 2.90 |
| **pareto α=1.5** (infinite variance) | 1293.4 | **3.17** | **7.91** | **19.39** |

**The scale varies 560×. The shape stays inside 1.66–2.02** across a gaussian, an
exponential, two lognormals, a Pareto and a bimodal mixture — distributions with
nothing in common.

So the case-by-case learning is essentially **one scalar: where the null sits.**
Its shape is close to a constant for anything with a finite variance.

## The cost, measured

Estimating a threshold for lognormal σ=1 (true median 180.6, true q95 299.7,
true ratio 1.66), from `k` A-vs-A pairs, median relative error over 400 draws:

| pairs | estimate the median | estimate q95 directly | median × a universal constant |
| --- | --- | --- | --- |
| 3 | 14.2% | 24.1% | ~21% |
| 5 | 10.6% | 18.5% | ~21% |
| 10 | 7.1% | 12.3% | ~21% |
| 20 | 5.7% | 9.8% | ~21% |
| 50 | 3.2% | 6.0% | ~21% |
| 100 | 2.4% | 3.9% | ~21% |
| 300 | 1.4% | 2.3% | ~21% |

Two readings, both important:

1. **Direct measurement converges and is cheap.** Ten pairs gets a threshold to
   about 12%, fifty to 6%. That is light by any standard.
2. **The universal-constant shortcut does not converge.** More data cannot fix a
   constant that is wrong for your source; the residual is however far your
   source's shape factor sits from the constant. The ~21% above is the worst case
   in the pack — it used 2.0 against a source whose true ratio is 1.66. With a
   constant near the centre of the observed range (~1.8), expect **±10% for
   finite-variance sources**, permanently.

Choose by what the number feeds: ~10% is fine for a detector threshold, not for a
reported error bar.

## Extreme quantiles are where it gets heavy

You cannot estimate a quantile past about `1 − 1/k` from `k` samples, and useful
precision needs an order of magnitude more. A 99.9th-percentile threshold
measured directly needs thousands of A-vs-A pairs, which no interleaving protocol
produces as a byproduct.

Two ways out, in order of preference:

- **Loosen the requirement.** A detector that fires once a week is usually fine,
  and it is two orders of magnitude cheaper to calibrate than one that fires once
  a year.
- **Extrapolate the tail.** Fit a generalized Pareto to the upper tail of the
  measured null and read the quantile off the fit. This converts a sampling
  problem into a parametric assumption, which is a real trade and not a free one.

## The shape factor is its own diagnostic

Because the shape is stable for finite-variance sources, **a shape factor far
outside 1.7–2.0 is telling you something about the source before you have done
any other analysis.** Pareto α=1.5 announces itself at 3.17.

Treat a q95/q50 above roughly 2.5 as "this source has pathological tails": expect
magnitudes to be unstable, expect to need many more runs, and prefer the
distributional tools over the variance-based ones.

## Implementation

```python
import numpy as np

def null_from_pairs(stat_values):
    """A-vs-A null summary. stat_values: the statistic computed between
    interleaved runs of the SAME configuration."""
    v = np.asarray(stat_values, float)
    if v.size < 3:
        raise ValueError("need at least 3 A-vs-A pairs to say anything")
    q50, q95 = np.percentile(v, [50, 95])
    return {
        "n_pairs": v.size,
        "scale": float(q50),
        "shape": float(q95 / q50),
        "threshold_measured": float(q95),
        "threshold_from_constant": float(q50 * 1.8),
        "suspect_heavy_tails": bool(q95 / q50 > 2.5),
    }
```

With fewer than ~10 pairs, prefer `threshold_from_constant` — the direct quantile
is noisier than the constant's bias at that sample size. Past ~20 pairs the
measured quantile wins. Report which one you used.

## When calibration goes stale

- The innovation variance of a deployed model drifts off 1 and stays there.
- The Allan curve is still rising at your τ — **then the null you just measured is
  already stale**, and no amount of recalibration fixes a non-stationary source;
  shorten the window or control the drifting variable.
- Host, image, workload or configuration changed. A null measured on hv01 does not
  transfer to hv02, for the same reason a measurement does not.

Carry provenance with every threshold: which source, which runs, how many pairs,
and which of the two routes produced it. A bare constant in a config file is
indistinguishable from a guess six months later.
