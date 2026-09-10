---
name: analyze-noise
description: Identify what color a measurement's noise is — white, flicker, random walk, drift, or a periodic component — from an Allan or Hadamard deviation curve, and read off the averaging interval, the run length, and the timescale a confounder lives on. Use when repeated measurements disagree by more than they should, when choosing how long to average or how many runs to take, when a standard error looks suspiciously tight, and when a perturbation needs its cause narrowed rather than described.
---

# Reading the color of noise

A measurement that varies is not thereby "noisy" in one way. **How the variation
scales with averaging time is a fingerprint**, and it names both what averaging
will buy you and what kind of mechanism is behind it. A stability plot —
deviation against averaging time τ, log-log — is how you read that fingerprint.

The whole method is one question asked at every timescale: *if I averaged over
τ, how much would consecutive averages still disagree?* White noise makes the
disagreement shrink as τ grows. Flicker makes it stop shrinking. Random walk
makes it grow. **You do not get to assume the first one**, and every familiar
tool — the standard error, "take more samples", a confidence interval — assumes
exactly that one.

This is the diagnostic behind `measure-performance` step 5. That skill says
interleave, take at least four runs a side, and report the spread. This one says
how long each run has to be, whether averaging inside it helps at all, and
whether the spread you computed means what you want it to.

## Why the standard deviation is not enough

**For anything redder than white, the sample variance depends on how long you
looked.** Flicker and random-walk processes have no convergent variance: run
twice as long and the number grows. So a standard deviation quoted without a
duration is not a property of the system, and an error bar that got tighter when
you took more samples may have gotten tighter *only because you took more
samples*.

Allan variance exists to fix this. It is a two-sample variance — the mean square
difference between *consecutive* τ-averages — and it converges where the plain
variance does not. Its value at τ is dominated by fluctuations near
**f ≈ 0.37/τ**, which is why the curve reads like a spectrum drawn in the time
domain: each τ is a band, and the slope between bands is the spectral exponent.

## Step 1 — Build the series before you transform it

The estimator has no idea what you fed it. Get four things right first:

1. **Uniform sampling.** One fixed τ₀ between samples. If you have raw events,
   bin them into equal intervals and take the per-bin statistic (mean, p99,
   rate — whatever the question is about). A τ₀ you inferred from an average
   interval is not a τ₀.
2. **A rate or a level, never a cumulative counter.** Allan deviation is defined
   on the *frequency-like* quantity; hand it the accumulation and every noise
   type reads exactly one shade redder than it is. This is the single largest
   source of misidentification. Differentiate counters first — the same
   `rate()`-before-you-reason rule as reading a rezolus recording.
3. **No filled gaps.** A hole patched with zeros or a last value injects a step,
   and a step reads as random walk. Split the series at the gap and analyze the
   pieces, or use a gap-aware implementation.
4. **Enough of it.** You can only characterize out to roughly τ = T/10 with any
   confidence, so **decide the largest timescale you care about and record ten
   times longer.** A floor at 100 s needs a run of hours, not minutes.

State N, τ₀, and T = N·τ₀ before going further. Everything downstream is
conditional on them.

## Step 2 — Compute the curve

Use the **overlapping** Allan deviation (OADEV) on octave-spaced τ. Overlapping
costs nothing and gives better confidence than the non-overlapping form at the
same τ.

Add a second estimator when the shape asks for one:

| Also compute | When | Because |
| --- | --- | --- |
| **Hadamard (OHDEV)** | ADEV rises toward τ^+1, or you can see drift in the raw series | the three-sample difference cancels linear drift and converges for noise redder than random walk, where Allan just reports the drift |
| **Modified (MDEV)** | the fast end slopes at τ^-1 | ADEV cannot tell white PM from flicker PM; MDEV splits them (τ^-3/2 vs τ^-1) |

`references/computing.md` has the estimators, the τ grid, the confidence rule,
and a NumPy implementation short enough to paste. Read it with `skill_resource`
before writing your own — the off-by-one in the overlapping sum is silent and
tilts the whole curve.

## Step 3 — Validate before you read anything off

**Prove the pipeline on synthetic data first.** Feed it Gaussian white noise
(must give slope −1/2) and the cumulative sum of that same noise (must give
+1/2). An implementation that gets those two wrong will produce a beautiful,
confident, wrong plot for your real data.

Then, on the real curve:

- **Cap τ.** The last points are computed from a handful of independent
  differences and wander freely. The fractional uncertainty on a point is
  roughly `1/√(2(N/m − 1))` — at ten independent clusters that is already ±24%,
  which is most of a slope. **Never fit a slope through the tail.**
- **Check for a single outlier.** One spike creates a τ^-1 region that
  impersonates white PM across the whole fast end. Look at the raw series.
- **Require a decade.** A slope fitted over less than a decade of τ is a guess.
  If you only have half a decade, say the color is undetermined.

## Step 4 — Identify the color

Read the ADEV slope on log-log:

| ADEV slope | Noise | What it usually is in a system | What averaging does |
| --- | --- | --- | --- |
| τ^-1 | white / flicker PM | timer resolution, counter quantization, per-sample jitter that does not accumulate | vanishes fast; usually not your problem |
| τ^-1/2 | white FM | genuinely independent per-interval variation — independent arrivals, queueing | works: error falls as 1/√N |
| τ^0 (flat) | flicker FM | contention, thermal and frequency scaling, background daemons, allocator and cache state | **nothing.** This is a floor |
| τ^+1/2 | random walk FM | temperature ramp, a leak, fragmentation, cache filling, clock drift | actively hurts |
| τ^+1 | deterministic drift | throttling ramp, a warming machine, a growing dataset | remove or attribute it; do not average it |
| null at τ=T₀, repeats at 2T₀, 3T₀ | periodic component of period T₀ | a cron job, a GC cycle, a rebalancer, a fan or power cycle | irrelevant — find the cycle |

