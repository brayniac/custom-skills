# Where an analysis runs

The question is not "how many cycles does this cost". It is **"does running it
change the number I am trying to measure"**. That reframes the whole cost
question: a technique that burns 5% of a core off the measured path is free, and
one that burns 0.5% *on* the measured path has contaminated the result.

Three placements, and the rule that decides between them.

## Tier 1 — on the node, in the measurement path

Runs alongside the workload, inside the agent, as samples arrive. Admission
criteria are strict and they are about the hot path, not the total:

- **O(1) or O(log N) per sample**, bounded memory decided at startup;
- **no allocation** after startup, and no lock the workload also takes;
- pinned off the measured cores where the platform allows it.

| Technique | Per-sample cost | State |
| --- | --- | --- |
| Welford mean/variance | O(1) | 3 floats |
| Histogram accumulation | O(1) | fixed buckets |
| **Streaming Allan / Hadamard / Modified deviation** | O(octaves) | ~4–8 floats per octave |
| EWMA and EWMA variance | O(1) | 2 floats per rate |
| CUSUM | O(1) | 2 floats — this is why it is the classic streaming detector |
| Lag-1..k autocorrelation products (k ≤ 32) | O(k) | k floats; yields τ_int |
| t-digest / P² quantiles | O(1) amortized | bounded |
| **W1 between consecutive histogram snapshots** | O(B) *per snapshot*, not per sample | none beyond the two histograms |

Two of those deserve emphasis because they are nearly free where the cost is
already being paid:

- **Allan deviation streams.** The whole curve is a handful of accumulators per
  octave, so a stability curve costs about what a running variance costs. The
  `allan` crate (MIT/Apache-2.0, brayniac) does exactly this with circular
  buffers, covering overlapping ADEV, MDEV and overlapping HDEV.
- **Histogram distance is free where histograms are already recorded.** rezolus
  pays the bucketing cost regardless; W1 between two snapshots is one cumulative
  sum over the buckets and touches no raw samples at all.

**What tier 1 can answer: that something changed.** Not what it changed with —
attribution needs other series, and pulling those together on the measured node
is how you turn a measurement into a distributed system.

## Tier 2 — live, off the measured cores

A window buffer and a transform, running on the collector, a sidecar, or the
hypervisor's reserved host CPUs while the guest is under measurement. This is
where you steer a running experiment: alert, abort, or extend it.

| Technique | Cost per window | Notes |
| --- | --- | --- |
| Welch PSD | O(N log N) | the cheap spectral baseline |
| Multitaper + F-test | K × O(N log N) | K = 7 typically, so ~7× Welch |
| Coherence, nominated pair | 2 FFTs + averaging | needs ≥16 segments to mean anything |
| Prewhitened CCF, nominated pair | O(N log N) via FFT | a *pair*, not all pairs |
| Lomb–Scargle | O(N log N) fast, O(N·F) naive | for gapped data |
| Overlapping ADEV with confidence | O(N) per τ × octaves | the offline-quality version |
| Blocking / τ_int with windowing | O(N) | error bars while the run is live |
| Online changepoint (BOCPD) | O(R) per step, pruned | R = retained run lengths |

On hv01/hv02 this tier has an obvious home: the emulator and iothread are
already pinned to reserved host CPUs, so **host-side analysis of a guest under
measurement is tier 2 by construction** — provided it stays on the reserved set
and does not touch the guest's allocation.

## Tier 3 — batch, on the downloaded recording

Multi-pass, iterative, or a cross-product over metrics. Runs after
`download_artifact`, on a machine that is not under measurement. **Verdicts come
from here.**

| Technique | Cost | What makes it batch |
| --- | --- | --- |
| PELT segmentation | O(N log N) pruned, O(N²) worst | needs the whole record |
| PCA / SVD over M metrics | O(N·M²) | all metrics at once |
| **All-pairs screening** | O(M²) transforms | this is the one that explodes — M=300 is 45k pairs |
| Structural time series / Kalman **fitting** (MLE or EM) | dozens of passes | iterative; but see below — the *fitted* model runs at tier 1 |
| ARFIMA | iterative | likelihood optimization |
| Wavelet coherence with surrogates | surrogates × scales × O(N log N) | hundreds of transforms |
| DFA across scales | O(N × scales) | multi-scale detrending |
| Block bootstrap / permutation tests | resamples × statistic | hundreds of statistic evaluations |
| Foundation-model inference over many metrics | GPU-minutes | not going near a measured node |

## The one technique that spans tiers

**A structural time series model is expensive to fit and free to run.** Fitting is
iterative and belongs above; but once the parameters are fixed the Kalman filter
reaches a steady state, and for a local level model that steady state is an EWMA
with a closed-form gain — two floats of state, one multiply-add per sample.

So the deployment is tier 3 for the fit, tier 1 for the filter, with the
standardized innovations as the thing you watch. That is `fit-structural-model`,
and it is the only entry in this reference that legitimately appears in two
tiers.

## The rules

1. **Budget on-node analysis explicitly, then verify it.** Run the instrumentation
   against a null workload and check the floor did not move. An analysis you did
   not budget is in your result whether or not you accounted for it.
2. **Tier 1 detects; tier 3 concludes.** A streaming detector firing is a reason
   to look, never a reported number. The same discipline as `detect_anomalies`.
3. **Never promote a technique a tier to save time.** All-pairs screening on the
   node is not a faster analysis, it is a broken measurement.
4. **Push work down only where the cost is already paid.** W1 on existing
   histograms and a streaming Allan curve are tier 1 because they add almost
   nothing to an existing hot path. Most things are not like that.
5. **Match the tier to the decision's deadline.** If nothing acts on the answer
   before the run ends, it belongs in tier 3, where it is cheaper and better.
