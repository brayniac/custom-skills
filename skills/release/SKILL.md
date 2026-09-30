---
name: release
description: Cut a release for a Rust repo — discover the repo's own release mechanism, then bump, changelog, and open the release PR. Use when asked to release, cut a version, tag a version, or ship a new version, and when a release did not tag or publish and you need to find out why.
---

# Release

Every repo here releases the same way in outline and differently in detail.
Most of the detail is recorded in the repo — in `release.toml`, in the tag
workflow's trigger condition, in the tag history. **Read it. Do not carry a
procedure in from another repo**, and do not carry one in from a previous
session.

The exception matters: repos releasing through rack-ci are armed by config that
lives on delta and is in no commit, so the checkout cannot tell you whether a
tag will publish. Knowing which questions the repo *cannot* answer is part of
discovery.

The failure this exists to prevent: a release PR that merges cleanly, reports
success, and never tags, because the commit message did not match what the
workflow was watching for. Across these repos the trigger prefix is variously
`release: prepare v`, `release: v`, and `release: ` — a one-word difference that
nothing checks and no test covers.

## Step 1 — Discover, before touching anything

Answer all six. `references/discovery.md` has the exact commands and what each
answer implies.

1. **Where does the version live?** Root `[package]`, `[workspace.package]`, or a
   member manifest. Some repos version a subdirectory crate, not the root.
2. **Shared, per-crate, or hybrid versioning?** Tags reading `<crate>-v<version>`
   mean independent crates released one per run, in dependency order — a
   different workflow, not a variation. Harder: a workspace can tag `vX.Y.Z`
   while most members share that version and a couple of satellite crates sit on
   their own cadence. Compare every member's version before deciding what moves.
3. **Is there a `release.toml`?** If so it configures `cargo-release`, and its
   `tag`, `push`, `publish`, and `pre-release-commit-message` keys are the
   authority on what the tool will do. These differ between repos: some set
   `tag = false, push = false` and leave both to the workflow, others set both
   true and expect the tool to do it.
4. **What triggers a release here — and is it GitHub Actions at all?**
   Establish the mechanism first. Actions is disabled on some of these repos
   after a billing lapse, and **`.github/workflows/` still holds files in that
   state**, so reading them tells you what would run rather than what does.
   `brayniac/ferallm` and `brayniac/slipway` release through rack-ci on the
   rack instead; `references/rack-ci.md` covers that path. For the Actions
   path, read the `if:` condition in `.github/workflows/tag-release.yml` and
   derive the commit message from it — the condition is the specification, the
   skill is not. **The absence of `tag-release.yml` does not mean tagging is
   manual.**
5. **What does the automation do after tagging?** Publish to crates.io, build a
   GitHub release, bump to a dev version, or nothing. Read the steps — do not
   promise the user an outcome you have not seen in the workflow file.
6. **What are this repo's checks?** From `.rack-ci.toml`, its CI workflows, or
   `CLAUDE.md`, not from habit. `--all-features`, `--workspace`, `--lib`, and a
   `cargo fmt --check` rung all appear in different repos here.

## Step 2 — State the plan, then stop

Report what you found and what you are about to do: version source and current
version, new version, the exact commit message and the condition it satisfies,
the checks you will run, and what happens after merge. Name anything you could
not determine.

**If discovery was ambiguous, stop and ask.** A wrong guess here produces a
release that looks successful. Specifically stop when: no tag workflow and no
`release.toml`, so the mechanism is unknown; a `release.toml` that disagrees with
the workflow about who tags; or a workspace where you cannot tell whether
versions move together.

**On the rack path, whether releases are armed is not in the repository.** It
needs `[release]` in `.rack-ci.toml` *and* an override on delta, and the second
half is not at any commit — so a repo carrying the block alone looks armed and
is not. Report that as unknown rather than inferring it either way.

## Step 3 — Execute

1. **Prerequisites.** On `main`, clean tree, up to date with `origin/main`. Stop
   on any of the three rather than fixing it.
2. **Run the repo's checks** with `verify-change`: every gate, to a file, exit
   code first. If any fails, stop and report — do not release past a red check.
3. **Compute the new version** from the level argument (`patch`/`minor`/`major`)
   or take the explicit version given. Dev suffixes like `-alpha.N` are dropped
   by the bump, not carried.
4. **Branch** `release/v<version>`.
5. **Bump.** With `cargo release version <level> --execute --no-confirm` when
   `release.toml` exists, by editing the manifest found in step 1 otherwise.
6. **Changelog.** Move `Unreleased` into a new `<version>` section with today's
   date, open a fresh empty `Unreleased`. Keep a Changelog format. If
   `Unreleased` is thin, fill it from `git log <last-tag>..HEAD` using
   `references/changelog.md`. **Show the user the section and ask before
   continuing** — this is the one part of the release that carries prose a
   reader will rely on.
7. **Commit** with the message derived in step 1, question 4. Nothing before the
   prefix. On a squash merge the PR's single commit message becomes the merge
   commit message, which is what the workflow matches against.
8. **Push and open the PR** with `gh pr create`, titled the same as the commit.
   The body states the version, the changelog section, and what merging will
   trigger.
9. **Report the PR URL.**

## Step 4 — Verify after merge

A release is not done because the PR merged. Once it is on `main`:

```
git fetch --tags origin && git tag --sort=-creatordate | head -3
gh run list --workflow tag-release.yml --limit 3
```

The tag must exist and the workflow must have *run*, not merely been eligible.
If the workflow was skipped, the commit message did not match its condition —
report that, and say so plainly rather than reporting the release as complete.

On the rack path there is no workflow run to check. The verdict is the
`rack-ci/release` commit status, and `Error` there means the build never
started — which is not the same as a failing build. **A tag builds from the
tag's tree, so fixing `main` does not fix a broken tag**; it needs a new tag,
and re-pointing a published one is never the answer. `references/rack-ci.md`
has the status mapping and what verifying a publish actually requires.

## Never

- **Never invent the commit prefix.** It comes from the workflow condition or it
  is a question for the user.
- **Never release from a dirty tree or a red check**, including "just formatting".
- **Never release several crates in one run** in a per-crate workspace. One run
  per crate, lowest in the dependency graph first.
- **Never tell the user a release published to crates.io** unless you read a
  publish step in the workflow. Several of these repos set `publish = false`.
- **Never conclude that tagging is manual from a missing `tag-release.yml`.**
  Check whether Actions is enabled and whether the repo releases on the rack.
- **Never report a publish as verified because the publish job went green.**
  That is three layers above the claim; `references/rack-ci.md` has the five.
