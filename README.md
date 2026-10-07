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

Turn on auto-update, so each machine picks up every merge:

```sh
python3 - <<'PY'
import json, os
p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")), "settings.json")
d = json.load(open(p))
m = d.setdefault("extraKnownMarketplaces", {}).setdefault("custom-skills", {})
m["source"] = {"source": "github", "repo": "brayniac/custom-skills"}
m["autoUpdate"] = True
json.dump(d, open(p, "w"), indent=2)
PY
```

or toggle **Enable auto-update** for the marketplace under `/plugin` →
**Marketplaces**. Claude Code reads the flag from user settings, under
`extraKnownMarketplaces`. Without it, run
`claude plugin update custom-skills@custom-skills` after a merge. The plugin
sets no `version`, so its version is the commit it was installed from and every
merge is an update.

Every install, including one from a local checkout, runs from a copy Claude
Code takes at install time (`plugins/cache/custom-skills/custom-skills/<commit>`
in the config directory): an edit to a checkout, or a merge, reaches sessions
only after an update. `claude plugin list` shows the commit a config directory
runs.

Each Claude Code config directory (`CLAUDE_CONFIG_DIR`, such as `~/.claude`
and a second profile directory) has its own marketplaces, plugins and settings,
so install and turn on auto-update in each, with `CLAUDE_CONFIG_DIR` set for
the commands above. The `brayniac/infra` repository declares and checks this
for its Macs (`[claude]` in `fleet/hosts`, `host-setup/sync-claude-config`).

### Testing a change before it merges

`claude --plugin-dir <checkout>` loads a checkout for one session, without
touching the installed copy. Installed copies stay on `main`.

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
