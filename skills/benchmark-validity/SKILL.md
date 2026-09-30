---
name: benchmark-validity
description: Check that a measurement measured its subject before anyone interprets it — that the instrument was not the bottleneck, that the run reached steady state, that the comparison changed one variable, and that a green result did not come from work that never happened. Use when running or reading a benchmark, when two runs disagree, when a result looks clean, and before writing any number into a document or an issue.
---

# Benchmark validity

A benchmark number is a claim about a system. Most bad claims are not noisy —
they are precise, plausible, and about something other than the subject. Every
check below corresponds to a measurement that looked fine and was wrong.

This is the instrument-agnostic layer. `measure-performance` owns getting a
number out of this lab specifically — hosts, recordings, and whether a
difference between two numbers is real — and is the authority where the two
overlap.

## Before reporting any number

Answer four questions, in the report:

1. **What command produced it?** The one whose output you are reading, not the
   one you meant to run. If you are quoting what a script does, check the
   script produced the number and you did not run the underlying tool by hand.
2. **What else was running?** See "Before trusting a timing".
3. **Which part was measured and which was inferred?** State an inference at
   the confidence of an inference.
4. **Did each step do what it is for?** Check its effect, not its exit status.

Capture the whole run to a file and filter the file. Piping a run through
`tail` or `head` cut the evidence five times in one day across two sessions: a
report of 7 test binaries when 55 ran, the `real` line of `/usr/bin/time`
output cut off twice, a whole check battery's output lost, and the "behind
origin/main by 25 commits" line that was the evidence being sought.

## Before interpreting a number

**Is the instrument the bottleneck?** Check saturation on the *load generator*,
not only on the server, and on the environment as well as the processes. On
cloud instances that means the platform's own allowance counters on every host
in the run — `network_ena_bandwidth_allowance_exceeded`,
`network_ena_pps_allowance_exceeded`. In one run the generators were throttled
in 97% of the one-second samples of the measured window while the server
recorded zero throttle events, so every latency figure bounded the generators
rather than the server. The asymmetry gave it away before the counters did: two
generators driving identical load reported materially different tails.

**Did the run reach steady state?** A run that starts cold and reports one
average across its duration reports a value that occurs nowhere in it. After
dropping caches, one miss rate went 57.9% → 29.9% → 24.7% across an hour, and a
five-minute run reported the second block as though it were the answer. Read
the tail of the per-second data and confirm it has flattened; if it is still
moving at the end, the run was too short. The bias has a direction, which is
worse than noise — it distorts the *shape* of a sweep rather than its level,
because it is strongest at one end.

**Does the comparison change exactly one variable?** Before explaining why two
runs disagree, enumerate every difference between them. Two experiments once
differed in working set by 16x *and* in topology, with the effects comparable
in size and opposite in sign, so they landed within 20% of each other for
unrelated reasons and the agreement was read as a fact about topology. The fix
is cheap: take one run's own evaluated spec, change the single variable, re-run.

**Does the mechanism explain the magnitude, at the operating point that
matters?** The first plausible mechanism that fits the sign is not necessarily
the operative one. A read path burning 1.8x the CPU per byte looked like a
sufficient explanation for its deficit — but the deficit appeared at an
operating point where neither CPU nor link was saturated, which that figure
cannot account for. The discriminator was segment formation: measured from the
packet counters, the same 56 KiB value cost 3.98 packets on one path and 6.96
on the other, so 1.75x the segments for identical bytes. The CPU difference was
real, and was not the cause.

**Is the tier you named the tier you exercised?** A cache benchmark whose
working set fits in page cache measures the network and CPU path and says
nothing about flash. `blockio_bytes{op="read"}` flat at zero across every run
is the tell. One query, before the headline.

## Before trusting a green result

**Ask what would have to be true for this to pass while the subject did
nothing.** If you can construct that story, the check is not evidence yet. A
14-experiment A/B of two inference engines reported `Ok: 12 Err: 0` on every
run, with correct-looking engine names and version strings, and was one engine
benchmarked against itself: the second never started — `Address already in use`
— and the readiness probe curled `/health`, which both engines serve. It got a
200 from the stale server and printed "ready".

**A readiness probe must verify identity, not liveness.** "Something answers the
port" is not "my process is up". Gate the endpoint probe on the process being
alive, and distinguish "never started" from "was up, then died".

**Provenance comes from the thing that answered, not the thing you launched.**
Labels read from `--version` on the binary on disk are perfectly accurate about
a process that has already exited, and perfectly misleading about the server
that served the requests.

**A green suite proves no regression, not that the feature works.** A full
goldens run can pass without anything in it ever setting the new flag.

**Assert on evidence that work happened, not on the absence of failure.** A tier
that skips can skip its way to green — one gate passed with 41 of its checks
skipped for missing checkpoints, rendered identically to a real pass. Decide
before the run which line in the log proves the work ran, and grep for that.

## Before trusting a derived view

**Does the chart agree with the counter?** Dashboards compute. One metrics view
rendered block IO at 2x because it summed two overlapping recordings of the same
host, while the cumulative counter in the file was correct throughout. For any
number that will be quoted, derive it once from the raw counter —
`delta / elapsed`, no rate window, no aggregation — and check.

**Did you read the whole recording?** Recordings are chunked, and files written
by background jobs are not finished because they exist. Reading the first of
five segments produced "0 events" for a counter that a query over the same file
showed peaking at 179,749/s. **Two of your own analyses disagreeing is a bug to
find, not a curiosity to note.**

