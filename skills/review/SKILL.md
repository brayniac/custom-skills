---
name: review
description: Review a change adversarially with a fresh-context agent, then answer the findings. The reviewer tries to break the change — concrete failure scenarios, every factual claim in code comments, docs, commit messages and PR bodies checked against the code or the system, staleness and conflicts against the base branch — plus, when a public interface changed, what a caller can no longer do, and when docs changed, whether they state current behaviour. Findings come back as file:line with a failure scenario, marked confirmed or plausible; blocking ones are reproduced before anything is applied; every finding gets one disposition. Records the reviewed head so the merge gate lets it through. Use before opening a PR (`open-pr` runs it), before merging (`drive-pr-to-green` runs it; a hook refuses `gh pr merge` of an unreviewed head), when asked to review, adversarially review or sanity-check a change or a set of open PRs, and when answering findings from a person, Copilot or another agent.
---

# Review

Green gates show that a change is valid. They do not show that it works for
the people and systems that use it, or that what it says about itself is
true. A fresh reviewer told to break the change finds what the author, who
argued for it all session, cannot: a removed capability no caller in the tree
exercised, a doc claim the code contradicts, a PR that would undo one merged
the day before, a rebase that replayed someone else's commits.

Answering findings someone else made (a person, Copilot, another agent): go to
step 7. A change whose gates are still red is not ready for review; fix those
first (`verify-change`).

## 1. Dispatch a fresh agent, not a fork

A fork inherits the context that produced the change and argues for it. Start
a new agent (`subagent_type` general-purpose) and give it everything in the
brief. For several PRs, one agent per PR, in parallel. The reviewer is
read-only: no push, comment, approve, merge, submitted job or host change; a
worktree under the scratch directory if it needs a checkout.

## 2. Write the brief

In this order:

1. **What the change does**, before and after stated plainly, and what has
   happened since it was written (merged neighbours, rebases), so the reviewer
   does not reconstruct intent or history from the diff.
2. **The mandates that apply** (steps 3 to 5), kept as separate sections.
   Combined into one instruction they produce a review that does none of them.
3. **Concerns as questions** ("does the cancel race with placement?"), not a
   checklist; a checklist invites agreement.
4. **Where to look**: the PR number or diff command, the files, the base.
5. **Conventions to check against**, by path: the repo's CLAUDE.md and style
   docs, `rust-conventions`, `write-technical-prose`, `~/.claude/CLAUDE.md`.
6. **The output shape**: findings ranked most severe first, each with
   `file:line`, the offending text quoted, the concrete failure scenario, a
   concrete replacement (findings you have to interpret get half-applied),
   and **confirmed** (ran it, read the code path) or **plausible**.
   Unsubstantiated findings are dropped, not listed. Then the
   commands run and what they returned, what could not be checked, and a
   one-line verdict (merge, fix first, rebase, close as superseded).
7. **Permission to say a section is fine**, or the reviewer pads.

## 3. Mandate: what breaks (always)

- The failure scenario for each change: what input, state, timing or host
  makes it do the wrong thing. Partial failure, retries, restarts, a cancel
  mid-step, a host that is busy, a second run.
- **Every factual claim** in comments, docs, the commit message and the PR
  body, checked against the code or the live system: numbers against the
  fixture they cite, "X has no Y" by a grep, "Z is gone from upstream" by
  looking. A false claim in a PR body ends up quoted as fact.
- **The branch against the base as it is now**: does it merge, does it undo
  or duplicate something merged since it was opened, does its base still
  exist. A stacked branch rebased onto a squash-merged parent carries the
  parent's commits again.
- Tests: would they fail on the regression the change prevents, and do they
  reach it through the real entry point.

## 4. Mandate: what a caller can no longer do (public interface changed)

- What could a caller do before that they cannot now? Hold two at once, call
  concurrently, use it across an `.await`, recover from an error, construct it
  without a builder. A removed capability produces no compiler error. An API
  change once passed every gate while removing the ability to hold two pooled
  connections at once, because every in-tree caller was sequential.
