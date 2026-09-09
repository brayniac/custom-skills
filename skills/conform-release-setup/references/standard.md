# The release standard

## The caller

A conforming repo's `.github/workflows/tag-release.yml` is this and nothing more:

```yaml
name: Tag Release

on:
  push:
    branches: [main]

jobs:
  tag-release:
    uses: brayniac/rust-workflows/.github/workflows/tag-release.yml@v1
    secrets: inherit
    with:
      dev-bump: pr
```

`secrets: inherit` passes `RELEASE_TOKEN`. Pin `@v1`, never a branch: a branch
ref means every repo adopts a change to the shared workflow the moment it lands,
which is the drift this replaces, only faster.

The workflow's source lives at
[`brayniac/rust-workflows`](https://github.com/brayniac/rust-workflows) and is
deliberately not copied here. Read it there when you need to know what a step
does; a second copy would drift from the first, which is the failure this whole
standard exists to end.

## The inputs, and only these

Four, because these are the only differences between repos that mean anything.
Anything else that differs is drift, not policy.

| Input | Default | Set it when |
| --- | --- | --- |
| `version-manifest` | `Cargo.toml` | the root is a virtual manifest and one member carries the released version (`server/Cargo.toml`, `<name>/Cargo.toml`) |
| `tag-prefix` | `v` | never, so far |
| `dev-bump` | `pr` | `direct` where a bump PR is noise on a repo you release often; `none` where versions are bumped by hand |
| `only-repository` | *(empty)* | the repo is forked and the fork's `main` must not tag — e.g. `iopsystems/rezolus` |

## Fixed here, not negotiable per repo

These caused the drift. They live in the shared workflow now, and a repo that
overrides them locally is non-conforming even if it works.

- **What counts as a release commit.** `release: v1.2.3`,
  `release: prepare v1.2.3`, and a merge commit naming `release/v1.2.3` are all
  accepted, so adopting the standard does not require changing a repo's release
  convention in the same PR. The prefix is only a pre-check: the gate is that
  **the commit must name the version the manifest holds**. Previously each repo's
  prefix was coupled to its own workflow copy by nothing but copy discipline,
  and a mismatch merged cleanly, reported success, and never tagged.
- **Version extraction is section-aware.** `grep -m1 '^version = '` and
  `sed -i "0,/^version = .../"` both take the *first* version key in the file,
  which is the package's only by convention. Checked against all ten manifests
  here, the two agree today — this is a latent hazard, not an observed bug, and
  the section-aware form costs nothing to adopt before a manifest reorders.
- **Dev bump runs `cargo release version`,** not `sed` on one manifest.
  `cargo-release` updates every manifest sharing the version and refreshes
  `Cargo.lock`; a single-file `sed` leaves a workspace internally inconsistent
  and the lockfile stale.
- **Next dev version is `MAJOR.MINOR.(PATCH+1)-alpha.0`,** with any existing
  prerelease suffix dropped first. A bare `X.Y.Z+1` with no suffix is a
  hand-edit, not this workflow's output.
- **`actions/checkout@v5` with `fetch-depth: 0` and the PAT.** v4 and v7 were
  both in use; nothing depended on either.
- **The gate is a step, not a job-level `if:`.** A job that never runs leaves no
  trace, so "the release did not tag" and "the workflow was not eligible" look
  identical afterward. As a step it logs the reason.

## Per-repo settings

Derived from each repo's current workflow and tag history. Confirm against the
repo before applying — this table is evidence, not authority.

| Repo | `version-manifest` | `dev-bump` | `only-repository` |
| --- | --- | --- | --- |
| rezolus | `Cargo.toml` | `direct` | `iopsystems/rezolus` |
| rpc-perf | `Cargo.toml` | `pr` | `iopsystems/rpc-perf` |
| insights | *confirm* | `pr` | `iopsystems/insights` |
| llm-perf | `Cargo.toml` | `pr` | `iopsystems/llm-perf` |
| clocksource | `Cargo.toml` | `pr` | `iopsystems/clocksource` |
| histogram | `Cargo.toml` | `pr` | *confirm* |
| ratelimit | `Cargo.toml` | `pr` | *confirm* |
| cachecannon | `Cargo.toml` | `pr` | `cachecannon/cachecannon` |
| crucible | `server/Cargo.toml` | `pr` | *(none — no fork)* |
| ringline | `ringline/Cargo.toml` | `pr` | `ringline-rs/ringline` |

## Repos this standard does not cover

- **metriken** — five independently versioned crates, tags `<crate>-v<version>`,
  no automation by choice. One shared version is the wrong model for it. Leave
  it manual and say so in its own `release.toml` or CLAUDE.md, so "no workflow"
  reads as a decision rather than an omission.
- **pelikan**, **forge** — no tag workflow today. Adopting the standard is a
  change in behavior, not a cleanup. Treat as new adoption and confirm first.
  `forge` additionally has `release.toml` with `tag = true, push = true`, so
  `cargo-release` there tags and pushes directly rather than via PR; adopting
  the standard means changing those keys too.

## `release.toml` under the standard

Where `cargo-release` is used, the workflow tags and the local skill pushes, so:

```toml
tag = false          # the workflow tags
push = false         # the release skill pushes the branch
publish = false      # unless the crate genuinely goes to crates.io
allow-branch = ["main", "release/*"]
consolidate-commits = true
pre-release-commit-message = "release: v{{version}}"
```

`tag = true, push = true` (crucible, forge) describes a direct tag-and-push flow.
Where the repo actually releases by PR, those keys are stale and will double-tag
if anyone runs `cargo release` locally.

`pre-release-commit-message` does **not** need to change during a migration. The
shared workflow accepts both `release: v{{version}}` and
`release: prepare v{{version}}`, precisely so that swapping the workflow and
changing a repo's release convention stay separate changes.
