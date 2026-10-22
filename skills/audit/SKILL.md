---
name: audit
description: Audit a subsystem that already exists — not a diff — for correctness, concurrency, failure handling, resource bounds, or how far its docs match its code — by writing down the invariants it must hold first, mapping its entry points and state, fanning out fresh reviewer agents one per concern, reproducing every finding before accepting it, reporting the confirmed list for the owner to rank, then fixing one finding at a time with a failing test, a review and its own commit or PR, and recording what the audit did not cover. Use when asked for a deep review, audit or health check of a module, subsystem or crate (an eviction policy, a tiering layer, a protocol state machine, an allocator); when a subsystem keeps producing bugs; before building on code nobody has reviewed as a whole; and when `review` does not fit because there is no change to review.
---

# Audit a subsystem

`review` reads a change against what it replaced. An audit has no diff: the
question is whether the code as it stands holds what it promises. Two
sessions audited a cache's eviction and tiering this way: parallel
reviewers, the main findings reproduced, then each fixed separately with a
test and a review.

## 1. Scope and invariants

Write down, before reading for bugs:

- the subsystem's boundary: the files, the entry points, the state it owns;
- the question: correctness, concurrency, failure handling, resource bounds,
  performance, or docs against code;
- **the invariants it must hold**, each as a checkable statement ("an item
  evicted from the hot tier is either in the cold tier or counted as
  dropped", "every reserved slot is released on every exit path"). Take them
  from the docs, the comments, the tests and the journal; mark the ones you
  inferred.

Show the user the scope and invariants, and agree on them, before step 3.
An audit against invariants nobody agreed to finds the wrong things.

## 2. Map it

Read the entry points and trace the state: who creates, mutates and frees
each piece, under which lock or on which thread, and what persists across a
restart. Note the tests that exist and what they reach. The map is the brief
for step 3.

## 3. Fan out, one reviewer per concern

Start fresh agents (`subagent_type` general-purpose, default model, not
forks), one per concern the question needs, in parallel: for example
invariants and correctness; concurrency and ordering; error paths, partial
failure and restart; resource bounds and growth; docs and comments against
the code. Each gets the scope, the invariants, the map, and `review`'s
output shape: findings with `file:line`, the failure scenario, confirmed or
plausible, and what it could not check. Reviewers are read-only.

## 4. Reproduce before accepting

Merge duplicates. For each finding that claims a failure, reproduce it: a
test that fails, an input that produces the wrong state, a trace of the code
path. Mark each **confirmed**, **plausible** (the path is real, the trigger
is unshown) or **refuted**, with the evidence. Do not carry a reviewer's
finding forward on its say-so.

## 5. Report, then let the owner rank

Report the confirmed and plausible findings, ranked by consequence, each with
its evidence and a proposed fix. List the refuted ones briefly, so they are
not raised again. Stop there: the owner decides which to fix and in what
order.

## 6. Fix one finding at a time

For each finding the owner chose: a test that fails on the current code
(`verify` step 8), the fix, the gates, a `review`, and its own commit or PR.
One fix per change, so a review sees one reason for each line.

## 7. Record it

Write the audit up where the repository keeps such records (`journal`): the
scope and invariants, each finding with its disposition, and **what the audit
did not cover** — concerns not examined, paths not reached, invariants left
unchecked. An audit that does not say what it skipped reads as a clean bill.

## Never

- **Never fix a finding that has not been reproduced** or marked plausible
  with the owner's go-ahead.
- **Never batch several fixes in one change.**
- **Never report a plausible finding as confirmed.**
- **Never fork for a reviewer**; a fork inherits the context it is meant to
  check.
- **Never end an audit without saying what it did not cover.**
