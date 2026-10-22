---
name: backport
description: Carry changes from main to a maintenance branch (X.Y.x, release/X.Y.x, release/5.x) — read what the line takes from the repository, find what it lacks by checking for each change in the line's code rather than by commit title or patch-id, carry fixes, dependency floors, and features where the line takes them, cherry-pick with -x and adapt conflicts to the old line instead of pulling in the new one, keep the CHANGELOG entry under the line's Unreleased, run the gates and an audit on the line, and review the backport as its own change. Also answers whether a given release contains a change, from the tag's tree. Use when asked to backport a fix or feature, find what main has that a release line lacks, carry a security floor to an older line, or say whether a change shipped in a version.
---

# Backport

A backport fails in two ways: a change that looked carried and was not,
because the line was checked by commit title or patch, and a change that was
carried by pulling the new line's code in with it.

## 1. Find the line and its rules

Read the maintenance-branch section of `CLAUDE.md` and the branches
(`git ls-remote --heads <remote>`): `X.Y.x`, `release/X.Y.x` or
`release/<major>.x`. Note what the repository says:

- what the line takes. Lines differ: ringline's `release/X.Y.x` takes fixes
  and dependency floors only; rezolus's `release/5.x` takes features and cuts
  minor releases;
- fix `main` first, and `-x` on cherry-picks;
- where the line's CHANGELOG records a release, and whether `main` records
  it too;
- how a PR's head branch must be named: a ruleset on `release/**` can forbid
  deleting any branch under it.

## 2. Find what the line lacks

```sh
git fetch <remote>
git cherry -v <remote>/<line> <remote>/main | grep '^+' \
  | grep -E ' (fix|feat|perf|test|ci|chore\(deps\))'   # a first filter
git log <remote>/<line> --format=%B | grep -o 'cherry picked from commit [0-9a-f]*'
git log <remote>/<line> --oneline | grep -i 'backport'
```

`git cherry` matches patch-ids, so a carried change still shows `+` when it
was adapted, when it applied to a path `main` has since renamed, or when the
line's PR squashed several picks into one commit. Not every backport carries
a `-x` trailer, and backport titles often name the source as `(#N)` or
`(backport of #N)`. So for each candidate, look for the change itself in the
line's tree: grep `<remote>/<line>` for the function, constant or condition
it introduced. A matching title is not evidence.

`main` cannot show an advisory against a dependency version only the line
uses. Run `cargo audit` (or the repository's audit) in a worktree of the line
too; it reads the checked-out `Cargo.lock`.

To say whether a release contains a change, ask the tag's tree:
`git grep -n '<the code>' <tag>`. `git tag --contains <sha>` finds only the
same commit, never a cherry-pick of it.

## 3. Decide what to carry

Carry what the line's users need and the line takes (step 1): fixes,
dependency floors for advisories, and features where the repository says the
line takes them. Leave out:

- a breaking change;
- a change that needs a series of `main`'s changes underneath it. Write a
  targeted change for the line instead, or leave it to the next release;
- a refactor that only makes the change smaller on `main`.

Report the list with a reason for each item left out, and ask before
starting if the user named a scope that differs.

## 4. Cherry-pick and adapt

Branch from `<remote>/<line>`, named as step 1 requires, then
`git cherry-pick -x <commit on main>` for each change, oldest first.

On a conflict, keep the line's code and apply only what the change does:
`main` has usually moved on around it. Drop tests that exercise APIs the
line does not have, and keep the change's own tests, adapted. Do not take
`main`'s version of a file to make a conflict go away. Regenerate
`Cargo.lock` rather than resolving it by hand (`cargo update -p <crate>
--precise <version>` for a floor).

## 5. CHANGELOG and gates

The entry goes under the line's own `Unreleased`, not under a released
heading. Run the line's gates with `verify`: the line may have a different
toolchain floor, feature set or CI matrix. A backport that cannot build on
the developer's platform (io_uring on macOS, for example) is verified by the
line's CI; say so.

## 6. Review and open the PR

Run `review` on the backport as a change of its own, against the line: the
old code around a change can differ in ways `main`'s review never saw. Open
the PR into `<line>` (`pr`), and say in the body which commits it carries,
what was adapted and why, and what was left out. Cutting the line's release
is `release`.

## Never

- **Never decide a change is missing or present from a matching title or a
  `git cherry` `+`**, or that a release has it from `git tag --contains`.
- **Never resolve a backport conflict by taking `main`'s version** of the
  file.
- **Never backport a breaking change**, or a feature to a line that takes
  only fixes.
- **Never fix the line first** unless the bug exists only there, or `main`'s
  fix needs a series the line cannot take (step 3).
