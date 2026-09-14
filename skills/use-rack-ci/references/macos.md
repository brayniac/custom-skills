# macOS on this rack

Two separate things, and the first gates the second: **studio as a rack-ci
runner**, and **a macOS artifact to distribute**.

Read from `brayniac/infra` at `576bf7c` and not run. No access from here to
delta, to either Mac, or to the rack.

## studio as a runner: what actually blocks it

A Mac runner has to be a **bare** target — the script runs on the host itself,
no guest — and `bare = true` is already a first-class mode (`[targets.pi]` uses
it). But the bare path as implemented is Linux-only in three places, and only
one of them is "setup".

### 1. The sandbox is hardcoded, and does not exist on macOS

`crates/rack-ci/src/job.rs:263` emits, unconditionally for every bare target:

```
bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp …
```

**Bubblewrap is Linux user/mount/pid namespaces. There is no macOS build, and
no port.** A test at `job.rs:633` asserts that string, so the coupling is
deliberate rather than accidental — which also means changing it is a
one-file, testable change.

The fix is a per-target sandbox choice, defaulting so nothing about the pis
moves:

```toml
[targets.studio]
host_tags = ["studio"]
bare = true
sandbox = "none"        # "bwrap" (default) | "sandbox-exec" | "none"
```

- `sandbox-exec` is macOS's Seatbelt. It is present on every Mac and takes a
  `.sb` profile that can make the filesystem read-only except named paths —
  the closest analogue. Apple has marked it deprecated for years and ships it
  anyway.
- `none` leans on what already closes the untrusted-code vector: **rack-ci
  refuses fork pull requests outright**, and every allowlisted repository is
  first-party. A dedicated unprivileged user with no sudo, a run directory the
  trap removes, and a read-only toolchain get most of the isolation.

**What `none` costs is worth stating before choosing it.** No pid namespace, so
a build that leaves something running leaves it running. No read-only root, so
a build can read anything that user can. On a pi that does nothing else, that
is a small surface. **studio is described in the design as a control point —
"never managed" — so it is the machine where that surface is least acceptable.**
If studio is going to run CI, `sandbox-exec` is worth the profile.

### 2. The installer is Debian-only

`host-setup/install-rack-ci-host` does `apt-get install … bubblewrap` and
`useradd --system --shell /usr/sbin/nologin`. macOS has neither. A darwin
sibling needs:

| what | Debian | macOS |
| --- | --- | --- |
| build deps | `apt-get` | Homebrew, or Xcode CLT alone |
| the sandbox | `bubblewrap` | `sandbox-exec` (built in) or none |
| the user | `useradd --system` | `dscl` / `sysadminctl`, shell `/usr/bin/false` |
| toolchain | rustup into `/opt/rust`, `chmod -R a+rX` | **same, works unchanged** |
| run home | `/var/tmp/rack-ci` mode 1777 | same, works unchanged |

So roughly half of it transfers verbatim.

### 3. studio is not a systemslab host yet

`fleet/hosts/` holds delta, forge, hv01, hv02 and pi00–pi19. There is no
`studio.toml`, and the design calls macstudio a control point, "never managed".
Before any of the above matters:

- `systemslab-agent` running on studio, registered, with a host tag the target
  can name;
- **`sudo` for the agent's user** — the bare payload runs `sudo rm -rf` and
  `sudo chown -R rack-ci:rack-ci` before dropping privileges;
- a decision about whether studio becomes a *managed* fleet host or stays
  unmanaged with rack-ci as the exception. Declaring it in `fleet/` is what
  makes drift visible; leaving it out means nothing notices when it changes.

### What transfers unchanged

Source serving, the no-credential rule, the warm `CARGO_TARGET_DIR`, and
building the tag rather than a checkout — all of it is arch- and OS-agnostic.
The Mac curls its tarball over the flat network exactly as a pi does.

## The distributable

Status: the Debian half is built and running; this half is **designed and not
built**. `infra/docs/superpowers/specs/2026-09-12-rack-packaging-pipeline-design.md`
section 6 is the proposal, and its plan carries one unchecked task.

### The open question, and why the pi already answers it

The design stops here:

> The open question is the source: a Mac job cannot use rack-ci's source serving
> unless the Mac host is on the flat network (it is, when docked), and a release
> from the Mac's own checkout is not a release of a tag.

**The `pi` target is the precedent, and a Mac is the same shape.** A pi is not a
guest: the script runs on the host's own OS as an unprivileged `rack-ci` user,
the tree is fetched fresh each run into a directory the run removes, and a warm
`CARGO_TARGET_DIR` persists between builds. That is exactly what a Mac target
needs to be.

