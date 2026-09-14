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
git apply --stat /tmp/job/x.patch
git apply /tmp/job/x.patch || { echo "PATCH DID NOT APPLY"; exit 1; }
```

The `exit 1` runs inside the template's `{ ... } | tee` group, so it aborts
the work with `status` still at 1 and the outer `exit 0` keeps the uploads
alive. Without it the tests run on the unpatched base and can report green
for code that was never applied.

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

Sizes: `z2.c` with `slots = 4` is 32 vCPU / 128 GiB allocated (the guest's
`free` shows 125); hv01 whole host 56 vCPU / ~224 GiB; hv02 whole host 24
vCPU / ~96 GiB. Guest kernels: `debian-13-ci`
and `-base` 6.12.63 (Debian), `rocky-10` 6.12.0-211 (el10). `debian-13-ci`
has `kernel.io_uring_disabled=0`; `rocky-10` has `2`, so anything that needs
io_uring fails there by design and a mio/epoll fallback is what to test.

## Two guests that have to meet

A client/server benchmark across both hypervisors. The barrier is what frees
the server when the client dies; see skill step 3 for why nothing else does.
Trimmed to the coordination -- the payload bodies are ordinary.

```toml
name = "client-server-bench"

[params]
server_ip = "172.31.0.1"      # fixed secondary address: a guest's DHCP lease
client_ip = "172.31.0.2"      # is not knowable to the other job
done_port = "9099"

[[jobs]]
name = "server"
tags = ["z1.baremetal"]

[[jobs.steps]]
type = "anvil-vm"
background = true             # frees this runner to wait at the barrier
shape = "z1.c"
image = "spool/images/debian-13-ci@golden"
gpu = false
payload_timeout = 3600
payload = '''
sudo ip addr add {server_ip}/24 dev bond0 || true
# ... build, tune, start the server, wait for it to listen ...

# Happy path only: lets this payload return 0 so the run reports `complete`.
# A dead client is handled by the barrier, not by this timeout.
python3 -c "
import socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', {done_port})); s.listen(1); s.settimeout(1800)
try: s.accept(); print('client signalled done')
except Exception as e: print('handshake timed out:', e)
"
# ... stats, reap background PIDs ...
exit 0
'''

[[jobs.steps]]
type = "barrier"
name = "benchmark-complete"
timeout = 3600                # literal: [params] substitution is string-only

[[jobs.steps]]
type = "shell"
run = "sleep 20; echo 'teardown room before the SIGKILL'"

[[jobs]]
name = "client"
tags = ["z2.baremetal"]

[[jobs.steps]]
type = "anvil-vm"             # foreground: this job's work IS the payload
shape = "z2.c"
image = "spool/images/debian-13-ci@golden"
gpu = false
payload_timeout = 3600
artifacts = ["/tmp/job/results.json"]
payload = '''
sudo ip addr add {client_ip}/24 dev bond0 || true
# The server cannot announce readiness from inside its guest, so retry.
for i in $(seq 1 900); do
    (exec 3<>/dev/tcp/{server_ip}/7878) 2>/dev/null && { exec 3>&-; break; }
    sleep 1
done
# ... run the benchmark, write /tmp/job/results.json ...
(exec 3<>/dev/tcp/{server_ip}/{done_port}) 2>/dev/null && exec 3>&-
exit 0
'''

[[jobs.steps]]
type = "systemslab/upload-artifact"
path = "results.json"         # no `name =` here: it would RENAME the artifact

[[jobs.steps]]
type = "barrier"              # LAST: any earlier failure leaves it unreached
name = "benchmark-complete"
timeout = 3600
```

What each failure does now:

| what happens | before (handshake only) | with the barrier |
| --- | --- | --- |
| client fails at instance creation | server holds hv02 for the full wait | server released in seconds, run `cancelled` |
| client payload dies mid-run | same | same |
| both succeed | server exits on the handshake | unchanged; both runs `complete` |
| server guest never boots | client retries 900 s, then fails | same, then both end |

Live example: `~/workspace/brayniac/ringline/experiments/tcp-client-compare.toml`.

## Read results

```sh
systemslab experiment show <id>                       # state per job
systemslab logs --experiment <id>                     # everything the payload printed
systemslab api /api/v1/experiment/<id> | jq '.artifacts[] | {id,name,size}'
systemslab api /api/v1/artifact/<artifact-id> > run.log
```

MCP: `wait_for_experiment`, `get_logs` (`grep`, `tail`, `offset`/`limit`),
`download_artifact(artifactId, outputPath)`.

`artifact list --experiment` and `download-all` scope correctly. Verified on the
rack against CLI 160.0.0: two sibling experiments carrying identical artifact
names returned 11 artifacts each with zero id overlap, the CLI's id set was
byte-identical to `api /api/v1/artifact?experiment=<id>`, and `download-all`
rejects `--experiment` outright rather than widening. An earlier "do not use"
here was wrong.

**Experiment-scoped queries exclude context-attached artifacts by design.** A
file pre-staged on a context is absent from `list --experiment` — correct, and
indistinguishable from the tool lying. `artifact list` has no `--context` flag
at all, so such a file is unreachable through that command by every route it
offers; the raw API (`api "/api/v1/artifact?context=<ctx>"`) is the only way to
see it. Still untested on the deployed client: a re-run with `run_id > 0`.

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
