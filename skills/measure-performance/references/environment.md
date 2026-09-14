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
which are `pi4b-thermal`), `delta` (`z4.baremetal`, `validation`), and
`macbook`. Re-verify rather than trusting that roster.

**`list_hosts` answers for the deployment you are pointed at, and there is more
than one.** A finding from another SystemsLab instance — a different roster,
cloud instances, different hardware entirely — is not a fact about this rack.
Check the roster before carrying a number or a threshold across.

| Class | Hardware | Slots |
| --- | --- | --- |
| `z2.baremetal` (hv01) | Zen 2, 56 vCPU, ~224 GiB, one RTX 4090 | 7 usable |
| `z1.baremetal` (hv02) | Zen 1 Threadripper 1950X, 24 vCPU, ~96 GiB, one RTX 4090 | 3 usable |
| `pi4b` | Raspberry Pi 4B ×18 | — |
| `pi4b-thermal` | Raspberry Pi 4B ×2, held apart | — |
| `z4.baremetal` (delta) | Zen 4 — **services host, not a measurement host** | 1 |

One slot is one CCX: 4 cores / 8 threads, 4 GiB per thread, on both hosts.

**`delta` is not a comparability class — it is not a measurement environment at
all.** It is the services host (slipway registry, internal apt repo, Caddy) and
since 2026-09-11 the validation host, where image builds and rack-ci-style
checks run without queueing behind a measurement on hv01/hv02. It is
deliberately *not* tagged `hypervisor`, `z1.baremetal` or `z2.baremetal`,
because those are what measurement jobs ask for. A guest there shares delta's
isolated CCX with the resident systemslab, forge and plex VMs and draws on
about 4 GB of 1G pages, so validation jobs say `slots = 1` and
`memory_gib <= 4`. Probes and builds belong there; numbers do not. See
`infra/fleet/hosts/delta.toml`.

**Zen 1 and Zen 2 are different microarchitectures, and hv02 is a Threadripper
rather than a server part.** A z1 number and a z2
number are two facts about two machines, and neither is a baseline for the
other. The generation also constrains the shape: `z2.c` only runs where
`z2.baremetal` is, so an instance type already implies a host.

`pi4b-thermal` is the subtle one. Two hosts carry it *instead of* `pi4b`, so
scheduling by tag `pi4b` never places onto them. A run that landed on one was
deliberate, and its numbers belong to that host rather than to the pool.

**A subset-matching scheduler cannot express exclusion.** There is no "not
thermal": a host stays out of a pool only by lacking a tag, so a tag's
*absence* can be the load-bearing part — and absence is invisible when you read
the tag instead of the roster. Before replacing a tag with what looks like an
equivalent capability, count the hosts matching before and after. Translating
`pi4b` to `["bare","aarch64"]` reads as a faithful rewrite and silently widens
the pool from eighteen hosts to twenty, because both are true of the two
thermal Pis.

## Exclusivity is already guaranteed — do not manage it

**SystemsLab runs one job per host.** That is the isolation: if your job is
running, you have the machine. There is no co-tenant to measure alongside, and
there is nothing to drain.

**That guarantee is about scheduling, not about the hardware, and it does not
carry to a cloud instance.** On an EC2-backed deployment you get the whole
instance and still not the whole pipe: a hypervisor-level shaper you cannot see
from inside clips the network, and its allowance is a credit bucket whose state
depends on what ran recently. Nothing surfaces it as contention — `list_hosts`
shows the host idle and the job has it to itself. So before treating a cloud
host as exclusive:

- **Audit the platform's own throttle counters** in the server recording, not
  just the server's. On EC2 that is `network_ena_bandwidth_allowance_exceeded`
  and `network_ena_pps_allowance_exceeded`. A run with them firing is a lower
  bound, not a measurement — and because a shaper makes latency rise before
  achieved throughput falls, an environment cap and a server limit both surface
  at the load generator as "latency exceeded". The counters are the only thing
  that separates them.
- **Treat any credit-metered resource as a hidden variable**: burst network
  allowance, CPU credits, burst IOPS. Interleaving does not rescue these —
  A/B/A/B spreads the depletion across arms instead of removing it, and total
  sweep length silently becomes part of the experiment. A short run is a
  burst-rate number and a long one is a baseline number; both are real, and
  they are not the same measurement. Say which one you are reporting.

This is different from measuring on a shared workstation, and it changes what
the failure looks like:

- `state: busy` means **another job owns the host**. You wait for it; you do not
  measure next to it.
- `503 No suitable slots available` is **never ordinary contention**, but it has
  two unrelated causes and the message distinguishes neither. Check them in this
  order:

  1. **A generation mismatch in your own spec.** `anvil-server` filters candidate
     hosts by generation *before* it looks at slots
     (`crates/anvil-server/src/main.rs`, `a.generation == instance_type.generation`),
     so a `z2.c` request that landed on hv02 is refused **while slots are free**,
     and nothing in the message says "generation". A constraints bug wearing a
     capacity error's clothes, and the cheap thing to rule out.

     The specific trap *was* `tags = ["hypervisor"]` paired with a
     generation-specific shape: both hypervisors carry `hypervisor`, so the
     scheduler may place either way while `z2.c` only works on one.

     **The fix is no longer to pin the tag.** Since anvil 0.8.6, `auto.c` and
     `auto.g` resolve the generation against the host the guest is actually
     being built on — the first moment it is knowable (`InstanceType::parse_for`
     in anvil-types). So say `tags = ["hypervisor"]` with `shape = "auto.c"`
     and let it land either way. Name a generation only when the silicon is
     part of the measurement and a comparison needs the same hardware every
     time. Pinning is what kept every CI check on this rack on one hypervisor
     for five days, and left one of two RTX 4090s unused for the same reason.
     As with fidelity, this is a property of the anvil version *deployed* on
     the hypervisor, not of anvil's `main`.

  2. **An orphaned guest holding slots, or a slot-release bug** — only once the
     spec is ruled out. `vm-job`'s "Cancel, timeout, orphan" step (6) has the
     recovery.

  In neither case retry around it, and never treat a number obtained after a
  retry as clean.

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

`rocky-10` and `rocky-10-base` are on **both** hypervisors now. A
Rocky-versus-Debian comparison used to be same-host by necessity; it no longer
is, so arrange it deliberately — pin both arms to one `host:` tag — rather than
relying on scarcity to do it for you.

## On the hypervisors, measure in a VM

**Default to a VM on hv01/hv02 for every measurement.** Not as a trade-off
against bare metal — bare metal there is the worse environment, because the
hardware worth measuring is not on the host.

The NIC ports and the GPU go to the guest. A VM asks for 0–4 NIC ports and gets
**whole physical functions**, bonded inside the guest — all four if it asks for
four. The host's RTX 4090 likewise goes to a guest unless the spec sets
`gpu = false`.

A device passed through to a guest is **not present on the host**, so a
bare-metal `shell` step cannot measure the network or the GPU at all. It is not a
less isolated view of the same machine; it is a different, poorer one — and the
more of the hardware a measurement actually cares about, the less a bare-metal
step can see of it.

Port layout is per host and configured in `infra/fleet/hosts/<host>.toml`, which
is authoritative. Do not infer it from anvil's `config/agent.toml`, which is a
commented example, or from `host-setup/anvil-sriov-vfs.sh`, which is about
providing SR-IOV VFs to slots that were not given a PF — neither describes what a
given VM can request today.

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
