---
name: vm-job
description: Run work inside an ephemeral VM on the lab hypervisors (hv01, hv02, delta) or the Raspberry Pis through a SystemsLab job using the anvil-vm action, and pick the guest image for it. Use when something must run on a whole machine, a specific kernel or distro (Debian, Ubuntu, Rocky/RHEL, Amazon Linux, Alpine/musl), a kernel with sched_ext or a mainline release candidate, a GPU (CUDA 12 or 13), guest hardware counters, or simply on Linux when the workstation is a Mac; when asked to test, build, benchmark or probe "in a VM", "on the rack", "on hv01", "on a Pi", or "on Ubuntu/Rocky/Alpine"; and before touching a hypervisor in any other way.
---

# VM job

The rack rule: **hv01 and hv02 are only ever used through SystemsLab jobs.** A
job on a host is the exclusivity guarantee (one job per host). Never `ssh` to a
hypervisor to build, test, or demo, never create a guest with `virsh` by hand,
never `rsync` a tree over. Put the work in a job payload. The one sanctioned
out-of-band action is destroying an orphaned guest after a cancel (step 7).

A whole job — boot, toolchain, clone, cold build, test suite, teardown — is
about three minutes. Treat "run it on distro X" as routine, not an expedition.

## 1. Pick image, shape, tags

| Need | image | where | notes |
| --- | --- | --- | --- |
| build / test Rust | `debian-13-ci` | x86, Pis | rustup, gcc, git, warm crates index; kernel 6.12. `debian-13-base` has **no** toolchain |
| measurement tooling only | `debian-13-base` | x86, Pis | rezolus, slipway's remote, bubblewrap, stressapptest |
| newer kernel, io_uring after 6.14 | `debian-13-ci-bpo` | x86, Pis | `debian-13-ci` on trixie-backports 7.1.13 |
| a release candidate or kernel tree | `debian-13-mainline` | x86 | `debian-13-base` on a kernel.org build (7.3.0-rc6 on 2026-10-06); infra's `jobs/build-kernel-mainline` moves it |
| Ubuntu | `ubuntu-24.04-base`, `ubuntu-26.04-base` | x86 | rezolus, bubblewrap, stressapptest; no internal apt repo or slipway (its packages are built on trixie) |
| RHEL-family behaviour (io_uring refused, SELinux, dnf) | `rocky-10-base` | x86, Pis | rezolus; install a toolchain in the payload (recipes); `io_uring_disabled=2` |
| Amazon Linux | `al2023-i40e` | x86 | kernel 6.12, can drive the passthrough ports. Stock `al2023` needs `ports = 0` |
| musl, OpenRC | `alpine-3.24` | x86, Pis | busybox userland; no rezolus (recipes, "Alpine") |
| GPU, CUDA 12 | `debian-13-gpu` | hv01, hv02 | driver 550, CUDA 12.4 toolkit; shape `z2.g` (hv01) or `z1.g` (hv02), one RTX 4090 each |
| GPU, CUDA 13 | `debian-13-gpu-cu13` | hv01, hv02 | NVIDIA's 595 driver, no toolkit (for pip wheels such as vLLM) |

Name the family (`debian-13-base`), not `spool/images/<x>@golden`: the family
resolves to its current build on whichever host the job lands on. Pin a build
(`spool/images/debian-13-base-20260912.3@golden`, or the `.qcow2` name on a
Pi) only when the exact image is part of the result. Stock images
(`debian-13`, `ubuntu-24.04`, `rocky-10`, `al2023`) exist as sources for the
builds; a job rarely wants one. Ubuntu 26.04's stock image in particular can
bring its data NIC up as `enp2s0` instead of `data`.

**sched_ext** needs it compiled in, and Debian's 6.12 leaves it out. It is in
`debian-13-ci-bpo`, `debian-13-mainline`, `ubuntu-26.04*` and `rocky-10*`; not
in the other Debian images, `ubuntu-24.04*` or `alpine-3.24`. infra's
docs/guides/vm-jobs.md keeps the table. A guest's scheduler places threads on
vCPUs and the host's still decides when the vCPUs run, so a guest shows a
policy's effect, not bare-metal latency.

