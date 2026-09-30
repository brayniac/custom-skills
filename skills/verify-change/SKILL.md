---
name: verify-change
description: Check a code change against the repository's own declared gates before pushing it or saying it works — the branch's prior CI state read first so a later failure can be attributed, every listed gate command run verbatim to a finished exit code, test counts checked so a gated-out file is not read as a pass, cfg-gated call sites found by grep, and a caller-side review for API changes. Use before any push or PR, before writing "tests pass", "fixed" or "CI is green", after a fix to one crate of a workspace, and when local gates are green but CI is red.
---

# Verify a change

Every failure this skill exists for was green locally. The gates were real;
what went wrong was which gates ran, how their result was read, and what the
local platform could not compile. Work through the steps in order and report
per gate.

This covers code changes. For a benchmark number, use `benchmark-validity`;
for a test you just wrote, use `verify-by-breaking` to show it can fail.

## 1. Read the branch's CI state before starting

```sh
gh pr checks                                            # if a PR exists
gh api repos/OWNER/REPO/commits/$(git rev-parse HEAD)/status \
  --jq '.statuses[] | [.context, .state] | @tsv'         # rack-ci posts here
```

If the branch was already red, write down which check and on which commit.
Two rounds of work once went onto a branch whose `get_stream_end_to_end`
failure predated them, because the local gates were treated as the state of the
world. A failure you cannot attribute costs a bisect later.

A `rack-ci/*` status of `error` is infrastructure, not code; `use-rack-ci` has
the table.

## 2. Build the gate list from the repository, not from memory

Read, in this order, and take the union:

- `.rack-ci.toml` and the scripts it names;
- `.github/workflows/*.yml`;
- the "Checks" or "Build" section of `CLAUDE.md` / `AGENTS.md`.

Copy each command **verbatim** into a checklist. The differences are the point:
`cargo doc --workspace` versus `-p <crate>`, a clippy rung with
`--features <flag>` or `--all-features`, `--examples`, `--locked`,
`cargo +nightly fmt`. One push went out with three gaps — `cargo doc` run per
crate, a feature-flagged clippy job never run, `--examples` never built — and
every one was a line already written in the repo's own docs.

## 3. Run each gate to completion and take its exit code

```sh
cargo test --workspace --locked > /tmp/gate-test.log 2>&1; echo "exit=$?"
```

- **The exit code is the result.** A count scraped from output is a second
  check on a run that has already exited, never the first.
- **Never pipe a gate.** `cargo … | tail` reports `tail`'s status. If a pipe is
  unavoidable, `set -o pipefail` or read `${PIPESTATUS[0]}` (bash) /
  `${pipestatus[1]}` (zsh).
- **A log still being written is not a result.** "491 passed, 0 failed" was
  once read from a file a backgrounded `cargo test` was still appending to; the
  finished total was 874 with three failures. Wait for the process to exit.
  For a job running elsewhere, `watch-long-job` covers reading it.
- **No failure line is not a pass.** `grep -c FAILED` on truncated output
  returns 0, and a missing `test result:` line was a compile error.

## 4. Check that the tests you meant to run ran

Exit 0 is compatible with running nothing:

- a test filter that matches no test exits 0;
- `-- --ignored` runs **only** ignored tests — a suite mixing `#[ignore]` and
  plain tests needs `--include-ignored`;
- a crate whose `default = []` features compile to an empty crate on this
  platform reports `0 passed`;
- a file carrying `#![cfg(has_io_uring)]` builds on macOS, runs, and reports
  `running 0 tests … test result: ok`.

So for each crate the change touches:

```sh
grep -rn '#!\[cfg(' <crate>/tests <crate>/src | grep -v 'cfg(test)'
grep -E '^\s+Running|^running [0-9]+ test' /tmp/gate-test.log
```

A binary reporting `running 0 tests` that covers the change is a gate you did
not run. Say so; do not count it. The last one of these was a nine-gate local
sweep that was green while CI failed on the gated-out file.

## 5. Find what this platform cannot compile

A change that alters ownership — `Copy` to moved-on-use, a new borrow, a
changed signature — can break a use inside a `cfg` block the local compiler
never sees. Grep every use of the changed binding or item, including inside
`#[cfg(...)]` and `cfg_if!`:

```sh
grep -rn -F '<name>' --include='*.rs' .
```

Name the CI job that compiles each gated block (the Linux job for io_uring, the
CUDA job for a GPU backend). That job is the real compile for that code; a
local green says nothing about it. If you cannot run it, report the change as
unverified on that platform rather than as passing.

## 6. After a fix, re-run the whole list

"Doctests now pass" was once said after `-p ringline --doc` while another
crate was still red. A claim is as wide as the command that produced it: after
fixing one crate, run every gate again, not the one that failed.

## 7. For an API change, ask what a caller can no longer do

Green gates show the code is valid; they do not show it is usable. An API change
once removed the ability to hold two pooled connections at once — the borrow
held the whole pool — and every gate passed, because every in-tree caller was
sequential.

For any change to a public signature, ownership, or lifetime, get a review from
a clean context (a fresh agent, not a fork of this one) asked specifically:

- what could a caller do before that it cannot do now (hold two at once, call
  concurrently, recover from an error, use it across an `.await`)?
- which callers outside this repository exist, and what do they do?

`adversarial-review` has the full procedure.

## 8. Report

One line per gate: the command, `pass` / `fail` / `not run here`, and for
`not run here` the reason and the CI job that will run it. Include the prior CI
state from step 1. Push only when every gate is `pass` or `not run here` with a
named job; after pushing, confirm the remote has your commit:

```sh
git rev-parse HEAD origin/$(git branch --show-current)
```

## Never

- **Never push with a declared gate skipped** without saying which and why.
- **Never count `running 0 tests` or `0 passed` as a pass** for code the change
  touched.
- **Never report a result from a file a process is still writing.**
- **Never claim a wider result than the command you ran** — a per-crate pass is
  not a workspace pass.
- **Never read a `rack-ci` `error` as a code failure**, and never read a GitHub
  check that failed in four seconds with no steps as one either (`use-rack-ci`).
