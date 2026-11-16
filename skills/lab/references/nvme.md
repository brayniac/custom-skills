# NVMe and block devices on the rack

Four kinds of device, from cheapest to dearest. Pick the cheapest one that has
the property under test: a block layer's flush and FUA handling does not need
a real drive, and a drive's latency, cache and wear do. The drive on hv02 is
the only one that shows a real drive's behaviour.

| Device | Where | What it shows | What it does not |
| --- | --- | --- | --- |
| `null_blk` | a Debian guest | the block layer's handling of FUA, flushes and write caches, set per device | a controller, latency, data a real drive would lose |
| NVMe target over loop (`nvmet` + `nvme-loop`), file-backed | a Debian guest | the kernel's NVMe driver, `/dev/ngXnY` and `IORING_OP_URING_CMD` passthrough end to end | a PCI controller, a drive's timing |
| hv02's spare NVMe, passed through | hv02 | a physical controller: cache, FUA, latency, heat | another drive model |
| NVMeVirt | hv01 (whole host), hv02, delta, by reservation size | a PCI NVMe controller emulated in reserved guest memory, with a programmable timing model | a real drive, unless the model is calibrated against one |

Sections 1 and 2 ran on `debian-13-6.12` and `debian-13-7.1`; other images
were not tried. A guest's root disk is virtio, so in sections 2 to 4 the
device under test is the guest's only NVMe, and its names are `nvme0`,
`/dev/nvme0n1` and `/dev/ng0n1` unless something else created one first.
Find it rather than assuming: list `/dev/ng*` before and after creating it.

Writing to a block device needs root: the anvil user has passwordless `sudo`
in the Debian images; check with `sudo -n true` first.

## 1. null_blk: FUA, flush and write-cache behaviour

`null_blk` takes the cache and FUA as module parameters:

```sh
sudo modprobe null_blk nr_devices=1 memory_backed=1 bs=4096 gb=1 cache_size=64 fua=1
cat /sys/block/nullb0/queue/write_cache /sys/block/nullb0/queue/fua
```

- `cache_size=0` gives a write-through device; `cache_size=64` (MiB) a
  write-back one.
- `fua=0` with a cache gives a write-back device without FUA, where the block
  layer turns each FUA write into a write and a flush.
- `echo "write through" > /sys/block/nullb0/queue/write_cache` switches a
  write-back device; the block layer then strips FUA and flushes.
- Print `write_cache` and `fua` from sysfs in each arm: they are the evidence
  that the parameters took. A module parameter the kernel does not know is
  ignored with a warning, not an error. `fua=0` took effect on 6.12 and 7.1;
  older kernels were not tried.

Count what reaches the device with the block tracepoints, around the workload
only, as root (`sudo bash -s <<'TRACE'` ... `TRACE`):

```sh
T=/sys/kernel/tracing
dev=$(( 0x$(stat -c %t /dev/nullb0) )),$(( 0x$(stat -c %T /dev/nullb0) ))
echo > $T/trace
echo 1 > $T/events/block/block_bio_queue/enable   # what was submitted
echo 1 > $T/events/block/block_rq_issue/enable    # what the device got
echo 1 > $T/tracing_on
# ... workload ...
echo 0 > $T/tracing_on
grep -E "block_(bio_queue|rq_issue): $dev " $T/trace \
  | sed -E 's/.*(block_[a-z_]+): [0-9]+,[0-9]+ ([A-Z]+) .*/\1 \2/' | sort | uniq -c
echo 0 > $T/events/enable
```

The second field is `rwbs`: `WFS` is a write with FUA, `WS` a plain write,
`FF` a flush request, and a `FWS` bio is an empty write carrying a preflush.
Add `events/io_uring/io_uring_submit_req` to show whether io_uring submitted
the I/O; on a program with two backends it proves which one ran. Include a
control arm in which the mechanism predicts no FUA and no flush; a count there
means the filter catches something other than the workload.

Measured on Linux 6.12 and 7.1, 64 sequential 4 KiB `O_DIRECT | O_DSYNC`
writes (ringline's direct I/O probe; SystemsLab 01a1e100-79d6 and
01a1e100-7b31):

