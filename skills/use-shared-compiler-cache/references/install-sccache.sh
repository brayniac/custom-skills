#!/usr/bin/env bash
# Point this machine's cargo at the rack's shared compiler cache (sccache over
# WebDAV on delta), or at a local disk cache, and prove a build uses it.
#
#   bash install-sccache.sh [--local] [--no-incremental]
#
# Run as the user who builds, not under sudo. macOS or Linux (x86_64,
# aarch64). Needs cargo on PATH. Idempotent.
#
#   --local            a disk cache on this machine instead of the store, for a
#                      machine that is often off the LAN
#   --no-incremental   also set `incremental = false`, as the CI images do: for
#                      a throwaway VM or build host, not for a machine someone
#                      edits code on
#
# Environment: SCCACHE_ENDPOINT overrides the store (default http://delta:8081,
# falling back to http://10.1.0.0:8081 when `delta` does not resolve).
#
# Exit 0 only when a probe build went through sccache and sccache reported the
# expected backend. Anything else exits non-zero with the reason.

set -euo pipefail

VERSION=0.18.0          # the CI images' pin; cache keys are shared across hosts
LOCAL=0
NO_INCREMENTAL=0
for a in "$@"; do
    case $a in
        --local) LOCAL=1 ;;
        --no-incremental) NO_INCREMENTAL=1 ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "error: unknown argument $a" >&2; exit 64 ;;
    esac
done
[[ $EUID -ne 0 ]] || { echo "error: run as the user who builds, not root" >&2; exit 64; }
command -v cargo >/dev/null || { echo "error: no cargo on PATH; install rustup first" >&2; exit 64; }

OS=$(uname -s)
say() { echo "==> $*"; }

# --- sccache ---------------------------------------------------------------
case $OS in
Darwin)
    # Homebrew, as the infra installer does. A cargo-installed copy in
    # ~/.cargo/bin shadows it and was once a different version (0.14.0 against
    # brew's 0.18.0), which changes what a cache key is.
    command -v brew >/dev/null || { echo "error: no brew to install sccache with" >&2; exit 1; }
    brew list --versions sccache >/dev/null 2>&1 || brew install -q sccache
    if [[ -x ${CARGO_HOME:-$HOME/.cargo}/bin/sccache ]]; then
        say "removing ${CARGO_HOME:-$HOME/.cargo}/bin/sccache, which shadows brew's"
        rm -f "${CARGO_HOME:-$HOME/.cargo}/bin/sccache"
    fi
    CONF_DIR="$HOME/Library/Application Support/Mozilla.sccache"
    DISK_DIR="$HOME/Library/Caches/Mozilla.sccache"
    ;;
Linux)
    case $(uname -m) in
        x86_64)  ARCH=x86_64;  SHA=45f1447fbe231e3037bde351ef70677dd212216c8d62ae7ca409fecc4d6acc89 ;;
        aarch64) ARCH=aarch64; SHA=2b3284d5da3b46a47dc4229e75bb7b88ac4aa99c8d754fb7d2f84997e5a4354a ;;
        *) echo "error: no sccache build for $(uname -m)" >&2; exit 1 ;;
    esac
    BIN_DIR="$HOME/.local/bin"
    if ! "$BIN_DIR/sccache" --version 2>/dev/null | grep -qx "sccache $VERSION"; then
        TGZ="sccache-v${VERSION}-${ARCH}-unknown-linux-musl"
        tmp=$(mktemp -d)
        curl -fsSL -o "$tmp/s.tgz" \
            "https://github.com/mozilla/sccache/releases/download/v${VERSION}/${TGZ}.tar.gz"
        echo "${SHA}  $tmp/s.tgz" | sha256sum -c - >/dev/null \
            || { echo "error: sccache checksum mismatch" >&2; exit 1; }
        tar -xzf "$tmp/s.tgz" -C "$tmp"
        install -D -m 0755 "$tmp/$TGZ/sccache" "$BIN_DIR/sccache"
        rm -rf "$tmp"
    fi
    case ":$PATH:" in *":$BIN_DIR:"*) ;; *) export PATH="$BIN_DIR:$PATH"
        echo "warning: $BIN_DIR is not on PATH; add it in your shell profile" >&2 ;; esac
    CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/sccache"
    DISK_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/sccache"
    ;;
