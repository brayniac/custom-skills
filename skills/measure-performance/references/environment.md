# The lab, and what a number from it means

Getting work onto the rack is the `vm-job` skill's subject, and it is the
authority on shapes, images, specs, and orphan recovery. This file covers only
what bears on whether a *measurement* from a given host means anything.

## Find the fleet, do not remember it

```
list_hosts                    # systemslab MCP; no arguments
list_hosts(tag: "pi4b")       # filter by tag substring
```

Read `state` as well as `tags`. Registration times are recent because agents
re-register; a fresh `registeredAt` does not mean a fresh machine.

## Host classes are comparability classes

At last observation: `hv01` (`z2.baremetal`, `hypervisor`), `hv02`
(`z1.baremetal`, `hypervisor`), `pi00`–`pi19` (`pi4b`, except `pi01` and `pi06`
which are `pi4b-thermal`), and `macbook`. Re-verify rather than trusting that
roster.

| Class | Hardware | Slots |
| --- | --- | --- |
| `z2.baremetal` (hv01) | Zen 2, 56 vCPU, ~224 GiB, one RTX 4090 | 7 usable |
| `z1.baremetal` (hv02) | Zen 1, 24 vCPU, ~96 GiB, one RTX 4090 | 3 usable |
| `pi4b` | Raspberry Pi 4B ×18 | — |
| `pi4b-thermal` | Raspberry Pi 4B ×2, held apart | — |

One slot is one CCX: 4 cores / 8 threads, 4 GiB per thread, on both hosts.

**Zen 1 and Zen 2 are different microarchitectures.** A z1 number and a z2
number are two facts about two machines, and neither is a baseline for the
other. The generation also constrains the shape: `z2.c` only runs where
`z2.baremetal` is, so an instance type already implies a host.

`pi4b-thermal` is the subtle one. Two hosts carry it *instead of* `pi4b`, so
scheduling by tag `pi4b` never places onto them. A run that landed on one was
deliberate, and its numbers belong to that host rather than to the pool.

## Exclusivity is already guaranteed — do not manage it

**SystemsLab runs one job per host.** That is the isolation: if your job is
running, you have the machine. There is no co-tenant to measure alongside, and
there is nothing to drain.

This is different from measuring on a shared workstation, and it changes what
the failure looks like:

- `state: busy` means **another job owns the host**. You wait for it; you do not
  measure next to it.
- `503 No suitable slots available` is **never ordinary contention**. With one
  job per host it means an orphaned guest is holding slots, or a slot-release
  bug. `vm-job` step 6 has the recovery. Do not retry around it, and do not
  treat a number obtained after a retry as clean.

What still applies from measuring anywhere else: if `user` + `sys` come back far
below `real`, the process was waiting rather than running, and something in the
setup — not a co-tenant on the host — is responsible.

## Which image to measure in

`debian-13-base@golden` carries **rezolus**, plus slipway and stressapptest. It
is the measurement image, and it has no Rust toolchain. `debian-13-ci@golden` has
the toolchain and a warm crates index but is built for building.

Two image differences change results outright:

- **`io_uring_disabled` is 0 on the Debian images and 2 on `rocky-10`.** Any
  io_uring measurement — ringline especially — is measuring a different code
  path on Rocky, not a slower one.
- Kernel version travels with the image (6.12 on `debian-13-ci`). A comparison
  across images is a comparison across kernels.

`rocky-10` exists on hv01 only, which means a Rocky-versus-Debian comparison is
also a same-host comparison by necessity. That is the good case; take it.

## On the hypervisors, measure in a VM

**Default to a VM on hv01/hv02 for every measurement.** Not as a trade-off
against bare metal — bare metal there is the worse environment, because the
hardware worth measuring is not on the host.

The NIC ports and the GPU are assigned to slots for guest passthrough. On hv01
the X710's port 0 carries five SR-IOV VFs, one per non-PF slot (1, 2, 3, 6, 7);
remaining ports go to slots as whole-PF passthrough, and each host's RTX 4090
goes to a guest unless the spec sets `gpu = false`. A device bound to vfio for
passthrough is **not present on the host**, so a bare-metal `shell` step cannot
measure the network or the GPU at all. It is not a less isolated view of the same
machine; it is a different, poorer one.

