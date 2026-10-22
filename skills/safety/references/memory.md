# Memory safety in unsafe Rust

A test that passes over undefined behaviour shows nothing: the program read
freed memory and got the value it expected. On a toy crate checked here
(2026-10-22, nightly `miri 0.1.0 (cea272fa35 2026-09-07)`, aarch64 macOS), a
test that reads a `Box` after dropping it passed under `cargo test`, and was
reported by both tools below:

```text
cargo +nightly miri test
error: Undefined Behavior: memory access failed: alloc42205 has been freed,
so this pointer is dangling

RUSTFLAGS=-Zsanitizer=address cargo +nightly test --target aarch64-apple-darwin
ERROR: AddressSanitizer: heap-use-after-free ... lib.rs:5 in read_after_free
```

## 1. Pick the tool by what the code does

| The unsafe code | Tool | Why |
| --- | --- | --- |
| raw pointers, `transmute`, `MaybeUninit`, unchecked indexing, hand-rolled allocators, no system calls | Miri | interprets the program and reports undefined behaviour at the operation that causes it, including aliasing (`-Zmiri-tree-borrows`) and uninitialised reads that never crash |
| FFI, system calls (io_uring, mmap, `ioctl`), or a test Miri cannot run | AddressSanitizer | runs native code; finds out-of-bounds and use-after-free on the heap and stack, but not aliasing violations or every uninitialised read |
| shared state across threads | the rest of this skill (loom, shuttle) and ThreadSanitizer | a data race is a concurrency property; Miri also reports races between the threads it runs |
| input from outside the process | `fuzz-crash-to-test`, then the tools above on the crash | fuzzing finds the input; the tools above say what it broke |

Miri cannot execute most system calls or foreign functions; move the unsafe
logic that does not need them behind a function Miri can test, and cover the
rest with AddressSanitizer.

## 2. Run them

```sh
rustup +nightly component add miri
cargo +nightly miri test                          # the whole suite
cargo +nightly miri test <name>                   # one test; Miri is slow
MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri test

RUSTFLAGS=-Zsanitizer=address cargo +nightly test --target <host-triple>
```

The `--target` flag is required for the sanitizer run: it keeps the
sanitizer flags off build scripts and proc macros. `rustc -vV` prints the
host triple.

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
