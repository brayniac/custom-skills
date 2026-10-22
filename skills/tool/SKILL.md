---
name: tool
description: Build a tool someone will run more than once — a converter, a report generator, a load or trace utility, a checker — in Rust by default, in the repository that uses it (a subcommand of its existing binary, or a small crate in its workspace), from a captured input fixture first, with a small CLI (help that shows an example, data on stdout, diagnostics on stderr, a non-zero exit on failure), tests from the fixture that have been seen to fail, output checked against a reference before anyone relies on it, and a review. Use when about to write a script that will outlive this session, when a one-off command is being run for the third time, when asked to build a converter, parser, generator or CLI utility, and when replacing a Python or shell script with something maintained.
---

# Build a tool

The owner's rule is to write tools in Rust, not Python scripts: "We should be
writing rust tools, not python scripts." A tool is code someone runs again,
so it gets the same treatment as the rest of the repository: a home, tests,
a review. A one-off command run once in a session is not a tool; the third
time it is run, it is.

## 1. Decide where it lives

In the repository whose work it serves:

- a subcommand of the repository's existing binary when there is one (one
  converter became `convert-trace` in `src/trace.rs` of the project's CLI);
- otherwise a small crate in the workspace (`tools/<name>`), with
  `publish = false` unless it ships.

Not the scratch directory and not a gist: a tool nobody can find gets
rewritten. Use another language only when the user asks, or when the tool
must run where Rust cannot (inside a guest image with no toolchain, a CI
step that only has a shell); say which and why.

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
- Read input in a streaming way when it can be large (the converter read the
  dataset's `.tar.gz` directly, a full day in 3.1 s).

Follow the repository's conventions for errors, naming and layout (`rust`).

## 4. Tests that can fail

Tests read the fixture through the real entry point. Break each one once to
see it fail (`verify` step 8): the converter's timestamp test was checked by
making the code treat `timestamp` as the start time.

## 5. Check the output against a reference

Before anything relies on the tool, compare its output with an independent
answer on real input: the script it replaces, a hand-computed case, or the
system's own counters. The converter's output was checked against the
earlier Python numbers on a full day of data. A tool that has only been
checked against its own tests has been checked against its author's
understanding.

## 6. Document and review

`--help` and a short section where the repository documents its tools (`docs`
for testing the help with a fresh agent). Then `verify` and `review`; the
converter's review found a hang on one input, reproduced with a regression
test that timed out before the fix.

## Never

- **Never leave a recurring task as a Python or shell script** without the
  user choosing that.
- **Never write a parser before capturing the input** it parses.
- **Never exit 0 after an error**, or mix diagnostics into stdout.
- **Never let anything depend on the tool's output** before step 5.
