// Calibration models for loom. Drop into a scratch crate with
//
//   [dependencies]
//   loom = { version = "0.7", optional = true }
//   [features]
//   loom = ["dep:loom"]
//
// and run `cargo test --features loom`. Observed with loom 0.7.2, rustc 1.98,
// 2026-09-30 (6 tests run, 2 pass, 4 fail):
//
//   loom_mp_relaxed_publish                FAILED  saw flag without data
//   loom_mp_release_acquire                ok
//   loom_sb_seqcst_litmus                  FAILED  loom reports store buffering
//                                                  under SeqCst (over-approximation)
//   loom_counter_load_store_loom_atomic    FAILED  lost update found
//   loom_counter_load_store_std_atomic     ok      std atomics are not modelled
//   loom_atomic_outside_model              FAILED  "cannot access Loom execution
//                                                  state from outside a Loom model"
//   cfg_mismatch::gated_on_bare_cfg_loom   (not compiled: 6 tests, not 7, and
//                                           rustc warns `unexpected cfg
//                                           condition name: loom`)
//
// If a newer loom changes any of these, the corresponding rule in the skill
// needs rechecking.

#[cfg(not(feature = "loom"))]
pub use std::sync::atomic::{AtomicUsize, Ordering};
#[cfg(feature = "loom")]
pub use loom::sync::atomic::{AtomicUsize, Ordering};

#[cfg(all(test, feature = "loom"))]
mod loom_models {
    use loom::sync::Arc;
    use loom::sync::atomic::{AtomicUsize, Ordering::*};
    use loom::thread;

    fn message_passing(store: loom::sync::atomic::Ordering, load: loom::sync::atomic::Ordering) {
        loom::model(move || {
            let data = Arc::new(AtomicUsize::new(0));
            let flag = Arc::new(AtomicUsize::new(0));
            let (d, f) = (data.clone(), flag.clone());
            let t = thread::spawn(move || {
                d.store(42, Relaxed);
                f.store(1, store);
            });
            if flag.load(load) == 1 {
                assert_eq!(data.load(Relaxed), 42, "saw flag without data");
            }
            t.join().unwrap();
        });
    }

    #[test]
    fn loom_mp_relaxed_publish() { message_passing(Relaxed, Relaxed); }

    #[test]
    fn loom_mp_release_acquire() { message_passing(Release, Acquire); }

    #[test]
    fn loom_sb_seqcst_litmus() {
        loom::model(|| {
            let x = Arc::new(AtomicUsize::new(0));
            let y = Arc::new(AtomicUsize::new(0));
            let (x2, y2) = (x.clone(), y.clone());
            let t = thread::spawn(move || {
                x2.store(1, SeqCst);
                y2.load(SeqCst)
            });
            y.store(1, SeqCst);
            let r2 = x.load(SeqCst);
            let r1 = t.join().unwrap();
            assert!(!(r1 == 0 && r2 == 0), "store buffering observed under SeqCst");
        });
    }

    #[test]
    fn loom_counter_load_store_loom_atomic() {
        loom::model(|| {
            let c = Arc::new(AtomicUsize::new(0));
            let c2 = c.clone();
            let t = thread::spawn(move || { let v = c2.load(SeqCst); c2.store(v + 1, SeqCst); });
            let v = c.load(SeqCst); c.store(v + 1, SeqCst);
            t.join().unwrap();
            assert_eq!(c.load(SeqCst), 2, "lost update");
        });
    }

    #[test]
    fn loom_counter_load_store_std_atomic() {
        loom::model(|| {
            let c = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
            let c2 = c.clone();
            let t = thread::spawn(move || {
                let v = c2.load(std::sync::atomic::Ordering::SeqCst);
                c2.store(v + 1, std::sync::atomic::Ordering::SeqCst);
            });
            let v = c.load(std::sync::atomic::Ordering::SeqCst);
            c.store(v + 1, std::sync::atomic::Ordering::SeqCst);
            t.join().unwrap();
            assert_eq!(c.load(std::sync::atomic::Ordering::SeqCst), 2, "lost update");
        });
    }

    #[test]
    fn loom_atomic_outside_model() {
        let a = AtomicUsize::new(0);
        a.store(1, SeqCst);
    }
}

#[cfg(test)]
mod cfg_mismatch {
    #[cfg(loom)]
    #[test]
    fn gated_on_bare_cfg_loom() {
        loom::model(|| {});
    }
}
