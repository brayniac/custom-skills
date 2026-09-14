---
name: measure-performance
description: Produce a performance number from the local lab — anvil VMs or bare metal, run through systemslab, read back from a rezolus recording — and decide whether a difference between two of them is real. Use before reporting any timing, throughput, or latency figure from this lab, when comparing two builds or configurations, and when a measured difference needs a verdict rather than a description.
---

# Measuring performance in the local lab

Three systems, one loop: **SystemsLab** picks the machine and runs the work,
**anvil** builds the VM the shape asks for, **rezolus** is what you read the
numbers out of. Most wrong numbers here come from the seams between them, not
from the workload.

**Getting work onto the rack is the `vm-job` skill.** It owns shapes, images,
specs, artifacts, and orphan recovery, and it is the authority whenever the two
disagree. Spec syntax beyond that is in
`systemslab/docs/llm/writing-experiments.md`. This skill starts where those leave
off: choosing an environment whose numbers mean something, and deciding whether a
difference between two of them is real.

## The two layers, and which one is wrong

**SystemsLab expresses constraints; anvil realizes a shape.** Tags say what kind
of machine the work needs — generation, capabilities — and SystemsLab schedules
onto a host that satisfies them. The shape (`z2.c`, `slots`, `ports`, `gpu`) says
what the VM should look like, and anvil builds one matching it on the host that
was chosen.

Measurement problems get misdiagnosed at that boundary, because the two sides
fail differently:

| Symptom | Layer | Look at |
| --- | --- | --- |
| job pends forever, or ran on the wrong generation | constraints | tags. They are ANDed, so `["z2.baremetal","z1.baremetal"]` matches nothing |
| `503 No suitable slots available` **while slots are free** | the two disagree | `anvil-server` filters hosts by generation before slots, so a `z2.c` job that landed on hv02 is refused without the message ever saying "generation" |
| instance creation fails | the two disagree | a pinned shape landed on the other generation. Prefer `auto.c`, which resolves against the host it is built on |
| guest topology, pinning, NUMA binding or clocksource wrong | shape realization | the anvil-agent on that host; verify with `virsh dumpxml` |
| no NIC ports or no GPU inside the guest | shape realization | the spec's `ports` and `gpu`, then that host's port config |

Nothing cross-checks the two. A shape that disagrees with the tags is reported at
instance creation rather than at scheduling, which is late enough to read like an
anvil fault when it is a spec fault.

**A number is not a result until you can say what produced it, on what hardware,
with what else running.**

## Step 1 — Choose the environment, and say which one

Call `list_hosts` first. Never assume the fleet, and never carry a host name in
from a previous session.

The tags are the classes, and **numbers do not cross them**: `z2.baremetal`
(hv01) is Zen 2 with 56 vCPU and 7 slots, `z1.baremetal` (hv02) is Zen 1 with
24 vCPU and 3 slots. Different microarchitectures — a z1 result and a z2 result
are two facts about two machines, not a comparison. `pi4b-thermal` is carried by
two Pis *instead of* `pi4b`, so tag `pi4b` never schedules onto them and a run
that landed on one was deliberate. `macbook` measures nothing you would report.
`references/environment.md` has the full table and the image differences that
change results.

**Exclusivity is already guaranteed: SystemsLab runs one job per host.** If your
job is running, you have the machine — there is no co-tenant and nothing to
drain. So `busy` means another job owns the host and you wait for it, and a
`503 No suitable slots available` is never ordinary contention. It has two causes
the message does not distinguish: a **generation mismatch in your own spec**
— check this first, since a generation-specific shape under `tags =
["hypervisor"]` is a coin flip, which `shape = "auto.c"` now removes — or an
orphaned guest holding
slots, which `vm-job`'s "Cancel, timeout, orphan" step (6) recovers. A number
obtained after retrying around a 503 is not a clean number.

## Step 2 — On the hypervisors, measure in a VM, and verify fidelity

**Every measurement on hv01/hv02 happens inside a VM.** Bare metal there is not a
cleaner alternative: the NIC ports and the GPU go to the guest — a VM asks for
0–4 ports and gets whole physical functions, all four if it asks for four — so
they are not present on the host, and a bare-metal `shell` step cannot measure
network or GPU at all. Reach for bare metal only when a named performance question
requires it — a suspected virtualization overhead, something in the host kernel —
and never to avoid verifying fidelity.

The `pi4b` and Mac hosts run work directly and none of this applies to them; see
`references/environment.md` for what replaces it.

### Verify fidelity

A VM is a valid measurement environment only because anvil was fixed to make it
one. Five properties carry that:

1. **emulator and iothread pinned to reserved host CPUs** — otherwise QEMU's own
   threads land on the vCPUs you are measuring;