- Trace **every consumer** of each changed interface, here and in known
  dependents, and say what each does with it.
- The compiler error on misuse; a broken crate convention (units, naming,
  fallibility, borrow shape); anything now unreachable or exported but
  unusable.

## 5. Mandate: docs state current behaviour (docs or comments changed)

Ask for every instance of:

- metaphor, personification, idiom, imagery;
- rhetorical questions, asides, argument aimed at a reader, emphasis
  mid-sentence;
- long sentences where plain declarative ones would do;
- history instead of behaviour: what it used to be, why the old shape was
  wrong. The most common finding of this mandate is a doc comment written as
  the justification of the change;
- references a reader at HEAD cannot resolve (a plan section, a review thread,
  "the new approach");
- wording against `write-technical-prose` (the reader, modality, one name per
  thing);
- a claim of absence, equivalence or who-does-what not checked by a grep
  (`open-pr`'s comment sweep,
  `${CLAUDE_SKILL_DIR}/../open-pr/references/sweep-comments.md` step 5).

A comment can be well worded and false, so each claim is checked against the
code. Reference documentation describes the result; the argument goes in the
CHANGELOG, the PR or the journal. Name conventions to keep (issue-number
references, for example), and exclude registers meant to differ: a journal
entry is not reference documentation.

## 6. Check the findings

- **Reproduce a blocking finding before acting on it**: compile the misuse,
  run the input, read the code path. Do not apply what you have not
  reproduced, and say when you disagree.
- **Design findings go to the owner** before implementation; a reviewer can
  show a capability was lost, only the owner decides whether to restore it.
- After applying a prose replacement, **check the old text is gone**
  (`rewrite-mechanically` step 5): a correction appended to a stale paragraph
  leaves documentation that says both things.
- **Re-run the full gate list** afterwards (`verify-change`); doc comments are
  compiled by doctests and checked by the intra-doc link lint.

## 7. Answer every finding

One disposition each: **fixed** (the commit), **disputed** (the evidence),
or **deferred** (why, where tracked, what reopens it). Reply where the finding
was made and list changes nobody asked for. The full procedure, including
answering a person's or Copilot's review, is
`${CLAUDE_SKILL_DIR}/references/answering.md`. Report the findings to the user
with the dispositions; an empty list means nothing actionable was found, not
that the change is correct.

Fix commits have not been reviewed. Review the new head again unless every
fix is mechanical (a typo, a wrapped line, a renamed reference), and say which
you decided and why.

## 8. Record the review

When every finding has a disposition and none that blocks the merge is open,
record the head, so the merge gate (a PreToolUse hook) lets a merge pinned to
it through. That is the head the last review read, or, when only mechanical
fixes (step 7) followed that review, the head with those fixes; then the
summary names the reviewed SHA and the fixes.

```sh
bash ${CLAUDE_SKILL_DIR}/references/record-review.sh <owner/repo> <head-sha> merge "<summary>"
```

The merge must then pin that head: `gh pr merge <n> --repo <owner/repo>
--match-head-commit <head-sha>`, so GitHub refuses it if the head moved. A
review whose verdict is "fix first" is not recorded. For a change with nothing
to review (a version bump, a lockfile refresh), and only when the user agrees,
record `--waive "<reason>"` in place of `merge "<summary>"`. The record does
not cover the base: if the base branch moved after the review, check the PR
still merges and re-review when the base change touches the same files.

## Never

- **Never fork for a review.**
- **Never merge because the gates are green**, or merge a head that was not
  the one reviewed.
- **Never apply a finding you have not reproduced** when it claims a failure,
  or implement a design finding without the owner's decision.
- **Never record a review you did not run**, a review with a blocking finding
  open, or a waiver without the user.
- **Never ask for "illustrative examples"** of problems; ask for every
  instance.
