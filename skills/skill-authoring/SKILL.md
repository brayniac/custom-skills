---
name: skill-authoring
description: Add or revise a skill served by this MCP server. Use when the user wants a new custom skill, wants an existing one changed, or asks how skills in this repository are structured.
---

# Authoring a skill

A skill is one directory under `skills/` holding a `SKILL.md`. The server turns
each one into an MCP tool: the tool's name and description come from the
frontmatter, and calling it returns everything below the frontmatter.

## Steps

1. **Name it.** Pick a verb-first, hyphenated name — `review-guide`, not
   `reviewer`. The name is the tool name, so it must match `[a-z0-9_-]{1,64}`
   and cannot be `skill_catalog` or `skill_resource`.

2. **Create `skills/<name>/SKILL.md`** with the frontmatter contract in
   `references/frontmatter.md` (read it with `skill_resource`).

3. **Write the description for a reader who has not seen the body.** It is the
   only thing an agent sees when deciding whether to call the tool, so say what
   the skill does *and* when to reach for it. "Use when …" earns its place here.

4. **Write the body as instructions to an agent, not documentation for a
   person.** Numbered steps, explicit inputs, explicit stopping conditions. State
   what the skill must not do — those lines do more work than the happy path.

5. **Put long material in sibling files** rather than inline: a reference table,
   a template, a checklist. Name them in the body and say to fetch them with
   `skill_resource`, so the body stays short enough to be read every time.

6. **Rebuild and check.** `cargo test` covers loading and routing;
   `./scripts/smoke.sh` shows the real `tools/list` and `tools/call` responses.

## While iterating

Point `CUSTOM_SKILLS_PATH` at a directory of skills and restart the client to
reload — no rebuild. Move the skill into `skills/` once it settles, so it ships
with the binary.

## Constraints

- Do not add a skill whose body only restates its description; a skill earns its
  place by carrying detail the agent would otherwise guess at.
- Do not make a skill that writes files as a side effect of being read. A skill
  returns instructions; the agent and the user decide what happens next.
