# VM job recipes

Every block here has run to success on the rack (2026-09-09). Copy, do not
re-derive.

## Test uncommitted work without pushing a branch

On the workstation, from the checkout. The guest clones the remote, so the
diff must be taken against a commit the remote has: the merge-base with the
pushed branch, not HEAD, whenever there are unpushed commits. `git diff`
alone also drops new files and staged hunks, so untracked files get their own
new-file diffs:

```sh
base=$(git merge-base HEAD origin/main)     # the sha the payload will check out
{
  git diff "$base"
  git ls-files --others --exclude-standard | while read -r f; do
    git diff --no-index /dev/null "$f" || true
  done
} > /tmp/x.patch
base64 -i /tmp/x.patch | tr -d '\n' > /tmp/x.b64      # one line, no braces
```

In the payload (base64 sidesteps both TOML escaping and `{VAR}` templating):

```sh
git clone -q https://github.com/ORG/REPO /tmp/job/src && cd /tmp/job/src
git checkout -q <the $base sha>
echo "<paste of /tmp/x.b64>" | base64 -d > /tmp/job/x.patch
git apply --stat /tmp/job/x.patch && git apply /tmp/job/x.patch
```

Generate the spec with a small script rather than pasting 30 KB by hand; keep
the spec file outside the checkout or it becomes part of the next patch.

## Rust toolchain on a guest that has none (rocky-10, debian-13-base)

```sh
sudo dnf install -y -q git gcc make          # Rocky; Debian: sudo apt-get install -y git build-essential
curl -sSf https://sh.rustup.rs | sh -s -- -y -q --profile minimal --default-toolchain stable
. "$HOME/.cargo/env"
rustup component add clippy                  # only if you run clippy
```

About 20 s on Rocky. Guests reach github.com, sh.rustup.rs, crates.io,
dl.rockylinux.org; `debian-13-ci` already has all of this plus a warm index.

## Numbers to budget with

Reference workload: a 12-crate Rust workspace (ringline), cold build and full
test suite, on hv01 with `slots = 4` (32 vCPU). The whole-host default is 56
vCPU and is not slower.

| step | measured |
| --- | --- |
| create -> reachable | 22-31 s (Debian and Rocky alike) |
| Rocky: dnf + rustup + clone + cold build of one crate's tests | ~35 s |
| cold `cargo test --all`, 12 crates | ~45 s |
| whole job incl. teardown | 2 min 40 s - 2 min 50 s |

Sizes: `z2.c` with `slots = 4` is 32 vCPU / 125 GiB; hv01 whole host 56 vCPU
/ ~224 GiB; hv02 whole host 24 vCPU / ~96 GiB. Guest kernels: `debian-13-ci`
and `-base` 6.12.63 (Debian), `rocky-10` 6.12.0-211 (el10). `debian-13-ci`
has `kernel.io_uring_disabled=0`; `rocky-10` has `2`, so anything that needs
io_uring fails there by design and a mio/epoll fallback is what to test.

## Read results

```sh
systemslab experiment show <id>                       # state per job
systemslab logs --experiment <id>                     # everything the payload printed
systemslab api /api/v1/experiment/<id> | jq '.artifacts[] | {id,name,size}'
systemslab api /api/v1/artifact/<artifact-id> > run.log
```

MCP: `wait_for_experiment`, `get_logs` (`grep`, `tail`, `offset`/`limit`),
`download_artifact(artifactId, outputPath)`. Do not use `systemslab artifact
download-all` or `artifact list --experiment`: on CLI 160 they ignore the
experiment and hand back other experiments' files.

## Import a cloud image as a new guest image (persistent rack state)

Runs as a job on the hypervisor that will hold the image, so the exclusivity
contract holds. Then declare it in `infra/fleet/hosts/<host>.toml` and tell the
infra owner. Rocky 10 needs x86-64-v3 (Zen2 ok) and boots under SeaBIOS.

```toml
name = "rocky-10-image-import"

[[jobs]]
name = "import"
tags = ["z2.baremetal"]                    # the host that will hold it

[[jobs.steps]]
uses = "shell"
[jobs.steps.with]
run = '''
set -euo pipefail
IMG=Rocky-10-GenericCloud-Base-10.2-20260525.0.x86_64.qcow2
SHA=<sha256 from the .CHECKSUM file next to the image>
DS=spool/images/rocky-10
sudo zfs list -H "$DS" >/dev/null 2>&1 && { echo "$DS exists"; exit 1; }
cd /tmp && curl -sSfL -o "$IMG" "https://dl.rockylinux.org/pub/rocky/10/images/x86_64/$IMG"
echo "$SHA  $IMG" | sha256sum -c
sudo zfs create -s -V 100G -o volblocksize=16K -o compression=lz4 "$DS"
sudo udevadm settle
sudo qemu-img convert -n -p -f qcow2 -O raw "$IMG" "/dev/zvol/$DS"
sync && sudo zfs snapshot "$DS@golden"
sudo zfs set anvil:source="$IMG" "$DS"
rm -f "$IMG"
'''
```

Amazon Linux images do not work this way: their cloud-init only takes the Ec2
datasource and ignores the NoCloud seed, so the guest never joins the control
network. Rocky/Debian GenericCloud images do.

## Make a syscall fail without changing the host

To exercise an EPERM/seccomp path, do it per-process inside the guest rather
than by sysctl:

```sh
systemd-run --user --pipe --wait -p SystemCallFilter=~io_uring_setup \
  -p SystemCallErrorNumber=EPERM ./path/to/binary
```

For the sysctl itself (`kernel.io_uring_disabled=2`), use the rocky-10 image,
where it is the default.
