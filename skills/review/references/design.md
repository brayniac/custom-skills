# Reviewing a design

A design review reads a proposal before the code exists: a design doc, an
RFC, a plan, an issue that proposes a change, or a journal entry that opens
an effort. There is no diff to break, so the reviewer looks for what would
make the build fail or the result mean nothing, while changing course is
still cheap.

Dispatch a fresh agent as in steps 1 and 2 of the review skill, read-only,
with the proposal and the code it would change as item 1 of the brief, these
mandates, as separate sections, in place of steps 3 to 5, and the Output
section below in place of item 6.

## Mandate: the claims about today

Every statement about the current system, checked against the code or the
running system with a `file:line` or a command: "X has no Y", "the hot path
does Z", a cost, a count.

## Mandate: the problem and the criterion

- Is the problem stated without a solution in it? "We need a caching layer"
  and "X is slow, so we should add Y" name a solution. Ask what failure or
  cost a user sees, and judge the alternatives against that.
- Is the problem shown with evidence (a measurement, an incident, a user
  report), or assumed?
- Is there a success criterion that a measurement can meet or miss, and a
  stated outcome that would stop the work (a NO-GO)? "Faster" is not one;
  "p99 below 2 ms at 100k req/s on hv01" is.
- Is there an earlier attempt or a recorded NO-GO for the same idea
  (`journal`'s entries and its NO-GO ledger)? If so, what is new now?
- Which adjacent problems does the proposal set aside? They should be named
  as non-goals, so the scope does not grow during the build.

## Mandate: alternatives and the cheapest test

- Which alternatives were considered, including doing nothing and the
  smallest change that might be enough?
- What is the cheapest experiment that would decide between them, and should
  it run before the build?
- Name the two or three hard choices if the proposal does not. For each: the
  options, what it costs to reverse each one and what follows if it is wrong,
  and the factor that decided it. Mark a choice that is hard to reverse (a data
  format, a public interface, a storage layout) as before building, in the
  Output below.

## Mandate: what breaks

- Partial failure, restart, and a second run.
- Rollout and rollback: a migration, a format or protocol change, mixed
  versions running at once.
- A change across repositories: the order they land in, what each one does
  while another is still at the old version, an owner for each repository,
  and one person accountable for the whole.
- What a caller can no longer do (`review` step 4 applies to a proposed
  interface as much as to a changed one).
- Operational cost: new state, new dependencies, new things to monitor.

## Output

Questions, not a rewrite, ranked by how much the answer could change the
design. Each names its evidence (`file:line`, a measurement, or "not shown")
and is marked **before building** (the answer could change the design) or
**during building** (it can be settled as the work goes). Then what the
reviewer could not check.

Before handing the questions over, open each cited `file:line` and confirm
it; drop or mark what does not hold, as in step 3 of `others.md`, beside this
file. The owner decides what to change. Do not record the review with
`record-review.sh`: a design has no head to merge.
