---
name: open-pr
description: Open a pull request from local work in any of these repositories — find the upstream and fork remotes, branch if on main, sweep the comments the change touches (where each fact lives, every claim of absence or equivalence checked by a grep), run the repo's gates, stage files by name, follow its commit convention and per-repo PR steps, run a `review` of the commits and answer it, push, and write the body as a guide for the reviewer (why, the decisions, where to look, what the tests ran and do not cover). Use when asked to open, create, submit, or send a PR; when uncommitted changes or unpushed commits need to become a PR; when asked to write or update a PR description, or to add, document, sweep, clean up or check the comments in a change, in any language; and before trusting a repo-local `pr` skill, several of which point at the wrong repository.
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

## 4. Sweep the comments, then verify

Sweep every comment and doc comment the change touches with
`${CLAUDE_SKILL_DIR}/references/sweep-comments.md`: where each fact lives,
what a reader derives from the code and so is deleted, every surviving claim
of absence, equivalence or who-does-what checked with a grep, and text written
from the session's vantage removed. It reports one line per comment touched.
Run it alone (mode `audit`) when asked to check a change's comments.

Then run the repository's declared gates with `verify-change`. If a gate fails,
fix it or stop and report; do not open a PR on a red gate without saying so in
the body.

## 5. Stage and commit

- Stage files **by name**. Never `git add -A` or `git add .`; they pick up
  scratch files, logs, and secrets.
- Review `git diff --staged` before committing.
- Write the message with a heredoc so it is not mangled by the shell.
- Do not amend or force-push commits that are already on the remote.

## 6. Review the commits

Run `review` on the commits (a fresh agent; its mandates for what breaks, and
for API and docs when they changed). Answer every finding before pushing:
fix, dispute with evidence, or defer with the user. Fix commits are part of
what goes up; if the fixes are more than mechanical, review again. Skip only
when the user says to, and say so in the PR body.

## 7. Push and create the PR

```sh
git push -u origin <branch>
gh pr create --repo <owner/repo> --head <head> --base main \
  --title "<subject>" --body-file <file>
```

Write the body with `${CLAUDE_SKILL_DIR}/references/pr-body.md`: why the change
exists, the decisions that want the reviewer, where to look more closely, what
the tests ran and do not cover (the per-gate lines from `verify-change`), and
what only production can show. Say what `review` found and how each finding was
answered. Use the same file to update a body after new commits, or when asked to
write a PR description. For an API change, state what a caller can no longer do,
not only what was added. Keep engagement or client detail out of public
repositories (`publishing-findings`; a hook enforces the literal terms).

If a PR already exists for the branch, report its URL instead of creating
another.

## 8. Record the review, confirm and report

```sh
git rev-parse HEAD origin/<branch>     # must match
gh pr view --json url,state,isDraft,headRefOid
```

Record the step 6 review against that head (`review` step 8) if no commit
landed after it and its verdict was merge; the merge gate refuses an
unrecorded head. Report the URL
and what the review found. If CI has started, give its state; on repos with
rack-ci, read the `rack-ci/*` statuses (`use-rack-ci`). When a reviewer
answers, reply with `review` step 7.

## Never

- **Never `git add -A`.**
- **Never open a PR against a repository you have not matched to a remote.**
- **Never force-push** without the user asking, and then only with
  `--force-with-lease=<branch>:<observed-sha>`.
- **Never hard-code a co-author trailer**; use the harness's.
