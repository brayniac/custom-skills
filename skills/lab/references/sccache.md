# Use the shared compiler cache

sccache wraps every `rustc` call and keys it by compiler, flags and source
hash, so a crate compiled once on any machine using the store is a cache hit
everywhere else with the same key. On the rack, that means:

- **Every rack guest image built on a platform recipe already uses it**,
  rack-ci's included. They carry sccache 0.18.0, `incremental = false` and
  `rustc-wrapper = "/usr/local/bin/sccache-or-rustc"`, which goes through
  sccache and `http://delta:8081` when the store answers and straight to rustc
  when it does not. A `.rack-ci.toml` or a vm job payload needs nothing. Every
  Debian 13 and 14 family also has the C build libraries (`vm.md`, beside this
  file, "Choosing between them"). Alpine and the stock images have no toolchain.
  A vm job on a stock image runs the installer in its payload; `recipes.md`
  (beside this file) says how.
- **C and C++ in build scripts.** `brayniac/infra` #124 (`d48a201`) sends
  cc-rs and CMake compiles through the cache on platform images built from
  it; images built before it cache only rustc, because cc-rs wraps the C
  compiler only when the wrapper's file name is `sccache`. On a machine set up
  by this installer (`rustc-wrapper = "sccache"`), cc-rs compiles are cached
  and CMake ones are not; on a Mac, infra's `host-setup/install-sccache-mac`
  adds the CMake launchers. sccache keys a C or C++ compile by its absolute
  path, so it hits only when the build runs in the same directory.
- **What it bought**, measured on a Pi guest: slipway's test check 951 s
  populating, 503 s warm with 305 of 307 rustc calls served; anvil 191 s cold,
  69 s warm with 59 of 59. What remains is linking and running tests, which no
  compiler cache touches.
- **Workstations benefit from it across target directories.** One laptop had
  35 target directories and the Studio 18, each compiling the same
  dependencies from scratch, because cargo shares nothing between them. It
  saves compile time, not disk: objects still land in every target directory.

Everything needed is in `lab`; no infra checkout is required on the
machine being set up.

## 1. Choose the mode

| Machine | Mode |
| --- | --- |
| on the LAN, someone edits code on it (Mac, dev VM) | the store, incremental left on |
| on the LAN, only builds (throwaway VM, build host) | the store, `--no-incremental` |
| often off the LAN (a laptop that travels) | `--local`: a 50 GiB disk cache on the machine |

Incremental stays on where someone edits: the edit-compile loop on the crate
being changed depends on it, and sccache passes incremental calls through
uncached while still caching every dependency. The CI images turn it off
because a CI build never benefits from it and every call then becomes
cacheable.

## 2. Run the installer

Run `install-sccache.sh` (beside this file) as the user who builds
(not under sudo), with cargo already installed:

```sh
S=<this file's directory>/install-sccache.sh
bash $S                     # the store
bash $S --no-incremental    # the store, for a build-only host
bash $S --local             # disk cache, off-LAN machine
```

It installs sccache (Homebrew on macOS; on Linux the pinned 0.18.0 musl
build, checksum-verified, into `~/.local/bin`), writes the sccache config in
the place that OS reads it, adds `rustc-wrapper = "sccache"` to
`$CARGO_HOME/config.toml` without overwriting other keys, sets
`SCCACHE_MAX_FRAME_LENGTH = "134217728"` under `[env]` there (step 4),
restarts the sccache server, and builds a probe crate. **It exits 0 only
when the probe made sccache requests and sccache reported the expected
backend.** Read the exit status; a non-zero exit names the problem.

If `delta` does not resolve (it resolves through the LAN's `localdomain`
search domain, which a container or a new VM may not have), it falls back to
`http://10.1.0.0:8081` and says so. `SCCACHE_ENDPOINT` overrides both.

Tested 2026-09-30 on macOS (aarch64) and in a Debian bookworm container
(aarch64), including the checks that must fail: an unreachable endpoint, a
config sccache ignores, a different `rustc-wrapper` already set, and
`RUSTC_WRAPPER` set in the environment.

## 3. Check it in normal use

```sh
sccache --show-stats | grep -E 'Cache location|Compile requests|Cache hits'
```

- `Cache location` reads `webdav` for the store, `Local disk` for `--local`.
- Compile requests rise with each build; hits rise on the second build of
  anything already compiled anywhere with the same key.
- To see what one build did, take the counts before and after it and print
  the difference. Do not `sccache --zero-stats`: the server is shared by
  every build on the machine, so zeroing erases another build's numbers and
  a concurrent build's requests land in yours either way.

```bash
sccache_counts() {  # requests hits misses errors; fails with no stats
  sccache --show-stats | awk '
    /^Compile requests +[0-9]+$/ {r=$NF} /^Cache hits +[0-9]+$/ {h=$NF}
    /^Cache misses +[0-9]+$/ {m=$NF} /^Cache errors +[0-9]+$/ {e=$NF}
    END {if (r == "") exit 1; print r+0, h+0, m+0, e+0}'
}
c0=$(sccache_counts) || echo "sccache: no stats before the build" >&2
cargo build --release
c1=$(sccache_counts) || echo "sccache: no stats after the build" >&2
read r0 h0 m0 e0 <<< "${c0:-0 0 0 0}"
read r1 h1 m1 e1 <<< "${c1:-0 0 0 0}"
echo "sccache: requests=$((r1-r0)) hits=$((h1-h0)) misses=$((m1-m0)) errors=$((e1-e0))"
```

