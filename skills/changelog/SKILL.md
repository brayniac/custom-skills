---
name: changelog
description: Add, write or fix entries in CHANGELOG.md, and audit a changelog section before it ships — follow the file's own headings and reference style, write each entry for a user of the last release deciding whether to upgrade, file a new flag or config key as a feature and say when its default changes an existing config, name a fix by the symptom and the released versions that had it, keep rationale in the PR, and at release time re-check every entry against the present and trace it to its PR. Use before editing CHANGELOG.md for any reason, including when asked to add the changelog entries for a commit or branch, when a change needs a CHANGELOG entry (in a PR, a backport or a sync), when cutting a release (`release` step 6), when filling Unreleased from history, when reviewing or tightening a changelog section, and when someone says the changelog is wrong, stale or unclear.
---

# Changelog

The reader is a user of the last release deciding whether to upgrade and what
changes or breaks for them when they do. An entry is written once per change
and read at release time, often weeks later, so many errors are entries that
were true when written and are not true at release.

## 1. Read the file's conventions

Before writing anything, read the two most recent released sections:

- the headings in use (`Features` / `Changes` / `Bug Fixes` / `Security`, or
  Keep a Changelog's `Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` /
  `Security`). Use the file's headings. If the file has no released section,
  use Keep a Changelog's;
- the reference style (`(#123)` at the end of each entry, or none);
- how dates are written in section titles, and in which time zone if a commit
  or the file says;
- whether entries carry sub-bullets (a library note under a user entry), and
  how Security entries are split (one bump per line, or grouped).

## 2. Write an entry for a change

1. **File it by what a user can now do.** A new command, flag, config key,
   endpoint or public API is a feature, even when it was added to fix
   something; the entry then also names the symptom and the affected releases
   (2.4), so a user looking for the fix finds it. A change to existing
   behaviour is a change. A removal or deprecation goes under the file's
   removal or deprecation heading, or first under its changes heading. A fix is
   a fix when nothing new is added for the user to call or set.
2. **Lead with what changes or breaks for an existing user.** Removals, breaking
   changes and data loss go first in their section. If a new key's default
   changes what an existing config does, say so in the entry's second sentence,
   with the condition it depends on: "With the defaults, existing configs resend
   a request whose send fails with a connection error; before, with `max_retries
   = 0` (the default), each was reported as an error." Anything now dropped,
   skipped, counted differently or no longer read goes first in its entry: a
   parser that used to record a line and now skips it loses that line's series.
3. **Write behaviour, not the dependency.** "metriken-recorder 0.3.1: …" makes
   the reader translate. Write what the user sees ("`server_metrics_url` set
   to a Prometheus URL: …") and cite the PR. Name a crate version only in a
   Security entry or when the version is what the user acts on (MSRV, a
   feature flag). State the capability change, not the diff's shape: "the call
   shape is unchanged" was accurate and hid that two connections could no
   longer be checked out at once.
4. **Name a fix by its symptom.** The command or config that failed, the
   error text a user would search for, and the released versions that had
   it: "v0.1.21 could not read any compressed parquet file: `mmlu-pro` failed
   with `Disabled feature at compile time: snap`." Not the mechanism
   (feature unification, a version split): that goes in the PR.
5. **Compare a restored capability with the last release where it worked.**
   When a fix brings something back, check what the last good release
   supported (its `Cargo.lock`, its feature list, its code) and name anything
   still missing: "Brotli, which v0.1.20 read, is not supported." Leaving it
   out reads as a full restoration.
6. **Check every claim about old behaviour and other products.** "Before, a
   Prometheus line with a label name containing `.` was kept under the labels
   that parsed" was false: prometheus-parse 0.2.5 recorded the line with the
   label name as written. Read or run the old code before describing it. For
   another product's versions, look up its latest release (`git tag`, the
   registry, its releases page) before writing a range: "rezolus 5.21 to 5.28
   read dendro schema 4" was written after 5.29 had shipped. Write the range up
   to the latest release you checked, not "and later".
7. **Date claims about external state, at the precision of the evidence.** "The
   assets are corrupt" was true on the day the PR merged and false the same
   evening, when the assets were replaced. For state outside the repository
   (published assets, a server, another project), write it as dated fact or as
   the action the user takes: "v0.1.15 to v0.1.21 packages downloaded before
   2026-10-30 20:51 UTC may be corrupt; their assets were replaced between 20:33
   and 20:51 UTC that day." A date alone would have told a user who downloaded
   at 10:00 UTC that day that their package was good.
8. **Leave out rationale and test numbers.** Why the design is right, the test
   configurations measured and the runs it took belong in the PR. A number
   stays only if it states the conditions a user needs to compare it with
   their own setup (server version, hardware, load); without them, leave it
   out. An upstream issue number stays when it is what a user watches for a
   fix ("llama-server (llama.cpp issue #29680) closes …").
9. **Flag a break for library callers** in a sub-bullet: what stops
   compiling and the replacement. Name every public type that changed, not
   only the one the PR is about. In a `0.x` crate a field added to a struct
   built with a literal breaks callers in a patch release; say so in the PR
   body and in the sub-bullet, since it may call for a minor bump (`release`
   step 3 reads it).
10. **Put a new entry under `Unreleased`**, never under a released heading.
    If the file has none, add an `Unreleased` heading above the newest
    release, at the same level and style as the release headings. A
    correction to a released entry edits that entry in place; say so in the
    commit. Add the PR reference in the file's style when the PR has a
    number, or leave it for the release audit (3.1). Present tense for current
    behaviour; backticks on what a user types or calls (`--flag`,
    `[section] key`, `Type::method`).

## 3. Audit a section before it ships

