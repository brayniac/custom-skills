---
name: catch-up-on-repo
description: Brief the user, or yourself at the start of a session, on the state of a repository before work resumes — the current branch's position against its upstream and main, uncommitted work, stashes and other worktrees, the CI state of the branch and of the user's open PRs, instruction files changed since the window began, and what landed on main grouped by theme with risky changes first. Picks the window by time or reflog, because commits authored by the user's git identity include every agent session's work. Read-only. Use when the user says "catch me up", "what did I miss", "what changed while I was out", "where was I", at the start of a session that resumes earlier work, and before starting new work on a branch you did not create in this session.
---

# Catch up on a repository

The briefing has two jobs: say what state the work is in, and say what changed
around it. The first matters more. Two rounds of work once went onto a branch
whose `get_stream_end_to_end` failure predated them, because nobody read the
branch's CI state before starting (`verify-change` step 1).

The command sequence is read-only apart from `git fetch`, which updates
remote-tracking refs and nothing in the working tree. Skip the fetch if the
user asks for an offline briefing, and say the upstream comparison is as of
the last fetch.

## Inputs

- The repository path (default: the working directory).
- A window, if the user names one ("since Monday", "since v0.4.0").

## 1. Pick the window

Do not select the window by the user's authorship. Here, agent sessions commit
under the user's git identity: in `custom-skills`, 22 of the last 30 commits
were authored as the user with a Claude co-author trailer; in
`crucible-wt-cachers`, 50 of 50. In `custom-skills`, `git log -1
--author=<user email>` returned `HEAD`, so "since your last commit" was an
empty window although the three most recent commits came from an agent
session.

In order:

1. The window the user named.
2. The last time this checkout was worked in before the current break.
   `git reflog --date=iso -n 30` lists recent moves of `HEAD`; find the newest
   gap of more than about four hours between consecutive entries, and start
   the window at the older entry. Consecutive entries minutes apart are one
   session's commits, so the previous entry alone is not the boundary.
3. The last 7 days on the default branch, widened to at least 10 commits.

State the window at the top of the briefing, with the reason it was chosen.
Record its start as a commit on the default branch for the later steps:

```sh
W=$(git rev-list -1 --before='<window start>' origin/main)
```

## 2. Where the work stands

```sh
git fetch --quiet --all --prune
git status --short --branch                 # ahead/behind upstream, dirty files
git rev-list --left-right --count origin/main...HEAD
git stash list
git worktree list                           # other sessions' checkouts
git log --oneline @{u}..HEAD 2>/dev/null    # unpushed commits
```

Report: branch, ahead/behind upstream and main, uncommitted files, stashes,
unpushed commits, and every other worktree with its branch. Another worktree
usually means another session is working in this repository; name its branch
so work does not collide.

## 3. CI state of this branch and of open PRs

```sh
gh pr list --author @me --state open \
  --json number,title,headRefName,isDraft,reviewDecision
gh pr view --json number,statusCheckRollup,mergeStateStatus   # this branch's PR
gh api repos/OWNER/REPO/commits/$(git rev-parse HEAD)/status \
  --jq '.statuses[] | [.context, .state] | @tsv'              # rack-ci statuses
```

For each open PR: checks passing, failing, pending, or absent, and whether a
review is waiting. Read red marks through `use-rack-ci` first: a GitHub check
that failed in a few seconds with no steps is billing, and `rack-ci/*` `error`
is infrastructure. Neither is a code failure.

If this branch is red, say which check and on which commit before anything
else in the briefing.

## 4. Instructions that changed

```sh
git log --since='<window start>' --name-only --format= origin/main -- \
  CLAUDE.md AGENTS.md ':(glob)**/CLAUDE.md' .rack-ci.toml .github/workflows \
  rust-toolchain.toml rustfmt.toml | sort -u
```

A changed `CLAUDE.md`, gate list, or toolchain pin changes how the next piece
of work must be done. List each with a one-line summary of the change
(`git diff $W origin/main -- <file>`). Read the new text of
any instruction file before resuming work.

## 5. What landed on main

Use the repository's default branch where this says `main`.

```sh
git log --no-merges --date=short --format='%h%x09%ad%x09%s' \
  --since='<window start>' origin/main
git diff --stat $W origin/main | tail -20
```

Group by theme (area of the code, feature), not by date. Order the groups:

1. changes to public APIs, schemas, file formats, config formats, or gates;
2. new features;
3. refactors touching many files;
4. fixes relevant to the current branch;
5. tests, CI, docs and chores, in one line.

For each group, one line of intent and one to three short SHAs. List fewer than
eight commits individually instead of grouping. If the repository keeps a
journal (`docs/journal/`), name entries opened or closed in the window.

Then cross the current branch's changed files with main's:

```sh
comm -12 <(git diff --name-only origin/main...HEAD | sort) \
         <(git diff --name-only $W origin/main | sort)
```

Files in both are the likely merge conflicts.

## 6. Write the briefing

Under about 40 lines:

```
Window: <range> (<why>)
Branch: <name>, <ahead/behind>, <dirty files / stashes / unpushed>
Other worktrees: <path: branch> ...
CI: <this branch>; open PRs: #n <state>, ...
Instructions changed: <file: one line> ...
Landed on main:
  <theme>: <intent> (<sha>, <sha>)
  ...
Overlap with this branch: <files>
Next step: <one concrete action, only if the state calls for one>
```

If nothing changed and the branch is clean and green, say so in two lines.

## Stopping condition

The briefing is done when every section above is either reported or marked
"none". Do not start the next piece of work inside this skill.

## Never

- **Never choose the window by commit author.** The user's identity is on
  most agent commits.
- **Never omit a red check on the current branch** from the first lines of the
  briefing.
- **Never modify the repository** beyond `git fetch`: no checkout, rebase,
  stash, pull, or commit.
- **Never paste a raw `git log`** in place of the grouped summary.
- **Never report another worktree's branch as abandoned** without evidence;
  it may belong to a live session.
