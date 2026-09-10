---
name: compare-distributions
description: Decide whether two measured distributions differ and in what way — location, shape, or tail — using Wasserstein distance computed straight from recorded histograms. Use when comparing latency between two builds or configurations, when a percentile moved but the mean did not (or the reverse), when "it got slower" needs to become a specific claim, and before reducing two distributions to a single number.
---

# Comparing two distributions

A mean-based A/B is blind to most of what goes wrong with latency, and a p99-based
one is blind to the rest. **The distribution is the measurement**; a percentile is
a lossy summary of it chosen before you knew what changed.

This skill is about the comparison itself. Whether the difference is *real* is
`measure-performance` step 5 (interleave, enough runs, spread that does not cover
the difference), and whether your samples are independent enough to support any
error bar is `analyze-noise`. Neither of those changes because the statistic is a
distance rather than a mean.

## Step 1 — Work from the histograms, not from quantiles

rezolus records histograms. Use them directly: they carry the whole shape, they
are already paid for, and reducing them to p50/p99 before comparing throws away
the part that identifies the mechanism.

**Both sides must be on the same bucket grid.** A histogram config that changed
between runs is not comparable to one that did not — re-bin to a common grid, or
say the comparison cannot be made. Never compare bucket-for-bucket across grids
because the indices line up.

Normalize to equal mass. Two histograms over different durations hold different
counts, and a distance computed on raw counts is measuring the durations.

## Step 2 — Compute W1, one pass over the buckets

The 1-D Wasserstein (earth-mover) distance is the mass-transport cost between the
two distributions:

```
W1 = Σ_i |CDF_a(i) − CDF_b(i)| · (x_{i+1} − x_i)
```

One cumulative sum over the buckets, `O(B)`, no raw samples — cheap enough to run
on the node beside the measurement (see `analysis-placement.md` in
`measure-performance`).

**W1 comes out in the units of the metric.** "The distribution moved 107 µs of
mass" is a sentence an engineer can act on, where a KS statistic of 0.32 is not.

`references/histogram-distance.md` has the implementation, the log-bucket
handling, and the numbers all of this was checked against.

## Step 3 — Split location from shape

This is the reading that makes W1 worth computing rather than just diffing means.
Because `|Δmean| = |∫(F−G)| ≤ ∫|F−G| = W1`:

| Relationship | Reading |
| --- | --- |
| `W1 ≈ |Δmean|` | **pure location shift** — the CDFs do not cross, everything moved the same direction. "It got slower." |
| `W1 ≫ |Δmean|` | **shape change** — mass moved both directions and partly cancelled in the mean. "It got less consistent." |
| `Δmean ≈ 0`, `W1 > 0` | shape change with the mean pinned — the case a mean-based A/B reports as no change |

Checked. A 2% slow-tail regression gives W1 = 107,030 ns and |Δmean| = 107,030 ns
off the same buckets — ratio 1.0000, pure location shift. (Sample-level W1 is
106,999 ns, so a 200-bucket log grid costs 0.03%.) A unimodal distribution
replaced by a bimodal one with the means matched gives W1 = 7.249 against
|Δmean| = 2.9e-5 — a ratio of 2.5e5, and a mean-based A/B reporting nothing.

**Report the ratio, not just the distance.** It is the difference between a
regression you can attribute to a slower path and one you have to attribute to a
new source of variance.

## Step 4 — Choose the statistic for the question

| Statistic | Answers | Fails at |
| --- | --- | --- |
| **W1** | how much mass moved, times how far, in metric units | needs a shared grid; no built-in significance |
| KS | the largest single CDF gap | **saturates** — it counts how much mass moved and ignores how far |
| Anderson–Darling | is any difference real, tail-weighted | a test statistic, not an interpretable magnitude |
| Per-quantile deltas | where in the distribution it moved | says nothing about mass not at those quantiles |

The saturation is not a subtlety. Moving 1% of the mass progressively further out:

| tail moved | KS | W1 |
| --- | --- | --- |
| ×2 | 0.0100 | 1.00 |
| ×10 | 0.0100 | 9.00 |
| ×100 | 0.0100 | 98.99 |
| ×1000 | 0.0100 | 999.07 |

KS reports the identical statistic for a tail 2× out and one 1000× out. **For
latency work that is the whole question**, so KS is the wrong default and W1 is
the right one. Use AD when you want a hypothesis test, and always alongside W1 for
the magnitude.

## Step 5 — Get the null from repeated runs, not from resampling

**Do not bootstrap over samples within a run.** Samples inside a run are
correlated — that is what `analyze-noise` is for — so a resampling null is far too
tight and will call every comparison significant. Same failure as `1/√N`.

The null you want is **A-vs-A**: compute W1 between interleaved runs of the *same*
configuration, several times, and take that spread as the noise floor. Then the
A-vs-B distance is meaningful only if it clears it. You are already interleaving
for `measure-performance` step 5, so the runs exist.

If A-vs-A W1 is comparable to A-vs-B W1, there is no difference yet — report that,
rather than a distance with a confident sign.

## Step 6 — Report

State: the bucket grid and that both sides shared it, the durations and counts
normalized, W1 with its units, `|Δmean|` and the ratio, the A-vs-A floor and how
many runs produced it, and which quantiles moved. Then name the shape of the
change — location, spread, tail, or a new mode — because that is what points at a
mechanism.

## Never

- **Never compare histograms across different bucket configurations** by index.
- **Never compute a distance on unnormalized counts** — you will measure the
  durations.
- **Never use KS to quantify how much worse a tail got.** It cannot; see step 4.
- **Never bootstrap within a run for significance.** The null comes from repeated
  runs.
- **Never report W1 without `|Δmean|` beside it.** The distance alone does not
  distinguish "slower" from "less consistent", and those have different causes.
- **Never take a distance as a cause.** It says the shape changed and where; the
  mechanism is `attribute-perturbation`.
