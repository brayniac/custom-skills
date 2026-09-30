---
name: debug-intermittent-failure
description: Find the mechanism of a failure that happens in some runs and not others, and show a fix works — size each sweep from the failure rate, check the suspect predates the failure, carry a positive control in every sweep, write the prediction and what would refute it into the spec before running, record per-event state instead of reasoning from the error string, and record what was ruled out with the condition for reopening it. Use when a test, job, or connection fails intermittently; before claiming a flaky failure is fixed; when a clean run is about to be read as evidence; and when two hypotheses both fit an error message.
---

# Debug an intermittent failure

A failure that appears in some runs is expensive in two ways: a clean run proves
little, and a mechanism read off an error message is usually wrong. The costly
case this skill is built from: a control predicted 0/100 failures and measured
10/100. The fix had not fixed the bug, it had moved it, and the claim had
already been merged.

This is about correctness failures. For a performance difference, use
`measure-performance` and `attribute-perturbation`.

## 1. Measure the rate and size the sweep from it

Run the unchanged code enough times to estimate the failure rate `p`. A sweep
of `n` runs sees no failure with probability `(1 − p)^n`:

| p | P(0 failures in 100 runs) | runs for 95% confidence of ≥1 failure |
| --- | --- | --- |
| 1% | 0.37 | 299 |
| 2% | 0.13 | 149 |
| 5% | 0.006 | 59 |
| 10% | < 0.001 | 29 |

A clean sweep smaller than the right-hand column is not evidence of a fix. Say
what `n` and `p` were when reporting one.

## 2. Check the timeline before blaming anything

For the suspect commit, deploy, or dependency bump, compare when it landed with
when the failure was first seen:

```sh
git log -1 --format='%H %cI' <suspect>
gh run list --branch main --status failure --limit 50 \
  --json createdAt,headSha,conclusion
```

A suspect commit was exonerated this way: it merged thirteen hours after the
failure it was supposed to have caused. One command removed a whole line of
investigation. If the failure predates the suspect, stop investigating the
suspect.

## 3. Write the prediction into the spec before running

In the experiment spec, the PR, or the journal, before submitting:

- what each outcome (fails in every arm, fails only in arm X, never fails)
  would mean, and what you would look at next for each;
- what result would refute the current hypothesis.

A sweep that failed in all four arms once had "fails in all four → look at
accept and slot allocation, not sends" written down in advance, which stopped
the result being reinterpreted as a backpressure problem. A prediction written
afterwards is a story fitted to the result.

## 4. Carry a positive control in every sweep

Every sweep includes an arm that must fail: the unfixed build, or the fixed
build with the fault injected. Read the treatment arm only after the control
has failed at about its known rate. **A clean arm without a failing control
cannot be told apart from an instrument that could not see the failure.**
After the 10/100 result above, every sweep carried a positive control, and that
is the only reason the later clean results meant anything.

If the control does not fail, the harness, the load, or the instrument changed.
Fix that before reading anything else.

## 5. Record per-event state instead of reading the error

Two hypotheses built from a panic message were both wrong. Recording, per
connection, which accept it was, how many operations succeeded, the raw `errno`,
and what the peer observed identified the mechanism in one run.

- Record at the boundaries of each component: what went in, what came out.
- One structured line per event, one file per connection, worker, or thread,
  so the files can be diffed. `references/divergence-diff.md` (fetch with
  `skill_resource`) has the method for finding the first event where a failing
  unit departs from a good one.
- **Break it once on purpose before trusting a clean run from a new
  instrument.** Confirm the instrument reports the injected fault.
- Instrumentation can change timing enough to hide a race. If the rate drops
  when instrumented, say so and reduce the instrumentation.

## 6. Name the measurement that separates the hypotheses

Before collecting more data, write down which measurement would come out
differently under each candidate mechanism. An issue titled as data loss had
`sends_ok × 4096 == bytes_received` in 79 of 79 cases with no read errors:
nothing was lost or duplicated. The mechanism was an early half-close, and
naming that one comparison changed the whole search. A number can be correct
and still be the wrong statistic for the question.

## 7. Confirm by intervention, then by sweep

Change the one thing the mechanism names and show the failure rate moves as
predicted (`attribute-perturbation` step 7 covers intervention). Then run the
fix with its positive control, sized from step 1. If three fixes in a row have
failed and each exposed a different shared-state problem, stop fixing and
question the design with the user.

## 8. Record what was ruled out

In the journal or the issue:

- each refuted hypothesis, the evidence that refuted it, and the condition
  under which it should be reopened;
- each knob that was varied and did nothing, with the range tried;
- corrections to earlier claims, made in place where the claim was read
  (`publishing-findings`).

An unrecorded dead end is investigated again by the next person.

## Never

- **Never report a fix from a sweep with no positive control**, or from one
  smaller than step 1 says it needs.
- **Never pick a mechanism from the error text alone** when per-event
  instrumentation is possible.
- **Never write the prediction after the result.**
- **Never delete a refuted hypothesis from the record**; label it refuted.
