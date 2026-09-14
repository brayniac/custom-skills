# custom-skills

A single-binary MCP server (`custom-skills-mcp`) that serves a personal library
of agent skills over stdio. Each `skills/<name>/SKILL.md` becomes one MCP tool
whose call returns the skill's body. Two Rust-backed tools round it out:
`skill_catalog` (metadata) and `skill_resource` (one file beside a `SKILL.md`).

Most work here is **writing skills**, not changing the server. The server is
~830 lines including tests and stable; the library is where the content lives.

README.md covers install, client wiring, and raw-protocol debugging. This file
covers what is not obvious from reading the code.

## Checks

Run all four before claiming a change is done — CI runs exactly these:

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --locked && ./scripts/smoke.sh   # needs jq
```

`scripts/smoke.sh` drives the real JSON-RPC exchange against
`target/debug/custom-skills-mcp`, so it needs a build first. It asserts on
`skill-authoring` specifically — renaming or restructuring that skill means
updating the script's `jq` checks.

## Invariants

- **The server never writes.** Every tool is annotated read-only. A skill
  returns instructions; the agent and the user decide what happens next. Do not
  add a tool or a skill that has a side effect.
- **Fail fast at load, never serve a library with a hole in it.** Malformed
  frontmatter, a bad name, an empty description, a duplicate name within a root,
  or a directory under `skills/` holding neither a `SKILL.md` nor further skill
  directories all abort startup. Keep it that way — silently skipping a
  misfiled skill is how it disappears from the tool list unnoticed.
- **`skill_resource` resolves only inside a skill's own directory.** Traversal
  is rejected for both embedded and on-disk skills, and there are tests for it.
- Skill names must match `[a-z0-9_-]{1,64}` and may not collide with
  `skill_catalog` or `skill_resource`; tool lists are sorted and deduped.

## Adding or changing a skill

The `skill-authoring` skill (`skills/skill-authoring/SKILL.md`) is the
authoritative process; read it before writing one. In short:

1. `skills/<name>/SKILL.md`, verb-first hyphenated name, YAML frontmatter with
   `name` and `description`.
2. The `description` is the only text an agent sees when choosing a tool — it
   states what the skill does *and* ends with "Use when …". These run long (a
   few lines); that is deliberate, not sloppy.
3. The body is instructions to an agent: numbered steps, explicit inputs,
   explicit stopping conditions, and explicit "do not" lines.
4. Long material goes in `skills/<name>/references/*.md`, named in the body with
   an instruction to fetch it via `skill_resource`, so the body stays short
   enough to read every time.
5. `cargo build && ./scripts/smoke.sh`.

Conventions the existing skills follow:

- Prose wraps at 80 columns. Frontmatter `description` and Markdown tables are
  the exceptions and run long on one line.
- Skills cross-reference each other by name in backticks (`` `analyze-noise` ``,
  `` `measure-performance` step 5 ``) rather than restating the other skill.
  Keep those references accurate when a skill is renamed or its steps are
  renumbered.
- `skills/` is a flat list today, but nested directories are legal as grouping
  levels — a directory with a `SKILL.md` is a skill, one with only directories
  is a group.

### Iterating without a rebuild

`skills/` is `include_dir!`-embedded at compile time. While drafting, point
`CUSTOM_SKILLS_PATH` (PATH-separated roots, searched recursively) at a draft
directory and restart the client instead of rebuilding. Disk roots override
embedded skills by name and the **last** root wins. Move the skill into
`skills/` once it settles.

`build.rs` watches `skills/` so a *newly added* file triggers a rebuild;
`include_dir!` alone would not notice one.

## Layout

| Path | Responsibility |
| --- | --- |
| `src/main.rs` | MCP init, tool schemas, routing, responses, server tests |
| `src/skill.rs` | Discovery, frontmatter parsing, resource access, loader tests |
| `skills/` | The skills, embedded at compile time |
| `build.rs` | Rebuild when a skill file is added |
| `scripts/smoke.sh` | End-to-end check of the real MCP exchange |

Tests live inline in `#[cfg(test)]` modules; `tests/` is empty. New server
behavior gets a unit test next to it.

## Commits

Subject lines are sentence-case statements of what changed and why it matters,
often `<verb> <thing>: <the point>` — "Add calibrate-to-source: what travels,
and what a local null costs", "Correct the W1 ratio's meaning, and add the
reading that replaces it". Not conventional-commit prefixes.

Bodies are substantial when the change is substantial: for a skill carrying an
empirical claim, the body records the evidence — what was measured, across
what, and what the numbers were — because that reasoning has no other home in
the repo. A correction says plainly what was wrong and what replaced it.
