# Filling Unreleased from history

For a release whose `Unreleased` was not kept up to date: which commits get an
entry. Write each entry by step 2 of the `changelog` skill, then audit the
section by its step 3.

## 1. Find the range

Use the range from `changelog` step 3.1, which checks that the tag is an
ancestor of `HEAD`. In a per-crate workspace, use that crate's `<crate>-v`
tags and `git log -- <crate-dir>`.

## 2. Keep what a user would notice

Keep: new commands, flags, config options, endpoints, or public API; changed
behaviour; removed or renamed anything; bug fixes to a symptom a user could
hit; performance changes large enough to notice.

Drop: dependency bumps (unless they change MSRV, a feature, or a security
advisory), CI and packaging-only changes, internal docs and skills,
formatting, lint and comment fixes, test-only changes, refactors with no
behaviour change.

**Read the diff before dropping a "refactor".** A commit described as removing
dead or redundant code can remove a side effect — an extra process, file, log
line, or request — and so be a user-visible fix. `git show <sha>` and ask
whether the removed path could have caused a symptom.

When unsure whether a user would notice a commit, leave it out and list it
under §4.

## 3. Write each entry

Follow `changelog` step 2.

## 4. Report what was left out

List the commits excluded and why, in one line each, so the user can move any
back. Do not commit the section; `changelog` step 3.8 shows it to the user
first.
