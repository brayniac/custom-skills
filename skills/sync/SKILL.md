---
name: sync
description: Bring a branch up to date with its base — merge or rebase as the repository requires (linear history, a cog or commitlint check, a shared branch), resolve each conflict by reading both sides, re-derive what must not be merged by hand (an -alpha.N bump, Cargo.lock, generated files, sequence numbers), look for the conflicts git resolves silently and wrongly (a CHANGELOG entry under a heading released since, a call to something renamed on the base), check the diff against the base is only the branch's own change, run the gates, and push without force unless the user agrees. Use when a branch or PR is behind or conflicts with main, when asked to sync, update, rebase or merge main into a branch, after a parent PR in a stack merged, and before re-requesting review on a branch whose base moved.
---

# Sync a branch

A clean merge is not a correct one. The failures here came from conflicts git
resolved without a marker: a CHANGELOG entry that landed under a version
released since, two migrations with one number, a lockfile merged line by
line, a version bump computed from a base that had moved.

## 1. Read the situation

```sh
git fetch <remote>
git status -sb
git log --oneline <remote>/main..HEAD        # the branch's own commits
git log --oneline HEAD..<remote>/main        # what it is missing
gh pr view --json number,headRefOid,baseRefName,state 2>/dev/null
```

`<remote>` is the one that points at the project (`upstream` in a fork
checkout). Then find out how this repository wants it done:

- **Linear history:** a `required_linear_history` rule (`gh api
  repos/<owner/repo>/rules/branches/main`), a `cog check` or commitlint
  step in CI, or a line in `CLAUDE.md` or the contributing guide. One repo's
  CI rejected a merge commit through `cog check`.
- **Whether the branch is pushed, and whether anyone else commits to it.**

## 2. Merge or rebase

- Not pushed: rebase onto `<remote>/main`.
- Pushed, linear history not required: merge `<remote>/main` in. It needs no
  force-push.
- Pushed, linear history required: a rebase needs a force-push; ask the user
  first, then push with `--force-with-lease=<branch>:<sha you observed>`.
- Stacked on a parent that was squash-merged: the branch still carries the
  parent's commits. `git rebase --onto <remote>/main <old parent tip>` moves
  only the branch's own commits.

## 3. Resolve each conflict by reading both sides

For each conflicted file, read what the base changed and what the branch
changed (`git log -p --merge -- <file>`), and keep both intents. Do not
resolve a file, or the whole merge, with `-X ours` or `-X theirs`.

Some files are re-derived, not merged:

| File | Resolution |
| --- | --- |
| `Cargo.lock`, other lockfiles | take the base's, then regenerate (`cargo check`, or the repo's command) |
| an `-alpha.N` version that every PR bumps | take the base's value and bump it by one again (`pr` step 3) |
| generated files (docs, schemas, bindings, a version label) | take either side, rerun the generator, commit its output |
| numbered migrations or other sequences | renumber the branch's after the base's last |

## 4. Look for what git merged silently

After the merge completes, with no markers left:

- **CHANGELOG:** every entry the branch adds is under `Unreleased`, not under
  a version the base released since the branch was cut.
- **Renamed or removed on the base:** grep the branch's changes for each name
  the base renamed or removed; a call can merge cleanly and fail to build, or
  build and call the wrong thing.
- **Docs and comments** the branch wrote that describe code the base has
  changed since.

## 5. Check the result

```sh
git diff <remote>/main...HEAD --stat     # only the branch's own change
```

A file here the branch never touched means replayed commits or a wrong
resolution. Then run the gates with `verify`.

## 6. Push and say what changed

Push (no force unless step 2 agreed it). The head has moved, so a recorded
review no longer covers it: run `review` again unless every resolution was
mechanical (taking both sides of a list, a re-bumped version, a regenerated
lockfile), and say which. List each conflict and how it was resolved in the
PR or the report.

## Never

- **Never force-push without the user's agreement**, and then only with
  `--force-with-lease=<branch>:<sha>`.
- **Never resolve with `-X ours` or `-X theirs`**, or by taking one side of a
  file you have not read.
- **Never merge a lockfile or generated file by hand.**
- **Never treat a merge with no conflicts as correct** before step 4 and the
  gates.
