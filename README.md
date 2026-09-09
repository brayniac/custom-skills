# custom-skills

A single-binary [Model Context Protocol](https://modelcontextprotocol.io) server
that serves a personal library of agent skills. Each skill is one Markdown file;
the server exposes each as an MCP tool, so any MCP-capable agent picks them up
from its tool list without anything being copied into your projects.

Calling a skill tool returns its instructions. That is the whole contract — the
server reads, never writes.

## Why a server instead of files in each repo

A skill kept in `.claude/skills/` belongs to one checkout. Keeping the library in
one binary means every project that connects to the server sees the same skills,
an improvement lands everywhere at once, and nothing has to be copied or synced
into a repository that does not want it.

## Install

```sh
cargo install --path .
```

That puts `custom-skills-mcp` in `~/.cargo/bin`. For a contributor build, use
`cargo build --locked`; the debug binary is `target/debug/custom-skills-mcp`.

## Connect it

The server speaks JSON-RPC over stdin/stdout and has no command-line interface —
you never run it by hand. Your client spawns it.

For Claude Code:

```sh
claude mcp add --scope user custom-skills -- "$(command -v custom-skills-mcp)"
```

For any client that takes JSON configuration:

```json
{
  "mcpServers": {
    "custom-skills": {
      "command": "/absolute/path/to/custom-skills-mcp"
    }
  }
}
```

Use the absolute path from `command -v custom-skills-mcp` when the client does
not inherit your shell `PATH`. Reconnect the client and confirm `skill_catalog`
appears in its tool list.

## The tools

| Tool | What it does |
| --- | --- |
| one per skill | Returns that skill's instructions for the agent to follow. |
| `skill_catalog` | Lists every skill with its description, source, and files. Metadata only. |
| `skill_resource` | Returns one file sitting beside a skill's `SKILL.md`, by skill name and relative path. |

`skill_resource` is how a skill carries more than fits in a body worth reading
every time: put the long table or template in `references/` and name it in the
body. It resolves paths only inside the skill's own directory.

## Add a skill

Create `skills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: What it does. Use when <the situation that should trigger it>.
---

# My skill

1. First step.
2. Second step.
```

`name` becomes the tool name and must match `[a-z0-9_-]{1,64}`. `description` is
the only text an agent sees when choosing between tools, so it carries the
trigger. Everything below the frontmatter is what the tool returns.

Then `cargo build && ./scripts/smoke.sh`. The server refuses to start on a
malformed skill — bad frontmatter, a duplicate name, a directory holding neither
a `SKILL.md` nor further skill directories — rather than serving a library with a
hole in it.

The `skill-authoring` skill in this repository says the same thing to an agent;
ask yours to call it.

## Iterate without rebuilding

`skills/` is compiled into the binary, so a change needs a rebuild. While
drafting, point `CUSTOM_SKILLS_PATH` at one or more directories instead and just
restart the client:

```sh
CUSTOM_SKILLS_PATH=~/drafts/skills custom-skills-mcp
```

Roots are separated like `PATH`, are searched recursively, and override embedded
skills by name — the last root wins, so the directory you are editing is the one
that is served. Move the skill into `skills/` once it settles.

## Layout

| Path | Responsibility |
| --- | --- |
| `src/main.rs` | MCP initialization, tool schemas, routing, responses |
| `src/skill.rs` | Skill discovery, frontmatter parsing, resource access |
| `skills/` | The skills, embedded at compile time |
| `build.rs` | Rebuild when a skill file is added |
| `scripts/smoke.sh` | End-to-end check of the real MCP exchange |

Directories under `skills/` may group skills: a directory holding a `SKILL.md` is
a skill, one holding only directories is a grouping level.

## Checks

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --locked && ./scripts/smoke.sh   # needs jq
```

## Debugging the raw protocol

Each request is one JSON line:

```sh
(
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"manual","version":"0.1.0"}}}'
  printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
  printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
  printf '%s\n' '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"skill_catalog","arguments":{}}}'
) | ./target/debug/custom-skills-mcp | jq
```

Responses are JSON lines on stdout; diagnostics go to stderr, and
`RUST_LOG=info` turns them on.

## Credit

The structure follows [iopsystems/skills-mcp](https://github.com/iopsystems/skills-mcp),
reduced to the skill-serving core.

Dual-licensed under MIT or Apache-2.0.
