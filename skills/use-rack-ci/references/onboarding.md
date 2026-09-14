# Putting a repository on rack-ci

## The targets

Defined by the rack in `/etc/rack-ci/rack-ci.toml`, not by the repository.

| target | what it is | right for | watch out |
| --- | --- | --- | --- |
| `pi` | a Raspberry Pi 4B, aarch64, script run **on the host** as the unprivileged `rack-ci` user | lint, tests, anything needing no x86 and no GPU | twenty of them, never contended. Bare OS — only what the baseline installs |
| `x86` | a Debian guest on delta's validation shape | x86-only behaviour, release packaging | guest boot ~25 s; the image carries a standard toolset |
| `gpu` | a hypervisor guest holding the RTX 4090 | checks that use the card | blocks every GPU job on that host for the whole script; use sparingly |

A check naming a target the rack does not define gets an `error` **before a host
is spent**.

**A bare target keeps state between builds on purpose.** Each repository has a
warm `CARGO_TARGET_DIR` under `/var/tmp/rack-ci`, so a second pi build is
minutes rather than the eight a cold anvil workspace takes. The tree itself is
fetched fresh each run into a directory the run removes. A guest has neither —
it is destroyed.

## The config surface

```toml
[checks.<name>]
target = "pi"                  # pi | x86 | gpu
run = "…"                      # bash body; exit code is the verdict
on = ["tag"]                   # default ["pull-request", "tag"]
timeout_secs = 7200

[release]                      # v* tags only, if the override enables it
target = "x86"
run = "bash .rack-release.sh"  # the default
```

Environment inside `run`: `RACK_CI_REPO`, `RACK_CI_SHA`, `RACK_CI_REF`,
`RACK_CI_KIND`. Working directory is the tree, under `/home/anvil/src` in a
guest.

**A repository with no `.rack-ci.toml`** falls back to an executable
`.rack-ci.sh` at the root, run on the default target, reported as plain
`rack-ci`. Nothing has to move at once.

**A repository in the allowlist with neither file** is reported as an `error`,
detected from the tarball, before a host is spent — correctly, but on every
push.

`anvil/.rack-ci.toml` is the worked example.

## What only the rack owner can do

The checks file is yours. These are not:

1. add the repository to `repos` in `/etc/rack-ci/rack-ci.toml` on delta;
2. tick it in the fine-grained token (**Contents: read**, **Commit statuses:
   read and write**, nothing else — one token covers every repository);
3. `sudo systemctl restart rack-ci`.

The allowlist at the time of writing is `brayniac/anvil`, `brayniac/infra`,
`brayniac/ferallm`, `brayniac/slipway` — read from the starter config in
`host-setup/install-rack-ci`, so confirm against delta rather than trusting it.

**Silence is the failure mode.** A repository with a checks file and no
allowlist entry produces no builds and no error at all.

## Why it polls instead of taking a webhook

**GitHub cannot reach this rack.** Delta's Caddy answers on the LAN only,
tailscaled is logged out, there is no tunnel. Every fix is a network project —
a tailnet and a Funnel, a Cloudflare account and a domain, or a port forwarded
to the internet. Polling needs none of them, needs no inbound reachability, and
drops the webhook secret entirely: **the token is the only secret.** Three API
calls per repository per cycle against a 5000/hour budget.

`/webhook` is still implemented and mounts the moment a config names
`webhook_secret_env`. Nothing about polling is in the way of switching back.

## The rule that shapes everything: the guest holds no credential

rack-ci downloads the tarball GitHub already offers, holds it in memory, and
serves it once at an unguessable path on the flat network. **The guest curls a
URL and never clones.** The path stops working when the run ends.

That is what makes it safe for the guest to run whatever a repository's CI
script says. An ephemeral VM is cloned for every job and destroyed without
ceremony; a credential in one is a credential you have stopped tracking.

## Traps

- **A second push supersedes the first.** Runs are keyed by branch or PR number;
  a new commit cancels the experiment building the old one. Different branches
  never displace each other.
- **Two builds at once, maximum**, and they compete with measurement jobs. One
  guest per hypervisor is a rack-wide rule.
- **`host_tags` are ANDed.** A job runs where its tags are a *subset* of the
  host's, so `["z2.baremetal", "z1.baremetal"]` means "a host that is both" —
  nothing is. It does not fail; it waits until the timeout. Both hypervisors
  carry `hypervisor`, so "either one" is a single tag.
- **No build cache.** `Swatinem/rust-cache` has no equivalent — the guest is
  destroyed. The CI image ships a warm crates.io index, which covers the fetch
  and not the compile.
- **`cargo audit` is not covered.** `rustsec/audit-check` posts its own check
  run, which a token cannot create. Until `cargo-audit` is in the CI image,
  advisories are unchecked — and a step that silently skips when the tool is
  missing would be worse than the gap.
- **The log is the job's output, not an artifact.** systemslab stops at the
  first failed step and has no always-run step, so an `upload-artifact` after
  the build could only fire on a *passing* build. The payload's output is what
  the commit status links to.
- **Commit statuses, not check runs.** Only a GitHub App token can create a
  check run, and there is no App here. A status appears on the pull request,
  can be made required, and links to the run — but has no re-run button.

## Proving a build without waiting for a poll

On delta, with the service stopped (`build` serves the source itself and cannot
bind while the service holds the port):

```sh
sudo systemctl stop rack-ci
sudo -u rack-ci sh -c 'set -a; . /etc/rack-ci/secrets.env; set +a;
  exec rack-ci build --config /etc/rack-ci/rack-ci.toml \
    --repo brayniac/<repo> --sha <sha>'
```

The token is **sourced, not passed as an argument** — an argument is visible in
`ps` to every local user for as long as the build runs — and read by the
`rack-ci` user, because `/etc/rack-ci` is `0750 root:rack-ci` and your own
shell's `$(cat …)` cannot read it.

`rack-ci payload` prints what would run in the guest without spending one.
