# Histogram distances in practice

## W1 from bucket counts

Treat each bucket's mass as sitting at a representative value `x_i`, and the two
distributions become discrete on a shared support. Then

```
W1 = Σ_{i=0}^{B-2} |CumA_i − CumB_i| · (x_{i+1} − x_i)
```

is exact for that discretization — one cumulative sum, `O(B)`, no raw samples.

```python
import numpy as np

def w1_hist(counts_a, counts_b, x):
    """1-D Wasserstein distance between two histograms on a shared grid.
    counts_*: bucket counts. x: bucket representative values, same length.
    Returns a distance in the units of x. Normalization is handled here."""
    a = np.asarray(counts_a, float); b = np.asarray(counts_b, float)
    if a.sum() <= 0 or b.sum() <= 0:
        raise ValueError("empty histogram")
    a = a / a.sum(); b = b / b.sum()
    return float(np.sum(np.abs(np.cumsum(a)[:-1] - np.cumsum(b)[:-1]) * np.diff(x)))

def w1_by_band(counts_a, counts_b, x,
               bands=((0, .5), (.5, .9), (.9, .99), (.99, 1.0))):
    """(total_W1, [(lo, hi, share_of_W1)]) — where along A's distribution the
    transport happened. This is what separates a uniform shift from a tail-only
    blowup; the ratio in location_vs_shape cannot, since both are monotone."""
    a = np.asarray(counts_a, float); b = np.asarray(counts_b, float)
    a = a / a.sum(); b = b / b.sum()
    A = np.cumsum(a)[:-1]; B = np.cumsum(b)[:-1]
    inc = np.abs(A - B) * np.diff(x)
    tot = inc.sum()
    return float(tot), [(lo, hi, float(inc[(A >= lo) & (A < hi)].sum() / tot))
                        for lo, hi in bands]

def location_vs_shape(counts_a, counts_b, x):
    """(W1, |dmean|, ratio). ratio ~1 is a pure location shift;
    ratio >> 1 means mass moved both ways and cancelled in the mean."""
    a = np.asarray(counts_a, float); b = np.asarray(counts_b, float)
    a = a / a.sum(); b = b / b.sum()
    w1 = w1_hist(counts_a, counts_b, x)
    dmean = abs(float(a @ x - b @ x))
    return w1, dmean, (w1 / dmean if dmean > 0 else float("inf"))
```

Checked against `scipy.stats.wasserstein_distance` on the same discrete support:
agreement to 13 significant figures.

## Choosing the representative value

For a log or log-linear bucket grid (what rezolus records), use the **geometric**
midpoint `√(e_i · e_{i+1})`, not the arithmetic one. On a bucket spanning
1 ms–2 ms the arithmetic midpoint is 1.5 ms and the geometric is 1.41 ms; the
geometric one is the value that splits the bucket evenly in the space the buckets
were laid out in.

With 200 log-spaced buckets covering 1 µs to 1 s, `w1_hist` recovers the
sample-level W1 of a lognormal-with-slow-tail comparison to within 0.03%
(107,030 ns against 106,999 ns). **Bucket resolution is not the limiting factor**
in this analysis; grid mismatch is.

## Value space versus index space

Running `w1_hist` against bucket *indices* instead of values is a different and
occasionally useful quantity: on a log grid it is a distance in log space, so it
measures a **ratio** rather than an absolute shift. The same comparison above
gives 1.324 buckets in index space versus 107,030 ns in value space.

Index-space W1 is scale-free, which makes it comparable across metrics with
different units — useful for ranking many metrics at once. **It is not a latency.**
Never report it in time units, and say which space you used.

## What the ratio separates

| Case | W1 | \|Δmean\| | ratio | Reading |
| --- | --- | --- | --- | --- |
| 2% of mass moved to a slow tail | 107,030 ns | 107,030 ns | 1.0000 | monotone — CDFs do not cross |
| uniform 20% slowdown | — | — | 1.000 | monotone — **same ratio, different regression** |
| body faster, tail worse | — | — | 1.229 | CDFs cross |
| unimodal → bimodal, means matched | 7.249 | 2.9e-5 | 2.5e5 | crossing with the mean pinned |

**The ratio detects crossing, not "shape change".** Two of the rows above are
monotone and share a ratio of 1.000 while describing completely different
regressions. Use `w1_by_band` to tell them apart: the uniform slowdown spreads
its transport 14/43/32/11% across the bands, the tail-only one puts 94.6% of it
past p99.

Both columns are computed off the same buckets, so the first row's agreement is
exact rather than approximate. Against sample-level values the same comparison
gives W1 = 106,999 ns, which is the 0.03% the bucket grid costs.

The inequality `|Δmean| ≤ W1` is exact and always holds, with equality precisely
when the CDFs never cross. So the ratio is bounded below by 1, and how far above
1 it sits is how much of the change cancelled in the mean.

## Why not KS

KS is the largest single gap between the two CDFs. It measures **how much** mass
moved and is completely insensitive to **how far** it moved:

| tail displacement (1% of mass) | KS | W1 |
| --- | --- | --- |
| ×2 | 0.0100 | 1.00 |
| ×10 | 0.0100 | 9.00 |
| ×100 | 0.0100 | 98.99 |
| ×1000 | 0.0100 | 999.07 |

Identical KS across three orders of magnitude of tail displacement. KS is also
least sensitive exactly where latency work cares most — its power concentrates
near the median. Anderson–Darling fixes the tail weighting and remains a test
statistic rather than a magnitude, so it answers "is this real" and never "how
much worse".

## W2 and beyond

`W2` (quadratic transport cost) weights distant mass more heavily and will
respond harder to a far tail. It is also no longer in the units of the metric,
which costs the interpretability that makes W1 worth reporting. Use W1 by
default; reach for W2 only when a stakeholder specifically wants far-tail
excursions dominating a single number, and label it clearly.

## The significance question

There is no clean analytic null for W1 on correlated samples, and this is a
feature — it stops you reaching for one that assumes independence.

**The null is A-vs-A.** Compute W1 between interleaved runs of the same
configuration; that spread is the floor. A-vs-B has to clear it.

A block bootstrap (moving-block, block length past the correlation time from
`analyze-noise`) is the fallback when only one run per side exists, and it is
strictly worse: it assumes the single run sampled the run-to-run variation, which
is exactly the assumption that interleaving exists to avoid. **A plain i.i.d.
bootstrap over samples within a run is always wrong here** and will report
significance for everything.

## Cost

`O(B)` per comparison over the bucket count, touching no raw samples, on
histograms that are already being recorded. That is tier 1 in
`measure-performance`'s `analysis-placement.md` — cheap enough to run on the node
beside the workload, provided the histograms were going to be built anyway.