| Device (counts at `block_rq_issue`) | io_uring write | `pwrite(2)` |
| --- | --- | --- |
| write-back, FUA | 64 `WFS`, no flush | 64 `WFS` and 64 `FF` |
| write-back, no FUA | 64 `WS` and 64 `FF` | 64 `WS` and 128 `FF` |
| write-through | 64 `WS` | 64 `WS` |
| no `O_DSYNC` | 64 `WS` | 64 `WS` |

On a write-back device every `O_DSYNC` write is `WFS` at `block_bio_queue`,
and `pwrite(2)` adds 64 `FWS`; without FUA the block layer turns each into a
write and a flush before `block_rq_issue`. On a write-through device FUA and
the preflush are removed before `block_bio_queue`, so both tracepoints show
64 `WS`.

## 2. NVMe over loop: passthrough without hardware

The NVMe target serves a namespace from a file, and the loop transport
connects the guest's own NVMe host driver to it. The namespace gets a
`/dev/nvmeXnY` and a generic `/dev/ngXnY`, which accept
`IORING_OP_URING_CMD`.

```sh
truncate -s 256M /home/anvil/nvme.img
sudo modprobe -a nvmet nvme-loop
sudo bash -s <<'SETUP'
set -e
C=/sys/kernel/config/nvmet
mkdir $C/subsystems/rl
echo 1 > $C/subsystems/rl/attr_allow_any_host
mkdir $C/subsystems/rl/namespaces/1
echo -n /home/anvil/nvme.img > $C/subsystems/rl/namespaces/1/device_path
echo 1 > $C/subsystems/rl/namespaces/1/enable
mkdir $C/ports/1
echo loop > $C/ports/1/addr_trtype
ln -s $C/subsystems/rl $C/ports/1/subsystems/rl
echo "transport=loop,nqn=rl" > /dev/nvme-fabrics
SETUP
sleep 2; sudo udevadm settle; ls -l /dev/ng*
```

- The file backend reports the backing filesystem's block size: 4096 on the
  Debian images' ext4.
- Write a marker into the file before connecting and check that a read of LBA
  0 returns it: that is the positive control that the I/O reached the file.
  Read the file after disconnecting to check what a write left there.
- Ran on `debian-13-6.12` and `debian-13-7.1` on delta (SystemsLab
  01a1e100-7abb and 01a1e100-7bcb): `nvmet` and `nvme-loop` load from the
  stock kernel, and the namespace appeared as `/dev/ng0n1`.

## 3. hv02's spare NVMe, passed through

hv02 has a spare Samsung SSD 960 EVO 1TB (firmware 2B7QCXE7). anvil passes it
to a guest when the step asks for the role:

```toml
[[jobs]]
name = "nvme"
tags = ["z1.baremetal"]

[[jobs.steps]]
type = "anvil-vm"
shape = "z1.c"
image = "debian-13-6.12"
gpu = false
ports = 0
pci_roles = ["nvme"]
boot_timeout = 600
```

- The role is resolved on the host from `[[pci_devices]]` (`address`, `role`)
  in its `/etc/anvil/agent.toml`, so specs carry no PCI address. A host with no
  device for the role fails at instance creation with "host offers no PCI
  device for role". No host tag says a host has one; `z1.baremetal` (or
  `host:hv02`) is how a spec reaches it. No other host is recorded as having
  one.
- libvirt rebinds the drive to `vfio-pci` at start and back at destroy
  (`managed='yes'`), which adds about 150 to 200 ms to teardown. Nothing needs
  binding by hand.
- The guest boots from virtio and the drive holds nothing that is kept: specs
  discard and overwrite it whole. Guard anyway, before the first write, so a
  spec that lands somewhere else cannot destroy that host's disk: exactly one
  NVMe controller, its model is the 960 EVO
  (`/sys/class/nvme/nvme0/model`, padded with spaces), nothing mounted from
  it, and the root filesystem not on it. Do not trust the kernel's partition
  list for that: after a fill it has shown phantom partitions parsed from the
  fill data. Use `sudo blkid -p` and `sudo wipefs -n` to look for real
  signatures; both are in `/usr/sbin`, which the ssh user's PATH lacks.
- A discarded NVMe reads zeros at DRAM speed. Write the range before
  measuring reads from it.
- `write_cache` is a per-job setting in sysfs, not part of the image. Setting
  it to `write through` cut fsync p99.9 from 64.8 ms to 0.43 ms on this drive,
  because the kernel then sends no flush or FUA and the drive, which has no
  power-loss protection, keeps the data in its volatile cache. A fast fsync
  there is not a durable one. Print it, and set it in the spec when it
  matters.