Both halves of the question dissolve against that precedent:

- **Source serving works unchanged.** The Mac curls the tarball from
  `http://delta:<port>/<unguessable>` over the flat network, the same way a pi
  and a guest do. Nothing about the transport assumes a VM.
- **It builds the tag, not a checkout.** rack-ci serves the *tag's* tarball. The
  Mac's own working tree is never consulted, so "a release from the Mac's own
  checkout" is not what happens — the same reason a pi build is a build of the
  commit and not of whatever is lying around on pi07.

What remains is a **scheduling** constraint, not an architectural one: the Mac
must be docked on the flat network when the job runs. That degrades correctly
on its own — an undocked Mac means the job waits and times out, and rack-ci
reports a timeout as **`error`, not `failure`**. Nothing about the code is
wrong, and the status says so.

### What is actually different

#### The artifact

No apt, and a `.pkg` buys nothing for two machines that already share a staging
directory. A tarball is the right shape:

```
ferallm-<version>-macos-arm64.tar.gz   ->  dist/
```

Published to `/srv/dist/macos/` on delta, which Caddy already serves, so
`http://delta/dist/macos/<name>` is the pin and
`/Volumes/Training/systemslab-stage/bin/` becomes a `curl`.

#### Signing: less than you would expect, and the reason matters

**An unsigned arm64 binary fetched with `curl` and unpacked with `tar` runs.**
Two facts combine:

- On Apple Silicon every executable must carry *some* signature, but an **ad-hoc
  signature counts**, and the toolchain applies one at link time. A
  `cargo build --release` binary is already ad-hoc signed and travels fine
  inside a tarball.
- `com.apple.quarantine` is set by the **downloading application** through
  LaunchServices — browsers, Mail, Messages. `curl` does not set it, and neither
  does `tar`. No quarantine means Gatekeeper never adjudicates.

So the staging-directory workflow needs **no Developer ID and no notarization**.
A Homebrew tap is the same: `brew` fetches with curl, so a formula pointing at
that URL needs nothing on the rack and nothing from Apple.

**The threshold where that stops being true** is worth naming, because crossing
it costs a $99/year account and a notarization step in the release job:

| distribution | needs Developer ID + notarization? |
| --- | --- |
| `curl` + `tar` into a staging dir | no |
| Homebrew tap formula | no |
| `.pkg` or `.dmg` | **yes** |
| anything a browser downloads | **yes** (the browser quarantines it) |
| anything leaving these machines | **yes**, in practice |

Until one of the bottom three is wanted, signing is a cost with no benefit.

#### Architecture

Both Macs are arm64 darwin. Name the artifact `-macos-arm64` and do not build
universal — `lipo` and an `x86_64-apple-darwin` target only earn their place if
an Intel Mac appears.

#### The publish job is not new

The Debian shape is already built: a build job uploads `dist.tar`, and a shell
job on delta (`tags = ["validation"]`) waits at a barrier, fetches the artifact
from its own experiment, and publishes. The macOS version is the same two-job
shape with a different second half — a `publish-dist-macos.sh` sibling of
`jobs/publish-debs.sh` that unpacks into `/srv/dist/macos/` instead of calling
`publish-apt-internal`.

### Recommended shape

1. **`.rack-release-macos.sh`** in the repository: `cargo build --release`
   (Metal where relevant), tarball into `dist/`.
2. **A `mac` target** in the rack config, defined like `pi` — bare host,
   unprivileged user, fetch-fresh-and-remove, warm `CARGO_TARGET_DIR` — tagged
   `macbook` (and the studio when registered).
3. **`jobs/publish-dist-macos.sh`** on delta after a barrier, dropping into
   `/srv/dist/macos/`.
4. **A separate status context**, `rack-ci/release-macos`, rather than folding
   it into `rack-ci/release`. The Mac can be undocked; that must not turn the
   Debian release red, and two shelves failing for unrelated reasons should not
   share one mark.
5. **A Homebrew tap** as the follow-on: a formula with `url` and `sha256`
   pointing at the delta URL. Needs nothing else on the rack.

### What this has not verified

The Macs are systemslab hosts but
**not managed fleet hosts** — `fleet/hosts/` has delta, forge, hv01, hv02 and
pi00–pi19 and no Mac — and the design calls macstudio a "control point only;
never managed". Whether a `rack-ci` user, a warm target dir, and a
fetch-and-remove scratch path can be provisioned on a host the fleet does not
manage is the one thing to settle before building any of this.
