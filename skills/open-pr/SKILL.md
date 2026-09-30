---
name: open-pr
description: Open a pull request from local work in any of these repositories — find the upstream and fork remotes, branch if on main, stage files by name, follow the repo's own commit convention and per-repo PR steps, run its gates, push, and create the PR against the right repository with the attribution the harness specifies. Use when asked to open, create, submit, or send a PR; when uncommitted changes or unpushed commits need to become a PR; and before trusting a repo-local `pr` skill, several of which point at the wrong repository.
---

# Open a PR

The mechanics are the same in every repository here; what differs is the
commit convention, a few per-repo steps, and which repository is upstream. Take
all three from the repository, never from another repo's habits. Ten repos
carried their own copy of this procedure, and one of them opened PRs against a
different project than its own.

## 1. Find the remotes and the target

```sh
git remote -v
git branch --show-current
git status --short
```

- **Fork layout** (`origin` = your fork, `upstream` = the project): the PR goes
  to `upstream` with `--head <fork-owner>:<branch>`.
- **Single remote** (`origin` is the project): the PR goes to `origin` with
  `--head <branch>`.
- Derive owners from the URLs; accept both `git@github.com:owner/repo(.git)`
  and `https://github.com/owner/repo(.git)`.

If a repo-local `pr` skill or `CLAUDE.md` names a target repository, check it
against these remotes. If they disagree, stop and ask.

Before writing anything that will be published, read the destination's
visibility (`gh repo view <repo> --json visibility`) and apply
`publishing-findings`. A branch name, commit message, or PR body pushed to a
public repository cannot be taken back.

## 2. Branch

If on `main`, create a branch named for the change in kebab-case. If already on
a feature branch with unrelated unpushed commits, stop and ask rather than
mixing two changes into one PR.

## 3. Read the repo's conventions

```sh
git log --format='%s' -15 upstream/main 2>/dev/null || git log --format='%s' -15
```

and the "Commits" / "Pull requests" section of `CLAUDE.md` if there is one.

- **Subject style differs by repo**: some use conventional commits
  (`fix(scope): …`), others sentence-case statements of what changed. Match
  the recent history.
- **Per-repo PR steps live in that repo's `CLAUDE.md`**, for example a docs
  version sync script, an `-alpha.N` bump rule for non-release PRs, per-crate
  CHANGELOG subsections, or opening as a draft. Do each one listed.
- **Attribution**: use the trailer and PR-body line the harness specifies for
  this session. Do not copy a model name from an old commit or from a repo
  skill; several hard-code one that is out of date.

## 4. Verify before committing

Run the repository's declared gates with `verify-change`. If a gate fails, fix
it or stop and report; do not open a PR on a red gate without saying so in the
body.

## 5. Stage and commit

- Stage files **by name**. Never `git add -A` or `git add .`; they pick up
  scratch files, logs, and secrets.
- Review `git diff --staged` before committing.
- Write the message with a heredoc so it is not mangled by the shell.
- Do not amend or force-push commits that are already on the remote.

## 6. Push and create the PR

```sh
git push -u origin <branch>
gh pr create --repo <owner/repo> --head <head> --base main \
  --title "<subject>" --body-file <file>
```

The body says what changed and why, how it was verified (the per-gate lines
from `verify-change`), and anything not verified. For an API change, state
what a caller can no longer do, not only what was added. Keep engagement or
client detail out of public repositories (`publishing-findings`; a hook
enforces the literal terms).

If a PR already exists for the branch, report its URL instead of creating
another.

## 7. Confirm and report

```sh
git rev-parse HEAD origin/<branch>     # must match
gh pr view --json url,state,isDraft
```

Report the URL. If CI has started, give its state; on repos with rack-ci, read
the `rack-ci/*` statuses (`use-rack-ci`).

## Never

- **Never `git add -A`.**
- **Never open a PR against a repository you have not matched to a remote.**
- **Never force-push** without the user asking, and then only with
  `--force-with-lease=<branch>:<observed-sha>`.
- **Never hard-code a co-author trailer**; use the harness's.
