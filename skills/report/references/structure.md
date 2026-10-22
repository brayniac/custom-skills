# Report structure

The sections in order, with what each must contain. Leave a section out only
when it would be empty, and say so in one line rather than dropping it
silently (an assessment with no rejected hypotheses says "None tested").

## 1. Result

Three to six sentences a reader can act on without reading further:

- the answer to the reader's question, with its number and the population it
  holds for;
- the binding constraint: what the result runs into (a core, a link, a lock,
  a queue, the client);
- the recommendation, and the confidence in it as a statement about the
  evidence ("four interleaved runs per side, difference outside the A-vs-A
  null"), not an adjective.

## 2. Setup

A table: hosts and their hardware, software versions (commit SHAs or package
versions), configuration, load generator and its settings, run length,
number of runs per arm, and how runs were ordered. Anything a number
depends on goes here, so the findings can point at it.

## 3. Findings

One subsection per finding, in order of the reader's decision:

- the claim, with its number and the ledger row it comes from;
- the mechanism: why it happens, with the evidence for the mechanism itself
  (a counter, a profile, a control that removes it), not only the outcome;
- the chart or table that shows it, with a caption that states what the
  reader should see in it.

## 4. Tested and rejected

Each hypothesis or change that did not hold: what was tried, what it
predicted, what was measured, and why that rules it out. A knob that turned
out to do nothing belongs here, so nobody tunes it again.

## 5. Open questions

Each one: the question, the test that would settle it, the cost of running
that test, and who owns it. "Needs more investigation" is not an open
question.

## 6. Method

Enough to reproduce: where the specs, scripts and raw results are (a path
or URL the reader can open), the commands, and the analysis that turned runs
into numbers. Link the working notes here.

## Status line

At the top, under the title: the date, the status (`draft`, `final`,
`partly superseded`, `WITHDRAWN`), and for anything but `draft` or `final`,
a one-line pointer to what changed.