Run this at release time (`release` step 6), and on any request to review a
changelog section. Re-check every entry; do not assume an entry that passed
review when it merged is still true.

1. **Find the range and trace each entry to its PR.**

   ```sh
   LAST=$(git tag --sort=-creatordate | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
   { [ -n "$LAST" ] && git merge-base --is-ancestor "$LAST" HEAD; } ||
     { echo "LAST='$LAST' is empty or not an ancestor of HEAD; stop"; exit 1; }
   git log "$LAST"..HEAD --format='%h %s'
   git log --format='%h %s' -S'<a phrase from the entry>' "$LAST"..HEAD -- CHANGELOG.md
   ```

   The regex takes release tags only; in a per-crate workspace use that crate's
   `<crate>-v` tags and `git log -- <crate-dir>`. Stop if `LAST` is empty or is
   not an ancestor of `HEAD` (the newest tag can be on a maintenance line), and
   ask the user which release this section follows. Add each entry's missing PR
   reference; an entry a later PR rewrote cites both. Every user-visible commit
   in the range has an entry; when filling `Unreleased` from history, use
   `${CLAUDE_SKILL_DIR}/references/from-history.md` for what to keep and drop.
2. **Re-check every present-tense claim about state outside the repository**
   (assets, deployed services, another project's behaviour) against that state
   today, and every version range against the other product's releases today.
3. **Build Security from the lockfiles.** Run the audit on the last
   release's lockfile and on `HEAD`'s, and list every advisory cleared
   between them, each under the crate it was on, including `unsound` and
   `unmaintained` warnings if earlier Security sections of CHANGELOG.md list
   them. If the last release's tree has no `Cargo.lock`, the checkout does
   not track one, or `cargo audit` is not installed, stop and tell the user;
   do not write Security from memory. Without a lockfile, `cargo audit`
   resolves and writes one, and audits today's resolution.

   ```sh
   LAST=<the tag 3.1 settled on>
   git rev-parse -q --verify "refs/tags/$LAST" >/dev/null || { echo "no tag '$LAST'; stop"; exit 1; }
   git ls-files --error-unmatch Cargo.lock >/dev/null || { echo "Cargo.lock is not tracked; stop"; exit 1; }
   OLD=$(mktemp)
   git show "$LAST":Cargo.lock > "$OLD" || { echo "no Cargo.lock at $LAST; stop"; rm -f "$OLD"; exit 1; }
   [ -s "$OLD" ] || { echo "empty Cargo.lock at $LAST; stop"; rm -f "$OLD"; exit 1; }
   cargo audit -f "$OLD"
   cargo audit --no-fetch
   rm -f "$OLD"
   ```

   Set `LAST` in the same call: a shell variable does not survive between
   tool calls. The guards stop the cases where nothing would read as
   cleared: no tag, and no lockfile or an empty one at the tag, which audits
   as 0 dependencies with exit 0. The first audit fetches the advisory
   database; an old local copy misses recent advisories.

   In a per-crate workspace the root `Cargo.lock` covers every member: keep
   only advisories on crates in this crate's tree (`cargo tree --target all
   -p <crate> -i <dep>@<version>`, with the version each revision's lockfile
   has, at `HEAD` and in a worktree of `$LAST`; "did not match any
   packages" means the dependency is not in this crate's tree). For a crate
   others depend on as a library, its `Cargo.lock` does not reach them:
   write each entry as covering this repository's builds and the binaries
   it ships. Say library users are covered only when you have shown that no
   version their resolution may pick is affected, since a downstream
   lockfile can hold any version of a crate in this crate's tree that the
   requirements on the path to it allow, including versions older than
   this repository's lockfile has.

   Attribute each bump to the dependency that moved it (`Cargo.lock`'s
   dependency lists), not to the nearest bump in the same PR.
4. **Re-check the combined effect.** Read the entries for one subsystem
   together: a later PR may have changed a default, renamed a key, or undone
   part of an earlier fix. Compare the release with the previous release for
   anything that worked then and does not now (2.5).
5. **Check placement and order** against 2.1 and 2.2, and wording against
   2.3, 2.4 and 2.8.
6. **Keep every proposition a user needs.** When rewriting an entry, list the
   propositions of the old text, and for each one dropped, say whether it was
   rationale or something the user needed. Keep modal words and quantifiers
   ("may", "some", "every") as they were unless you checked the new ones.
7. **Check a rewrite as a new entry.** Every sentence of a replacement is a new
   claim, and so is a detail learned only by reading code: in the 3.8 report,
   mark it as read from code, not observed. Shortening can drop a qualifier the
   claim needed: "Trace replay never resends a generation request" became
   "Trace replay does not resend", and replay's render and tokenize requests do
   retry. A correction can be written more broadly than its evidence: "releases
   have a `SHA256SUMS`" was true from v0.1.15 on and was written as "every
   release has a `SHA256SUMS`". Check each sentence you wrote against its
   source. Outside a release, have a fresh agent review the section with
   `review`. At release, skip it here: `release` step 7 runs it on the release
   commit, with every rewritten entry named in its brief.
8. **Report the section with what changed.** Show the user the section, then
   one line per entry you changed: what was wrong, the evidence (a command and
   its output, a file and line), and what it says now. `release` waits for the
   user's answer before committing.

## Never

- Never state as current a claim about published assets, a deployed service
  or another project without checking it today.
- Never describe how the old version behaved without reading or running the
  old code.
- Never describe a fix as complete without comparing with the last release
  where the capability worked.
- Never move design rationale into an entry, or a test number or upstream
  issue that 2.8 does not keep; cite the PR.
- Never impose a heading scheme the file does not use.
- Never commit a release section before the user has seen it and the list of
  changes made to it.
