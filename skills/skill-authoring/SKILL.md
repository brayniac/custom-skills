---
name: skill-authoring
description: Add or revise a skill in the custom-skills Claude Code plugin — name, frontmatter, body, sibling files addressed through ${CLAUDE_SKILL_DIR}, the repository's check, and a test against a baseline agent. Use when the user wants a new custom skill, wants an existing one changed, or asks how skills in this repository are structured.
---

# Authoring a skill

A skill is one directory under `skills/` holding a `SKILL.md`. The repository
is a Claude Code plugin, and its own marketplace: Claude Code lists each skill
as `custom-skills:<name>` with its description, and loads everything below the
frontmatter when the skill is invoked.

## Steps

1. **Name it.** Pick a verb-first, hyphenated name — `review-guide`, not
   `reviewer`. It must match `[a-z0-9_-]{1,64}` and equal the directory name.

2. **Create `skills/<name>/SKILL.md`** with the frontmatter contract in
   `${CLAUDE_SKILL_DIR}/references/frontmatter.md`.

3. **Write the description for a reader who has not seen the body.** It is the
   only thing an agent sees when deciding whether to invoke the skill, so say what
   the skill does *and* when to reach for it. "Use when …" earns its place here.

4. **Write the body as instructions to an agent, not documentation for a
   person.** Numbered steps, explicit inputs, explicit stopping conditions. State
   what the skill must not do — those lines do more work than the happy path.
   Run `write-technical-prose` over the body before committing. A 376-word
   section added to a PR-body skill to say "use plain words" lost nothing
   when cut to 151.

5. **Put long material in sibling files** rather than inline: a reference table,
   a template, a checklist, a script. Name each in the body as
   `${CLAUDE_SKILL_DIR}/references/<file>`, which Claude Code replaces with the
   skill's absolute directory; a script runs in place from there. A bare
   `references/<file>` resolves against the session's working directory, not
   the skill's. Another skill's file is
   `${CLAUDE_SKILL_DIR}/../<other>/references/<file>`.

6. **Run the check.** `cargo run --quiet` (the `check-skills` crate at the
   repository root) refuses what Claude Code would load wrongly without an
   error: frontmatter that is not YAML with exactly `name` and `description`,
   a name that differs from its directory, a description over 1,536
   characters, a directory holding no skill, and a `${CLAUDE_SKILL_DIR}` path
   that names no file. `claude plugin validate .` checks the manifests only; it
   passed a skill with broken YAML.

7. **Check that the skill changes what an agent does.** Loading proves the
   file parses, not that it helps. For a skill that corrects a behaviour, give
   a fresh agent (no skill) a realistic task that invites the mistake and
   record what it does, in its own words; then repeat with the skill available
   and compare. Two things to look for: whether the agent calls the skill at
   all from its description, and whether it follows the body or only the
   description — a description that summarises the steps can be followed
   instead of the body. Put what was observed in the commit body. If the
   baseline agent already does the right thing, the skill is not needed.

## While iterating

On a machine with this repository checked out, add the checkout as a
local-directory marketplace (`claude plugin marketplace add <path>`): the plugin
then loads in place, and an edit takes effect at the next session or after
`/reload-plugins`. For one session only, `claude --plugin-dir <path>` does the
same without installing. Installs from GitHub pick up a merged change with
`claude plugin update custom-skills@custom-skills`.

The listing budget is about 1% of the context window by default, and
descriptions past it are dropped starting with the least-used skills. The
check prints the total; if it grows past what the listing holds, check
`/context`, then shorten descriptions or raise `skillListingBudgetFraction`.

## Constraints

- Do not add a skill whose body only restates its description; a skill earns its
  place by carrying detail the agent would otherwise guess at.
- Do not make a skill that writes files as a side effect of being read. A skill
  returns instructions; the agent and the user decide what happens next. A
  script beside it runs only when the body tells the agent to run it.
- Do not make a skill depend on another repository being checked out. It must
  work on a new host with only this plugin installed: ship the script, the
  config values, and the endpoints in the skill.
