# Frontmatter contract

Every `SKILL.md` opens with YAML frontmatter between `---` fences:

```markdown
---
name: review-guide
description: Write a pull-request body as a guide for the reviewer. Use when opening a PR whose diff is large enough that reading order matters.
---

# Review guide

1. ...
```

## Fields

| Field | Required | Rules |
| --- | --- | --- |
| `name` | yes | 1–64 chars, `[a-z0-9_-]` only, equal to the skill's directory name. Claude Code lists it as `cs:<name>`. Unique across the tree, including grouping directories. |
| `description` | yes | Non-empty, at most 1,536 characters (Claude Code truncates past that). It is the only text an agent sees when choosing a skill. What it does, then when to use it, ending with "Use when …" and a list of the situations. These run a few lines; a short description is how a skill fails to be chosen. |

No other key is accepted. Claude Code supports more (`allowed-tools`,
`when_to_use`, `disable-model-invocation`, and others); add one to the
`Frontmatter` struct in `src/skill.rs` when a skill needs it, so a misspelled key
still fails the check instead of being ignored.

## Body

Everything after the closing `---` is loaded when the skill is invoked, with
`${CLAUDE_SKILL_DIR}` replaced by the skill's absolute directory. Name sibling
files through it.

## Failure modes

Claude Code loads a skill whose frontmatter does not parse with empty metadata,
so the skill drops out of the listing with no error, and `claude plugin validate`
does not inspect skills. `cargo run --quiet` refuses, and exits 1 on:

- missing frontmatter, or frontmatter that is not YAML with exactly `name` and
  `description`;
- a `name` outside the character set, or different from its directory;
- an empty description, or one over 1,536 characters;
- two skills with one name;
- a directory under `skills/` holding neither a `SKILL.md` nor further skill
  directories;
- a `${CLAUDE_SKILL_DIR}` path in a body that names no file, or a file outside
  `skills/`. A path containing `<` is a placeholder and is not checked.
