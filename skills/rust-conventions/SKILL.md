---
name: rust-conventions
description: The Rust conventions these repos actually follow — how errors are handled, how tests are named and placed, what comments are expected to carry, and which habits do not travel between repos. Use before writing or reviewing Rust in any repo here, when a review calls code "not idiomatic", and when carrying a pattern from one of these repos into another.
---

# Rust conventions here

Generic idiomatic-Rust advice is not what this carries. `cargo clippy` already
catches the mechanical half and CI gates on it. This is the part clippy cannot
see: what these repos have settled on, and where a habit from one of them is
wrong in another.

**The repo's own `CLAUDE.md` outranks this file.** Several are substantial —
rezolus runs to ~360 lines, ringline ~310 — and they carry architecture and
invariants no general convention can. Read it first; treat this as what holds
when it is silent.

## Habits do not travel between repos

The most common way to write non-idiomatic code here is to import a convention
from the repo you were in yesterday. Three that differ:

**Error handling is a per-repo choice, not a per-crate one.** slipway uses
`thiserror` in all seven of its crates and `anyhow` in none. systemslab uses
`anyhow` across thirteen crates — libraries included — alongside its own
`SystemsLabError` for anything crossing the API boundary. rezolus and anvil mix
both. So the rule is not "thiserror for libraries, anyhow for binaries", which
is the reflex you will arrive with. **Check what the crate's siblings do.**

**Git conventions differ too.** rezolus's `CLAUDE.md` says plainly: do not
append claude.ai session links to commit messages. Other repos here expect
them. A commit trailer is not a house style you carry in.

**Feature-gated code is checked per feature.** ringline runs clippy three
times — default, `force-mio`, `tls-unbuffered` — because a feature combination
nothing lints is a feature combination nothing compiles. If you add a feature,
add its clippy rung.

## Tests

**Name a test for the behaviour it pins, as a sentence.** This is the strongest
convention here and it is nearly universal:

```rust
fn an_inverted_window_saturates_to_zero_width()
fn two_skills_with_one_name_in_the_same_root_is_an_error()
fn retry_delay_saturates_at_ten_minutes()
fn send_data_is_resilient_to_flow_control_backpressure()
fn unknown_tool_is_an_error_result_not_a_protocol_error()
```

Not `test_parse`, not `test_auth_state_creation`. anvil still carries `test_*`
names from before the convention settled; match the file you are in, and prefer
the sentence form in new code. A name that reads as a claim makes a failing
test self-describing in CI output, where nobody has the source in front of them.

**Unit tests go inline in `#[cfg(test)]` modules**, next to what they test —
278 files in rezolus, ~60 in each of systemslab, slipway and ringline.
Integration tests go in `tests/`. Both, not either.

**When fixtures must cross a crate boundary, put them behind a feature, not
`#[cfg(test)]`.** A `#[cfg(test)]` module is invisible to other crates' tests,
so rezolus's `rez` crate exposes its fixture builders under a `test-support`
feature that the binary and the viewer both enable. Reaching for `pub` and a
`#[doc(hidden)]` instead is the wrong fix.

## Comments carry the rationale, not the mechanism

Doc-comment density runs 8–13% of all lines across these repos, well above what
Rust code usually carries. That budget is not spent restating signatures. It is
spent on why a thing is the way it is, and what breaks if it changes:

```rust
/// `include_dir!` expands to one `include_bytes!` per file, so Cargo already
/// rebuilds when a tracked skill file changes. It does not notice a *new* file,
/// which would silently leave a freshly added skill out of the binary.
```

```rust
/// A typed error rather than a string because `describe-recording` renders the
/// "several recordings, pick one" case as its ANSWER, in its own words, while
/// every analysis tool renders it as a failure.
```

The shape to copy: **name the alternative and say what it would cost.** A
comment that says what the code does is redundant with the code; a comment that
says why the obvious alternative was rejected is the only place that survives.

Where a decision is deliberate and looks wrong, say so at the site. Load-bearing
absences — a missing tag, an omitted `?`, an error deliberately swallowed —
are invisible to a reader who was not there.

## What CI gates

Every repo: `cargo clippy --all-targets -- -D warnings` and
`cargo fmt --all -- --check`. Flags vary (`--all-features`, `--workspace`,
`--locked`); read the repo's workflow rather than assuming. **No repo here sets
`[workspace.lints]` or crate-level `#![deny]`** — the gate is clippy's defaults
at deny-warnings, so a lint you want enforced has to go in CI, not in an
attribute nobody will notice.

Run the repo's own checks before proposing a change; `release` skill step 1
question 6 covers finding them.

## Never

- **Never import an error-handling habit across repos.** Read the sibling
  crates first.
- **Never add a feature without adding its clippy rung**, or it compiles only
  by luck.
- **Never write a comment that restates the signature.** If the alternative is
  not named, the comment is not carrying its weight.
- **Never put cross-crate test fixtures behind `#[cfg(test)]`** — other crates
  cannot see them, and the workaround is worse than the feature.
- **Never carry a commit-message convention between repos.** At least one here
  forbids what another expects.
