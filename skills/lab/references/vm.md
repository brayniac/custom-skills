# VM job

The rack rule: **hv01 and hv02 are only ever used through SystemsLab jobs.** A
job on a host is the exclusivity guarantee (one job per host). Never `ssh` to a
hypervisor to build, test, or demo, never create a guest with `virsh` by hand,
never `rsync` a tree over. Put the work in a job payload. The one sanctioned
out-of-band action is destroying an orphaned guest after a cancel (step 7).

A whole job — boot, clone, cold build, test suite, teardown — is
about three minutes. Treat "run it on distro X" as routine, not an expedition.

## 1. Pick image, shape, tags

| Need | image | where | notes |
| --- | --- | --- | --- |
| build / test Rust, measure | `debian-13-6.12` | x86, Pis | stock Debian 13 plus rezolus, slipway's remote, bubblewrap, stressapptest, the Rust toolchain with the shared compiler cache, what build scripts commonly need (libssl-dev, libelf-dev, zlib1g-dev, clang, cmake) and a warm crates index; kernel 6.12 |
| newer kernel, io_uring after 6.14 | `debian-13-7.1` | x86, Pis | `debian-13-6.12` on trixie-backports 7.1.13 |
| a specific kernel series | `debian-12-5.10`, `debian-12-6.1`, `debian-12-{6.6,6.9,6.11}`, `debian-13-{6.17,6.18,7.1,7.2}`, `debian-14-7.2` (7.2.12) | hv01, hv02, hv03, Pis; `debian-13-7.1` also on delta; `debian-13-7.2` not on the Pis | rezolus, the Rust toolchain and compiler cache on a Debian kernel; the Debian 13 and 14 ones also have the C build libraries and crates index, Debian 12 does not (see Toolchain below); bookworm userspace for Debian 12, trixie for 13, forky for 14 |
| a kernel.org release or release candidate | `debian-13-7.3-mainline` (7.3.4), `debian-13-7.4-rc` (7.4.0-rc2) | x86, Pis | `debian-13-6.12` on a kernel.org build; infra's `jobs/build-kernel-mainline` builds the kernel, and a point release or rc moves the family. `debian-13-7.3-rc` (7.3.0-rc6) is no longer declared or rebuilt |
| Ubuntu | `ubuntu-24.04-6.8`, `ubuntu-26.04-7.0` | x86 | rezolus, bubblewrap, stressapptest; no internal apt repo or slipway (its packages are built on trixie) |
| RHEL-family behaviour (io_uring refused, SELinux, dnf) | `rocky-10-6.12` | x86, Pis | rezolus, the Rust toolchain; `io_uring_disabled=2` |
| Amazon Linux | `al2023-6.12-i40e` | x86 | kernel 6.12, can drive the passthrough ports. Stock `al2023` needs `ports = 0` |
| Amazon Linux 2, only if the question is AL2 | `al2` | hv01, hv02, hv03 | stock, out of support since 2026-06-30; no python3, `ports = 0`, start payloads with `export PATH=$PATH:/sbin:/usr/sbin` |
| musl, OpenRC | `alpine-3.24` | x86, Pis | busybox userland; no rezolus (recipes, "Alpine") |
| GPU, CUDA 12 | `debian-13-6.12-gpu-cu12` | hv01, hv02 | Debian's driver 550 and CUDA 12.4 toolkit, kernel 6.12; shape `z2.g` (hv01) or `z1.g` (hv02), one RTX 4090 each |
| GPU, CUDA 13 | `debian-13-6.12-gpu-cu13` | hv01, hv02 | NVIDIA's 595 driver and CUDA 13.2 toolkit, kernel 6.12; for CUDA 13 wheels such as vLLM |
| GPU on another kernel or release | `debian-13-{6.17,6.18}-gpu-cu12`, `debian-13-{6.17,6.18,7.1,7.2,7.3-mainline}-gpu-cu13`, `debian-12-6.1-gpu-cu12`, `debian-12-6.1-gpu-cu13`, `debian-14-7.2-gpu-cu13` | hv01, hv02 | no other combination exists. On bookworm (`debian-12-*`) cu12 is driver 535 (CUDA up to 12.2) and nvcc 11.8. A cu13 driver also runs CUDA 12 code. No GPU image on 7.4-rc: NVIDIA's 595 does not build against it |

