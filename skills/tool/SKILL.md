---
name: tool
description: Build a tool someone will run again — a converter, a report generator, a load or trace utility, a checker — in Rust by default, in the repository that uses it (a subcommand of its existing binary, or a small crate in its workspace), from a captured input fixture first, with a small CLI (help that shows an example, data on stdout, diagnostics on stderr, a non-zero exit on failure), tests from the fixture that have been seen to fail, output checked against an independent answer before anyone relies on it, and a review. Use when about to write a script that will be run again or by someone else, when asked to build a converter, parser, generator or CLI utility, and when replacing a Python or shell script with something maintained. Not for a script shipped inside a skill or a plugin hook.
---

# Build a tool

The owner's rule is to write tools in Rust, not Python scripts: "We should be
writing rust tools, not python scripts." A tool is code someone runs again,
so it gets the same treatment as the rest of the repository: a home, tests,
a review. A command run once is not a tool; a command that will run again,
or that someone else will run, is.

## 1. Decide where it lives, and in what

In the repository whose work it serves:

- a subcommand of the repository's existing binary when there is one (one
  converter became `convert-trace` in `src/trace.rs` of the project's CLI);
- otherwise a small crate in the workspace (`tools/<name>`), with
  `publish = false` unless it ships;
- in a repository with no Rust, ask before adding a Cargo workspace to it;
- a tool several repositories use goes in the repository that owns the
  shared concern, installed with `cargo install --git`, or run in place:
  `cargo run --manifest-path <repo>/Cargo.toml --bin <name>`.

Not the scratch directory: a tool there is deleted with the session.

Rust is the default. The exception is a script that must run with no build step:
one shipped in a skill's `references/` or as a plugin hook, which this plugin
requires to work on a host with nothing else installed. Write those in Python or
POSIX shell. A guest image or CI step without a Rust toolchain is not an
exception: it can run a binary built elsewhere for its target (Linux; aarch64 on
the Pis; musl on Alpine). Use another language otherwise only when the user
asks, and say why.

## 2. Capture the input first

Before writing the parser, record what the input actually looks like into a
committed fixture (`capture`): a real file, trimmed to what the tests need,
with the odd cases kept. Parse from the fixture, not from the format's
documentation or memory.

## 3. A small CLI

- `clap` derive; `--help` shows one complete example invocation.
- Data on stdout, diagnostics on stderr, so the output can be piped.
- A non-zero exit on any failure, including partial input; never print an
  error and exit 0.
- Deterministic output (sorted keys, stable order) when another tool or a
  test reads it; a `--json` mode when a program will.
- Read the input in the form it arrives instead of requiring an extracted
  copy (the converter reads the dataset's `.tar.gz` directly: a full day in
  3.1 s, 0.72 GB peak). Stream when memory must stay bounded.

Follow the repository's conventions for errors, naming and layout (`rust`).

## 4. Tests that can fail

Tests read the fixture through the real entry point. Break each one once to
see it fail (`verify` step 8): the converter's timestamp test was checked by
making the code treat `timestamp` as the start time.

## 5. Check the output against an independent answer

Before anything relies on the tool, compare its output with an answer that
does not come from its own code, on real input: the script it replaces, a
hand-computed case, or the system's own counters. The converter's session
and call counts on a full day matched the earlier Python analysis (54,368
sessions, 1,766,894 calls). Its own tests encode the author's reading of the
format, so they cannot catch a misreading of it.

## 6. Document and review

`--help` and a short section where the repository documents its tools (`docs`
for testing the help with a fresh agent). Then `verify` and `review`. The
converter's review found that it hung when every worker failed, and a
regression test timed out at 10 s on the code before the fix.

## Never

- **Never leave a recurring task as a Python or shell script** without the
  user choosing that, except a script that must run with no build step
  (step 1).
- **Never write a parser before capturing the input** it parses.
- **Never exit 0 after an error**, or mix diagnostics into stdout.
- **Never let anything depend on the tool's output** before step 5.