2. **guest memory bound to the allocated NUMA node** — otherwise memory
   bandwidth and latency are whatever the host felt like;
3. **one guest die per allocated CCX** — so the guest's L3 boundaries match the
   real ones and cache-aware code and the guest scheduler behave as on metal;
4. **`migratable='off'`** — libvirt strips invtsc from a migratable
   host-passthrough CPU, costing the guest a usable TSC clocksource. Without it,
   fine-grained timing inside the guest is not trustworthy at all;
5. **`host-passthrough` and `<cache mode='passthrough'/>`** — the guest sees the
   real CPU model and real cache sizes, so a cache-sized working set behaves as
   it does on metal.

**These come from the anvil-agent version actually deployed on the hypervisor,
not from anvil's `main`.** The fixes are on main and released, which says nothing
about what is running on hv01 today.

**Verify from the host, with `virsh dumpxml`, not from inside the guest.** A
guest's `lscpu` and `/proc/cpuinfo` report what it was told, which is the thing
under question. The one exception is a negative: if
`/sys/.../current_clocksource` is not `tsc`, the guest has no usable TSC whatever
the XML claims. `references/environment.md` has both sets of checks.

Multi-slot instances must land on one CCD. If placement spanned CCDs, a
cross-CCX memory access is in your measurement and you did not put it there.

## Step 3 — Run it, recording as you go

Attach `systemslab/start-metrics` around the measured region, not around the
whole job — setup, warmup and teardown in the recording are noise you will have
to reason around later. Name it after the thing being measured, and put anything
you will select on in `metadata` — **`start-metrics`'s own `source` field is a
rezolus endpoint address, not a label**, and a word there fails the step. The
selector you use later comes from `metadata`; `references/reading-recordings.md`
has the exact mapping.

For anything with a client and a server, `systemslab/barrier` is what makes the
measured window the same window on both hosts. Without it you are averaging over
one side's startup.

**Bracket one recording per measurement cell.** A recording cannot be sliced by
time afterward — `recording filter` trims columns, and `query` has no window
arguments — so an arm that loops over several message sizes or configurations
inside one recording can never attribute CPU or syscalls to any one of them.
Each `start-metrics`/`stop-metrics` pair is its own recording; a long-lived
detached server that is never re-bracketed gets one recording for its whole
life, idle included.

**Choose the loop before you run, and name it in the report.** A closed-loop
arm holds N requests in flight and lets throughput fall out; an open-loop arm
offers a fixed rate and lets latency fall out; an SLO search finds the highest
offered rate that still meets a latency target. They answer different questions
and are not interchangeable.

The closed-loop trap is that it *looks* like a throughput measurement.
Throughput there is `N / E[R]` by construction — the same identity Step 5 uses
to validate the arm — so against any shared ceiling every configuration
converges on the ceiling and reports it as its own number. Measured: three
server read paths on one rig landed within 2% of each other in closed loop,
while the server-side CPU cost of the cheapest and the dearest differed by 1.8x.
The throughput figures were a property of the link; the CPU figures were a
property of the servers. **Closing Little's law does not rescue this** — all
three arms closed it cleanly, and that is precisely why their throughput
comparison was worthless. It validates the arm; it does not make the number mean
what "throughput" implies.

So: closed loop for per-request cost at a fixed concurrency; open loop or an SLO
search for any throughput claim. Make the latency target CO-honest, measured
against offered time rather than service time, or the search finds the ceiling
again.

**Analysis you attach to a running measurement is part of the measurement.**
Before computing anything on the measured node, read
`references/analysis-placement.md`: it splits the analysis techniques in this
library into what is cheap enough to run in the measurement path, what belongs
off the measured cores while the run is live, and what has to wait for the
recording. The cost that matters there is perturbation, not cycles.

## Step 4 — Read the recording, not the console

`references/reading-recordings.md` has the chain and the traps. The short form:

`download_artifact` → `describe_recording` (which recordings exist) →
`describe_metrics` (**what type each metric is**) → `query`.

The type matters more than anything else in this step. A counter queried without
`rate()` returns a monotonically rising number that looks like a plausible
metric and means nothing. `detect_anomalies` needs exactly one series, so
aggregate with `sum()` before handing it a query.

Never invent a label selector. `describe_metrics` lists the labels that exist;
one that does not silently matches nothing, and an empty result reads like a
quiet zero.

## Step 5 — Decide whether the difference is real

- **Interleave, same session, at least four runs per side.** Not A-then-B in
  separate sessions: thermal state and cache warmth drift between them, and on
  the Pis thermal drift is the dominant term.