- The difference is meaningless if the server exited or restarted during
  the build: a new server's counts start at zero.
- On a rack image, a build that went uncached because the store was down
  leaves `${TMPDIR:-/tmp}/sccache-down-$(id -u)` holding sccache's error; its
  stats show no requests. Print the marker beside the counts.

## 4. When it is not working

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Cache location` is `Local disk` on a machine meant to use the store | the config is where this OS does not read it: macOS reads `~/Library/Application Support/Mozilla.sccache/config`, Linux `~/.config/sccache/config`. The first Mac install wrote `~/.config` and ran on a disk cache while reporting success | rerun the installer, which writes the right path |
| `Local disk` after starting a build off the LAN | sccache picks its backend when its server starts and keeps it for the server's life; off the LAN it falls back to disk | on the LAN again: `sccache --stop-server`; the next build starts a new server |
| every compile slow after leaving the LAN | a server started on the LAN waits on a network timeout per compile | `sccache --stop-server`; use `--local` on a machine where this is routine |
| zero compile requests | `RUSTC_WRAPPER` in the environment, or another `rustc-wrapper` in a project's `.cargo/config.toml`, overrides the user config | find it: `env | grep -i wrapper`, then `.cargo/config.toml` in the project and each parent directory |
| a build fails with `sccache ... (exit status: 254)` while compiling a crate with many source files | the sccache server ran out of file descriptors (`Too many open files`); seen once on a Mac, compiling `aws-sdk-ec2` | `sccache --stop-server; ulimit -n 65536 && SCCACHE_MAX_FRAME_LENGTH=134217728 sccache --start-server` in the shell that builds. A server started from a shell does not get cargo's `[env]` |
| a build stops with no CPU in use, cargo waiting on one crate, and finishes ten minutes after the machine's last other build (or never, while other builds keep the server busy) | the crate's compile output is over 8 MiB. sccache 0.18 frames responses with tokio-util's 8 MiB default, the encode fails, and the server drops the response without logging; the client waits until the server exits 600 s after its last request. Seen building Hermit's kernel `core` for `aarch64-unknown-none-softfloat` with `-Zbuild-std` (26.6 MB of stderr) | `SCCACHE_MAX_FRAME_LENGTH=134217728` where the server starts, then `sccache --stop-server`. The installer sets it in cargo's `[env]`; rerun it on a machine set up before it did. Rack images built after `brayniac/infra` #239 set it in `/usr/local/bin/sccache-or-rustc`; on any rack image, `export SCCACHE_MAX_FRAME_LENGTH=134217728` in the payload before the first cargo command is safe |
| two machines never hit each other's entries | different sccache versions or rustc versions change the key. One Mac had a cargo-installed 0.14.0 shadowing brew's 0.18.0 | same sccache (0.18.0) and same toolchain on both; the installer removes a shadowing `~/.cargo/bin/sccache` on macOS |

With `rustc-wrapper = "sccache"`, which the installer writes, a store that
does not answer when the sccache server starts fails every compile
(`Server startup failed: cache storage failed to read`). Build with
`RUSTC_WRAPPER=`, or rerun the installer with `--local`. The rack's images
use `sccache-or-rustc`, which compiles without sccache in that case.

## 5. Build times depend on the cache

A build or test duration measured on a machine using the cache is a statement
about the cache's state as much as the code. State whether the cache was cold
or warm with every build-time figure (`bench`'s `validity.md`). To measure
without it, disable the wrapper for that one command:

```sh
RUSTC_WRAPPER= cargo build --release      # empty overrides cargo's config
```

Checked: a build with the empty variable left sccache's compile-request
count unchanged, and the next normal build raised it.

The infra journal's CI core-count comparison ran with sccache bypassed for
exactly this reason, so every arm compiled cold.

## The store itself

The server side is the rack owner's: `host-setup/install-sccache-store` in
the infra repository, run on delta. Facts a user of it needs: nginx WebDAV on
`10.1.0.0:8081`, `/health` answers `ok`, no credential (reachable on the LAN
only, as the apt repository is), dataset `spool/sccache` with a 500 GiB quota,
evicted daily: entries unread for 14 days, then, if the store is above 85% of
the quota, the least recently read until it is below 70%. It grows about
12 GiB a day. When the store is full, every write fails with a 500 and
builds go on uncached; a second build of the same tree that gets no hits is
the sign. Anyone on the LAN can write to it; a poisoned entry is a wrong
build, which CI exists to find. If `/health` fails from every machine, tell
the rack owner rather than working around it.

## Never

- **Never run the installer under sudo**; it configures the user who builds.
- **Never turn incremental off on a machine someone edits code on.**
- **Never give sccache a credentialed backend in a VM image**; a credential in
  an image is a secret copied into every guest.
- **Never quote a build or test duration without the cache state.**
- **Never treat `Local disk` in the stats as working** on a machine meant to
  use the store.
