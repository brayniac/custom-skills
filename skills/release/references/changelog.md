# Writing a changelog section

For filling `Unreleased` from history when it was not kept up to date. The
reader is someone deciding whether to upgrade and what will break when they do.

## 1. Find the range

```sh
LAST=$(git tag --sort=-creatordate | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
git log "$LAST"..HEAD --format='%h %s'
```

Filter to release tags; a prerelease or per-crate tag at the top gives the
wrong range. In a per-crate workspace, use that crate's `<crate>-v` tags and
`git log -- <crate-dir>`.

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

When unsure, leave it out; a short changelog gets read.

## 3. Write each entry

- Sort into Keep a Changelog sections: Added, Changed, Deprecated, Removed,
  Fixed, Security.
- **Lead with what can lose data or break a build or a caller**: removals,
  breaking changes, and data-loss fixes go first within their sections.
- **State the capability change, not the diff's shape.** "The call shape and
  the number of awaits are unchanged" was accurate and hid that concurrent
  checkout had been removed. Write "`Pool::get` now borrows the pool mutably;
  two connections can no longer be checked out at once."
- Backtick the identifier a user types or calls (`--flag`, `Type::method`).
- One line per change, present tense, plain; no internal rationale — that is
  the PR's job.
- Add the PR or issue number if the file's existing entries do.

## 4. Report what was left out

List the commits excluded and why, in one line each, so the user can move any
back. Do not commit the section; step 6 of `release` shows it to the user
first.
