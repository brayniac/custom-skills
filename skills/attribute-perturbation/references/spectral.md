# Spectral tools: lines and coherence

Everything here is NumPy + SciPy (BSD-3), no extra dependency.

## Multitaper spectrum

Welch trades resolution for variance by cutting the record into segments.
Multitaper (Thomson) instead applies `K` orthogonal Slepian tapers to the *whole*
record and averages the resulting eigenspectra — same variance reduction without
throwing away resolution, and with far less leakage. That leakage margin is what
makes it usable against a 1/f background, where a Welch periodogram smears a
strong low-frequency component across the band you are inspecting.

Parameters: `NW` is the time-bandwidth product (4 is the workhorse; 2.5 for
finer resolution, 8 to suppress leakage harder), and `K = 2·NW − 1` tapers is the
most you can use before the later tapers leak.

## Thomson's harmonic F-test

This is the part that makes a periodic finding defensible. At each frequency it
fits a pure complex sinusoid and asks whether the fitted amplitude explains
enough of the local power to be a line rather than a bump in a colored
background. The statistic is `F(2, 2K−2)` distributed under the null.

Use it, not a peak-picker. **Against 1/f, eyeballed peaks are not evidence** —
the background itself rises without limit as frequency falls, so the largest
peaks in a periodogram of red noise are at the low-frequency end every time.

Reporting: quote the frequency, the F value, its p-value, **and the number of
frequency bins searched**. Scanning 4096 bins at α = 0.01 yields ~41 false lines;
apply Bonferroni (α/bins) or report the expected false count alongside.

```python
import numpy as np
from scipy.signal.windows import dpss

def multitaper(x, fs=1.0, NW=4, K=None):
    """(freqs, psd, F, p) — multitaper PSD and Thomson harmonic F-test."""
    from scipy.stats import f as fdist
    x = np.asarray(x, float) - np.mean(x)
    n = len(x); K = K or int(2 * NW - 1)
    tapers = dpss(n, NW, K)                       # (K, n)
    Y = np.fft.rfft(tapers * x, axis=1)           # (K, nfreq) eigencoefficients
    psd = (np.abs(Y) ** 2).mean(axis=0) / fs
    V0 = tapers.sum(axis=1)                       # taper DC gain; odd tapers ~0
    denom_V = (V0 ** 2).sum()
    mu = (V0 @ Y) / denom_V                       # fitted line amplitude per freq
    resid = Y - np.outer(V0, mu)
    num = (K - 1) * denom_V * np.abs(mu) ** 2
    den = (np.abs(resid) ** 2).sum(axis=0)
    F = num / np.maximum(den, 1e-300)
    p = fdist.sf(F, 2, 2 * K - 2)
    return np.fft.rfftfreq(n, 1 / fs), psd, F, p
```

### What it can actually find

Checked against a 1/f background of total σ = 10 with a line at f = 0.073,
n = 8192, Bonferroni-corrected α = 0.01 over 4097 bins:

| line amplitude | line PSD vs *local* background | detection rate |
| --- | --- | --- |
| 1 | 3.5× | 0.05 |
| 2 | 13× | 0.35 |
| 4 | 47× | 0.90 |
| 8 | 196× | 1.00 |

**A line competes only against the background at its own frequency, not against
the series' variance.** A component an order of magnitude below the overall
standard deviation is found easily if it sits where the background is quiet, and
a much stronger one is missed under the 1/f rise. Budget for roughly 50× above
the local background PSD for reliable detection; below about 10×, absence of a
line is not evidence of absence — say so rather than reporting a clean spectrum.

This is also why the leakage margin matters: a leaky estimator raises the local
background with power borrowed from the low-frequency end, which is exactly the
denominator this test divides by.

The null side holds. Over 40 records of pure 1/f noise the smallest p-value never
reached the Bonferroni threshold (median smallest p = 7.5e-2).

## Unevenly sampled or gapped data

**Lomb–Scargle** (`scipy.signal.lombscargle`) fits sinusoids by least squares at
each trial frequency and needs no uniform grid. It is the right answer where
`analyze-noise` tells you to split at gaps and you would rather not.

Two cautions: pass the normalization explicitly and know which convention you
asked for, and remember the false-alarm probability depends on the number of
*independent* frequencies, which for irregular sampling is not the number you
evaluated. Astropy's implementation carries a calibrated FAP if you need one.

## Coherence

Magnitude-squared coherence `C(f) ∈ [0,1]` is the frequency-resolved correlation:
how much of one signal is linearly predictable from the other, per frequency band.
The phase gives the lead/lag at each frequency.

**The null distribution is the whole story.** For `K` independent segments,
`P(C > c) = (1−c)^(K−1)` under the null, so:

```
mean under the null   = 1/K
α-level threshold     = 1 − α^(1/(K−1))
```

| K segments | null mean | 5% threshold | 1% threshold |
| --- | --- | --- | --- |
| 4 | 0.250 | 0.632 | 0.785 |
| 8 | 0.125 | 0.348 | 0.482 |
| 16 | 0.063 | 0.181 | 0.264 |
| 32 | 0.031 | 0.092 | 0.138 |
| 64 | 0.016 | 0.046 | 0.070 |

The simulated null means match `1/K` to three decimals. So a coherence of 0.3
from 8 segments is *below* the 5% threshold and means nothing; the same 0.3 from
64 segments is overwhelming. **Never read a coherence without K.**

The tradeoff is unavoidable: more segments means a trustworthy threshold and
worse frequency resolution. Below about 16 segments the threshold is so high the
test has almost no power — if you cannot afford 16 segments at the resolution you
need, the record is too short for the question.

```python
from scipy import signal

def coherence(a, b, fs=1.0, nperseg=256, noverlap=0):
    f, C = signal.coherence(a, b, fs=fs, nperseg=nperseg, noverlap=noverlap)
    K = len(a) // nperseg if noverlap == 0 else None   # only exact when disjoint
    return f, C, K

def coherence_threshold(K, alpha=0.05):
    return 1.0 - alpha ** (1.0 / (K - 1))
```

Overlapping segments (the SciPy default is 50%) raise `K` without adding
independent information — the thresholds above then read optimistic. Use
`noverlap=0` when you intend to test, and overlap only for a picture.

## Wavelet coherence

When the coupling is intermittent — present during one phase of a run and absent
in another — coherence over the whole record averages it away. Wavelet coherence
resolves time and frequency together and is the right tool for "they moved
together only while the cache was filling". It has no clean analytic null, so
significance comes from a surrogate ensemble (phase-randomized or block-bootstrap
resamples), which is a substantially bigger commitment than the table above.
Reach for it when the fixed-window answer is ambiguous, not before.
