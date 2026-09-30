# custom-skills

A personal library of agent skills, packaged as a Claude Code plugin. This
repository is both the plugin and the marketplace it is installed from. Each
skill is a directory under `skills/` holding a `SKILL.md`; Claude Code lists it
as `custom-skills:<name>` and loads its instructions when the skill is invoked.

## Install

On any machine with Claude Code and git access to this private repository
(`gh auth login`, or an SSH key GitHub accepts):

```sh
claude plugin marketplace add brayniac/custom-skills
claude plugin install --scope user custom-skills@custom-skills
```

Both commands run without prompts, so they work when provisioning a VM. Start a
new session, or run `/reload-plugins` in one that is open, and the skills are
listed as `custom-skills:*`.

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
claude plugin validate .          # manifests; a missing-version warning is expected
```

rack-ci runs the first four (`.rack-ci.toml`).

## Layout

| Path | Responsibility |
| --- | --- |
| `.claude-plugin/plugin.json` | The plugin manifest |
| `.claude-plugin/marketplace.json` | The `custom-skills` marketplace, listing this repository as its one plugin |
| `skills/` | The skills |
| `src/skill.rs` | The rules `check-skills` enforces, and their tests |
| `src/main.rs` | The `check-skills` command |

Directories under `skills/` may group skills: a directory holding a `SKILL.md` is
a skill, one holding only directories is a grouping level.

## Credit

The skill structure started from
[iopsystems/skills-mcp](https://github.com/iopsystems/skills-mcp).

Dual-licensed under MIT or Apache-2.0.
