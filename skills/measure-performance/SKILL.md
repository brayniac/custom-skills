---
name: measure-performance
description: Produce a performance number from the local lab — anvil VMs or bare metal, run through systemslab, read back from a rezolus recording — and decide whether a difference between two of them is real. Use before reporting any timing, throughput, or latency figure from this lab, when comparing two builds or configurations, and when a measured difference needs a verdict rather than a description.
---

# Measuring performance in the local lab

Three systems, one loop: **anvil** decides what hardware the workload actually
gets, **systemslab** runs it and records, **rezolus** is what you read the
numbers out of. Most wrong numbers here come from the seams between them, not
from the workload.

**Getting work onto the rack is the `vm-job` skill.** It owns shapes, images,
specs, artifacts, and orphan recovery, and it is the authority whenever the two
disagree. Spec syntax beyond that is in
`systemslab/docs/llm/writing-experiments.md`. This skill starts where those leave
off: choosing an environment whose numbers mean something, and deciding whether a
difference between two of them is real.

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
`503 No suitable slots available` is never ordinary contention: it means an
orphaned guest or a slot-release bug, which `vm-job` step 6 recovers. A number
obtained after retrying around a 503 is not a clean number.

## Step 2 — If measuring inside an anvil VM, verify fidelity first

A VM is a valid measurement environment here only because anvil was fixed to
make it one. Five properties carry that, and all of them are guest-visible:

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
to reason around later. Give it a `source`, because that is the label you select
the recording by afterward.

For anything with a client and a server, `systemslab/barrier` is what makes the
measured window the same window on both hosts. Without it you are averaging over
one side's startup.

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
- **Never work on hv01/hv02 outside a job**, and never report a number from a run
  that needed a retry past a 503.
- **Never cite a guest's own topology report as hardware fact.** Corroborate on
  the host.
- **Never pipe a run through `tail` or `head` and reason about what survived** —
  write it to a file and grep the file. The line you want is
  disproportionately the one you cut.
- **Never report a single run as a result**, and never quote a figure measured
  earlier under conditions you are no longer certain of.
