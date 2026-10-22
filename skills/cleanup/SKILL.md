---
name: cleanup
description: Clean up after work has merged — remove the session's worktrees, merged local branches, scratch copies, build directories and background processes, and, with the user's go-ahead, merged remote branches — proving each branch done by comparing its tip with its merged PR's head (a squash merge never shows as merged in git), and keeping, with the reason, anything with no PR, an open PR, uncommitted or unpushed work, or a sign it belongs to another session. Use after a PR or a batch of PRs merges, at the end of a session that created worktrees or branches, when asked to tidy up, prune or clean branches or worktrees, and when `git worktree list` or `git branch` has grown past what the current work explains.
---

# Clean up

Cleanup deletes things, and the failure it guards against is deleting work: a
branch whose last commits never reached its PR, a worktree with uncommitted
edits, a branch another session is still using. Prove each item is done
before removing it, keep what cannot be proved, and say what was kept.

## 1. Inventory

For each repository the session touched:

```sh
git worktree list
git branch -vv
git stash list
git status --short
```

Also list what lives outside git: scratch copies and build directories
(`CARGO_TARGET_DIR`s) under the session's scratch directory, background
processes and watchers this session started (by the IDs or PIDs it recorded,
never by a name pattern), and directories it created on remote hosts.

## 2. Decide each branch from its PR

```sh
gh pr list --repo <owner/repo> --head <branch> --state all \
  --json number,state,headRefOid,mergedAt
git rev-parse <branch>
```

A squash or rebase merge leaves the branch's commits off `main`, so
`git branch --merged` omits the branch. `git branch -d` checks against the
branch's upstream when it has one, else `HEAD`: it refuses a squash-merged
branch with no upstream, and deletes a pushed branch whose PR never merged.
Neither answers whether the work landed. The test is the PR: a branch is done when its PR is `MERGED` and the branch tip equals the
PR's `headRefOid`. A tip that differs carries commits the PR never had; keep
the branch and say which commits (`git log <headRefOid>..<branch>`).

Keep, and report with the reason:

- a branch with no PR, or an open or closed-unmerged PR;
- a worktree with uncommitted changes, untracked files, or a stash;
- a branch or worktree that may be another session's: a worktree under
  another session's scratch directory, a branch checked out in a worktree
  this session did not create, or commits this session did not make. Check
  the reflog and the worktree path rather than guessing; if it is still
  unclear, it is not this session's to delete.

## 3. Remove what is done

- **Worktrees:** `git -C <main checkout> worktree remove <path>`. It refuses
  a dirty worktree; do not reach for `--force` or `rm -rf` to get past that,
  since the refusal is the check. Then `git worktree prune`.
- **Local branches:** `git branch -D <branch>`, only for branches that passed
  step 2; the PR comparison is what makes `-D` safe.
- **Remote branches:** deleting one is visible to everyone, so ask first,
  unless the user has already said to. Check whether the repository deletes
  merged branches itself (`gh api repos/<owner/repo> -q
  .delete_branch_on_merge`); if it does not, offer to turn that on instead of
  deleting by hand each time. Then `git push origin --delete <branch>`.
- **Scratch copies, build directories, remote scratch:** remove the ones this
  session created. Before removing a copy of a worktree, check it is not
  still attached: a worktree's `.git` is a file pointing at the main
  repository, and a copy that kept it commits onto the real branch.
- **Processes:** stop the ones this session started, by recorded PID or task
  ID.

## 4. Report

One line per item: removed, or kept and why. List anything left for the
user to decide (remote branches, a branch that may be another session's).

## Never

- **Never decide a branch from `git branch --merged` or `git branch -d`.**
  Neither sees a squash merge. Decide from the PR.
- **Never `rm -rf` a worktree or pass `--force` to `git worktree remove`.**
- **Never delete a remote branch without the user's go-ahead.**
- **Never kill processes by name** (`pkill cargo`, `pkill -f watch`); other
  sessions run the same commands.
- **Never create a worktree inside the main checkout** by a relative path;
  put it under the scratch directory, so it is not mistaken for project files
  and does not get picked up by the repository's own tools.
