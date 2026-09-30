---
name: answer-review
description: Answer a round of review findings as the author — read every finding and every earlier round before replying, check each against the code before acting, give each exactly one disposition (fixed with the commit, disputed with evidence, or deferred with a reason and a reopen condition), reply where the finding was made, list changes nobody asked for, and ask for a review of the new head because fix commits have not been reviewed. Use when a human reviewer, `adversarial-review`, Copilot or another agent has left findings on a PR or branch; when asked to "address the review", "reply to the comments" or "resolve the feedback"; and when a finding you believe is wrong needs an answer instead of silence.
---

# Answer a review

A review round ends when every finding has an answer the reviewer can check.
When the author could not write back, findings the author disagreed with were
either accepted without a word or dropped, and the next round raised them
again. Every step below closes one of those gaps.

Copilot's loop, with its thread pagination and re-request traps, is in
`drive-copilot-review`; use that for the mechanics and this for the answers.

## 1. Collect every finding before answering any

- Every thread on the PR, all pages. `gh pr view --comments` omits inline
  review threads; use the GraphQL `reviewThreads` connection with pagination
  (`drive-copilot-review`'s helper lists them).
- Every earlier round, including resolved threads and review summaries, so
  that you do not re-answer a settled point or contradict an earlier reply.
- Any finding given in chat or in a file, copied into your list with its
  location.

Number them. The reply covers the whole list.

## 2. Check each finding against the code before acting

- Reread the code the finding cites, at the head you will push, not the line
  as the reviewer quoted it.
- **Reproduce a blocking finding before fixing it** (`adversarial-review`
  step 5). Compile the misuse, run the input, write the failing test with
  `verify-by-breaking`.
- **A reader's confusion is evidence the claim may be wrong.** When a reviewer
  says a passage does not make sense, go to the source before rewording. A PR
  body rewrite once kept a "before" state that had never existed, in
  well-formed sentences.
- **A complaint about structure may be missing material.** A reviewer said
  the questions at the top of a PR body were unreadable. The first fix moved
  and reformatted them and was rejected; each question lacked the context that
  made it a question, and no layout supplies that.
- Before asking the reviewer a question back, check whether the code or the
  document already answers it. A PR body once asked a reviewer whether an
  exception was justified when the file being changed granted it in two
  places.

## 3. Give each finding exactly one disposition

- **fixed** — the commit SHA and one line saying what changed. Push before
  replying, so the SHA resolves.
- **disputed** — the evidence that the finding is wrong or does not apply: a
  test, a quoted line, command output, a spec. Restating the original code is
  not evidence, and a dispute without evidence is a refusal.
- **deferred** — why, where it is tracked (an issue link), and the condition
  that reopens it.

No finding goes without one. A skipped finding comes back next round, and the
reviewer cannot tell whether you disagreed or missed it. Design findings go to
the owner before you implement them; a reviewer can show a capability was
lost, but only the owner decides whether to restore it.

## 4. Reply where the finding was made

Answer in the thread, not only in a summary. Follow the repository's
convention on who resolves a human reviewer's thread; if you resolve, reply
first, because a resolve without a reply loses the reason.

Then post one summary with:

- the disposition list, one line per finding, in the reviewer's order;
- answers to the reviewer's open questions;
- changes in this round that no finding asked for, so the reviewer reviews
  them too;
- the gate results for the new head (`verify-change`).

Write the replies with `write-technical-prose`, and check the destination
with `publishing-findings`; a reply on a public repository is public.

## 5. Ask for review of the new head

Fix commits are new code that nobody has reviewed. Request a review of the
head you pushed, once per batch of fixes. The round closes when the reviewer's
review of the current head adds no findings and no open questions. The
reviewer decides that; if you believe the thread is done, say so and leave it
open.

## When you are the reviewer

An empty findings list means nothing actionable was found. It is not evidence
the change is correct; say what you checked and what you could not. Do not
produce findings because the last round was empty.

## Never

- **Never reply before reading every finding and every earlier round.**
- **Never mark a finding fixed without a pushed commit** that fixes it.
- **Never dispute by restating the code**, or apply a finding you have not
  reproduced when it claims a failure.
- **Never leave a finding without a disposition.**
- **Never resolve a thread without a reply**, or declare the review converged
  on the reviewer's behalf.
