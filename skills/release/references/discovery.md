# Release discovery

Six questions, the command that answers each, and what the answer implies. Run
them all before proposing a plan; they are cheap and read-only.

## 1. Where does the version live?

```sh
grep -n '^\[package\]\|^\[workspace\]\|^\[workspace.package\]\|^version = ' Cargo.toml
# Members can nest (crates/app, cache/core), so read the list rather than globbing:
sed -n '/^members = \[/,/^\]/p' Cargo.toml
```

Then read the version out of every member the list names:

```sh
for m in $(sed -n '/^members = \[/,/^]/p' Cargo.toml | grep -oE '"[^"]+"' | tr -d '"'); do
  printf '%-28s %s\n' "$m" "$(grep -m1 '^version = ' "$m/Cargo.toml" 2>/dev/null)"
done
```

| Shape | Version source |
| --- | --- |
| `[package]` at root, no `[workspace]` | root `Cargo.toml` |
| `[workspace.package] version = ` | root `Cargo.toml`; members inherit via `version.workspace = true` |
| virtual manifest, every member on the same version | each member's manifest — they all move together, so several files change |
| virtual manifest, members on differing versions | see question 2; this is not one release |

`*/Cargo.toml` is not a substitute for the members list: members nest under
`crates/`, `cache/`, `protocol/` in these repos and a one-level glob silently
finds nothing, which reads identically to "no members".

**Cross-check the version against the latest tag before trusting it.** A root
version ahead of the newest tag is normal — it is the post-release dev bump — but
the size of the gap tells you which convention is in force. Both `0.1.18-alpha.0`
against tag `v0.1.17` and a bare `5.19.1` against tag `v5.19.0` occur here, and
they bump differently.

## 2. Shared, per-crate, or hybrid?

```sh
git tag --sort=-creatordate | head -10
```

Tag format is the first signal; agreement between member versions is the
confirming one. Use both, because the interesting case disagrees with a naive
reading of either.

| Tags | Member versions | Shape | What a release means |
| --- | --- | --- | --- |
| `v1.2.3` | one value, or inherited | **shared** | one version, all members move |
| `<crate>-v1.2.3` | all differ | **independent** | one crate per run, dependency order |
| `v1.2.3` | most agree, a few differ | **hybrid** | the agreeing set is the product and moves with the tag; the outliers are satellite crates released on their own |

The hybrid is the trap. A workspace can tag `v0.6.1` while most members sit at
`0.6.x` and a couple of utility crates sit at `0.2.0` and `0.3.8` on their own
cadence. Bumping everything to match the tag would silently version-bump crates
nobody meant to release. **Identify the product set before bumping**, and say
which members you are leaving alone and why.

For an independent workspace, releasing several crates means running this
workflow once per crate, lowest in the dependency graph first, so a dependent's
manifest can point at a version that already exists. Ask which crate if it was
not named.

## 3. Is `cargo-release` configured?

```sh
cat release.toml 2>/dev/null
command -v cargo-release || cargo release --version
```

Absent: bump by editing the manifest from question 1.

Present: `cargo release version <level> --execute --no-confirm` bumps, and these
keys decide what else happens. They differ between repos in this workspace, so
read them rather than recalling them:

| Key | Why it matters |
| --- | --- |
| `tag` | `false` means the workflow tags; `true` means the tool does, and a workflow that also tags will collide |
| `push` | `false` means you push the branch yourself, which is what the PR flow wants |
| `publish` | `false` means crates.io is not part of this release, whatever the workflow's name suggests |
| `pre-release-commit-message` | the commit message template — cross-check it against question 4 |
| `allow-branch` | refuses to run outside these branches; `release/*` must be listed for the PR flow |

A `release.toml` whose comments describe tagging and pushing directly, while the
repo actually releases through a PR, is drift: the file was written for an
earlier flow. Trust the keys, not the comments, and mention the discrepancy.

## 4. What triggers the tag workflow?

This is the one that silently breaks releases.

```sh
grep -n 'if:' .github/workflows/tag-release.yml
```

The condition is the specification for your commit message. Derive, do not
assume — all three of these are in use across these repos:

| Condition | Commit message must be |
| --- | --- |
| `startsWith(..., 'release: prepare v')` | `release: prepare v1.2.3` |
| `startsWith(..., 'release: v')` | `release: v1.2.3` |
| `startsWith(..., 'release: ')` | `release: v1.2.3` (any suffix, but stay consistent with tag history) |

Two further clauses to read out loud before relying on the workflow:

- `github.repository == '<org>/<repo>'` — the workflow is inert on a fork. If the
  release is being cut from a fork, tagging will not happen and nothing will say
  so.
- `contains(..., 'release/v')` — some workflows also match the merge-commit form,
  which makes them tolerant of a non-squash merge. Most do not.

No `tag-release.yml` at all means tagging is manual. Say so, and either tag by
hand after merge or ask.

## 5. What happens after the tag?

```sh
sed -n '1,80p' .github/workflows/tag-release.yml
ls .github/workflows/
```

Read the steps and report only what is there. Across these repos the tail of a
release variously: creates the tag and stops; triggers a `release.yml` that
builds artifacts and cuts a GitHub release; publishes to crates.io; and commits
a bump to the next `-alpha.N` dev version. Do not describe a step you did not
read, and do not promise crates.io when `publish = false`.

## 6. What are this repo's checks?

```sh
grep -n 'cargo ' .github/workflows/ci.yml 2>/dev/null
grep -n -i 'clippy\|cargo test\|cargo fmt' CLAUDE.md 2>/dev/null
```

Use what CI uses. The variations seen here — `--all-features`, `--workspace`,
`--lib`, `--all-targets`, with and without a `cargo fmt --all -- --check` rung —
are deliberate per repo, and a check you invented can fail for reasons the repo
does not care about, or pass over the ones it does.

## Reporting discovery

State every answer, including the ones you could not determine. The plan the
user approves should let them catch a wrong reading before it becomes a merged
PR — which means naming the evidence, not just the conclusion:

> Version: `5.19.0` in root `Cargo.toml` (`[workspace.package]`), matching tag `v5.19.0`.
> Shared versioning; tags are `vX.Y.Z`.
> `release.toml` present: `tag = false`, `push = false`, `publish = false`.
> `tag-release.yml` requires `startsWith(msg, 'release: prepare v')` and is gated
> to `iopsystems/rezolus`, so the commit will be `release: prepare v5.20.0`.
> After merge: tag `v5.20.0`, then `release.yml` builds packages and a GitHub
> release. No crates.io publish.
> Checks: `cargo clippy --all-targets -- -D warnings`, `cargo test`.