- **Interleaving does not rescue a credit-based resource.** Where the platform
  meters with a token bucket — "up to X Gbps" network, burst CPU credits, burst
  IOPS — every run after the first draws on a bucket the earlier runs drained.
  A/B/A/B spreads the depletion evenly instead of removing it, and total sweep
  length becomes a hidden variable. The tell is visible inside a single arm: on
  one such fleet the shaping counter climbed an order of magnitude across a
  180 s window at constant offered concurrency. A short run is a burst-rate
  number and a long one is a baseline number; neither is wrong and they are not
  the same measurement. Interleave anyway — but say which regime the figure came
  from, and treat run order as a confound whenever arms run serially against
  shared hardware. `references/environment.md` has the counters.
- **Price against the right baseline.** A win against a stale baseline is a
  measurement of the baseline.
- **Report the distribution, not one number.** If the spread of one side covers
  the difference, there is no difference yet — say that, rather than reporting a
  mean with a confident sign.
- **Use `detect_anomalies` and `analyze_correlation` to find the mechanism**,
  not to decide the verdict. A correlation tells you where to look next; it is
  not evidence that a change caused an effect.
- **Predict before you compute.** A delta you did not expect is information; one
  you did expect and got is not confirmation on its own.
- **Keep the same-configuration pairs.** Interleaving produces A-vs-A comparisons
  as a byproduct — four runs a side gives six — and those pairs are the null
  distribution for every threshold you will ever set on this source.
  `calibrate-to-source` turns them into one; most labs compute them and throw
  them away.
- **Close Little's law before believing a closed-loop arm.** `N = X · E[R]` is
  an identity in closed loop, so a violation indicts the *measurement* —
  coordinated omission, mis-counted operations, a stalled arm — not the system.
  Real arms on this rig close it to 0.1–0.3%. It needs the **mean**, not p50: on
  a mildly skewed latency distribution p50 gave 5.6% error where the mean gave
  1.4%, and a tolerance loose enough to admit that p50 is loose enough to admit
  genuinely broken arms. In-flight work is `connections × pipeline_depth`;
  dropping the depth term rejects every pipelined arm.
- **Validate a gate against real arms, not fabricated fixtures.** A detector
  built to fixtures encodes what you imagined the failure looks like. A
  single-core-funnel detector got it wrong twice, each time caught only by real
  data: *hottest-vs-median* rejected every healthy arm, because a
  thread-per-core runtime is supposed to saturate its workers and leave the rest
  idle (8 workers on 24 cores = 8 at 100%, 16 at ~0%) and that is
  indistinguishable by that rule from one core doing everything;
  *busy-cores-vs-worker-count* then rejected every lightly loaded arm, and
  passed the anomalous runtime while failing the correctly-idle ones — exactly
  backwards. What survived: a funnel is **concentration**, so compare the
  hottest core's share of total busy CPU, and only where there is enough total
  load for the question to mean anything. The fixtures had four moderately-busy
  cores, which is nothing like a pinned thread-per-core server, and that is
  precisely why they passed a broken gate.
- **When the spread will not settle, ask what color it is.** If more runs are not
  tightening the interval, the noise is not white and `1/√N` does not apply. The
  `analyze-noise` skill turns the series into an Allan deviation curve, which
  says whether averaging helps at all, how long a run has to be, and what
  timescale the confounder lives on.

## Step 6 — Report what you actually did

State: the exact command or experiment, the host and its tag, whether it was a
VM or bare metal and whether fidelity was verified, what else was running, how
many runs per side, and the spread. Separate the measured part from the inferred
part explicitly, and never state an inference at the confidence of the part you
executed.

## Never

- **Never compare across host classes.** A z1 number and a z2 number are two
  facts about two machines.
- **Never report a VM timing without saying whether fidelity was verified**, and
  never assume it from the anvil version on main.
- **Never choose bare metal on a hypervisor to sidestep fidelity verification.**
  The NIC and GPU are not on the host, so it answers less, not more. Bare metal
  needs a named question that requires it.
- **Never work on hv01/hv02 outside a job**, and never report a number from a run
  that needed a retry past a 503.
- **Never cite a guest's own topology report as hardware fact.** Corroborate on
  the host.
- **Never hand-roll a CPU sampler beside a recording that already has CPU
  data.** `/proc/stat` busy sums count iowait, which is not busy — it read an
  idle io_uring server as 806% against tokio's 33%, and it biases against
  io_uring specifically rather than adding noise evenly. Use `cpu_usage` or
  `task_cpu_usage`; `references/reading-recordings.md` has the breakdown.
- **Never report a per-operation figure below the floor the protocol requires.**
  An echo server cannot read less than once per operation. A number under the
  structural floor means the window is wrong, not that the runtime is clever.
- **Never pipe a run through `tail` or `head` and reason about what survived** —
  write it to a file and grep the file. The line you want is
  disproportionately the one you cut.
- **Never report a single run as a result**, and never quote a figure measured
  earlier under conditions you are no longer certain of.