Name the family (`debian-13-6.12`), not `spool/images/<x>@golden`: the family
resolves to its current build on whichever host the job lands on. Pin a build
(`debian-13-6.12-20261021.1`) only when the exact image is part of the result.
Build ids differ by host: infra's `host-setup/promote-image <host> --list
<family>` on hv01, hv02 and delta, `ls /var/lib/anvil/images` on hv03 and a Pi;
name the build without `.qcow2`. Stock images (`debian-13`, `ubuntu-24.04`,
`rocky-10`, `al2023`) exist as sources for the
builds; a job rarely wants one. Ubuntu 26.04's stock image in particular can
bring its data NIC up as `enp2s0` instead of `data`.

Every family is named for its distribution and kernel series. A spec that names
one of these old names fails with `no image or image family named`. Use:
`debian-13-ci` and `debian-13-base` -> `debian-13-6.12`; `debian-13-ci-bpo` ->
`debian-13-7.1`; `debian-13-mainline` -> `debian-13-7.3-mainline` (or `debian-13-7.4-rc`); `debian-12-base` ->
`debian-12-6.1`; `debian-14-base` -> `debian-14-7.2`; `ubuntu-24.04-base` ->
`ubuntu-24.04-6.8`; `ubuntu-26.04-base` -> `ubuntu-26.04-7.0`; `rocky-10-base`
-> `rocky-10-6.12`; `al2023-i40e` -> `al2023-6.12-i40e`; `debian-13-gpu-cu12` ->
`debian-13-6.12-gpu-cu12`; `debian-13-gpu-cu13` -> `debian-13-6.12-gpu-cu13`;
`debian-12-gpu-cu1x` -> `debian-12-6.1-gpu-cu1x`; `debian-14-gpu-cu13` ->
`debian-14-7.2-gpu-cu13`. A pinned build does not carry over:
`debian-13-6.12-<id>` is not the `debian-13-base-<id>` image, and a
`debian-13-7.1-<id>` pin older than the rename can name a different image with
no error.

**Choosing between them.**

- The distribution is part of the question only sometimes. When it is not,
  use Debian: `debian-13-6.12`, which builds, tests and measures. Every other
  family exists because some result depends on the distribution or the
  kernel.
- Toolchain: every family has rustup stable with clippy and rustfmt, a C
  compiler and the shared compiler cache, except Alpine, the stock images and
  `debian-13-gpu` (recipes). `debian-13-6.12` and `debian-13-7.1` also have what
  build scripts commonly need (libssl-dev, clang, cmake and others) and a warm
  crates index, and so does every family built from them and `debian-14-7.2`.
  Debian 12, Ubuntu, Rocky and Amazon
  Linux have neither, and a rebuild does not add them. A build there installs
  what it needs in the payload. A job that compiles nothing is unaffected.
- dm-crypt: every family has cryptsetup and a `dm_crypt` its kernel loads,
  checked per build by infra's `verify-guest-image`, except
  `ubuntu-26.04-7.0`, whose current build has no cryptsetup: on its 7.0
  kernel a direct (`O_DIRECT`) write through a plain mapping over a
  loop-backed file returns EIO. Guest kernel parameters (`init_on_free=1`,
  `secretmem.enable=1`) go in the anvil-vm `kernel_args` parameter, not the
  image.
- Debian against Ubuntu: Ubuntu when the workload's production fleet runs
  Ubuntu, or for Ubuntu's kernel. `ubuntu-24.04-6.8` is what is deployed
  widely today; `ubuntu-26.04-7.0` is the next LTS (kernel 7.0,
  sched_ext). Packages from infra's internal repo are built on Debian trixie
  (glibc 2.41), and a binary that needs 2.41 does not run on 24.04 (2.39):
  rezolus is the known case, so the Ubuntu families take rezolus's own Ubuntu
  build.
- Rocky when RHEL behaviour is the question: SELinux enforcing,
  `io_uring_disabled=2`, dnf, an EL kernel. `al2023-6.12-i40e` when Amazon Linux
  is; it is x86 only.
- `alpine-3.24` for musl and its allocator, or a small busybox userland.
- An older kernel than 6.12: `debian-12-5.10` (bullseye's 5.10.262),
  `debian-12-6.1`, `debian-12-6.6`, `debian-12-6.9` and
  `debian-12-6.11` on hv01, hv02, hv03 and the Pis; `ubuntu-24.04-6.8` on
  x86. There is no `debian-12-6.8`: bookworm-backports had none. The Pi builds
  of Debian 12 have no stressapptest (bookworm has no arm64 build);
  `/etc/anvil-image.json` lists it under `packages_absent`. No apt source in
  `debian-12-5.10`, `debian-12-6.6`, `debian-12-6.9` or `debian-12-6.11`
  carries headers for its kernel, so `apt-get install
  linux-headers-$(uname -r)` fails. `debian-12-5.10` carries rezolus 5.20.0
  on x86 and 5.28.0 on the Pis. On 5.10, rezolus 5.28.0's
  `blockio_requests`, `ext4_alloc` and `ext4_journal` samplers fail on both
  architectures and `tcp_connect_latency` fails on the Pis; the agent runs
  without them. On one hv01 boot `cpu_dtlb` was also not started (PMU budget).
- A kernel series after 6.12 on trixie userspace: `debian-13-6.17` and
  `debian-13-6.18` on hv01, hv02, hv03 and the Pis; `debian-13-7.1` on hv01,
  hv02, hv03, delta and the Pis; `debian-13-7.2` on hv01, hv02 and hv03.
  `debian-14-7.2` (forky userspace, 7.2.12) is on hv01, hv02, hv03 and the Pis.
  Of these, delta has only `debian-13-7.1`.
- A newer kernel, in order of preference: `debian-13-7.1` (Debian's backports
  kernel, 7.1.13: packaged, stable, sched_ext), then `ubuntu-26.04-7.0`, then
  `debian-13-7.3-mainline` (kernel.org 7.3.4), then `debian-13-7.4-rc` (a
  release candidate). The two kernel.org families change kernel when someone
  moves them to another point release or rc; record `/etc/anvil-image.json`
  with the result.
- GPU: `debian-13-6.12-gpu-cu12` for CUDA 12, `debian-13-6.12-gpu-cu13` for CUDA
  13; both have nvcc. In cu13 images nvcc is `/usr/local/cuda/bin/nvcc` and is
  on a login shell's PATH only, so a payload adds `/usr/local/cuda/bin` to PATH
  or calls it by full path. Name a family with another kernel series when the
  kernel is part of the result. A result measured on cu12 is not comparable with
  one on cu13: the driver differs.
- `debian-13-gpu`, the cu12 image's earlier name, is withdrawn: do not name it
  in a new spec, and it can be destroyed without notice. It has no Rust
  toolchain or compiler cache. Its builds (Debian's 550.163.01-2 on kernel
  6.12.107, from 2026-09-12) are not in `debian-13-6.12-gpu-cu12`, whose driver
  package (550.163.01-4~bpo13+1) and kernel (6.12.113) differ, so a series
  measured on the old one is not comparable with a run on the new one.
- Pis against x86: a Pi when the question is the A72 or there are many small
  independent cells to run (nineteen Pis match `["hypervisor", "aarch64"]`:
  eighteen Pi 4Bs and pi20, a Pi 5; add `pi4b` or `pi5` to choose; one job
  each); x86 for anything that needs more than 3 vCPU and ~3 GiB, the
  passthrough NICs, or a GPU.

**sched_ext** needs it compiled in, and Debian's 6.12 leaves it out. It is in
`debian-13-{6.17,6.18,7.1,7.2}`, `debian-14-7.2`,
`debian-13-7.3-mainline`, `debian-13-7.4-rc`, `ubuntu-26.04*` and `rocky-10*`. It is not in Debian
images on 6.12 or older, `ubuntu-24.04*` or `alpine-3.24`. Not every yes was
seen in a booted guest: `debian-13-7.2`'s comes from its kernel config,
`debian-13-7.1`'s from its 7.1.13 kernel, and
`debian-13-6.17`, `debian-13-6.18` and `debian-14-7.2` were checked booted on
arm64 only. A `-gpu-cu12` or `-gpu-cu13` image has its source family's answer:
`debian-13-7.2-gpu-cu13` has it, `debian-13-6.12-gpu-cu13` does not. infra's
docs/guides/vm-jobs.md keeps the table. A guest's scheduler places threads on
vCPUs and the host's still decides when the vCPUs run, so a guest shows a
policy's effect, not bare-metal latency.

**Hardware counters in a guest** on a Pi: `vpmu = false` on the step and
the `guest-pmc-dkms` package; infra's docs/examples/guest-pmc.toml is a
working job on `debian-13-6.12`. DKMS builds the module against
`linux-headers-$(uname -r)`. Use `debian-13-6.12`:
`guest_pmc.c` uses `BTF_KFUNCS_START` and `asm/arm_pmuv3.h`, which
bookworm's 6.1 headers lack, and no apt source in an image on a pinned
backports or bullseye kernel carries headers for it. With a vPMU (the
default) every counter read traps to the host, about 2.5 us on a Pi.

The authoritative per-host image lists are `infra/fleet/hosts/<host>.toml`.
Not available, and why, so nobody spends an afternoon on it: Amazon Linux
2023 on the Pis (its arm64 build requires Armv8.2 with crypto; the Pi 4 is
Armv8.0), and Ubuntu on the Pis (its arm64 images stopped in the UEFI firmware
in 3 of 6 boots on pi10, unexplained).

Shape is `{generation}.{class}`, and **the default is `auto`**: since anvil
0.8.6, `auto.c` and `auto.g` resolve the generation against the host the guest
is actually built on, so `tags = ["hypervisor", "x86_64"]` with `shape =
"auto.c"` lands on any of hv01, hv02 and hv03 and works. hv03 has one 16-thread
slot of 20 GiB, 30.6 GiB in all, and no NVIDIA GPU, passthrough NICs or scratch
pool; on hv03 `gpu = true` and `ports` do not fail, and the guest boots without
them. So a job that needs the 4090 adds `rtx4090` (or `gpu-passthrough` for any
passed-through GPU), one that needs ports adds `nic-passthrough`, and one that
uses `scratch_gib` adds `scratch`. One with `slots` above 1, or `memory_gib`
above what hv03 has free (anvil refuses a guest larger than MemAvailable less 1
GiB), names `zen1`, `zen2` or `host:<name>`. A measurement compared against
earlier runs names the hardware those runs used. infra's docs/guides/vm-jobs.md
has the full list. The `x86_64` is not optional since 2026-09-28: the Raspberry
Pis run guests too and carry `hypervisor`, so `["hypervisor"]` alone also
matches nineteen Pis (eighteen Pi 4Bs and pi20, a Pi 5; pi01 and pi06 run guests
but carry `thermal-vm` instead of `hypervisor`), where an x86 image, a 16 GiB
guest or a GPU does not exist. `["hypervisor", "aarch64"]` is a Pi guest (shape
`a72.c` or `auto.c`, an image the table marks "Pis"; see infra's
docs/guides/vm-jobs.md, "Guests on a Pi"). delta (`["validation"]`) runs guests
too, from a pool of 40 1G hugepages of which its resident systemslab and plex
VMs hold 32: a guest there gets at most 8 GiB, so say `memory_gib = 8` (and
`slots = 1`); a whole-host `auto.c` asks for 64 GiB and fails at creation. Pin a
generation — `z2.c` with `["z2.baremetal"]` (hv01, Zen2, 56 vCPU / ~224 GiB) or
`z1.c` with `["z1.baremetal"]` (hv02, Zen1, 24 vCPU / ~96 GiB) — only when the
silicon is part of the question. **A pinned shape whose generation disagrees
with the tags fails at instance creation**, and pinning by habit is what held
every CI check on one hypervisor for five days. Class `c` compute, `g` gpu, `n`
network.

**Tags are ANDed** (a job runs where its tags are a subset of the host's):
`["z2.baremetal","z1.baremetal"]` matches nothing, stays `pending`, and ends in
`timeout` after the server's unschedulable timeout (6 h by default). An image
that exists on one host with tags allowing the other fails at instance
creation.

**Two jobs in one experiment need two distinct hosts.** The scheduler matches
jobs to hosts 1-to-1 (maximal bipartite matching) and schedules only when
*every* job is covered, so an experiment with two jobs tagged for a
single-host class — `macbook`, `z2.baremetal`, or `host:hv01` — is
unsatisfiable. It does not fail at submit: it stays `pending`, indistinguishable
from an ordinary queue, and ends in `timeout` after the server's unschedulable
timeout (6 h by default).

The unschedulable timeout counts a host that is `locked`, `draining` or
`drained` as available. When a class has two hosts and one of them is out,
the experiment stays `pending` until the host is reactivated or the queue
timeout (7 days by default) ends it. Read `state` in `systemslab host list`
before submitting.

Each arm of a study is its own experiment, in one context, with each job pinned
to the same host for every arm when the arms are compared by value (`specs.md`,
"A study with more than one arm", beside this file); on a pinned host the arms
run one at a time. Two guests cannot share a hypervisor inside one job: anvil-vm
destroys every anvil guest already on the host before it launches one. Two roles
that must run at once on one host belong in one guest.

Whole host by default. `slots` (one slot = one CCX, 4 cores / 8
threads, 4 GiB per thread, on hv01 and hv02; hv01 has 7 usable, hv02 3;
hv03's one slot is all 16 threads at 1280 MiB per thread),
`memory_gib`, and `ports` (0-4 passthrough NIC ports, bonded in the guest)
only when the size is the experiment. `disk_gib` grows the root disk past the
image's 100 GiB (anvil >= 0.8.10; thin, so it costs only what the guest
writes; smaller than the image is refused). hv01 and hv02 each hold one RTX
4090, and a guest there gets it unless `gpu = false`; set that unless the payload uses the
card, so a stray or orphaned guest cannot sit on it. Timeouts are seconds.

## 2. Write the spec

Read `spec-template.toml` (beside this file) and start from it.
Rules:

- TOML, `uses = "anvil-vm"`. Payload in a `'''` literal string.
- **`name` is not a step label.** The reserved step keys are exactly
  `uses`/`type`, `id`, `background` and `with`; every other field is forwarded
  to the action as an argument. So `name` is a real argument — the barrier's
  name for `barrier`, the *artifact* name for `upload-artifact` — and putting a
  descriptive label there silently renames the artifact rather than annotating
  the step. `anvil-vm` sets `deny_unknown_fields`, so there it fails outright
  instead. Use `id` when you want a label.
- **End the payload with `exit 0`** and write the real status to a file.
  `anvil-vm` pulls `artifacts` into the job workdir whatever the payload's
  exit code, but a non-zero payload fails the step, and systemslab runs no
  later step after a failed one, so the `upload-artifact` never happens and
  the pulled files are discarded with the workdir. The template's final
  `shell` step re-raises the recorded status so the experiment state still
  reflects the result.
- Artifacts: absolute paths in `artifacts`, then `upload-artifact` with the
  **basename**. Write the full output of the work to its own artifact file;
  the console keeps everything, but `get_logs` returns 200 events per call,
  so keep the console to a summary.
- No background process may outlive the payload; it holds the ssh channel open
  until `payload_timeout`. Redirect, keep the PID, kill before `exit 0`.
- `{name}` / `${name}` are substituted only for names declared in `[params]`
  or `[matrix]`; everything else (`${PIPESTATUS[0]}`, `$(...)`, awk braces)
  passes through, so shell you write in the payload needs no escaping.
  Content you did not write for the payload (a patch, a source file, a
  config) goes in as **base64** (recipes): it is not audited for `{name}`
  collisions or `'''`, and a patch must arrive byte-exact.
- Payload runs as user `anvil`, passwordless `sudo`, `bash -s` over ssh (no
  profile sourced; cargo, rustc and sccache are in `/usr/local/bin` on every
  platform image).
- Uncommitted work: do not push a scratch branch. Ship a patch (recipes).
- **A payload that compiles Rust uses the rack's shared compiler cache.**
  Every platform image routes cargo's rustc calls through it
  (`/usr/local/bin/sccache-or-rustc`), and a store that is down makes the
  build uncached, not failed. Turn it off only for a command whose build is
  what the job measures (build or test duration, compiler behaviour, a cold
  build), and say so in the spec: `RUSTC_WRAPPER= cargo build`, with
  `CARGO_INCREMENTAL=1` for a dev rebuild. A job that builds and then
  measures something else builds first (`cargo build --release`,
  `cargo test --no-run`), then runs
  `sccache --stop-server >/dev/null 2>&1 || true` before the measured
  window, so the server is not running beside the measurement. It exits 2
  when no server is running (the store was down, `RUSTC_WRAPPER=` was set,
  or the server had idled out). On a stock image, recipes.

## 3. Two jobs that must meet

The two jobs need two distinct matching hosts, none of them `locked`,
`draining` or `drained` (section 1, "Two jobs in one experiment need two
distinct hosts").

A rendezvous between jobs in one experiment is a `barrier` step or it is a
bug. The barrier is the **only** construct that propagates one job's failure
to its peers: when a run reaches a terminal state its runner cancels every
barrier it has not yet arrived at, and a peer blocked on that barrier returns
`cancelled` within seconds. The experiment workflow does not cancel siblings
when a job fails -- it only waits for every run to finish. So a hand-rolled
rendezvous (socket handshake, marker file, poll loop) holds its peer's entire
hypervisor until a timeout the moment the other side dies. It cost hv02 34
minutes on 2026-09-09: a client failed 200 ms in at instance creation (503, no
slots) and the server sat in its `accept()` until a human cancelled it.

The shape is forced by anvil-vm being create -> payload -> tear down in one
step: a barrier step runs on the **host** runner, and a payload inside a guest
can never reach one. A job whose only step is `anvil-vm` has its runner buried
inside that step for the whole run, so nothing can interrupt it.

- The **long-lived** side (the server) runs its `anvil-vm` step with
  `background = true`, then a `barrier` step. The runner is now free to wait
  at the barrier while the guest serves. A cancel ends the run, the runner
  SIGTERMs the background step, and anvil-vm tears the guest down on SIGTERM.
- The **short-lived** side (the client) reaches the same barrier as its
  **last** step, after its uploads, so every way it can fail leaves the
  barrier unreached.
- Keep an in-guest handshake **as well**, for the happy path only: it lets the
  server payload return 0 by itself. A background step still running when the
  run ends is SIGTERMed and exits 75, which marks the run `cancelled` -- fine
  for a real failure, wrong for a good one.
- Give teardown room. `signal_background_tasks` SIGKILLs 10 s after the
  SIGTERM, and a guest still being reclaimed then is an orphan (step 7). A
  `shell` step with `sleep 20` after the barrier is enough.
- The two names must match **exactly**. A barrier is built from the steps that
  name it, so a typo does not error: it makes two one-job barriers, each
  satisfied the instant its own job arrives, and the jobs never meet.
- Readiness is not a barrier's job here. The server guest has no moment at
  which it can signal the host, so the client retries the connection.

Worked spec: `recipes.md` (beside this file), "Two guests that have
to meet".

## 4. Submit

```sh
systemslab evaluate spec.toml >/dev/null   # parses the TOML dialect; nothing checks anvil-vm fields before run time
systemslab submit spec.toml                # CLI ≥ 160, from the Mac
# prints: Experiment page is available at http://systemslab/experiment/<id>
```

The MCP `submit_experiment`/`validate_spec` tools do the same parse and accept
`anvil-vm` too, but only if the session's MCP server started after the CLI
was upgraded (it is the same binary, pinned at session start). To find out,
run `validate_spec` on the real spec. `list_actions` is **not** the test: it
lists built-ins only and never shows `anvil-vm`, on any version. An old server
fails with `unknown variant 'anvil-vm', expected one of shell, barrier, ...`;
use the CLI then. Either way, a wrong `anvil-vm` field (`deny_unknown_fields`)
is only reported when the step starts.

## 5. Wait and read

The experiment's state names, which differ from a run's, and the `submit
--wait` exit status are in `specs.md` ("Three things the CLI
will not tell you"). If you script a wait, follow `watch`: Monitor's
shell is zsh, which does not word-split unquoted variables, and macOS `bash` is
3.2, which has no `declare -A`. A monitor that has produced no output is
broken until shown otherwise — 45 minutes of silence read as "still queued"
when both runs had long finished.

- `wait_for_experiment` (MCP) or `systemslab experiment show <id>`, polled until
  the state is no longer `pending`.
- Log: `get_logs` (MCP; use `grep`/`tail`, the payload's stdout is all there)
  or `systemslab logs --experiment <id>`.
- Artifacts: `systemslab api /api/v1/experiment/<id>` lists `.artifacts[]` with
  ids; `systemslab api /api/v1/artifact/<artifact-id>` returns the body.
  `artifact list --experiment` and `download-all` scope correctly — verified on
  CLI 160.0.0 against the live rack, two sibling experiments carrying identical
  artifact names, zero id overlap. **What they do exclude is context-attached
  artifacts**, by design, so anything pre-staged on a context is absent from an
  experiment-scoped list and the tool looks like it is lying.

## 6. Before believing a green result

Ask what red would have looked like. A process that survives a `timeout` did
not crash; it did not necessarily serve. A run that "passed" under a feature
flag or backend must have actually compiled with it (check the guest's kernel
and the build flags in the log). If the check could not have failed, it
proved nothing.

**The experiment state is not the verdict.** The template here ends every
payload with `exit 0` on purpose, so the uploads survive — which means the
experiment reads `success` whenever the payload *ran*, whatever it found. A job
that writes its result to a `status` artifact is telling you to read the
artifact. A gate whose result was `fail` has been reported as a pass on the
strength of the experiment state alone.

The template pairs that `exit 0` with a final step that re-raises the recorded
status, which is what keeps the experiment state honest. **A spec that adopts
the `exit 0` half and omits the re-raise makes the state lie by construction.**
So when reading someone else's run: if the payload ends `exit 0`, find the
re-raise step before believing `success`.

The rest of the checks on a green result — evidence that work happened, a
suite that never set the new flag — are in `bench`'s `validity.md` ("Before
trusting a green result") and apply unchanged. In the log, the line proving work
occurred was a version banner, 7 pulls, 0 failures and a skip count of 16
rather than 41; decide before the run which line that is, and grep for it.

## 7. Cancel, timeout, orphan

**Cancelling a superseded run is not free.** Cancel applies to *queued*
experiments, so it no-ops on anything already scheduled; and rack-ci maps a
cancelled experiment to an error status. Where two runs write the same
commit-status context, cancelling one can overwrite the other's green with
`cancelled` — the intervention that looks protective is what causes the harm.
Let a superseded run finish unless it is holding a host you need.

Cancelling tears the guest down: `anvil-holder` watches the job's runner and
the guest is created with `virsh create --autodestroy`, so the runner exiting
destroys the domain and the libvirt hook removes its disk clone. If one is left
anyway, the next anvil-vm job on that host reclaims it before building its own
guest (one job per host makes anything already there an orphan) and prints
`reclaiming orphaned guest <id>` in its output. Each of those lines is a leak
worth filing in the anvil repo (`~/workspace/brayniac/anvil`).

To look at a host yourself, from the Mac:

```sh
systemslab host list                  # is a job running there?
ssh hv01 sudo virsh list              # the guests that exist
ssh hv01 pgrep -af anvil-holder       # what is keeping each one alive
```

A guest on a host systemslab shows busy belongs to that job (rack-ci or
another session) and is left alone. A guest on an idle host with no live
holder is an orphan; `ssh hv01 sudo virsh destroy <id>` removes it now rather
than at the next job. There is no anvil control plane or `anvilctl` any more
(retired in anvil 0.9.0); anything telling you to ask `http://forge:8080` is
out of date. Do not add retry loops.

