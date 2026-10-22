---
name: lab
description: Work on the local rack — hypervisors hv01, hv02 and delta, the Raspberry Pis and the Mac hosts, all scheduled through SystemsLab — by finding the hosts and guest images that exist, running work in an ephemeral VM with the anvil-vm action, writing SystemsLab specs that survive the interpolator, `set -e` and a mixed fleet, putting a repository on rack-ci and reading its verdicts, and putting a machine's cargo on the shared compiler cache on delta:8081. Use when something must run on a whole machine, a specific kernel or distro (Debian, Ubuntu, Rocky/RHEL, Amazon Linux, Alpine/musl), a GPU (CUDA 12 or 13), or on Linux from a Mac; when asked to test, build, benchmark or probe "in a VM", "on the rack", "on hv01", "on a Pi" or "on Ubuntu/Rocky/Alpine"; when authoring or fixing a SystemsLab spec or one fails at submit-evaluation; when a private repo's GitHub check fails in seconds with no steps run, a `rack-ci/*` status is missing, pending or `error`, or a `.rack-ci.toml` is added or changed; when setting up a workstation, VM or build host, when builds are slow across many target directories, or `sccache --show-stats` shows no hits; and before touching a hypervisor in any other way.
---

# Lab

The rack runs work only through SystemsLab jobs: a job is what makes a host
exclusive to it, and rack-ci, VM guests and benchmarks are all jobs. Find out
what exists before planning, then read the reference for the task.

## What exists

- **Hosts:** call `list_hosts` (systemslab MCP) and read `state` and `tags`.
  Never plan from a remembered roster. At last observation: `hv01` and `hv02`
  (x86 hypervisors, one RTX 4090 each), `delta` (x86, tag `validation`; it
  also serves the shared compiler cache at `delta:8081`), `pi00`–`pi19`
  (Raspberry Pi 4B; `pi01` and `pi06` tagged `pi4b-thermal`), and `macbook`
  and `macstudio` (jobs run directly on macOS). `fleet/hosts/<host>.toml` in
  `brayniac/infra` declares each host's role, services, tags and guest images.
  `${CLAUDE_SKILL_DIR}/../measure-performance/references/environment.md` has
  each class's hardware and what a number from it means.
- **Guest images:** the table in step 1 of
  `${CLAUDE_SKILL_DIR}/references/vm.md` lists every family (Debian 12 to 14
  on a range of kernels, a mainline release candidate, Ubuntu 24.04 and 26.04,
  Rocky 10, Amazon Linux 2023 and 2, Alpine, and the GPU images) and which
  hosts carry each. Name a family, not a build, unless the build is part of
  the result.

## What to read

| Task | Read |
| --- | --- |
| Run work in a VM, pick an image and shape, two guests that must meet, cancel or recover an orphan | `${CLAUDE_SKILL_DIR}/references/vm.md` |
| Write or fix a SystemsLab spec (interpolator, reserved keys, `set -ex`, distro differences, staging a local file) | `${CLAUDE_SKILL_DIR}/references/specs.md` |
| Put a repository on rack-ci, read a `rack-ci/*` status, release through rack-ci | `${CLAUDE_SKILL_DIR}/references/rack-ci.md` |
| Put a machine's cargo on the shared compiler cache, or find why it is not used | `${CLAUDE_SKILL_DIR}/references/sccache.md` |
| A job on a Mac, shipping a new version of a rack service, editing a host's live config | `${CLAUDE_SKILL_DIR}/references/operations.md` |
| Measure on the rack: host classes, exclusivity, VM fidelity | `${CLAUDE_SKILL_DIR}/../measure-performance/references/environment.md` |

The references name their own sibling files as "beside this file"; all of
them are in `${CLAUDE_SKILL_DIR}/references/`. The compiler cache installer
is `${CLAUDE_SKILL_DIR}/references/install-sccache.sh`.

## Never

- **Never `ssh` to a hypervisor to build, test or demo**, create a guest with
  `virsh` by hand, or `rsync` a tree to one. Put the work in a job. The one
  sanctioned out-of-band action is destroying an orphaned guest after a cancel
  (`vm.md` step 7).
- **Never read a `rack-ci/*` `error`, or a GitHub check that failed in seconds
  with no steps, as a code failure** (`rack-ci.md`, first section).
- **Never quote a build or test duration** without saying whether it went
  through the cache (`sccache.md` step 5).