**Hardware counters in a guest** on a Pi: `vpmu = false` on the step and
the `guest-pmc-dkms` package; infra's docs/examples/guest-pmc.toml is a
working job. With a vPMU (the default) every counter read traps to the host,
about 2.5 us on a Pi.

The authoritative per-host image lists are `infra/fleet/hosts/<host>.toml`.
Not available, and why, so nobody spends an afternoon on it: Amazon Linux
2023 on the Pis (its arm64 build requires Armv8.2 with crypto; the Pi 4 is
Armv8.0), and Ubuntu on the Pis (its arm64 images stopped in the UEFI firmware
in 3 of 6 boots on pi10, unexplained).

Shape is `{generation}.{class}`, and **the default is `auto`**: since anvil
0.8.6, `auto.c` and `auto.g` resolve the generation against the host the guest
is actually built on, so `tags = ["hypervisor", "x86_64"]` with `shape =
"auto.c"` lands on either hypervisor and works. The `x86_64` is not optional
since 2026-09-28: the Raspberry Pis run guests too and carry `hypervisor`, so
`["hypervisor"]` alone also matches twenty Pis, where an x86 image, a 16 GiB
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
`["z2.baremetal","z1.baremetal"]` matches nothing and pends forever. An image
that exists on one host with tags allowing the other fails at instance
creation.

**Two jobs in one experiment need two distinct hosts.** The scheduler matches
jobs to hosts 1-to-1 (maximal bipartite matching) and schedules only when
*every* job is covered, so an experiment with two jobs tagged for a
single-host class — `macbook`, or `z2.baremetal` — is unsatisfiable. It does
not fail: it sits `unscheduled` forever, indistinguishable from an ordinary
queue. It cost another session 40 jobs before anyone noticed. Sequential arms
belong in **one** job, which also measures better: the arms get the machine to
themselves instead of racing each other.

Whole host by default. `slots` (one slot = one CCX, 4 cores / 8
threads, 4 GiB per thread, on both hosts; hv01 has 7 usable, hv02 3),
`memory_gib`, and `ports` (0-4 passthrough NIC ports, bonded in the guest)
only when the size is the experiment. `disk_gib` grows the root disk past the
image's 100 GiB (anvil >= 0.8.10; thin, so it costs only what the guest
writes; smaller than the image is refused). Each host holds one RTX 4090 and a
guest gets it unless `gpu = false`; set that unless the payload uses the
card, so a stray or orphaned guest cannot sit on it. Timeouts are seconds.

## 2. Write the spec

Read `${CLAUDE_SKILL_DIR}/references/spec-template.toml` and start from it.
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
  profile sourced; `debian-13-ci` puts cargo on PATH anyway).
- Uncommitted work: do not push a scratch branch. Ship a patch (recipes).

## 3. Two jobs that must meet

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

Worked spec: `${CLAUDE_SKILL_DIR}/references/recipes.md`, "Two guests that have
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
--wait` exit status are in `systemslab-spec-authoring` ("Three things the CLI
will not tell you"). If you script a wait, follow `watch-long-job`: Monitor's
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
suite that never set the new flag — are in `benchmark-validity` ("Before
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
distribution anvil cannot log in to as shipped), and
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
- Never put two jobs on a single-host tag; the experiment pends forever rather
  than failing.
- Never read an experiment's `success` as the work's verdict when the payload
  ends `exit 0` — read the artifact it wrote.
- Never a payload that ends non-zero when you want the artifacts.
- Never coordinate two jobs with anything but a barrier; a handshake
  wedges the peer's host until a timeout when the other side dies.
- Never leave a cancelled job without checking for its guest.
- Never cite a guest's own topology report as hardware fact; corroborate on
  the host.
