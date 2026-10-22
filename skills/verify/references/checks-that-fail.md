# Writing a check that can fail

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
