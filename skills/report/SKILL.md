---
name: report
description: Write an evidence-based technical report — a performance improvement (what changed, by how much, why) or an assessment of a system (how it behaves, where it stops scaling, what limits it) — for a named reader, the decision they must make, and a destination checked before writing. Keeps working notes apart from the deliverable, builds an evidence ledger that tags every claim measured, derived, given or unknown with its runs, leads with the result, the binding constraint and a recommendation whose confidence names what it rests on, states the population each number was measured on, reads every chart as rendered, corrects overturned claims in place, and has a fresh agent check every factual sentence against the ledger and its sources before it ships. Use when asked to write up, report on, or present results of a performance change, a benchmark campaign, a characterisation or an evaluation; when turning a journal entry or a set of runs into a document another person will read; and before sending a writeup of results to someone who will act on them.
---

# Write a report

A report is read by someone who did not do the work and will act on it. They
cannot check a claim the report does not back, and they will repeat a number
without its conditions. Every step here ties each sentence they might act on
to the evidence for it.

## 1. Name the reader, the decision and the destination

Write down who reads it, what they will decide with it (ship the change,
choose a configuration, fund the next step, buy the hardware), and where it
goes (a repository, a channel, a recipient). The decision picks what goes
first and what can be left out. If you cannot name the decision, ask before
writing.

Run `publish`'s destination check now, before the ledger. If the report will
be public or leave your organisation, decide what must not travel first and
build the ledger without it: detail stripped after the text is built on it
survives in what the text says.

Two kinds of report, which lead differently:

- **Improvement:** a change and its effect. Leads with the effect, its size
  and its confidence, and what it costs.
- **Assessment:** a system's behaviour. Leads with the answer to the reader's
  question and the constraint that binds it (the resource, limit or
  mechanism the result runs into).

A note of a few paragraphs needs only the result, with its population, and a
pointer to the ledger and method. The structure in step 4 is for a document
someone will cite.

## 2. Keep the notes apart from the deliverable

The working record (the journal entry, the run log, the dead ends) stays
where it is. The report is a separate document that cites it. Do not edit
the notes into a report; a reader of the report should not have to skip the
history of how it was found.

## 3. Build the evidence ledger first

Before writing prose, list every claim the report will make, one row each,
tagged by `publish`'s kinds (measured, derived, given, unknown), with the
runs it rests on:

| Claim | Kind | Source | Runs |
| --- | --- | --- | --- |
| p99 fell from 4.1 ms to 2.6 ms at 200k req/s | measured | run sets `a1b2` (before), `c3d4` (after) | 4 per side, interleaved |
| the gain comes from fewer syscalls per request | derived | syscalls per request fell in `a1b2` against `c3d4`; control: the same build with batching reverted, set `e5f6`, p99 back to 4.0 ms | 4 per side, 4 control |
| the target host has 64 cores | given | inventory, not checked | — |
| behaviour above 400k req/s | unknown | not run | 0 |

Every number in the report appears here, with its run IDs and how many runs
it rests on. A measured row's runs have passed `benchmark-validity`;
`interpret` decides whether a difference is real, and a claim that fails it
does not enter the report as a finding. A mechanism is derived only with the
control that separates it from coincidence, as in the second row.

## 4. Shape

`${CLAUDE_SKILL_DIR}/references/structure.md` has the sections and what goes
in each. In short: the result, the binding constraint and a recommendation
with its confidence first; then the setup as a table; the findings, each
with its mechanism and the evidence that the mechanism, not something else,
caused it; what was tested and rejected; the open questions, each with the
test that would settle it and who owns it; the method, enough to reproduce;
and the ledger as an appendix.

## 5. Write it narrowly

- **State the population.** Each number holds for the configuration, load,
  host and version it was measured on. Say which, beside the number or in
  the setup table it points to.
- **Show the kind.** A claim that is not measured says so where it is made
  ("given: the target host has 64 cores"), as `publish` requires.
- **Narrow causal language.** "Reduced" and "caused" need the mechanism and a
  control; without them, write "coincided with" or "was measured alongside".
- **Name the right statistic.** When the effect lands in the tail (a stall on
  one operation), a mean that did not move is not evidence of no cost; say
  which percentile shows it.
- **Read every chart as rendered.** Open the image and check the axes, units,
  legend and the claim the caption makes against what is drawn.
- **Plain prose** (`prose`), and compared numbers written so each comparison
  reads without conversion (`interpret`'s `compared-numbers.md`).

## 6. Correct in place

When a later run or a reader overturns a claim, change the report where the
claim is, as `publish` does: mark it **does not survive**, with the date,
what overturned it and what replaces it, and keep the original visible. A
number withdrawn because its measurement was invalid is re-measured, and in
a report the old value stays struck through with the reason; this differs
from `journal`, which removes a published number that was invalid.

When the overturned claim is in the result, write the new result above the
marked original, set the status line to `partly superseded` (or `WITHDRAWN`
when nothing stands), update the ledger row, and run the claim check (step 7)
again.

## 7. Check before it ships

1. Run `interpret` on every comparison the report makes, if it has not been,
   and `prose` over the text. Re-check the destination against `publish`,
   and that the reader can open every path, URL and run ID the report and
   its ledger cite; where they cannot, say so beside the citation.
2. **A claim check by a fresh agent** (not a fork). Give it the report, the
   ledger, and read access to every source the ledger cites (result paths,
   run IDs it can query). Ask it to return one line per factual sentence
   that has a problem: the sentence, the ledger row it matches or "none", and
   the problem (no row, a source that does not say it, a number that differs,
   a kind shown wrongly). The report is clean when that list is empty.
3. Fix every line, then run the check again with a new fresh agent, until a
   check comes back empty. If the same sentence fails after three rounds,
   remove the claim or mark it unknown in the ledger, and tell the owner.

## Never

- **Never put a number in the report that is not in the ledger.**
- **Never present a derived or given claim as measured.**
- **Never quote a result without the population it was measured on.**
- **Never delete a claim that did not survive**; mark it in place.
- **Never send the report before a claim check comes back empty.**