## 8. Persistent state on the rack

A new image or any other host change is done as a job pinned to that host
(`systemslab-agent` has `sudo`), never over ssh. For images that is infra's
tooling, run from an infra checkout: `host-setup/import-zvol-image` puts a
stock cloud image on a hypervisor (a job; checksum-checked; `--prepare` for a
distribution anvil cannot log in to as shipped; `--replace` to move an
existing stock image of that name aside, as does `import-qcow2-image`), and
`host-setup/build-guest-image-job` builds a family from a recipe in
`host-setup/guest-images/` (a job); docs/guides/guest-images.md is the
procedure. On the Pis `host-setup/import-qcow2-image` still works over ssh:
drain the Pi first. It must then be added to the `images = [...]` list in
`~/workspace/brayniac/infra/fleet/hosts/<host>.toml` (drift tooling only sees
declared images), and the rack owner (Brian, in the recap) told; if a session
named `infra-*` is live (`ListAgents`), it is editing those files and should
make the change. Images are per host: building on hv01 does not put it on
hv02. Recipes has the import job.

To check a host against its declared state afterwards, the infra repo's
`infra-drift` skill runs `cargo run -q --bin infra -- diff --json` (exit 1
means drift). An unreachable host produces no findings, so a clean diff means
nothing checked has drifted, not that the rack is correct.

## Never

- Never work on hv01/hv02 outside a job, "just to check".
- Never put two jobs on a single-host tag; the experiment stays `pending` and
  ends in `timeout` hours later instead of failing at submit.
- Never read an experiment's `success` as the work's verdict when the payload
  ends `exit 0` — read the artifact it wrote.
- Never a payload that ends non-zero when you want the artifacts.
- Never coordinate two jobs with anything but a barrier; a handshake
  wedges the peer's host until a timeout when the other side dies.
- Never leave a cancelled job without checking for its guest.
- Never cite a guest's own topology report as hardware fact; corroborate on
  the host.
