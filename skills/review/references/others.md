# Reviewing someone else's pull request

The review is for the user, about a change a person or another team made.
Everything reaches the author through the user: nothing is posted, approved,
or marked as changes requested without the user's go-ahead. In past sessions
the user disproved several findings relayed from a reviewer agent one at a
time; each finding is checked here before the user sees it.

## 1. Read the conversation first

```sh
gh pr view <n> --repo <owner/repo> --json title,body,author,baseRefName,headRefOid,reviews,comments
gh api --paginate repos/<owner/repo>/pulls/<n>/comments   # inline, all rounds
```

Read the description, the linked issue, every earlier review round and the
author's replies. A point the author already answered is not a finding
unless the answer is wrong, and then the finding says why.

## 2. Run the review

Steps 1 to 5 of the review skill, with these differences in the brief:

- The checkout is the PR's head, detached, in a scratch worktree.
  `pull/<n>/head` exists only on the base repository, so fetch from the
  remote for `<owner/repo>`, not from a fork (or from
  `https://github.com/<owner/repo>.git` when no remote points there):

  ```sh
  git fetch <base-remote> pull/<n>/head
  git worktree add --detach <scratch>/pr-<n> FETCH_HEAD
  git -C <scratch>/pr-<n> rev-parse HEAD     # must equal headRefOid from step 1
  ```

  The reviewer runs nothing that writes outside that worktree.
- The conventions to check against are the repository's written ones (its
  `CLAUDE.md`, `CONTRIBUTING`, style docs, lint configs). The user's own
  preferences apply to the user's repositories, not to another project's.
- Ask the reviewer to separate defects (a failure scenario), missing tests,
  breaks of a written convention, and questions.

## 3. Check every finding before the user sees it

For each finding: open the quoted `file:line` at the PR's head and confirm the
text is there; follow the code path or run the input; and mark it
**confirmed** (reproduced or traced), **plausible** (the path is real, the
trigger is not shown), or drop it. A finding about code the PR does not touch
is out of scope unless the PR makes it reachable. When a finding is one case
of a kind, grep the PR's files for the same kind and report every instance as
one finding. Check each factual statement in a finding, and in its suggested
change, as `evidence` step 4 does. Say which findings were dropped and why.

## 4. Draft, then hand to the user

Give the user the findings ranked by consequence, each as a draft comment:
the `file:line`, one issue, the evidence, and a concrete suggestion. Write
plainly and about the code, not the author. Mark which ones block the change
in your view and which are questions.

Post only what the user approves, in the form the user chooses (inline
comments, a review with comments, a review requesting changes, or nothing).

## Never

- **Never post, approve, or request changes** without the user's go-ahead.
- **Never relay a finding you have not checked** against the PR's head.
- **Never record the review on your own initiative.** The record lets this
  session merge, and whether someone else's PR merges is the user's decision.
  When the user asks this session to merge it, the PR moves to the first row
  of the review skill's table: the author's answers, or the user's waiver of
  each open finding, take the place of step 7, step 6's fixes are the
  author's to make (check them as in step 3 here), and the head as it then
  stands is reviewed and recorded by step 8.
- **Never push to the author's branch**, including a suggested fix.
