---
name: sync
description: Bring a branch up to date with its base — merge or rebase as the repository requires (its merge methods, a per-commit message check such as cog or commitlint, a shared branch), resolve each conflict by reading both sides, re-derive what must not be merged by hand (an -alpha.N bump, Cargo.lock, generated files, sequence numbers) even when git merged it cleanly, look for the conflicts git resolves silently and wrongly (a CHANGELOG entry under a heading released since, a call to something renamed on the base), check the diff against the base is only the branch's own change, run the gates, and push without force unless the user agrees. Use when a branch or PR is behind or conflicts with its base, when asked to sync, update, rebase or merge main into a branch, after a parent PR in a stack merged, and before re-requesting review on a branch whose base moved.
---

# Sync a branch

Most failures here came from merges git completed without a conflict marker:
a CHANGELOG entry under a version released since the branch was cut, two
migrations with one number, a version bump the base had already made, a
generated file left stale.

## 1. Read the situation

```sh
gh pr view --json number,headRefOid,baseRefName,mergeStateStatus 2>/dev/null
git fetch <remote>
git log --oneline <remote>/<base>..HEAD      # the branch's own commits
git log --oneline HEAD..<remote>/<base>      # what it is missing
```

`<remote>` points at the project (`upstream` in a fork checkout); `<base>` is
the PR's `baseRefName`, which is not always `main`. If the PR is in a merge
queue (`gh api graphql -f query='{repository(owner:"<o>",name:"<r>"){
pullRequest(number:<n>){isInMergeQueue}}}'`), do not sync it unless it
conflicts: the queue tests it against the base, and a push removes it from
the queue.

Then find how the repository merges:

- **Merge methods:** `gh api repos/<owner/repo> --jq
  '{allow_merge_commit,allow_squash_merge,allow_rebase_merge}'`. A merge
  commit on the branch matters only when the PR is merged by rebase.
- **A per-commit check in CI:** `cog check`, commitlint, or a DCO check reads
  every commit on the branch and may reject a merge commit. Check its
  configuration: commitlint ignores merge commits by default, and cog does
  not unless `ignore_merge_commits` is set.
- **Branch rules,** which may come from a ruleset or classic protection:
  read both `repos/<owner/repo>/rules/branches/<base>` and
  `repos/<owner/repo>/branches/<base>/protection`.
- **Whether the branch is pushed, and whether anyone else commits to it.**

## 2. Merge or rebase

- Not pushed: rebase onto `<remote>/<base>`.
- Pushed, the PR will not be merged by rebase, and no CI check reads each
  commit: merge `<remote>/<base>` in. It needs no force-push.
- Pushed, and the repository merges by rebase or checks each commit: a rebase
  needs a force-push. Ask the user first; if others commit to the branch,
  tell them before pushing. Push with `--force-with-lease=<branch>:<sha you
  observed>`.
- Stacked on a parent that was squash-merged: the branch still carries the
  parent's commits, and git does not skip them because the squash commit has a
  different patch. `merge` covers the stacked case: the old parent tip is `git
  merge-base HEAD <parent head>`, with the parent head from `gh pr view <parent>
  --json headRefOid` (fetch it first with `git fetch <remote>
  pull/<parent>/head` if the parent branch is gone). Check `git log --oneline
  <old parent tip>..HEAD` lists only this branch's commits, then `git rebase
  --onto <remote>/<base> <old parent tip>`.

## 3. Resolve each conflict by reading both sides

For each conflicted file, read what the base changed and what the branch
changed, and keep both intents: `git log -p --merge -- <file>` (during a
rebase on older git, `git show REBASE_HEAD -- <file>` for the branch's side).
Do not resolve a file, or the whole merge, with `-X ours` or `-X theirs`.

A lockfile or generated file in conflict is re-derived, not merged: take the
base's copy, then regenerate. The base's side is `--theirs` when merging and
`--ours` when rebasing. In a rebase, regenerate at each stop so every
replayed commit builds.

## 4. Re-derive and check, even with no conflicts

After every sync, whether git reported conflicts or not:

- **A per-PR `-alpha.N` bump** (`pr` step 3): the branch's version must be
  the base's plus one (`git show <remote>/<base>:<manifest> | grep
  '^version'`). If the base made the same bump, the merge is clean and the
  branch has silently lost its own.
- **Lockfiles and generated files** (docs, schemas, bindings, a version
  label): rerun the command that produces them.
- **Numbered migrations or other sequences:** two files with one number never
  conflict. Renumber the branch's after the base's last.
- **CHANGELOG:** every entry the branch adds is under `Unreleased`, not under
  a version the base released since.
- **Renamed or removed on the base:** grep the branch's changes for each name
  the base renamed or removed.
- **Docs and comments** the branch wrote that describe code the base changed.

## 5. Check the result

```sh
git diff <remote>/<base>...HEAD --stat
```

It should list the branch's own files and the resolutions of step 3. A file
the branch never touched means replayed commits or a wrong resolution. Then
run the gates with `verify`.

## 6. Push and get the new head reviewed

Push to the branch's own remote (`origin`, the fork, in a fork checkout), with
no force unless step 2 agreed it. The head has moved, so a review recorded on
the old head does not cover it: run `review` on the new head before merging.
Whether the previous review can be carried over is `review` step 8's
decision. List each conflict and how it was resolved in the PR or the report.

## Never

- **Never force-push without the user's agreement**, and then only with
  `--force-with-lease=<branch>:<sha>`.
- **Never resolve with `-X ours` or `-X theirs`**, or by taking one side of a
  file you have not read.
- **Never merge a lockfile or generated file by hand.**
- **Never treat a merge with no conflicts as correct** before step 4 and the
  gates.
