# Setup for loom and shuttle in a crate

Taken from `cache-core` in `crucible-wt-cachers`. `loom-calibration.rs` beside
this file is a set of models with known outcomes; run it once against a new
loom version before relying on the rules in the skill.

## Cargo

```toml
[features]
default = []
loom = ["dep:loom"]
shuttle = ["dep:shuttle"]

[dependencies]
loom = { workspace = true, features = ["checkpoint"], optional = true }
shuttle = { workspace = true, optional = true }
```

Optional dependencies behind features keep both out of the production build
and make `cfg(feature = "loom")` the gate. Do not also use `cfg(loom)`; see the
skill, step 2.

## The shim

One module owns every atomic type the protocol uses:

```rust
#[cfg(not(feature = "loom"))]
pub use std::sync::atomic::{AtomicU16, AtomicU32, AtomicU64, Ordering, fence};
#[cfg(feature = "loom")]
pub use loom::sync::atomic::{AtomicU16, AtomicU32, AtomicU64, Ordering, fence};

#[inline]
pub fn spin_loop() {
    #[cfg(not(feature = "loom"))]
    std::hint::spin_loop();
    #[cfg(feature = "loom")]
    loom::thread::yield_now();
}
```

Export the same names from both branches. `cache-core`'s shim exports
`AtomicU8` only without loom, so any model that reaches code using it fails to
compile, which is the safe outcome. `cache-heap`'s shim re-exports `std`'s
`AtomicU16` under loom, which compiles and leaves every access to that type
unmodelled; if that is deliberate, say so in the shim.

Grep the crate for `std::sync::atomic` outside this module after adding it;
each hit in protocol code is an access loom will not model.

`cache-core` has no shuttle arm in the shim. Its shuttle models are standalone
mirrors written against shuttle's atomics, and re-exporting shuttle's types for
the whole crate would pull every `static` metric atomic into shuttle's
thread-local state. Decide the same question for your crate: models of the real
types need the shim; standalone mirrors do not.

## Gating the model modules

```rust
#[cfg(all(test, feature = "loom"))]
mod loom_models { /* fn loom_... */ }

#[cfg(all(test, feature = "shuttle", not(feature = "loom")))]
mod shuttle_models { /* fn shuttle_... */ }
```

loom takes precedence when both features are on, because `--all-features`
turns both on. Prefix every model name (`loom_`, `shuttle_`) so the runs can
filter to them; both runners' primitives panic outside a model.

Make an iteration override fail loudly when malformed:

```rust
std::env::var("SHUTTLE_ITERS").map(|v| v.parse().unwrap_or_else(|_|
    panic!("SHUTTLE_ITERS must be a number, got {v:?}")))
```

A silent fallback reports a deeper soak that never ran.

## Hazard witness

```rust
static WITNESS_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
static HAZARD_SEEN: std::sync::atomic::AtomicUsize = /* ... */;

pub struct HazardWitness(std::sync::MutexGuard<'static, ()>);

pub fn arm_hazard_witness() -> HazardWitness {
    let g = WITNESS_LOCK.lock().unwrap_or_else(|p| p.into_inner());
    HAZARD_SEEN.store(0, std::sync::atomic::Ordering::Relaxed);
    HazardWitness(g)
}

impl HazardWitness {
    pub fn assert_reached(self) {
        assert!(HAZARD_SEEN.load(std::sync::atomic::Ordering::Relaxed) > 0,
            "model never reached its hazard, so it would pass against broken code");
    }
}
```

The fixture increments `HAZARD_SEEN` (a `std` atomic, deliberately outside the
model) whenever the code under test is handed the hazardous state. Take the
poisoned guard on a panic so the next model still gets a working witness.
`assert_reached` consumes the guard, so a model that arms the witness and
forgets the check gets an unused-variable warning.

## CI jobs

```yaml
loom:
  env: { LOOM_MAX_PREEMPTIONS: 3 }
  run: cargo test -p <crate> --features loom --release -- loom_
  timeout-minutes: 120

shuttle:
  run: |
    cargo test -p <crate> --features shuttle --release -- shuttle_
    cargo clippy -p <crate> --features shuttle --all-targets -- -D warnings
```

The second shuttle line exists because the workspace clippy job runs
`--all-features`, which enables loom and compiles the shuttle module out.

The loom workflow there allows 120 minutes. On repositories moved to rack-ci
these become checks in `.rack-ci.toml` (`use-rack-ci`), where a check holds a
host for its whole run; measure the loom run's duration before choosing its
target and trigger.
