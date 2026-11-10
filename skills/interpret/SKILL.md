---
name: interpret
description: Decide what a set of measurements shows — the noise color and the averaging interval it implies, from an Allan or Hadamard deviation; whether two distributions differ in location, shape or tail, by Wasserstein distance; whether a trend or drift is real; what drives a perturbation, without a spurious correlation from autocorrelated data; and whether a threshold carries to a new metric or host. Use when repeated measurements disagree by more than they should, when choosing how long to average or how many runs to take, when a standard error looks too tight, when comparing latency between builds or configurations, when a percentile moved but the mean did not, when "it got slower" or "is there drift" needs a specific answer, when a run is anomalous, before quoting a cross-metric correlation, before reusing a threshold or detector on another source or running it online, before writing a threshold into a config, before publishing a comparison of measurements, and when a reader says two numbers are hard to compare.
---

# Interpret

`bench` produces a measurement and checks that it measured its subject; this
skill decides what it shows. Each question has its own procedure in a reference
file. Read the one the question needs, all of it, before computing anything.

| Question | Read |
| --- | --- |
| What is the noise, how long should I average, how many runs? | `${CLAUDE_SKILL_DIR}/references/noise.md` |
| Do two distributions differ, and in location, shape or tail? | `${CLAUDE_SKILL_DIR}/references/distributions.md` |
| Is there a trend or drift, and with what interval? | `${CLAUDE_SKILL_DIR}/references/structural-model.md` |
| What caused this perturbation, and on what timescale? | `${CLAUDE_SKILL_DIR}/references/perturbation.md` |
| Does this threshold carry to a new metric, host or build? | `${CLAUDE_SKILL_DIR}/references/calibrate.md` |
| Are the compared numbers in a document written so they can be read, and do they match their source? | `${CLAUDE_SKILL_DIR}/references/compared-numbers.md` |

## Order

1. **Noise first.** The others depend on it: a difference is real only against
   a measured null, a correlation between autocorrelated series is not
   evidence until the noise is characterised, and a model's adequacy check is
   the noise analysis run on its residuals. Run `noise.md` on any series
   before drawing a conclusion from it.
2. **Then the question.** `distributions.md` for a comparison,
   `structural-model.md` for a trend, `perturbation.md` for a cause.
3. **A threshold from somewhere else** goes through `calibrate.md` before it is
   used.
4. **Writing it up:** `compared-numbers.md` checks the document, then
   `publish` checks where it goes.

The reference files name each other by file name; they all sit in
`${CLAUDE_SKILL_DIR}/references/`.

## Never

- **Never quote a difference without the noise floor** it was compared
  against.
- **Never call a correlation between two time series evidence** before
  `perturbation.md`'s checks for autocorrelation.
- **Never reuse a threshold across sources** without `calibrate.md`.
