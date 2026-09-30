---
name: verify-by-breaking
description: Show that a test, guard, or gate can fail — apply the specific fault it exists to catch, confirm it goes red, restore, and report what was observed — and design checks so that they can fail in the first place (a non-vacuity assertion, a known-wrong variant the fixture must separate, one bound across every output). Use immediately after writing a test, regression test, guard, or CI rung and before counting it as coverage; when a check has never been seen to fail; and when a mutation or fault injection unexpectedly passes.
---

# Verify by breaking

A test that passes shows nothing about what it would catch. A test that fails
against the specific fault it was written for shows that it works. Every
instance below was green and was not coverage; each was found by breaking
something on purpose or by reading a count, never by a check going red.

`verify-change` is about which gates ran and how their result was read. This
skill is about whether one check is capable of failing.

## Procedure

1. **Name the fault.** Write down the specific mutation the check exists to
   catch — the reverted fix, the deleted call, the swapped operands — before
   touching anything.

2. **Back up the file outside the repository.** Do not rely on `git checkout`
   to restore; a timeout can kill the command mid-mutation.

3. **Apply the mutation and confirm it applied.** Count the occurrences before
   and after, or diff. Several mutations have silently matched nothing, and
   one matched the wrong copy: two functions contained an identical line, and
   `perl -0pi -e 's/…/…/'` without `/g` changed only the first — in a function
   the fixture never exercised — so the check "passed". Anchor to the
   enclosing function, or count first and expect exactly one.

4. **Run the check and read its exit code directly**, not through a pipe
   (`node t.js | head; echo $?` reports `head`). Expect failure.

5. **Restore and confirm the restoration**: `git status` clean, the occurrence
   count back to its original value.

6. **Report the observation**: which test failed, with what message. Not "the
   test covers X".

For a regression test the mutation is the fix itself: write the test, run it
against the unfixed code (it must fail), apply the fix (it must pass).

## When the mutation does not fail

That is the finding; do not move on. One of three things is true, and all
three have been reported as coverage before someone checked:

- **The fixture never reaches the branch.** A fixture that reached a branch only
  through an event ordering the real API cannot produce (`ORDER BY ts DESC`)
  gave coverage of an impossible input.
- **The mutation landed somewhere else** (step 3).
- **The property is not tested.** Reverting `ORDER BY ts DESC, rowid DESC` to
  `ts DESC` left its test passing because SQLite's own tie-break happened to
  match. The fix was real; the test did not prove it. Say that rather than
  counting it verified.

Fix the check, not the report.

## Writing a check that can fail

A tolerance answers "does this agree?". Only a control answers "would I have
noticed if it didn't?". Across five device backward kernels, tolerance
comparisons never once located a fault; every real bug was found by a control or
a non-vacuity assertion.

- **Non-vacuity first.** Assert the work happened before comparing its result.
  A kernel that never ran writes zeros and scores `rel = 1.0`, which reads as
  bad arithmetic rather than as no execution.
- **Build the specific wrong version and require the fixture to separate it.**
  Swapped operands, the dropped coupling term, the transposed axis. Record the
  separation in the test (`1.99e0` wrong vs `3.8e-3` right) so a later reader
  can see the fixture still discriminates.
- **Apply one bound to every output and print the whole distribution.** With
  eight gradients, a bound calibrated on the two checked first passed a run
  where seven were correct and `dk` was wrong by five orders of magnitude.
- **Assert the negative as well.** `dv` must be insensitive to the softmax
  coupling while `dq` is sensitive; asserting both is what makes the pair a
  control.
- **Choose an oracle that the bug changes.** An end-to-end greedy-parity test
  passed before the fix it was written to pin: the bug was a state-phase error
  (SSM state one token short) and 16 greedy tokens did not flip on it. The pin
  had to compare the captured state's bytes against the live state.
- **A guard that searches source must strip comments first.** A CSS guard
  searched for `[hidden]{display:none}`, found it verbatim in its own
  explanatory comment, and passed with the rule deleted.
- **A check whose result something depends on belongs in the gate.**
  `--all-targets` compiles examples; nothing runs them. Two probes in
  `examples/` drifted without going red while a kernel design depended on
  their answers.
- **Assert silence where silence is the behaviour.** A restoration test passed
  with the restoring code deleted, because a door already past threshold fires
  on first observation anyway; only asserting no event immediately after a
  simulated restart pinned it.

## Never

- **Never report a check as coverage without having seen it fail** against the
  fault it names.
- **Never mutate without a backup outside the repository** and a confirmed
  restore.
- **Never accept "the mutation passed" as a pass.** It is a finding about the
  check.
