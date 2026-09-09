---
name: vm-job
description: Run work inside an ephemeral VM on the lab hypervisors (hv01/hv02) through a SystemsLab job using the anvil-vm action. Use when something must run on a whole machine, a specific kernel or distro (Debian, Rocky/RHEL), a GPU, or simply on Linux when the workstation is a Mac; when asked to test, build, benchmark or probe "in a VM", "on the rack", "on hv01", or "on Rocky"; and before touching hv01/hv02 in any other way.
---

# VM job

The rack rule: **hv01 and hv02 are only ever used through SystemsLab jobs.** A
job on a host is the exclusivity guarantee (one job per host). Never `ssh` to a
hypervisor to build, test, or demo, never `anvilctl instance create` by hand,
never `rsync` a tree over. Put the work in a job payload. The one sanctioned
out-of-band action is terminating an orphaned guest after a cancel (step 6).

A whole job — boot, toolchain, clone, cold build, test suite, teardown — is
about three minutes. Treat "run it on distro X" as routine, not an expedition.

## 1. Pick image, shape, tags

| Need | image | notes |
| --- | --- | --- |
| build / test Rust | `spool/images/debian-13-ci@golden` | both hosts. rustup, gcc, git, warm crates index; kernel 6.12, `io_uring_disabled=0`. `debian-13-base` has **no** toolchain |
| RHEL-family behaviour (io_uring refused, SELinux, dnf) | `spool/images/rocky-10@golden` | **hv01 only**; install toolchain in payload (recipes); `io_uring_disabled=2` |
| measurement tooling only | `spool/images/debian-13-base@golden` | both hosts. rezolus, slipway, stressapptest |
| GPU | `spool/images/debian-13-gpu@golden` | both hosts; shape `z2.g`; only if the payload uses the card |

The authoritative per-host image lists are `infra/fleet/hosts/hv01.toml` and
`hv02.toml`.

Shape is `{generation}.{class}` and **the shape's generation must match the
host the tags select**: `shape = "z2.c"` with `tags = ["z2.baremetal"]` (hv01,
Zen2, whole host 56 vCPU / ~224 GiB) or `shape = "z1.c"` with
`tags = ["z1.baremetal"]` (hv02, Zen1, 24 vCPU / ~96 GiB). Class `c` compute,
`g` gpu, `n` network. Default to hv01 unless it is busy and the image is on
hv02. **Tags are ANDed** (a job runs where its tags are a subset of the host's):
`["z2.baremetal","z1.baremetal"]` matches nothing and pends forever. An image
that exists on one host with tags allowing the other fails at instance
creation. Whole host by default. `slots` (one slot = one CCX, 4 cores / 8
threads, 4 GiB per thread, on both hosts; hv01 has 7 usable, hv02 3),
`memory_gib`, and `ports` (0-4 passthrough NIC ports, bonded in the guest)
only when the size is the experiment. On hv01, which holds the RTX 4090, a
guest gets the card unless `gpu = false`; set it unless the payload uses the
card, so GPU jobs are not blocked. Timeouts are seconds.

## 2. Write the spec

Fetch `references/spec-template.toml` with `skill_resource` (or read it from
the skill directory) and start from it. Rules:

- TOML, `uses = "anvil-vm"`. Do not put `name =` on any step (the action
  rejects unknown fields). Payload in a `'''` literal string.
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

## 3. Submit

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

## 4. Wait and read

- `wait_for_experiment` (MCP) or `systemslab experiment show <id>`.
- Log: `get_logs` (MCP; use `grep`/`tail`, the payload's stdout is all there)
  or `systemslab logs --experiment <id>`.
- Artifacts: `systemslab api /api/v1/experiment/<id>` lists `.artifacts[]` with
  ids; `systemslab api /api/v1/artifact/<artifact-id>` returns the body.
  **`systemslab artifact download-all` / `list --experiment` ignore the filter
  and return other experiments' files** (CLI 160) — do not use them.

## 5. Before believing a green result

Ask what red would have looked like. A process that survives a `timeout` did
not crash; it did not necessarily serve. A run that "passed" under a feature
flag or backend must have actually compiled with it (check the guest's kernel
and the build flags in the log). If the check could not have failed, it
proved nothing.

## 6. Cancel, timeout, orphan

Cancelling is supposed to tear the guest down, but has left orphans that held
every slot and failed later jobs with `503 No suitable slots available`.
After any cancel or timeout, from the Mac:

```sh
anvilctl -e http://forge:8080 instance list        # ID, TYPE, HOST, STATUS
systemslab host list                               # is that HOST running a job?
anvilctl -e http://forge:8080 instance terminate <id>
```

An instance on a host that systemslab shows idle, or whose job is no longer
running, is an orphan; one on a busy host belongs to that job (rack-ci or
another session) and is left alone. Because systemslab runs one job per host,
a 503 is never ordinary contention: it means an orphan or a slot-release bug.
Terminate the orphan, file the bug in the anvil repo
(`~/workspace/brayniac/anvil`), then resubmit. Do not add retry loops.

## 7. Persistent state on the rack

A new image (`zfs create` + `qemu-img convert` + `@golden`) or any other host
change is done as a `shell` job pinned to that host (`systemslab-agent` has
`sudo`), never over ssh. It must then be added to the `images = [...]` list in
`~/workspace/brayniac/infra/fleet/hosts/<host>.toml` (drift tooling only sees
declared images), and the infra repo owner told; if a session named `infra-*`
is live (`ListAgents`), it is editing those files and should make the change.
Images are per host: building on hv01 does not put it on hv02. Recipes has
the import job.

## Never

- Never work on hv01/hv02 outside a job, "just to check".
- Never a payload that ends non-zero when you want the artifacts.
- Never leave a cancelled job without checking for its guest.
- Never cite a guest's own topology report as hardware fact; corroborate on
  the host.
