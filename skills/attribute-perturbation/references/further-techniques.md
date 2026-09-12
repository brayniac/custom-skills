# The wider toolkit — a working map

Techniques worth knowing that are **not distilled into steps anywhere in this
library yet**. Each entry says what question it answers and what it costs, so the
choice to reach for one is deliberate. Treat this as a map, not as instructions:
anything promoted out of here should get its own steps, traps, and checked
numbers first, the way `analyze-noise` and this skill's other references did.

Licences are noted because they decide whether a tool is usable here. NumPy,
SciPy, statsmodels and `ruptures` are all BSD; `allantools` is LGPL-3.0.

## Distribution shape, not location

A mean-based A/B is blind to a change that moves the shape without the centre —
which for latency is most of the interesting ones. The Wasserstein row below has
its own skill now; the rest are still notes.

| Technique | Answers | Cost |
| --- | --- | --- |
| ECDF / Q–Q comparison | where in the distribution A and B differ | trivial; the first thing to plot |
| Anderson–Darling | is the difference real, tail-weighted | prefer over KS when the tail is the product; KS is most sensitive near the median |
| **Wasserstein distance between histograms** | did the shape change while the mean held | **promoted — this is the `compare-distributions` skill.** O(B) over buckets, no raw samples |
| Extreme value theory (POT/GPD) | what the worst case looks like | threshold choice is fiddly and it needs a lot of tail data; reach for it last |

## Variance that moves

**GARCH / stochastic volatility.** "The machine got noisier under load" is a
different finding from "the machine got slower under load", and nothing in the
current library separates them: an Allan curve mixes a change in noise amplitude
into the same summary as a change in level. Worth having when the complaint is
inconsistency rather than slowness.

## Decomposition into interpretable parts

- **STL** (seasonal–trend–loess): splits trend / seasonal / remainder, and the
  remainder is the right input to `analyze-noise` when a known cycle dominates.
  Robust STL if outliers are present. Cheap, interpretable, in statsmodels.
- **Structural time series / Kalman** (local level + slope + seasonal):
  **promoted — this is the `fit-structural-model` skill.** Its estimated variances
  *are* the noise decomposition, so the Allan-plot content comes back as
  parameters with intervals you can test, and a fitted model deploys as an O(1)
  streaming detector.
- **ARFIMA**: the fractional differencing parameter estimates the long-memory
  exponent (β = 2d) — a likelihood-based counterpart to reading an Allan slope,
  with a standard error attached.

## Other routes to the same exponent

- **DFA** (detrended fluctuation analysis): the Hurst exponent, robust to
  polynomial trends. Popular in physiology; overlaps heavily with Allan but
  handles nonstationarity by construction rather than by the Hadamard trick.
- **Wavelet variance**: strictly more general than what `analyze-noise` does —
  **the Allan variance is the Haar wavelet variance up to a constant** (Percival
  & Guttorp). A longer filter (D4, D6) leaks less, which matters for slopes
  steeper than +1 where Haar leakage starts to bite. The natural upgrade path if
  the current estimator ever hits its limit.

## Nonlinear and structural

- **Permutation entropy** (Bandt–Pompe): one cheap number for "is this structured
  or random". A decent screen; not a diagnosis.
- **Recurrence plots**: visual, good for spotting intermittency and regime
  structure the ACF misses.
- **Convergent cross mapping**: coupling in deterministic nonlinear systems, where
  Granger's assumptions fail differently. Exotic; mentioned for completeness.
- **DTW**: aligning two runs that drifted apart in time before comparing them.

## Causal inference without randomization

**CausalImpact / Bayesian structural time series with control series** answers
"what would this metric have done without the change" using controls that the
intervention did not touch. This is the right tool for a canary or a production
deploy.

**It is not the right tool for this lab.** Interleaved, randomized A/B is
strictly stronger evidence, and `measure-performance` already requires it. Reach
for synthetic-control methods only where the intervention genuinely cannot be
randomized.

## Forecasting models, including foundation models

The honest verdict first: **the work here is attribution and characterization,
not prediction, and nothing downstream consumes a forecast.** Four reasons that
matters more than it sounds.

1. **Predictability is the diagnostic, not the product.** If a forecaster beats a
   naive baseline on a measurement series, that *is* the finding — the samples are
   correlated and the error bars are wrong. The ACF says the same thing for
   nothing, with a number you can interpret. A 2.5B-parameter model to discover
   ρ(1) ≠ 0 is a lot of GPU to avoid one line of NumPy.
2. **No interpretable parameters.** You cannot read a noise colour, a correlation
   time, or a bias instability off a forecasting transformer. A structural time
   series model hands you numbers you can defend in a commit message.
3. **Weakest exactly here.** Foundation models win on low-frequency, seasonal,
   business-like series. On high-frequency, noisy, non-seasonal machine telemetry,
   deep learning and statistical ensembles beat them, and seasonal-naive baselines
   have been reported beating every foundation model tested on cloud-infrastructure
   data at every horizon. They also need roughly 50–100 historical points before
   zero-shot output is meaningful at all.
4. **Built to smooth over spikes.** Observability pretraining corpora are
   explicitly anomaly-contaminated and the models are designed to be robust to
   that — which means smoothing over precisely the perturbation being investigated.

**Where they do earn a place:** zero-shot triage across many metrics at once.
A recording carries hundreds of series and you cannot hand-fit a model per metric.
Forecast one step ahead, flag where the actual leaves the predictive interval,
rank by surprise, open the top few. That is step 6 of this skill with a different
ranking function — **a search over metrics, never a verdict.**

If trying that, prefer an in-domain model. **Toto** (Datadog) is trained on
observability telemetry rather than retail and energy data, ships as a family from
4M to 2.5B parameters, and comes with **BOOM**, a benchmark of 350M observations
across 2,807 real observability series. The 22M variant is small enough to run
over a whole recording.

**Licence: Apache-2.0**, for both the inference code and the released weights.
That was checked before recommending it, and it is the reason it appears here at
all — a model under a bespoke community licence or an acceptable-use rider does
not go into this library regardless of how it benchmarks. Confirm the model card
independently before depending on it; the check here was made against the
repository and Datadog's release announcement, not the weight card directly.

The rule that survives all of this: **a model's output is a pointer to a metric
worth opening, and never a measured quantity.** If it appears in a report, it
appears as "the anomaly scorer flagged this, so I looked", not as a number.
