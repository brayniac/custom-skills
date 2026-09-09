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
| `name` | yes | 1–64 chars, `[a-z0-9_-]` only. Becomes the MCP tool name; must be unique across every skill root, and may not be `skill_catalog` or `skill_resource`. |
| `description` | yes | Non-empty. Becomes the MCP tool description — the only text an agent sees when choosing a tool. One or two sentences: what it does, then when to use it. |

Unknown keys are ignored, so a skill may carry its own metadata for other
tooling without breaking the server.

## Body

Everything after the closing `---` is the tool's return value, verbatim, with
leading blank lines trimmed. It is Markdown by convention only — the server does
not parse it.

## Failure modes

The server refuses to start rather than serving a broken library, so any of
these stops it at load time:

- missing or malformed frontmatter;
- a `name` outside the allowed character set, or an empty `description`;
- two skills claiming the same `name` within one root;
- a directory under a skill root holding neither a `SKILL.md` nor further skill
  directories — that shape means a misfiled skill nobody would serve.
