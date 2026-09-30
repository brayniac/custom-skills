---
name: model-check-concurrency
description: Test a Rust lock-free protocol or atomic handshake with loom (exhaustive interleavings under weak memory), shuttle (randomized, sequentially consistent) and ThreadSanitizer, so that each model can fail — a sync shim that swaps every shared atomic, a fixture whose mutations are single atomic operations, one model per entry point, a hazard witness proving the model reached the interleaving it exists for, a neutered-code run that turns it red, and properties chosen for what each checker can and cannot decide (loom reports store buffering even under SeqCst; shuttle cannot see an ordering that is too weak). Use when adding or changing atomics, orderings, CAS loops, reference counts, or reader/writer handshakes; when writing or reviewing a loom or shuttle test; when a loom suite is green and you need to know what that proves; and when a concurrent test flakes.
---

# Model-check concurrent Rust

A loom model that passes has explored every interleaving it could reach. What
it could reach is decided by the fixture, the shim, and the assertion, and in
the repository this skill comes from each of those has made a model pass
against broken code. So the work is proving the model can fail, then keeping
it able to.

Evidence below is from `cache-core` in `crucible-wt-cachers` (PRs #85–#131)
and from a toy crate run against loom 0.7.2 on 2026-09-30.

## Inputs

- The protocol under test: the shared words, who writes them, with what
  ordering, and the invariant (a reader never sees a freed segment; a key is
  never reported absent while present).
- The crate's existing concurrency test setup, if any.

## 1. Pick the checker by the property

| Checker | Explores | Can decide | Cannot decide |
| --- | --- | --- | --- |
| loom | every interleaving within a preemption bound, with a weak memory model | an ordering that is too weak (a `Release` degraded to `Relaxed`) | any property that holds only under the SeqCst total order: it reports the store-buffering outcome for a pure-SeqCst litmus |
| shuttle | random schedules, sequentially consistent | SeqCst-total-order properties (a pinned reader never coexists with a committed drain) | any ordering bug: it treats every access as SeqCst |
| ThreadSanitizer | the real program under real scheduling | a non-atomic access racing another access | any path no concurrent test executes |
| Miri | one execution, single-threaded is enough | aliasing and provenance: a `&[u8]` whose referent another path writes | interleavings |
| Kani | all inputs to a pure function | arithmetic of the bit-packing the protocol rests on | interleavings |

The loom row was confirmed on the toy crate: a two-thread store-buffering
litmus with all four accesses `SeqCst` fails under loom with both loads
reading 0. In `cache-core`, the SeqCst fix for the guard/drain handshake
(#131) could not be turned red by either checker, and was justified from the
memory model and prior art instead; say that plainly when it happens.

The TSan job found a race on its first run: the item flags byte was written by
an atomic `fetch_or` and read as a plain byte in every lookup's header decode
(#85). Its first scope, `--lib` only, missed a second non-atomic tombstone
write in a disk-tier type that only an integration test executes. Kani found a
packing that collided with the empty-slot sentinel, losing 1 key in 4096, in
19 ms (#115). Keep every suite green; none covers another.

## 2. Wire the shim so the model sees every access

loom instruments only its own types. Every shared atomic in the code under
test must come from one module that switches on the feature:

```rust
#[cfg(not(feature = "loom"))]
pub use std::sync::atomic::{AtomicU64, Ordering};
#[cfg(feature = "loom")]
pub use loom::sync::atomic::{AtomicU64, Ordering};
```

- A `std` atomic inside `loom::model` is invisible to it. On the toy crate, a
  load-then-store increment from two threads loses an update under loom with
  loom atomics and **passes** with `std` atomics.
- Match the `cfg` to how it is set. `--features loom` sets
  `cfg(feature = "loom")`; a test gated `#[cfg(loom)]` is compiled out and the
  run reports one fewer test with exit 0. The compiler warns
  `unexpected cfg condition name: loom`; treat that warning as this bug.
  `--cfg loom` comes only from `RUSTFLAGS`.
- Spin loops yield under loom (`loom::thread::yield_now()` in place of
  `std::hint::spin_loop()`), as `cache-core`'s `sync::spin_loop` does.
- loom and shuttle primitives panic outside their runner ("cannot access Loom
  execution state from outside a Loom model"), so gate the models to the
  feature and run them with a name filter (`-- loom_`, `-- shuttle_`).

`${CLAUDE_SKILL_DIR}/references/setup.md` has the Cargo features, the shuttle
gating, a hazard-witness sketch, and the CI jobs.
`${CLAUDE_SKILL_DIR}/references/loom-calibration.rs` holds the toy models behind
the claims in this step and step 1, with their observed outcomes; rerun it after
a loom upgrade.

## 3. Build a fixture that can express the hazard

- **A stub that always succeeds hides half the protocol.** `cache-core`'s
  models stubbed `KeyVerifier` with one that verified anything, so the whole
  verify-failure path (relocation walk, tombstone poll) was unreachable (#91).
  Replace such stubs with a stateful oracle backed by model atomics.
- **Encode the production ordering in the fixture's own mutations**
  (copy, then publish, then recycle), so the model cannot build a state the
  real system cannot reach.
- **Every fixture mutation is one atomic operation.** A tombstone written as
  `load` then `store` instead of `fetch_or` left the model green because its
  hazard was never reached: verifier misses over a run were 0 with the
  load-store and 183 with `fetch_or` (#95).
- Keep models small: loom allows at most 5 threads including the main one
  (`MAX_THREADS` in 0.7.2), and state space grows with every operation. Two
  or three threads with one or two operations each is the usual size.

## 4. One model per entry point

Four read paths in `cache-core` each carried their own copy of the scan loop
and its guard, so each got its own model (#91). A model of one sibling says
nothing about another's copy. When a model exists to exercise one branch,
count that it reaches it: the relocation models reached the lost-CAS branch 0
times; a two-ADD model written for it reached it 8 times (#98).

## 5. Prove each model can fail

Apply `verify-by-breaking`: neuter the guard the model defends (restore the
pre-fix `verify_slot`, remove the CAS re-check) and confirm the model goes
red with the forbidden outcome.

If it stays green, check the model before concluding anything. Two models
dropped as "cannot fail" in #91 were wrong verdicts: the probing patch had
replaced the assertion with an `eprintln!`, so the neutered runs had nothing
to assert (#95). A model that stays green with its assertion intact, under a
neutered guard, shows that guard is not what provides the safety; say which
check does (#98: the duplicate-entry guard, not the lost-CAS branch).

## 6. Make reachability a standing check

A red run under neutered code proves the model could fail once. Add a hazard
witness so it keeps failing if it ever stops reaching the hazard: the fixture
counts the hazardous observations (a verifier handed a stale location), and
the model asserts the count is non-zero at the end.

- In `cache-core` exposure ranged from 80–183 misses per run to 2, so a
  model can be one fixture change away from reaching nothing (#96).
- Reintroducing the #95 bug made the witness fail with "model never observed
  a delete-marked occupant", where before it had shipped green.
- Witness counters are process-global and `cargo test` runs tests in
  parallel, so hold a process-wide lock for the life of a witnessed model.

## 7. Reproduce a flake deterministically where possible

A `KeyNotFound` flake at about 1 run in 12 under full-suite load was
reproduced deterministically by performing the racing publish from inside the
verifier's own callback, with a precondition assert so the test could not go
vacuous. It was red before the fix, green after, and the original flake went
to 0 in 70 full-suite runs (#85). Size such sweeps with
`debug-intermittent-failure` step 1.

## 8. Run it in CI

- loom: `LOOM_MAX_PREEMPTIONS=3 cargo test -p <crate> --features loom
  --release -- loom_`. Loom's own docs say a bound of 2 or 3 catches most
  bugs; `--release` because models are slow.
- shuttle: its own job with its name filter. When the loom module wins with
  both features on, `clippy --all-features` compiles the shuttle module out,
  so lint it in a separate `--features shuttle` clippy run.
- TSan: `RUSTFLAGS=-Zsanitizer=thread TSAN_OPTIONS=halt_on_error=1 cargo
  +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu --lib`, plus
  every integration test that runs concurrent code the lib tests do not.
  Doctests do not get the sanitizer flags under `-Zbuild-std`. No
  suppressions: a report fails the job.

## 9. Report

For each model: the invariant, the neutered guard that turned it red and the
message, the witness count, and which checker's blind spot applies. For an
ordering change no checker can turn red, state that and give the
memory-model argument.

## Never

- **Never count a loom model as coverage until it has failed** against a
  neutered guard with its assertion intact.
- **Never use `std` atomics, or a non-atomic read-modify-write, inside a
  model's fixture.**
- **Never assert a SeqCst-only property under loom**; it will fail on correct
  code. Use shuttle for it.
- **Never treat a shuttle pass as evidence about memory ordering.**
- **Never gate models on `cfg(loom)` while enabling them with
  `--features loom`.**
- **Never delete a model as vacuous without checking the probe did not
  remove its assertion.**
