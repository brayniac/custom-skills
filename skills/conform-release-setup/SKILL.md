---
name: conform-release-setup
description: Bring one repo's release automation onto the shared standard, or report how far off it is. Use when asked to unify, standardize, or migrate release workflows, when a repo's release behaves differently from a sibling's, when setting up releases in a new repo, and before relying on a repo's tag automation you have not checked.
---

# Conform a repo's release setup

**This standard is the GitHub Actions path, and it does not apply to every
repo.** `brayniac/ferallm` and `brayniac/slipway` release through rack-ci on
the rack — a tag builds in a guest and publishes to the internal apt repo, with
no workflow file involved — and Actions is disabled on both. Conforming such a
repo to a reusable Actions workflow would be conforming it to a mechanism it
does not use. Establish which path a repo is on first (`release` skill,
discovery question 4); `release/references/rack-ci.md` describes the other one.

The release workflow was copied into every repo and drifted. This replaces each
copy with a ten-line call to one shared workflow, so the parts that must agree
are defined once and the parts that legitimately differ are named inputs.

`references/standard.md` is the standard: the caller stub, the six inputs, what
is fixed and why, and the per-repo settings derived from the current workflows.
Read it before proposing a migration. The shared workflow itself lives at
[`brayniac/rust-workflows`](https://github.com/brayniac/rust-workflows), pinned
by callers at `@v1`.

**One repo per run.** A sweep is this workflow repeated, not a batch.

## Step 1 — Read what the repo does now

Do not assume it matches its sibling. For the repo you are in:

```sh
git fetch --tags origin            # a local tag list is stale by default
cat .github/workflows/tag-release.yml 2>/dev/null
cat release.toml 2>/dev/null
git tag --sort=-creatordate | head -5
sed -n '/^members = \[/,/^\]/p' Cargo.toml
```

Sort tags by date, not lexically: `v5.9.1` sorts after `v5.19.1`, so a
lexical list truncated with `head`/`tail` reports the wrong newest tag and makes
a healthy repo look like a failed release.

Establish, and write down: the version manifest and current version; whether
versioning is shared, independent, or hybrid; the commit prefix its workflow
matches today; how it lands the dev bump; whether it is fork-gated; whether it
publishes. The `release` skill's `references/discovery.md` covers each of these
in detail — use it rather than re-deriving.

## Step 2 — Classify the repo

| Finding | What to do |
| --- | --- |
| Has a copied `tag-release.yml`, shared versioning | **Migrate.** The normal case. |
| Independently versioned crates (`<crate>-v<version>` tags) | **Do not migrate.** One shared version is the wrong model. Record that the manual process is deliberate. |
| No tag workflow at all | **Adoption, not cleanup.** This changes behavior. Confirm with the user before proposing it. |
| `release.toml` says `tag = true, push = true` | Migration must change those keys too, or the repo will double-tag. Call this out. |
| Root version does not match the newest tag in the expected way | **Fetch tags and re-check before concluding anything.** A local checkout's tag list is stale by default, and a repo mid-release sits at a released version with the tag not yet pulled. Only after `git fetch --tags` is a mismatch evidence of a hand-edit. |

## Step 3 — Report the diff, then stop

State, for this repo: what it does now, what the standard does, which of the
six inputs it needs and why, and what will change in observable behavior — in
particular whether the commit prefix changes, because that is the part that
silently breaks releases.

If the repo is already conforming, say so and stop. There is nothing to do and a
"cleanup" commit on a correct repo is churn.

**Get explicit approval before editing.** This edits release automation, where a
mistake is discovered at the next release and not before. Note in the report that
the repo's PR checks cannot validate the caller — `tag-release.yml` runs on push
to `main`, so a PR goes green regardless and the first real test is the merge.

## Step 4 — Migrate

1. Replace `.github/workflows/tag-release.yml` with the caller stub from
   `references/standard.md`, filling in only the inputs this repo needs.
2. Reconcile `release.toml` if present, per the standard's final section.
3. Update the repo's `CLAUDE.md` if it documents the old prefix or procedure.
4. Confirm `RELEASE_TOKEN` exists in the repo's secrets — the shared workflow
   needs it and the default `GITHUB_TOKEN` will not do:
   ```sh
   gh secret list --repo <owner>/<name>
   ```
5. Commit on a branch and open a PR. Never push release automation to `main`
   directly.

## Step 5 — Verify it actually works

A migration is not done because the PR merged. It is done when a release ran
through it.

```sh
gh workflow list  --repo <owner>/<name>
gh run list --workflow tag-release.yml --repo <owner>/<name> --limit 5
```

The shared workflow gates in a step rather than a job `if:`, so a non-release
push still produces a run whose log says why it stopped. **That run appearing is
the evidence the wiring is live.** If no run appears at all, the caller is not
being triggered and the migration did not take, whatever the PR says.

Read the run's own log rather than its colour. The line to find is the gate
step's reason — `Head commit is not a release commit` — and the seven steps after
it marked skipped. A green run with no gate step never loaded the shared
workflow.

Then say plainly that the first real release through it is still unproven, and
that step 4 of the `release` skill is what confirms it.

## Never

- **Never migrate more than one repo per run**, and never skip the report.
- **Never change a repo's versioning model** as part of a conformance pass. If
  shared-versus-independent looks wrong, that is a separate conversation.
- **Never point a caller at a branch** of the shared workflow. Pin a tag.
- **Never report a repo as conforming** because the file matches. It conforms
  when a run has been observed.