*) echo "error: unsupported OS $OS" >&2; exit 1 ;;
esac
hash -r
have=$(sccache --version | awk '{print $2}')
say "$(command -v sccache): sccache $have"
[[ $have == "$VERSION" ]] || echo "warning: sccache $have here, $VERSION in the CI images; keys may not match" >&2

# --- the backend -----------------------------------------------------------
# macOS reads ~/Library/Application Support/Mozilla.sccache/config, not
# ~/.config/sccache/config. A config in the wrong place is ignored and sccache
# uses a local disk cache while reporting success.
mkdir -p "$CONF_DIR"
if [[ $LOCAL -eq 1 ]]; then
    printf '[cache.disk]\ndir = "%s"\nsize = 53687091200\n' "$DISK_DIR" > "$CONF_DIR/config"
    WANT="Local disk"
    say "$CONF_DIR/config: local disk cache, 50 GiB"
else
    ENDPOINT=${SCCACHE_ENDPOINT:-http://delta:8081}
    if ! curl -sf -m 3 -o /dev/null "$ENDPOINT/health"; then
        if [[ -z ${SCCACHE_ENDPOINT:-} ]] && curl -sf -m 3 -o /dev/null http://10.1.0.0:8081/health; then
            echo "warning: 'delta' does not resolve or answer here; using 10.1.0.0" >&2
            ENDPOINT=http://10.1.0.0:8081
        else
            echo "error: $ENDPOINT/health does not answer. Off the LAN? Use --local." >&2
            exit 1
        fi
    fi
    printf '[cache.webdav]\nendpoint = "%s"\n' "$ENDPOINT" > "$CONF_DIR/config"
    WANT="webdav"
    say "$CONF_DIR/config: the store at $ENDPOINT"
fi

# --- cargo -----------------------------------------------------------------
# Merged into an existing config.toml, never overwritten.
CARGO_CONF="${CARGO_HOME:-$HOME/.cargo}/config.toml"
mkdir -p "$(dirname "$CARGO_CONF")"; touch "$CARGO_CONF"
set_build_key() {  # key value
    if grep -qE "^\s*$1\s*=" "$CARGO_CONF"; then
        say "$CARGO_CONF already sets $(grep -E "^\s*$1\s*=" "$CARGO_CONF" | head -1)"
    elif grep -qE '^\s*\[build\]\s*$' "$CARGO_CONF"; then
        python3 - "$CARGO_CONF" "$1" "$2" <<'PY'
import re, sys
p, k, v = sys.argv[1:]
s = open(p).read()
s = re.sub(r'(^\s*\[build\]\s*$)', lambda m: f'{m.group(1)}\n{k} = {v}', s, count=1, flags=re.M)
open(p, 'w').write(s)
PY
        say "added $1 to [build] in $CARGO_CONF"
    else
        printf '\n[build]\n%s = %s\n' "$1" "$2" >> "$CARGO_CONF"
        say "added [build] $1 to $CARGO_CONF"
    fi
}
set_build_key rustc-wrapper '"sccache"'
[[ $NO_INCREMENTAL -eq 1 ]] && set_build_key incremental false
grep -qE '^\s*rustc-wrapper\s*=\s*"sccache"' "$CARGO_CONF" \
    || { echo "error: $CARGO_CONF sets a different rustc-wrapper; not changing it" >&2; exit 1; }
[[ -z ${RUSTC_WRAPPER:-} || ${RUSTC_WRAPPER##*/} == sccache ]] \
    || { echo "error: RUSTC_WRAPPER=$RUSTC_WRAPPER in the environment overrides cargo's config" >&2; exit 1; }

# --- prove it --------------------------------------------------------------
# A running server keeps the backend it started with, so restart it before
# the probe; otherwise the probe reports the old backend.
sccache --stop-server >/dev/null 2>&1 || true
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
( cd "$tmp" && cargo init -q --name probe && cargo add -q anyhow >/dev/null 2>&1 \
    && cargo build -q ) || { echo "error: the probe build failed" >&2; exit 1; }
stats=$(sccache --show-stats)
loc=$(sed -n 's/^Cache location *//p' <<<"$stats")
req=$(sed -n 's/^Compile requests  *\([0-9]*\)$/\1/p' <<<"$stats")
say "probe: $req compile requests, cache location: $loc"
[[ ${req:-0} -gt 0 ]] || { echo "error: the probe build made no sccache requests" >&2; exit 1; }
[[ $loc == "$WANT"* ]] || { echo "error: sccache is using '$loc', expected $WANT" >&2; exit 1; }
say "ok"