**Flat is flicker, not white.** This is the mistake people carry over from
spectrograms, and it inverts the conclusion: flat means averaging has stopped
paying, which is the opposite of "it's just white noise."

Real curves are several processes summed — Allan *variances* add — so expect
segments with knees between them, and read each segment separately.
`references/slopes.md` has the full slope↔spectrum table, the degeneracies, the
periodic signature, and the causes worth suspecting per color.

## Step 5 — Read the decisions off the curve

- **The averaging interval is the minimum of the curve.** τ at the bottom is the
  longest averaging that still helps; past it you are integrating drift. This is
  the gyroscope-bias-instability reading, and it transfers directly: it is the
  answer to "how long should each sample window be".
- **The floor is your error bar.** The deviation at that minimum is the best
  you can resolve from one run, no matter how many samples you take inside it.
  A difference smaller than the floor is not measurable this way — say so
  instead of averaging harder.
- **Sample count only converts to precision on the −1/2 segment.** If the curve
  is flat or rising at the τ you average over, `1/√N` is a fiction and a
  confidence interval built on it is too tight. Get precision from *more
  independent runs*, spaced past the correlation timescale, not from a longer
  one.
- **Red noise means interleave.** Flat or rising says the mean itself moves on
  the timescale of your experiment, so A-then-B compares two epochs and not two
  configurations. This is exactly why `measure-performance` insists on
  interleaving; the curve is how you show it is necessary — or that it is not.
- **A null tells you the period.** First null at τ, repeating at 2τ and 3τ: a
  periodic component of period τ. Go find the thing with that period.

Coefficients worth quoting (random walk coefficient, bias instability, ramp
rate) are read off fitted slope lines at fixed τ; `references/slopes.md` gives
the five standard readings.

## Step 6 — Turn the curve into an error bar

The curve says whether a stable error bar exists. Three cheap computations say
what it is, and **they must agree**:

- **Integrated autocorrelation time.** `Var(x̄) = (σ²/N)·τ_int` with
  `τ_int = 1 + 2Σρ(k)`, so `N_eff = N/τ_int` is the honest sample count. Never
  sum the whole ACF — truncate it with automatic windowing.
- **Blocking.** Average adjacent pairs, re-estimate the standard error, double,
  repeat; read the plateau. **No plateau means no error bar** — the same finding
  as a curve that never bottoms out, reached independently.
- **Off the curve directly:** `SE(x̄) ≈ ADEV(τ)/√(T/τ)` for any τ past the knee.
  This works because `AVAR(τ) = Var(ȳ_τ) − Cov(adjacent blocks)`, and that
  covariance vanishes exactly where blocking plateaus.

**Quote `N_eff` beside `N` whenever you report a mean.** "12,000 samples" and
"12,000 samples, 340 effective" lead to different decisions, and only the second
is a fact about the system. `references/effective-samples.md` has the estimators,
the windowing rules, and the numbers all three routes were checked against.

## Step 7 — Compare two curves, not two numbers

Two ADEV curves on one axis answer questions a pair of means cannot:

- **Where they separate is the timescale of the difference.** A change that only
  moves the long-τ end is a drift or contention story; one that only moves the
  fast end is jitter or quantization.
- **Where they cross is where the dominant contributor changes** — which is the
  honest form of "is this signal stronger than that one". Below the crossing one
  process dominates, above it the other, and no single number says that.
- **Against a co-recorded suspect** (temperature, another service's rate, a
  neighbouring counter), a shared knee at the same τ is worth chasing. It is not
  evidence of a cause; it is a place to look. Same rule as `analyze_correlation`.

Chasing that suspect properly — segmenting first, prewhitening, resolving the
coupling by timescale — is the `attribute-perturbation` skill. Do not skip to a
correlation from here: two red-noise series correlate strongly with nothing
between them, and a curve that told you the noise is red just told you that you
are in exactly that case.

Match τ₀, run length, and τ range before comparing. Curves computed from
different-length runs disagree at the long end for reasons that have nothing to
do with the systems.

## Step 8 — Report the curve, not the adjective

State: N, τ₀, total duration, which estimator (overlapping? Hadamard?), the τ
range you fitted each slope over, the slopes, and the identified color per
segment. Then the derived numbers — τ at the minimum, the floor — and only then
the interpretation, marked as interpretation.

"The noise is pink" with no curve, no τ range, and no run length is not a
finding. It is a vibe, and it will get quoted later as a fact.

## Never

- **Never call flat "white".** Flat is flicker, and it means averaging has
  stopped buying anything.
- **Never feed a cumulative counter to the estimator.** Every color comes back
  one shade too red, and the plot looks entirely reasonable.
- **Never fit a slope through the tail of the curve**, and never through less
  than a decade of τ.
- **Never report a standard error from `1/√N` when the curve is not falling at
  −1/2 at that τ.** More samples do not fix correlated noise; they just make the
  wrong interval narrower.
- **Never compute `τ_int` or a blocking error bar on a series whose curve is
  still rising.** There is no stationary mean to attach one to, and both methods
  return a confident number anyway. Fix the drift, shorten the window to the
  knee, or report the trend instead of a mean.
- **Never fill a gap to make the estimator run.** Split the series.
- **Never compare ADEV curves computed with different τ₀ or run lengths** as if
  the difference were physical.
- **Never name a mechanism from the color alone.** A color narrows the search to
  a class of mechanism and a timescale; it does not identify the component. Say
  which part you measured and which part you inferred.
- **Never use this to rescue a bad measurement.** If the environment was
  contended, unpinned, or unverified, the curve characterizes the environment,
  faithfully and uselessly.
