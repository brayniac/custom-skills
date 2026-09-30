---
name: use-shared-compiler-cache
description: Put a machine's cargo on the rack's shared compiler cache — sccache 0.18.0 against the WebDAV store on delta:8081 that every rack CI guest already uses, or a local disk cache off the LAN — with a bundled installer for macOS and Linux that proves a probe build went through the cache, and diagnose a cache that is silently not being used. Use when setting up a new workstation, VM, or build host; when builds on a machine with many worktrees or target directories are slow; when `sccache --show-stats` shows no hits or a local disk location; when builds hang or crawl after a laptop leaves the LAN; and before quoting any build or test duration.
---

# Use the shared compiler cache

sccache wraps every `rustc` call and keys it by compiler, flags and source
hash, so a crate compiled once on any machine using the store is a cache hit
everywhere else with the same key. On the rack, that means:

- **Every rack-ci guest already uses it.** The ci images carry sccache 0.18.0,
  `rustc-wrapper = "sccache"` and `incremental = false`, pointed at
  `http://delta:8081`. A `.rack-ci.toml` needs nothing.
- **What it bought**, measured on a Pi guest: slipway's test check 951 s
  populating, 503 s warm with 305 of 307 rustc calls served; anvil 191 s cold,
  69 s warm with 59 of 59. What remains is linking and running tests, which no
  compiler cache touches.
- **Workstations benefit from it across target directories.** One laptop had
  35 target directories and the Studio 18, each compiling the same
  dependencies from scratch, because cargo shares nothing between them. It
  saves compile time, not disk: objects still land in every target directory.

Everything needed is in this skill; no infra checkout is required on the
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

Fetch `references/install-sccache.sh` with `skill_resource`, save it, and run
it as the user who builds (not under sudo), with cargo already installed:

```sh
bash install-sccache.sh                    # the store
bash install-sccache.sh --no-incremental   # the store, for a build-only host
bash install-sccache.sh --local            # disk cache, off-LAN machine
```

It installs sccache (Homebrew on macOS; on Linux the pinned 0.18.0 musl
build, checksum-verified, into `~/.local/bin`), writes the sccache config in
the place that OS reads it, adds `rustc-wrapper = "sccache"` to
`$CARGO_HOME/config.toml` without overwriting other keys, restarts the sccache
server, and builds a probe crate. **It exits 0 only when the probe made
sccache requests and sccache reported the expected backend.** Read the exit
status; a non-zero exit names the problem.

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
- `sccache --zero-stats` before a build isolates that build's numbers.

## 4. When it is not working

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Cache location` is `Local disk` on a machine meant to use the store | the config is where this OS does not read it: macOS reads `~/Library/Application Support/Mozilla.sccache/config`, Linux `~/.config/sccache/config`. The first Mac install wrote `~/.config` and ran on a disk cache while reporting success | rerun the installer, which writes the right path |
| `Local disk` after starting a build off the LAN | sccache picks its backend when its server starts and keeps it for the server's life; off the LAN it falls back to disk | on the LAN again: `sccache --stop-server`; the next build starts a new server |
| every compile slow after leaving the LAN | a server started on the LAN waits on a network timeout per compile | `sccache --stop-server`; use `--local` on a machine where this is routine |
| zero compile requests | `RUSTC_WRAPPER` in the environment, or another `rustc-wrapper` in a project's `.cargo/config.toml`, overrides the user config | find it: `env | grep -i wrapper`, then `.cargo/config.toml` in the project and each parent directory |
| two machines never hit each other's entries | different sccache versions or rustc versions change the key. One Mac had a cargo-installed 0.14.0 shadowing brew's 0.18.0 | same sccache (0.18.0) and same toolchain on both; the installer removes a shadowing `~/.cargo/bin/sccache` on macOS |

A store that is down is a cache miss, not a build failure; sccache compiles
locally and carries on.

## 5. Build times depend on the cache

A build or test duration measured on a machine using the cache is a statement
about the cache's state as much as the code. State whether the cache was cold
or warm with every build-time figure (`benchmark-validity`). To measure
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
only, as the apt repository is), dataset `spool/sccache` with a 200 GiB quota,
entries unread for 60 days evicted weekly. Anyone on the LAN can write to it;
a poisoned entry is a wrong build, which CI exists to find. If `/health`
fails from every machine, tell the rack owner rather than working around it.

## Never

- **Never run the installer under sudo**; it configures the user who builds.
- **Never turn incremental off on a machine someone edits code on.**
- **Never give sccache a credentialed backend in a VM image**; a credential in
  an image is a secret copied into every guest.
- **Never quote a build or test duration without the cache state.**
- **Never treat `Local disk` in the stats as working** on a machine meant to
  use the store.