A plain `shell` step pinned to a hypervisor is technically permitted, and is the
right tool only when there is a **named performance question that requires it** —
a suspected virtualization overhead, or something in the host kernel. "To avoid
verifying fidelity" is not such a question. When you do it, say in the report
that it was bare metal and which devices were therefore unavailable.

## The non-hypervisor hosts are a different story

`pi4b`, `pi4b-thermal`, and the Mac hosts (`macbook` was the only one registered
at last look; a `macstudio` may join) run work directly. There is no VM layer, so
the fidelity section below is irrelevant to them — and different concerns replace
it:

- **Pis are thermally limited.** That is what the separate `pi4b-thermal` tag is
  about, and it makes run order matter: back-to-back runs on one Pi are not
  independent samples, and a long A/B on a single Pi drifts. Interleaving matters
  more here than anywhere else in the lab.
- **Eighteen `pi4b` hosts are not eighteen identical hosts.** Per-unit variation
  and cooling differences are real, so a comparison that changes host between
  sides has host variance in it. Pin both sides to one Pi, or run enough hosts to
  measure the spread and report it.
- **A Mac host is also somebody's workstation.** The one-job-per-host guarantee
  is weakest where a human is typing; treat a Mac number as indicative and never
  as the basis for a regression verdict.
- **Metric coverage differs by platform.** rezolus's samplers are Linux-centric,
  so confirm with `describe_metrics` what a given host's recording actually
  contains rather than assuming parity with a Debian guest.

## VM fidelity: what to verify, and where

anvil makes a VM a usable measurement environment through properties in the
libvirt domain XML. They were added as fixes, so a hypervisor running an older
agent produces VMs without them, and nothing in the guest announces their
absence.

| Property | Why a measurement needs it | Element |
| --- | --- | --- |
| emulator + iothread pinned to reserved host CPUs | QEMU's own threads otherwise run on the vCPUs under measurement | `<emulatorpin cpuset=…>`, `<iothreadpin iothread='1' cpuset=…>` outside the guest's `<vcpupin>` set |
| guest memory strict-bound to the allocated NUMA node | otherwise memory latency and bandwidth are whatever the host chose | `<numatune><memory mode='strict' nodeset=…/>` |
| one guest die per allocated CCX | the guest's L3 boundaries match the real ones, so cache-aware code and the guest scheduler behave as on metal | `<topology sockets='1' dies='N' …/>` with `N` = CCX count |
| `migratable='off'` | libvirt strips invtsc from a *migratable* host-passthrough CPU, costing the guest a usable TSC clocksource. Without it, fine-grained timing in the guest is untrustworthy | `<cpu mode='host-passthrough' check='none' migratable='off'>` |
| `host-passthrough` + cache passthrough | the guest sees the real CPU model and real cache sizes, so a cache-sized working set behaves as on metal | the `<cpu>` block above, plus `<cache mode='passthrough'/>` |

`crates/anvil-agent/src/domain.rs` emits these and carries a test per property
(`cpu_is_not_migratable_so_invtsc_survives` and siblings), so those test names
tell you whether a given anvil *build* has them.

**Verify from the host, not from the guest.** `virsh dumpxml <domain>` on the
hypervisor is the authoritative answer, run as a `shell` job pinned to that host
per `vm-job`. A guest's own `lscpu`, `numactl --hardware`, and `/proc/cpuinfo`
report what it was *told*, which is the thing under question — they are a useful
cross-check and are not evidence on their own.

The one guest-side reading worth taking at face value is a negative:

```sh
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
```

If that is not `tsc`, the guest does not have a usable TSC regardless of what the
XML says, and every sub-millisecond timing from it is unusable. Say so rather
than adjusting for it.

**Multi-slot placement must stay on one CCD.** If it spanned CCDs, cross-CCX
memory traffic is inside the measurement and nobody put it there deliberately.
