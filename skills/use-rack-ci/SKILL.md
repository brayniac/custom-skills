---
name: use-rack-ci
description: Put a repository on rack-ci — the rack's own CI, which replaced GitHub Actions here — and read its verdicts correctly. Use when a private repo's GitHub check fails in a few seconds with no steps run, when adding or changing a `.rack-ci.toml`, when a build is missing or stuck pending, when a tag needs to publish packages, and before treating any red mark on these repositories as a code failure.
---

# rack-ci

**GitHub's hosted runners do not work on this account's private repositories.**
Every push fails in about four seconds, no steps executed, because account
payments failed or the spending limit needs raising. `rack-ci` replaces them,
running builds on the rack instead:

```
GitHub <-- delta polls --> systemslab experiment --> anvil guest --> commit status
```

The authority is `docs/guides/ci.md` in `brayniac/infra`; this skill is what you
need when that repo is not checked out, and it defers to it wherever they differ.

## First: is this failure even a build failure?

Before reading a diff, check the shape of the red mark.

| Symptom | What it is | What to do |
| --- | --- | --- |
| GitHub check fails in ~4 s, **no steps, no runner assigned, empty logs** | **billing.** The job was never dispatched | **Do not re-run — it cannot pass.** Move the repo to rack-ci |
| `rack-ci/<name>` reports **`failure`** | the CI script exited non-zero | a real failure; read the log at the linked experiment |
| `rack-ci/<name>` reports **`error`** | infrastructure: rack unreachable, source download broken, superseded run, timeout | **not a code problem.** Do not send anyone to read the diff |
| status stuck **`pending`** forever | a restart orphaned the verdict (pre-0.3.2), or the run was superseded | re-run with `rack-ci build`, or post the status by hand |
| `rack-ci/<name>` fails on one host and passes on another **for the same commit** | host drift: a package, image, or config that differs between hosts | from `brayniac/infra`: `cargo run -q --bin infra -- diff --json` (exit 1 is drift) and `host-setup/deploy-anvil --check`. Report the host; do not change code for it |

**That `failure`/`error` split is deliberate.** Reporting an
infrastructure problem as a failing build sends someone hunting a bug that is
not there.

## Step 1 — Add `.rack-ci.toml` to the repository

It names the checks, and which target each runs on:

```toml
[checks.lint]
target = "pi"
run = """
bad=0
cargo fmt --all -- --check || bad=1
cargo clippy --all-targets -- -D warnings || bad=1
exit $bad
"""

[checks.test]
target = "pi"
run = "cargo test --workspace"
```

Each check is one experiment, one host, and one commit status
(`rack-ci/<name>`). `run` is a bash script body with the tree as its working
directory, `RACK_CI_REPO`/`SHA`/`REF`/`KIND` in the environment, and **its exit
code as the verdict**.

Two shape rules that are not style preferences:

- **Few checks, each one script.** A hosted runner was free and parallel; here a
  check holds a host for the length of its script. Sequential fmt-then-clippy in
  one check shares one host.
- **Make every step run even after one fails** (the `bad=1` pattern above).
  Stopping at the first problem costs another push and another host to find the
  second.

`references/onboarding.md` has the targets table, the full config surface, and
which steps you cannot do yourself.

## Step 2 — Pick the target honestly

`pi` (aarch64, bare, twenty of them, uncontended) for anything that needs no x86
and no GPU. `x86` (Debian guest on delta) for x86-only behaviour and release
packaging. `gpu` (hypervisor guest with the 4090) sparingly — it blocks every
GPU job on that host for the length of the script.

**Check what the target actually has before assuming a tool.** A bare pi runs
your script on its own OS, and the pi baseline declares no packages; the Debian
guest image installs a standard set. A script that assumes `jq` passes on a
guest and fails on a pi, and that is not a code failure either.

## Step 3 — Know what triggers a build

The default is **pull requests and tags, not branches.** A push straight to
`main` gets no build — that is the point: a build holds a host for minutes, and
docs-only pushes to `main` have starved real measurement jobs.

- Want a build before merge → **open a pull request.**
- Must be green to ship → **tag it.**
- Fork pull requests are **refused outright** (CI executes the code it is given).
- A pull request opened on an unmoved head triggers nothing; the commit keeps
  the status it earned when it was pushed.

## Step 4 — The rack owner has to do the rest

You can add the checks file. You cannot finish the onboarding:

1. `brayniac/<repo>` added to `repos` in `/etc/rack-ci/rack-ci.toml` on delta —
   **the allowlist is the entire authorization model**, and rack-ci asks about
   nothing else;
2. the repository ticked in the fine-grained token (Contents: read, Commit
   statuses: read and write);
3. `sudo systemctl restart rack-ci`.

**The token's repository list and the allowlist are not the same list.** A repo
in the token but not the allowlist is never polled, so a generous token costs
nothing. A repo in the allowlist but not the token makes every sweep log a 403.

Say plainly which of these you did and which you are asking for. A repo with a
`.rack-ci.toml` and no allowlist entry gets no builds and no error — silence.

## Step 5 — Releases, if the repo publishes

A `v*` tag on a repository whose override says `release = true` runs
`.rack-release.sh` and publishes what it leaves in `dist/`, under the
`rack-ci/release` status context. Today that means `.deb`s into the internal apt
repo on delta.

**A tag pushed while the service was down is never caught up** — release it by
hand with `rack-ci build --release`, or delete and re-push the tag.

macOS — studio as a runner, and a macOS artifact to ship — is
`references/macos.md`. The runner is blocked on more than setup: the bare-target
sandbox is bubblewrap, hardcoded, and Linux-only.

## Step 6 — Retire the Actions workflow

Delete `.github/workflows/*.yml` once the repository is on rack-ci. Leaving it
means every pull request carries a permanent red mark that means nothing, which
is exactly how a real failure gets ignored.

Keeping it "as a fallback" is not a fallback: over budget, Actions cannot run at
all on a private repository here, so the workflow is not a second opinion — it
is a guaranteed false one.

## Never

- **Never re-run a GitHub check that failed in seconds with no steps.** It is
  billing. It cannot pass, and each attempt looks like diligence.
- **Never read `error` as a code failure**, or report it as one.
- **Never assume a tool exists on a bare target.** Check the baseline.
- **Never add a repository to the allowlist expecting CI without a checks file**
  — every commit then reports `error`, correctly, forever.
- **Never split a check per step** because hosted CI did. Each split costs a
  whole host.
- **Never deploy rack-ci with builds in flight** without checking `/health`;
  pre-0.3.2 that orphaned their verdicts, and the tarball a guest had not yet
  fetched is gone.
- **Never expect a build cache.** Every run starts cold; there is no
  `rust-cache` equivalent because the guest is destroyed. A bare target keeps a
  warm `CARGO_TARGET_DIR`; a guest does not.
- **Never debug code for a failure that follows the host.** Two different
  anvil builds were once both installed as `0.3.0-1`, and a hypervisor's
  rezolus config without `reserved_pmu_counters` left every guest's hardware
  counters reading near zero while reporting healthy; neither shows in the
  job's own output. Check drift first. A clean `infra diff` means nothing it
  checks has drifted, and an unreachable host produces no findings at all.