**Does a negative result mean absence?** Analysis tools have parameters that can
erase what you are looking for. An FFT reported "no significant cyclic patterns"
because its auto-selected smoothing window, 15 s, was approximately the 17 s
period it would otherwise have found — it located the period and used it as the
filter width. When a tool reports nothing, check that its settings could have
found something.

**Does the answer know how old it is?** Before believing any claim about what
*currently* exists, check when the thing answering last learned. A package index
frozen for nine days answered "no arm64 build past 5.19.0" with complete
confidence; the registry had it all along. A git checkout 111 commits behind
described a documented parameter as nonexistent. Neither reports its own
staleness — both fail by succeeding.

**Suspicious agreement is evidence, not reassurance.** Two refs at ratios of
exactly 1.001 and 1.000, and a whole-matrix spread inside the noise floor, is
the shape of a rig that measured one thing twice. When a result is suspiciously
clean, read the logs before reporting it.

## Before trusting a timing

**State the compiler cache's state with any build or test duration.** With
sccache on the shared store, the same check took 951 s cold and 503 s warm.
A build time without "cold" or "warm" cannot be compared with anything; to
measure without the cache, run with `RUSTC_WRAPPER=` (empty)
(`use-shared-compiler-cache` step 5).

**Compare `user` + `sys` with `real`.** When CPU time is far below wall time,
the timer measured a wait. Cargo's target-directory lock does this: a second
build elsewhere blocks yours and the wall clock counts the queue. One build read
2658 s wall against 203 s CPU.

**A uniform slowdown across unrelated units is contention.** Contention scales
everything together, so it reads like a fixed cost. One gate run showed 54 s
for each of several test binaries that take 0.1–1.6 s idle. The same rung was
reported three ways — 15 min, "30 min warm / 90 min cold", and 30 s — and only
the last was taken on an idle machine; the first two were published and were
wrong by more than an order of magnitude. Name what else was running before
reporting any duration.

## Before quoting a ratio

**Measure the noise floor first.** Repeats of unchanged code have spanned
0.72–1.15x on one rig, and llama.cpp moved 1.8 points between two clean runs at
temperature 0 — five times the gap that was about to be called an engine
difference. A ratio without a repeat measurement is not a number.

**Comparability of the denominator is separate from its size.** Two arms once
counted tokens on different bases — one estimated, one the exact vocabulary —
differing by ~5%. The *rate* was unaffected, since the same counts sat in
numerator and denominator, so the fix mattered for comparability across arms and
moved the number by 0.3%. Predict which it will be before you fix it.

**Prefer a per-unit figure that does not depend on how much work was produced.**
One engine silently dropped `ignore_eos` and produced 306 tokens where 512 were
requested, with zero errors reported; it surfaced only because the latencies
were arithmetically impossible against each other — higher time-to-first-token
*and* higher per-token time, yet lower total. Check units-per-request, and
compare engines on per-token latency.

**Subtract the fixed floor before computing a ratio.** Two GPU kernels at
240 µs and 279 µs over a ~210 µs dispatch floor are ~30 µs and ~70 µs of work,
not 1.16× apart. Measure the floor with an empty operation and say whether a
ratio includes it.

**An isolated component probe overestimates its share.** Against the real
model, an isolated probe was 1.5–4× over, and counting the operations in a
chain was 5.3× over; differencing the real model with and without a prefix was
within 8%. Measure in place where you can.

**Report sizes the system counted, not sizes the generator intended.** A
prompt generator's nominal sizes ran ~0.87× the tokenizer's count, so a "16k"
prompt was ~14.1k and sat on the other side of a 13,824-token limit. Take sizes
from the system's own counters and label nominal sizes as nominal.

**Check synthetic inputs for aliasing.** Filler seeded as `seed × 7919 mod 24`
gave the 12k and 24k prompts the same opening tokens, so a "cold" run was a
partial cache hit and two cells could not be reported. Use a distinct seed per
input.

## Before writing a measured value into a threshold

- **Calibrate from the whole distribution and have the failing check print
  it.** A bound set from two of eight values fired on a row drifting 2.61 and
  let a row drifting 1.75 through unexamined.
- **Apply one bound to every row.** A bound that applies to some rows and not
  others does not gate the rest.
- **Compare against the format's resolution, not equality.** bf16 has 8
  significand bits, so `ulp(x) = 2^(floor(log2|x|) − 7)`. A difference of one
  ulp means the values cannot be distinguished; a check for `gap == 0.0` calls
  that a failure.
- **Record the platform and inputs** the value was measured on, next to it.

## Order of operations

Establish the measurement envelope before the measurements: which sizes, rates
and durations this rig measures honestly. Find the regimes where the instrument
is not the constraint, then work inside them. A precise answer from outside that
envelope costs the same as a correct one and is much harder to retract.

## Never

- **Never report a per-unit figure below the floor the work structurally
  requires.** An echo server cannot read less than once per operation.
- **Never treat convergence as equivalence.** Two configurations landing within
  a few percent is the signature of a shared ceiling at least as often as it is
  equivalence. Name the constraint both sides were against and say whether
  either had headroom — and note that a closed-loop arm converges on a shared
  ceiling *by construction*, so the agreement is not evidence at all.
- **Never read a load generator's failure reason as the constraint.** When a
  shaper clips, requests queue and service latency rises *before* achieved
  throughput falls below target, so an environment cap and a server limit both
  surface as "latency exceeded". Only the platform's own throttle counters
  separate them, and a run with them firing is a lower bound rather than a
  measurement.
- **Never trust the absence of results** from a query you have not seen return
  a positive. A capped list API reporting 0 rows, a name that matched two
  experiments, and a CLI printing usage text all read as "nothing there".