- The drive heats by about 3 °C per minute under load and does not cool
  between arms; throughput correlated with starting temperature at -0.92 in
  one study. Read the temperature (`sudo nvme smart-log`, with
  `packages = ["nvme-cli"]` on the step, or
  `/sys/class/nvme/nvme0/hwmon*/temp1_input`) per arm, and treat A/B
  differences under about 12% as noise unless the arms are interleaved and
  the temperature is controlled.
- The standard SMART log works (it reports host writes only); the OCP log
  page `0xC0` and the vendor pages `0xC1`, `0xC2`, `0xCA`, `0xD0` and `0xDD`
  return Invalid Log Page.
- Seen in the guest (SystemsLab 01a1e109-4726-715e-de70-536a4567f949,
  `debian-13-6.12`): `/dev/nvme0n1` and `/dev/ng0n1`, a 512-byte logical block,
  `write_cache` "write back", `fua` 1. The 64-write `O_DSYNC` probe of section 1
  gave the same counts as `null_blk`'s write-back FUA row: 64 `WFS` from
  io_uring with no flush, 64 `WFS` and 64 `FF` from `pwrite(2)`.
- The block trace of a whole device also shows a few `R` and `RA` reads per
  arm that the workload did not issue, most likely udev probing the device
  after a process that had it open for writing closes it (inferred, not
  traced). Count by `rwbs` rather than in total.
- It is one consumer drive. Say so in any result about drives in general.

## 4. NVMeVirt

NVMeVirt (github.com/snu-csl/nvmevirt) is a kernel module that presents a PCI
NVMe controller backed by memory reserved at boot, with a timing model set by
module parameters. The reservation decides the host. A 128 GiB reservation
needs a whole hv01 (`z2.c`, 56 vCPU), below. hv02 has run it with 48 GiB
reserved (`z1.c`, `memory_gib = 80`, `memmap=48G$16G`, `isolcpus=16-23`,
`cpus=16,18,20,22`), and delta with 2 GiB.

```toml
[[jobs]]
name = "vm"
tags = ["z2.baremetal"]

[[jobs.steps]]
type = "anvil-vm"
mode = "start"
shape = "z2.c"
image = "debian-13-6.12"
gpu = false
memory_gib = 152
boot_timeout = 900
kernel_args = ["memmap=128G$16G", "isolcpus=48-55"]
```

That step only starts the guest. Follow it with `mode = "exec"` steps that
build, load and run, and a `mode = "stop"` step.

- `kernel_args` (anvil >= 0.10.9) writes a grub drop-in, reboots once and fails
  unless `/proc/cmdline` carries each argument. An argument with `$` needs
  `update-grub`, so a Debian or Ubuntu image.
- `memory_gib` must cover the offset plus the reservation: 128 GiB at 16 GiB
  needs at least 144.
- Build in the guest: `linux-headers-$(uname -r)`, `build-essential`, `git`;
  clone and pin a commit, then `make`. The stock module advertises no
  deallocate (`oncs 0`, `discard_max_bytes 0`); discard needs a patch.
- Load with the reservation and dedicated cores, matching `kernel_args`:
  `sudo insmod nvmev.ko memmap_start=16G memmap_size=128G cpus=48,50,52,54`
  (a dispatcher and I/O workers on isolated cores). Capacity depends on the
  profile's spare area: 128 GiB reserved gave 98.5 GiB logical with a patched
  profile at 30% spare, and 109.4 GiB with another.
- A 2 GiB reservation gives 24 erase units of logical space, which leaves
  greedy garbage collection little choice of victim. The GC comparisons used
  128 GiB, about 1,500 erase units.
- One run on hv01 oopsed in the patched module's submission-queue path
  (`nvmev_proc_io_sq`) during a fill: one in 41 arms at 3200 MT/s, and 39
  clean at 2666 MT/s, to which hv01's memory was lowered on 2026-11-05. The
  clean runs do not separate a memory error from a bug in the patch. Keep the
  kernel log (`dmesg`) as an artifact of every arm.
- Its numbers are the model's. A result from it is about a real drive only as
  far as the profile was calibrated against that drive.
