---
name: adversarial-review
description: Get a review from a fresh-context agent that asks what a caller can no longer do and whether the documentation states current behaviour plainly — two separate mandates, every consumer of a changed interface traced, findings required as file:line with the quoted text and a concrete replacement, and blocking findings reproduced before they are applied. Use before merging a change to a public API (signatures, ownership, lifetimes, removed entry points), after writing or rewriting doc comments in volume, when every gate is green and nobody has asked what a caller can now express, and when applying a previous review's findings.
---

# Adversarial review

Green gates show that a change is valid. They do not show that it is usable,
and they say nothing about whether its documentation is true. An API change
once passed every gate while removing the ability to hold two pooled
connections at once — the borrow held the whole pool — because every in-tree
caller was sequential. A fresh reviewer reasoning about call sites found it in
one pass.

Not for internal refactors with no public change, or for a change whose gates
are still red; fix those first (`verify-change`).

## 1. Dispatch a fresh agent, not a fork

A fork inherits the context that produced the change and argues for it. Start
a new agent and give it everything it needs in the brief.

## 2. Write the brief

In this order:

1. **What the change does**, with the before and after shape stated plainly,
   so the reviewer does not reconstruct intent from the diff.
2. **Two mandates, kept separate** (steps 3 and 4). Combined into one
   instruction they produce a review that does neither.
3. **Concerns as questions** ("is X right here, or would Y be clearer?"), not
   a checklist to tick; a checklist invites agreement.
4. **Where to look**: the diff command and the files.
5. **Conventions to check against**, by path: the repo's API or style docs,
   `rust-conventions`, and the writing rules in `~/.claude/CLAUDE.md`.
6. **The output shape**: each finding as `file:line`, the offending text quoted
   exactly, and a concrete replacement. Findings you have to interpret get
   half-applied. Then the commands the reviewer ran and what they returned,
   and what it could not check. An empty findings list means nothing
   actionable was found; it is not evidence the change is correct.
7. **Permission to say a section is fine**, or the reviewer pads.

## 3. Mandate 1 — what a caller can express

- What could a caller do before that they cannot do now? Hold two at once, call
  concurrently, use it across an `.await`, recover from an error, construct it
  without a builder. Ask this explicitly; a removed capability produces no
  compiler error.
- Trace **every consumer** of each changed interface, in this repository and in
  known dependents, and say what each one does with it.
- What does the compiler error look like when it is misused?
- Does it break a convention the crate already has (units, naming,
  fallibility, borrow shape)?
- Is anything now unreachable, orphaned, or exported but unusable?
- Do the tests exercise the change through the real entry point, and would they
  fail on the regression it prevents?

## 4. Mandate 2 — documentation states current behaviour

Ask for every instance of:

- metaphor, personification, idiom, imagery;
- rhetorical questions, asides, argument aimed at a reader;
- bold or italics for emphasis mid-sentence;
- sentences about history — what the API used to be, why the old shape was
  wrong, what was removed — instead of what it does now;
- references a reader at HEAD cannot resolve (a plan section, a review
  comment, "the new approach");
- long sentences where plain declarative ones would do.

Reference documentation describes the result. The argument for the change goes
in the CHANGELOG, the PR, or the journal. The most common finding of this review
is doc comments written as justification of the change.

The wording rules the reviewer checks against are in `write-technical-prose`
(reader, modality, one name per thing) and `sweep-comments` step 4 (what a
reader at HEAD cannot resolve). Ask the reviewer to check each claim of
absence or equivalence in a comment against the code; a comment can be well
worded and false.

Name conventions to keep (issue-number references, for example), and exclude
registers that are meant to differ: a journal entry or design note is not
reference documentation.

## 5. Apply the findings

Answer every finding with `answer-review`: one disposition each, fixed with
the commit, disputed with evidence, or deferred with a reopen condition.

- **Reproduce a blocking finding before acting on it** — compile the misuse
  the reviewer describes. Do not apply what you have not reproduced.
- **Say when you disagree** with a finding, and why, instead of applying it
  silently or dropping it.
- Apply prose replacements, then **check the old text is gone**
  (`rewrite-mechanically` step 5). Appending a correction to a stale paragraph
  leaves documentation that says both things.
- **Design findings go back to the owner** before implementation. A reviewer
  can show a capability was lost; only the owner decides whether to restore it.
- Re-run the full gate list afterwards (`verify-change`). Doc comments are
  compiled by doctests and checked by the intra-doc link lint.

## Never

- **Never fork for this review.**
- **Never merge because the gates are green** when a public signature changed
  and no one has asked what a caller can no longer do.
- **Never implement a design finding without the owner's decision.**
- **Never ask for "illustrative examples"** of problems; ask for every
  instance, with replacements.
