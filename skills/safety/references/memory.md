# Memory safety in unsafe Rust

A test that passes over undefined behaviour shows nothing: the program read
freed memory and got the value it expected. On a toy crate checked here
(2026-10-21, nightly `miri 0.1.0 (cea272fa35 2026-09-07)`, aarch64 macOS), a
test that reads a `Box` after dropping it passed under `cargo test`, and was
reported by both tools below:

```text
cargo +nightly miri test
error: Undefined Behavior: memory access failed: alloc42205 has been freed,
so this pointer is dangling

RUSTFLAGS=-Zsanitizer=address cargo +nightly test --target aarch64-apple-darwin
# (a crate with no doctests; see step 2 for RUSTDOCFLAGS)
ERROR: AddressSanitizer: heap-use-after-free ... lib.rs:5 in read_after_free
```

## 1. Pick the tool by what the code does

| The unsafe code | Tool | What it finds, and does not |
| --- | --- | --- |
| raw pointers, `transmute`, `MaybeUninit`, unchecked indexing, hand-rolled allocators | Miri | interprets the program and reports undefined behaviour where it happens: use-after-free, out-of-bounds, aliasing violations (Stacked Borrows by default), uninitialised reads, data races between the threads it runs, and leaks |
| FFI into C, or system calls Miri has no shim for (io_uring, `ioctl`) | AddressSanitizer | runs native code; finds heap and stack out-of-bounds and use-after-free, and leaks with `ASAN_OPTIONS=detect_leaks=1` on macOS. Not aliasing violations, uninitialised reads (MemorySanitizer, Linux only) or data races |
| shared state across threads | the rest of this skill (loom, shuttle) and ThreadSanitizer | the orderings; Miri also reports races on the schedules it runs |
| input from outside the process | `fuzz-crash-to-test`, then the tools above on the crash | fuzzing finds the input; the tools above say what it broke |

Unsafe code shared across threads gets both: Miri for the pointer errors, loom
for the orderings.

Miri shims part of libc (memory, threads, clocks, and files and the
environment with `MIRIFLAGS=-Zmiri-disable-isolation`; anonymous `mmap` ran
here) and stops with `unsupported operation`, or "can't call foreign
function", naming the call it lacks. Disable isolation for file I/O; move
what is still unsupported behind a function Miri can test, and cover the rest
with AddressSanitizer.

## 2. Run them

```sh
rustup +nightly component add miri
cargo +nightly miri test                          # the whole suite
cargo +nightly miri test <name>                   # one test; Miri is slow
MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri test

RUSTFLAGS=-Zsanitizer=address RUSTDOCFLAGS=-Zsanitizer=address \
  cargo +nightly test --target <host-triple>
```

`-Zmiri-tree-borrows` is a second, more permissive aliasing model, not the
switch that turns aliasing checks on: code that fails only under the default
breaks the stricter rules. `RUSTDOCFLAGS` is needed because rustdoc builds the
doctests and does not read `RUSTFLAGS`; without it, any crate with a doctest
fails to link. `--target` keeps the sanitizer off build scripts and proc macros,
which otherwise abort the build. `rustc -vV` prints the host triple.
AddressSanitizer aborts the test binary at its first report, so later errors in
the same binary appear only after the first is fixed and the run repeated.

## 3. Show the check can fail

As for a loom model (step 5 of the skill), a clean Miri or sanitizer run
means something only if the test reaches the unsafe code. Break it once on
purpose (drop the guard, read past the end) and confirm the tool reports it
(`verify` step 8), then restore.

## 4. Keep it running

Add the Miri run, scoped to the tests that touch unsafe code if the whole
suite is too slow, and the sanitizer run to the repository's gates; a check
that is run once at authoring time stops covering the code at the next
change.
