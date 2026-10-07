---
name: drive-pr-to-green
description: Watch an open pull request's CI and reviews until it is green, reviewed and mergeable, or blocked, and merge it when asked — one snapshot per poll covering GitHub check runs and rack-ci commit statuses, each failure classified before acting (billing, infrastructure, caused by the branch, flaky), fixes pushed only for failures the branch caused, at most one rerun per infrastructure failure per commit, flakes recorded instead of rerun until green, human review comments answered only with the user's approval, Copilot review rounds driven until a review of the current head adds no threads, a `review` of the exact head before any merge, and a heartbeat and deadline on the wait. Use when asked to babysit, watch, shepherd, land or merge a PR, to "get CI green", to iterate with or resolve Copilot's review, or to keep an eye on a PR's checks and comments; and after pushing to a PR whose checks you are responsible for.
---

# Drive a PR to green

The loop is: snapshot, classify, act, wait, repeat. The part that goes wrong
is classification. On this account a GitHub check that fails in two or three
seconds is billing, not code: `custom-skills` PRs #1–#3 each show one failed
`check` run of 2–3 s with zero steps and no runner. Rerunning it cannot pass,
and editing code to fix it changes nothing. `use-rack-ci` has the full table.

Copilot review rounds have their own mechanics (thread pagination, the
`[bot]` re-request, re-raised findings); they are in
`${CLAUDE_SKILL_DIR}/references/copilot.md`, which drives its GraphQL helper
as `H=${CLAUDE_SKILL_DIR}/references/copilot_review.py`.

## Inputs

- The PR number or URL (default: the PR for the current branch).
- Whether the user wants you to merge when it is ready. The default is no.

## 1. Snapshot

`${CLAUDE_SKILL_DIR}/references/pr_state.sh` prints one `PR` line, one `CHECK`
line per check run or commit status, and one `VERDICT` line:

```sh
bash ${CLAUDE_SKILL_DIR}/references/pr_state.sh <pr> [OWNER/REPO]
```

Also read the review state:

```sh
gh pr view <pr> --json reviews,comments,reviewDecision
gh api repos/OWNER/REPO/pulls/<pr>/comments --paginate   # inline comments
```

If the PR is merged or closed, report that and stop.

## 2. Classify every failing check before acting

| Shape | Class | Action |
| --- | --- | --- |
| GitHub check run, fails in seconds, `hint=suspect-billing`; `gh run view <id> --json jobs` shows no steps and no runner | billing | none; report it. The repository belongs on rack-ci |
| `rack-ci/<name>` `error`, or an Actions runner-provisioning, network, or registry timeout | infrastructure | one rerun for this commit (step 4) |
| compile, lint, format, or a test that fails the same way on rerun, in code the branch touches | caused by the branch | fix (step 3) |
| a test that fails on this commit and passes on rerun, or fails on `main` too | flaky or pre-existing | record it (step 4); do not edit the test to pass |
| no checks at all on a rack-ci repository | nothing triggered | a PR opened on an unmoved head triggers no build (`use-rack-ci` step 3); the next push builds it |

Read the failed job's log before choosing a class. For Actions, a failed job's
log is available before the whole run finishes:

```sh
gh api repos/OWNER/REPO/actions/jobs/<job-id>/logs
```

For rack-ci, the `url` on the `CHECK` line is the SystemsLab experiment; read
its log there. Check the base branch too: if the same check is red on `main`,
the failure predates the PR (`verify-change` step 1).

## 3. Fix failures the branch caused

Check the worktree is clean apart from your own changes; if it has unrelated
edits, stop and ask. Fix, run the repository's gates (`verify-change`),
commit, and push. A push starts a new round of checks, so return to step 1 on
the new head.

If a review comment and a CI failure both need a commit, make both changes
before pushing, so one round of checks covers both.

## 4. Reruns and flakes

- Rerun an infrastructure failure once for a given commit. On Actions:
  `gh run rerun <run-id> --failed`. rack-ci posts commit statuses, which have
  no rerun button, and `rack-ci build` runs on delta with the service stopped,
  which is the rack owner's step. Ask for it, or push a new commit if the user
  agrees. A second infrastructure failure on the same commit is a blocker to
  report.
- Do not rerun a test failure to get a pass. A pass on rerun says the test is
  intermittent, and a clean rerun proves little (`debug-intermittent-failure`
  step 1: at a 5% failure rate, a single rerun passes 95% of the time).
  Record it in the PR (test name, run links, commit), open or update an issue,
  and tell the user. Whether to merge over a known flake is their decision.
- Never rerun a check on an old commit when you are about to push a new one.

## 5. Review comments

- A comment from a person: if it asks for a change you agree with, make it
  (step 3) and reply with the commit. If it needs a written answer, a
  disagreement, or a product decision, draft the reply and show it to the
  user; post only what they approve.
- A bot's comment: triage as `${CLAUDE_SKILL_DIR}/references/copilot.md`
  step 2 does. On a PR Copilot reviews, run its rounds from that file until a
  review of the current head adds no threads.
- Resolve a thread only after replying to it.

## 6. Wait with a heartbeat and a deadline

Poll step 1 every minute or two while checks are pending. Follow
`watch-long-job`: print one line per poll (time, head, `VERDICT` line), and
stop with `watcher-timeout` after about twice the checks' usual duration. A
watcher that has printed nothing is broken until shown otherwise.

## 7. Stop

Stop and report when one of these holds:

- **ready**: `VERDICT green`, `mergeable=MERGEABLE`, no unanswered review
  comment, and `reviewDecision` not `CHANGES_REQUESTED` or `REVIEW_REQUIRED`.
  Merge only if the user asked, and only after step 8.
- **merged or closed** by someone else.
- **blocked**: billing, a repeated infrastructure failure, a flake awaiting
  the user's decision, a comment awaiting an approved reply, a merge conflict
  you were not asked to resolve, or a permission error.

The report: head commit, the final `VERDICT` line, what was fixed with
commits, what was rerun and why, flakes recorded with links, and anything
waiting on the user.

## 8. Review the head that will merge, then merge

Before `gh pr merge`, run `review` on the PR's current head and answer its
findings; record it as that skill says. The plugin's merge gate refuses
`gh pr merge` of a head with no record, and a commit pushed after the review
is a new head. Then confirm the head did not move and merge:

```sh
gh pr view <pr> --json headRefOid -q .headRefOid   # the head that was reviewed
gh pr merge <pr> --repo <owner/repo> --squash       # or the repo's convention
gh pr view <pr> --json state,mergedAt,baseRefName
```

For a stack, merge bottom-up. After a squash merge, the next PR's branch
still carries the parent's commits. Move only its own commits onto the new
base: cherry-pick the PR's commits (`gh pr view <pr> --json commits`), or
`git rebase --onto origin/main <base> <branch>` where `<base>` is the commit
the branch was built on. If the parent branch was rebased after this one was
cut, its current tip is not that commit, and the rebase replays the parent's
old commits into a conflict. Check `git diff` against the PR's original
change, push, retarget, and review the new head before merging it.

## Never

- **Never rerun a check that failed in seconds with no steps.** It is billing.
- **Never read a `rack-ci/*` `error` as a code failure.**
- **Never edit a test, CI config, or dependency pin to get a failure unrelated
  to the branch to pass.**
- **Never rerun a test failure until it passes** and report the PR green
  without recording the flake.
- **Never post a reply to a person's review comment** without the user's
  approval of the text.
- **Never merge unless the user asked**, or merge a head that was not the
  one reviewed.
