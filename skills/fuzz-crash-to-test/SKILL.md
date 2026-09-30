---
name: fuzz-crash-to-test
description: Turn a cargo-fuzz / libFuzzer finding into a regression guard the repository's gate actually runs — preserve and minimize the artifact, fix the invariant rather than the one input, find the twin site downstream, write the failing test first, and choose the strongest guard the property allows (Kani proof, proptest, unit test). Use when a fuzz target reports a crash-, oom- or timeout- artifact, an overflow or out-of-bounds panic from hostile input, and when deciding what to commit after fuzzing found a bug or whether a committed seed counts as protection.
---

# Turn a fuzz crash into a test

A fuzz crash is fixed when a check the gate runs would catch it again. Fuzz
crates are usually their own nightly-only workspaces, excluded from the
workspace: `cargo test` and clippy never run a fuzz target. So a fix with no
gate-runnable test is unprotected, and the next regression passes every gate.

**The deliverable is a test or a proof.** `fuzz/artifacts/` is gitignored and
cargo-fuzz overwrites it. A committed seed replays the case only when someone
runs the fuzzer; it adds coverage and guards nothing.

## 1. Preserve and reproduce

Copy the artifact out of `fuzz/artifacts/` immediately. Confirm it crashes on
its own, not only from fuzzer state:

```sh
cargo +nightly fuzz run <target> <artifact>
```

## 2. Minimize

```sh
cargo +nightly fuzz tmin <target> <artifact>
```

The minimized bytes are the test vector.

## 3. Fix the invariant, not the input

State the property the crash violates — "this parser returns an error for any
input and never panics or wraps", not "`u64::MAX` as a dimension overflows".
Find every site the property covers. An overflow usually has a twin
downstream: `numel()` and then the `numel × type_size` multiply.

## 4. Write the failing gate test first

Write the guard (step 5), run it against the unfixed code, and see it fail. Then
fix, and see it pass. A test written after the fix has not been shown to catch
the bug (`verify-by-breaking`).

## 5. Choose the strongest guard the property allows

| Property | Guard, strongest first |
| --- | --- |
| Integer, index, overflow or bounds arithmetic (`numel`, `byte_len`, offsets) | **Kani proof** over `kani::any()`: covers the whole domain, not one input. Put it under `#[cfg(kani)]` and declare `cfg(kani)` in `[lints.rust] check-cfg`, or the unexpected-cfg lint fires. |
| Any bytes → `Ok` or a typed `Err`, never a panic | **proptest** over arbitrary bytes, generalizing the crash shape. Runs in the gate. |
| One case neither can express | **Unit test** with the minimized bytes inline. |

A unit test with the one input is the minimum, not the goal. Check that the
gate runs the chosen guard: a Kani proof needs a gate step that runs
`cargo kani`, and if the repo has none, say so and add the proptest or unit
test as well.

## 6. Re-fuzz and keep the seed

Re-run the fuzzer from the existing seeds for long enough to pass the point
where it crashed before. Then commit the minimized bytes as a seed under the
crate's tracked seed directory (for example `fuzz/seeds/<target>/`), never
under `corpus/`, which is generated and usually ignored.

## 7. Gate and PR

Run the repository's gates (`verify-change`) and open the PR (`open-pr`). The
PR body names the invariant, every site fixed, and the guard.

## Never

- **Never count a committed crasher or seed as the regression guard.**
- **Never count a clean fuzz run as a gate result.**
- **Never fix before the failing test exists.**
- **Never stop at the first overflow site** without looking for the twin.
- **Never leave the reproducer only in `fuzz/artifacts/`.**
