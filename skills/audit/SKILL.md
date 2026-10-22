---
name: audit
description: Audit a subsystem that already exists — not a diff — for correctness, concurrency, failure handling, resource bounds, or how far its docs match its code — by writing down the invariants it must hold first, mapping its entry points and state, fanning out fresh reviewer agents one per concern, reproducing every finding before accepting it, separating bugs from design limitations, recording the result, then fixing one root cause at a time with a failing test, a review and its own commit or PR, and saying what the audit did not cover. Use when asked for a deep review, audit or health check of a module, subsystem or crate (an eviction policy, a tiering layer, a protocol state machine, an allocator); when a subsystem keeps producing bugs; before building on code nobody has reviewed as a whole; and when `review` does not fit because there is no change to review. For a change's comments, use `pr`'s sweep instead.
---

# Audit a subsystem

`review` reads a change against what it replaced. An audit has no diff: the
question is whether the code as it stands holds what it promises. Two past
audits of a cache's eviction and tiering ran parallel reviewers, reproduced
the main findings, and fixed each separately with a test and a review.

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

Show the user the scope and invariants and agree on them before step 3:
reviewers sent after invariants the owner has not agreed check properties
the owner does not need. If the user cannot be asked, continue with the
invariants as written, the inferred ones marked, and say in the report and
the record that they were not agreed.

## 2. Map it

Read the entry points and trace the state: who creates, mutates and frees
each piece, under which lock or on which thread, and what persists across a
restart. Note the tests that exist and what they reach. The map goes into
every reviewer's brief.

## 3. Fan out, one reviewer per concern

Start fresh agents (`subagent_type` general-purpose, default model, not
forks), one per concern the question needs, in parallel: for example
invariants and correctness; concurrency and ordering; error paths, partial
failure and restart; resource bounds and growth; docs and comments against
the code. Write each brief per `review` step 2: the scope, invariants and map
as item 1, the reviewer's concern as its mandate, and items 3 to 7 as
`review` gives them. The verdict line is the reviewer's confidence that each
invariant in its concern holds, not merge or fix first. Reviewers are
read-only.

If one concern spans more code than one reviewer can read in full, split it
by the components in the map, and give each reviewer the invariants that
cross its boundary. Note every part no reviewer read.

## 4. Reproduce before accepting

Merge duplicates. For each finding that claims a failure, reproduce it: a
test that fails, an input that produces the wrong state, a trace of the code
path. Mark each **confirmed**, **plausible** (the path is real, the trigger
is unshown) or **refuted**, with the evidence. Do not carry a reviewer's
finding forward on its say-so; check its other claims as `evidence` step 4
does.

Separate **design limitations**: the code does what it was built to do, and
that breaks an invariant or a property the owner wants (an O(n) eviction scan
by design, an invariant the on-disk format cannot hold). These are questions
for the owner, not fixes.

## 5. Record, report, and let the owner rank

Write the record now, where the repository keeps such records (`journal`):
the scope and invariants (agreed or not), each finding with its evidence and
status, the design limitations, and **what the audit did not cover**:
concerns not examined, parts no reviewer read, invariants left unchecked. A
reader takes a record that omits what was skipped to mean everything was
checked.

Then report the findings to the user, ranked by consequence, each with a
proposed fix, the design limitations as questions, and the refuted findings
briefly so they are not raised again. Stop there: the owner decides which to
fix and in what order.

## 6. Fix one root cause at a time

For each finding the owner chose: a test that fails on the current code
(`verify` step 8), the fix, the gates, a `review`, and its own commit or PR.
One root cause per change; a fix that closes two findings with one cause is
one change. For a concurrency finding, build the failing test with `safety`;
for an intermittent one, with `debug`. If no test reproduces it, fix it only
with the owner's go-ahead, and say in the change that no test reproduces it.

Update the record as findings close. Each ends with one disposition: fixed
(the commit), refuted (the evidence), design limitation, or not fixed (where
it is tracked in the backlog, and what reopens it).

## Never

- **Never fix a plausible finding without the owner's go-ahead**, or a
  confirmed one without a test that fails first, except as step 6 allows.
- **Never put two root causes in one change.**
- **Never report a plausible finding as confirmed.**
- **Never fork for a reviewer**; a fork inherits the context it is meant to
  check.
- **Never end an audit without a record of what it did not cover.**
