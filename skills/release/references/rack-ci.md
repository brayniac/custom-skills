# Releasing through rack-ci

Some repos here do not release through GitHub Actions. `brayniac/ferallm` and
`brayniac/slipway` release on the rack: a v-prefixed tag builds in a guest, the
`.deb` is published to the internal apt repo on delta, and the verdict arrives
as a `rack-ci/release` commit status.

Nothing in `.github/` is involved. Actions has been *disabled* on both repos, so
the workflow files that remain there describe what would run, not what does.

## Is it armed? Not answerable from the checkout

Two things are required and only one is in the repo:

| Where | What |
| --- | --- |
| the repo's `.rack-ci.toml` | a `[release]` block |
| `/etc/rack-ci/rack-ci.toml` on delta | `release = true` under `[overrides."OWNER/REPO"]` |

The repo-side block alone does nothing. Since the override is not in the
repository at any commit, **no amount of reading the checkout tells you whether
releases are armed.** Say that rather than inferring, and confirm with whoever
owns rack-ci before promising the user that a tag will publish.

A tag also produces a separate CI run (`{repo}#tag-ci:{tag}`, distinct from the
release run `{repo}#tag:{tag}`), deliberately, so a repo whose tags release gets
both and neither supersedes the other.

## A tag builds from the tag's tree

This is mechanism, not policy. rack-ci never clones, and the guest never
resolves a ref. rack-ci fetches `repos/{repo}/tarball/{sha}` for the commit the
tag names, holds the bytes in memory, and serves them once at an unguessable
path on the flat network; the guest curls that URL, because it holds no GitHub
credential.

So the guest only ever sees that one tree, and `main` is never consulted.

**Fixing main does not fix a broken tag.** A release that failed on
infrastructure cannot be re-run into success after the fix merges — it needs a
new tag. And a tag containing *an* attempt at the fix is not a tag that works:
ferallm v0.2.1 failed on a bug whose earlier, ineffective fix was already in
that tree. A fresh tag was cut rather than re-pointing the old one, which is
also the rule — re-pointing a published tag makes one version name mean two
different contents, the exact property the policy exists to protect. It costs
nothing when nothing was published under the old name.

## One version string means one artifact

Enforced by byte comparison at publish time, not by any version check. The
publisher compares the offered `.deb` against what is already in the pool:

- **identical bytes** — no-op, exits 0, "already published, identical bytes".
- **different bytes** — refuses and exits 1, printing both sha256 prefixes.
- **it never overwrites**, and publishing never deletes. Removal is explicit
  (`--retire <package> <version>`), because a retracted figure can be explained
  but not demonstrated once the build that produced it is no longer installable.

**This is the last line of defence and it fires late**, after a full build.
Nothing earlier catches a merge that changed packaged code without bumping the
version. That gap produced two collisions in one repo in a single day — 0.2.5
and 0.2.6 each published from one tree while master held a different tree under
the same version — and in the second case the published build had a feature
that hangs forever. A check that fails any PR touching packaged paths without
touching the manifest would close it; nothing implements that today.

Reproducible builds make a republish a clean no-op: a duplicate release of
ferallm v0.3.0 six minutes later on a different guest produced byte-identical
output and the publisher skipped it. Do not generalize from that — nothing in
the build declares reproducibility as a goal, so it can regress silently.

## The chain, tag to pool

1. The poller sees the tag and creates a release run keyed `{repo}#tag:{tag}`.
2. One experiment, **two jobs**: a guest job runs `.rack-release.sh` against the
   tree at `/home/anvil/src`, leaves packages in `dist/`, tars them to
   `/home/anvil/dist.tar` and uploads that as artifact `dist.tar`; and a `shell`
   job on the host holding the apt repo (delta, tag `validation`).
3. They meet at a barrier named `publish`, which the **build** job reaches last,
   so a failed build never holds the publish host. (See `vm-job` step 3 for why
   a barrier rather than a handshake.)
4. The publish job takes the newest artifact named `dist.tar`, unpacks it, and
   hands each `.deb` to the publisher on delta.
5. The publisher writes into `pool/main/` and regenerates the indexes by
   scanning the pool, so the index cannot drift from what is on disk.

The publish script is compiled into rack-ci via `include_str!`, so the copy on
delta and the copy rack-ci ships cannot diverge.

**Gotcha:** `SYSTEMSLAB_SERVER_URL` arrives from the agent with a trailing
slash, and `//api/v1/...` reaches the dashboard rather than the API. The script
strips it; anything else reading that variable must too.

## Reading the verdict

Context `rack-ci/release`. CI checks use `rack-ci/<check>`.

| Experiment outcome | Status | Meaning |
| --- | --- | --- |
| succeeded | Success, "published" | the `.deb` is in the pool |
| failure, source was fetched | Failure | the build ran and failed |
| failure, source never fetched | **Error** | the build never started — not a failing build |
| cancelled | Error, "cancelled" | |
| timeout, or still waiting | Error | |

The "never fetched" distinction is deliberate: a commit whose build never
started must not be reported as a failing build.

A publish job reading `cancelled` alongside a failed build is the barrier design
working, not a second fault — the build never reached the barrier, so the
publish runner was released instead of holding delta.

## Verifying a publish

"The publish job succeeded" is three layers above the claim. The full check is:

1. the index entry exists;
2. the file it names actually serves (HTTP 200, expected length);
3. the package parses — control fields (name, version, arch), dependencies
   satisfiable;
4. the payload contains what it should;
5. **the index's declared checksum matches the bytes served.**

The last is its own failure mode: an index can declare a hash that does not
match its file, and apt then refuses the download. Capturing independently —
once from index metadata, once from the downloaded bytes — is what establishes
it.

One more, if the release also deploys: **a script with an installed copy has two
versions and only one of them runs.** An apt publisher had a multi-architecture
fix committed for eight hours while `/usr/local/sbin` still held the old
single-arch copy, and the first real two-architecture publish failed in exactly
the way the fix existed to prevent. Editing the repo copy changed nothing.
