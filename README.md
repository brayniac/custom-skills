# custom-skills

A personal library of agent skills, packaged as a Claude Code plugin. This
repository is both the plugin and the marketplace it is installed from. Each
skill is a directory under `skills/` holding a `SKILL.md`; Claude Code lists it
as `cs:<name>` and loads its instructions when the skill is invoked.

## Install

On any machine with Claude Code and git access to this repository
(`gh auth login`, or an SSH key GitHub accepts):

```sh
claude plugin marketplace add brayniac/custom-skills
claude plugin install --scope user custom-skills@custom-skills
```

Both commands run without prompts, so they work when provisioning a VM. Start a
new session, or run `/reload-plugins` in one that is open, and the skills are
listed as `cs:*`.

To pick up merged changes:

```sh
claude plugin update custom-skills@custom-skills
```

The plugin sets no `version`, so its version is the commit it was installed
from and every merge is an update. To have Claude Code update it in the
background instead, turn on **Enable auto-update** for the `custom-skills`
marketplace under `/plugin` → **Marketplaces**.

### On a machine with the repository checked out

Add the checkout instead of GitHub, and the plugin loads in place from it: an
edit takes effect at the next session start or after `/reload-plugins`, with
nothing to update.

```sh
claude plugin marketplace add ~/workspace/brayniac/custom-skills
claude plugin install --scope user custom-skills@custom-skills
```

A marketplace name is registered once per user, so remove the GitHub one first
(`claude plugin marketplace remove custom-skills`) if it is already added. For a
single session without installing, `claude --plugin-dir <checkout>` loads it.

### Moving from the MCP server

This repository used to build an MCP server, `custom-skills-mcp`. Once the plugin
is installed, remove the server so the skills are not listed twice:

```sh
claude mcp remove custom-skills --scope user
rm -f ~/.cargo/bin/custom-skills-mcp
```

## The review gate

The plugin installs one hook. It refuses a PR merge from a Bash command unless
the merge is pinned to a head commit with a review recorded on this machine:

```sh
gh pr merge <n> --repo <owner/repo> --match-head-commit <sha> --squash
```

`/cs:review` reviews a change with a fresh agent and, once its findings are
answered and its verdict is merge, records the head it read; `open-pr` and
`drive-pr-to-green` run it before opening and merging. `--match-head-commit`
makes GitHub refuse the merge if the head moved after the review. The SHA has to
be written out: the gate reads the command before the shell expands a variable.

The gate parses common shell forms: line continuations, comments, newlines and
`;`, `&&` and `|`, `if`/`for`/`while` bodies, wrappers such as `sudo` and
`xargs`, `bash -c`, `eval`, `$( )` and backticks, and heredocs and here-strings
a shell reads, and the command `ssh` runs on another host.
`hooks/review_gate.py` lists exactly what it reads. It refuses `--auto`, a pipe
into a shell in a command that mentions a merge, and `gh api` merges (the pull
merge and repository `merges` endpoints, and the merge, auto-merge and
merge-queue mutations). It does not see a gh alias, gh run from another
language, or a branch merged locally and pushed to the base (not a PR merge), it
does not check the base branch, and whether GitHub re-checks the pinned head
when a merge queue or auto-merge completes is untested. It is a backstop for an
agent that skipped the review, not an access control.

When the gate refuses a merge, it prints the command that records a review. For
a change with nothing to review, the same command takes `--waive "<reason>"` in
place of the verdict. Records are files under `~/.claude/cs-reviews`
(`CS_REVIEW_DIR` moves them), so a merge from another machine needs its own
record there. To turn the gate off, disable the plugin; removing
`hooks/hooks.json` lasts only until the plugin next updates.

## Add a skill

Create `skills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: What it does. Use when <the situation that should trigger it>.
---

# My skill

1. First step.
2. Read `${CLAUDE_SKILL_DIR}/references/table.md` for the details.
```

`name` must match `[a-z0-9_-]{1,64}` and equal the directory name. `description`
is the only text an agent sees when choosing a skill, so it carries the trigger;
Claude Code truncates it past 1,536 characters. Files beside `SKILL.md` are
named through `${CLAUDE_SKILL_DIR}`, which Claude Code replaces with the skill's
absolute directory, so a bundled script runs in place.

The `skill-authoring` skill says the same thing to an agent, with the rest of the
conventions.

## Checks

Claude Code loads a skill whose frontmatter does not parse with empty metadata,
so a broken skill drops out of the listing without an error, and
`claude plugin validate` checks only the manifests. The `check-skills` crate at
the repository root refuses those cases:

```sh
cargo run --quiet                 # check skills/
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
python3 hooks/test_review_gate.py  # the review gate, offline
claude plugin validate .          # manifests; a missing-version warning is expected
```

rack-ci runs all but the last (`.rack-ci.toml`).

## Layout

| Path | Responsibility |
| --- | --- |
| `.claude-plugin/plugin.json` | The plugin manifest |
| `.claude-plugin/marketplace.json` | The `custom-skills` marketplace, listing this repository as its one plugin |
| `skills/` | The skills |
| `hooks/` | `hooks.json` and the review gate (`review_gate.py`, its test) |
| `src/skill.rs` | The rules `check-skills` enforces, and their tests |
| `src/main.rs` | The `check-skills` command |

Directories under `skills/` may group skills: a directory holding a `SKILL.md` is
a skill, one holding only directories is a grouping level.

## Credit

The skill structure started from
[iopsystems/skills-mcp](https://github.com/iopsystems/skills-mcp).

Dual-licensed under MIT or Apache-2.0.
