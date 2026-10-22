---
name: bench
description: Benchmark something in any repository and get a number that means what it says — state the question and the result that would refute it before running, check the instrument measured the subject (not the client, a queue, a lock, or work that never happened), run A/B comparisons interleaved in one session with at least four runs a side and a measured A-vs-A floor, capture the whole run before filtering it, and record every number with the command, the conditions and the run count that produced it. Also carries the local rack's path (SystemsLab, anvil VMs, rezolus recordings) and tiered sweeps of a configuration space with per-cell gates. Use before running or reading a benchmark, before reporting any timing, throughput, latency, memory or tok/s figure, when two runs disagree, when a result looks clean, when comparing two builds or configurations, when mapping how a server scales across processes, threads, placement or connections, and before writing a measured value into a test threshold, a comment or a commit message.
---

# Benchmark

A benchmark number is a claim about a system. The wrong ones were rarely
noisy; they were precise, plausible, and about something else: the client,
a lock wait, a stale baseline, a run that did no work. Every step below ties
the number to what produced it.

## 1. Write the question down before running

The subject (the code or server under test), the comparison, the statistic
that answers it (a percentile, not a mean, when the cost lands in the tail),
and the result that would refute your expectation. A prediction written
after the run gets fitted to it.

## 2. Check the instrument measures the subject

`${CLAUDE_SKILL_DIR}/references/validity.md` is the checklist, in the order
it gives: what produced each number, what else was running, whether the
client or the harness was the bottleneck, whether the run reached steady
state, whether a green result did work, and whether a ratio sits on a fixed
floor. Run it on the first run, not after the campaign.

## 3. Compare with discipline

- **One session, interleaved** (A B A B, not all A then all B), **at least
  four runs a side.** Thermal state, caches and other tenants drift between
  sessions.
- **The same instrumentation on both sides.** A facility on one side only is
  the comparison.
- **A current baseline**, built from the same commit the change is based on.
- **Fresh state per arm** (one server per arm, caches and trees empty at the
  start), and one control point that every arm shares with the last
  published run, so a run on a loaded box shows up as a moved control.
- **The A-vs-A floor:** the spread between runs of the same configuration.
  A difference inside it is not a difference. `interpret` decides whether a
  difference is real and what kind it is.
- **One variable per comparison.**

## 4. Capture, then filter

Write each run's whole output to a file, take the exit code, then grep the
file. A run piped through `tail` or `head` loses the line you will need, and
a count taken from truncated output counts what survived the pipe. Keep the
raw results where a reader can find them (`report`'s method section).

## 5. Record every number with its provenance

The command, the commit, the host and its state (idle or not), the
configuration, the run count, and which part is measured and which inferred.
A number written into a test threshold records the distribution it came
from, applies its bound to every case, and prints the distribution when it
fails (`validity.md`, "Before writing a measured value into a threshold").

## On the local rack

Running on hv01, hv02, delta, the Pis or the Macs through SystemsLab, with
rezolus recordings, follows `${CLAUDE_SKILL_DIR}/references/rack.md`: which
environment, VM fidelity, recording as you go, reading the recording rather
than the console, and the A/B decision rule for this lab. `lab` covers
getting the job onto the rack.

Mapping a server across a configuration space (processes, threads, CPU and
IRQ placement, connections, payload size) in tiers from a wide grid to long
runs of the leaders, gating every cell before ranking it, follows
`${CLAUDE_SKILL_DIR}/references/sweep.md`. Its report script is
`${CLAUDE_SKILL_DIR}/references/sweep_report.py`.

The references name their siblings as "beside this file"; all of them are in
`${CLAUDE_SKILL_DIR}/references/`.

## Never

- **Never report a number you cannot trace to the command that produced
  it**, or one measured earlier under different conditions as if current.
- **Never compare sessions run at different times** without a shared
  control point.
- **Never read output you truncated**, or a pipeline's exit code as the
  tool's.
- **Never quote a difference without the A-vs-A floor** it was compared
  against.
