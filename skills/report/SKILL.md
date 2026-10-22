---
name: report
description: Write an evidence-based technical report — a performance improvement (what changed, by how much, why) or an assessment of a system (how it behaves, where it stops scaling, what limits it) — for a named reader and the decision they must make. Keeps working notes apart from the deliverable, builds an evidence ledger that tags every claim measured, derived, given or unknown with its run IDs and run counts, leads with the result, the binding constraint and a recommendation with its confidence, states the population each number was measured on, reads every chart as rendered, records retractions in place, and has a fresh agent check every claim against the ledger before it ships. Use when asked to write up, report on, or present results of a performance change, a benchmark campaign, a characterisation or an evaluation; when turning a journal entry or a set of runs into something another person will read; and before sending numbers to someone who will act on them.
---

# Write a report

A report is read by someone who did not do the work and will act on it. They
cannot check a claim the report does not back, and they will repeat a number
without its conditions. Every step here exists so that each sentence they
might act on is tied to the evidence for it.

## 1. Name the reader and the decision

Write down who reads it and what they will decide with it: ship the change,
choose a configuration, fund the next step, buy the hardware. The decision
picks what goes first and what can be left out. If you cannot name the
decision, ask before writing.

Two kinds of report, which lead differently:

- **Improvement:** a change and its effect. Leads with the effect, its size
  and its confidence, and what it costs.
- **Assessment:** a system's behaviour. Leads with the answer to the reader's
  question and the constraint that binds it (the resource, limit or
  mechanism the result runs into).

## 2. Keep the notes apart from the deliverable

The working record (the journal entry, the run log, the dead ends) stays
where it is. The report is a separate document that cites it. Do not edit
the notes into a report; a reader of the report should not have to skip the
history of how it was found.

## 3. Build the evidence ledger first

Before writing prose, list every claim the report will make, one row each:

| Claim | Kind | Source | Runs |
| --- | --- | --- | --- |
| p99 fell from 4.1 ms to 2.6 ms at 200k req/s | measured | runs `a1b2`, `c3d4` | 4 per side, interleaved |
| the gain comes from fewer syscalls per request | derived | syscall counts in the same runs; mechanism below | 4 |
| the target host has 64 cores | given | inventory, not checked | — |
| behaviour above 400k req/s | unknown | not run | 0 |

Kinds: **measured** (observed in a run), **derived** (computed or reasoned
from measured data; say from what), **given** (stated by someone or a
document, not checked here), **unknown** (not established). Every number in
the report appears here with its run IDs and how many runs it rests on.
`interpret` decides whether a difference is real; a claim that fails it does
not enter the report as a finding.

## 4. Shape

`${CLAUDE_SKILL_DIR}/references/structure.md` has the sections and what goes
in each. In short: the result, the binding constraint and a recommendation
with its confidence first; then the setup as a table; the findings, each
with its mechanism and the evidence that the mechanism, not something else,
caused it; what was tested and rejected; the open questions, each with the
test that would settle it and who owns it; and the method, enough to
reproduce.

## 5. Write it narrowly

- **State the population.** Each number holds for the configuration, load,
  host and version it was measured on. Say which, beside the number or in
  the setup table it points to.
- **Narrow causal language.** "Reduced" and "caused" need the mechanism and a
  control; without them, write "coincided with" or "was measured alongside".
- **Read every chart as rendered.** Open the image and check the axes,
  units, legend and the claim the caption makes against what is drawn.
- **Plain prose** (`prose`), and compared numbers written so each comparison
  reads without conversion (`interpret`'s `compared-numbers.md`).

## 6. Correct in place

When a later run or a reader overturns a claim, change the report where the
claim is: mark the finding **does not survive** (or the whole report
**WITHDRAWN**) with the date, what overturned it, and what replaces it. Keep
the original text visible. A correction appended at the end leaves a report
that says both things.

## 7. Check before it ships

1. Run `interpret` on every comparison the report makes, if it has not been.
2. Run `prose` over the text, and `publish` for the destination: what must
   not travel, and whether the reader can see what it cites.
3. **A claim check by a fresh agent** (not a fork): give it the report and
   the ledger, and ask it to find every sentence that states a fact, match
   each to a ledger row, and report the ones with no row, a row whose source
   does not say it, or a number that differs. Fix every one before sending.

## Never

- **Never put a number in the report that is not in the ledger.**
- **Never present a derived or given claim as measured.**
- **Never quote a result without the population it was measured on.**
- **Never delete a claim that did not survive**; mark it in place.
- **Never send the report before the claim check comes back clean.**
