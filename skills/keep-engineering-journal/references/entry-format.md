# Entry format

Use this when a repository has no journal convention. When it has one, keep
it; this file is also the checklist for what an existing format must be able
to express.

## Path

`docs/journal/YYYY-MM-DD-short-slug.md`, dated by the day the entry was
opened. Some repositories use `YYYY-MM-slug.md`; keep whichever is there.

## Frontmatter and states

```yaml
---
status: open
opened: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Optional keys appear only when they apply: `superseded_by: <slug>` (required
with `superseded`), `issues: [123]`, `prs: [456]`, `beta_skills: [...]`
(`skill-use-appendix.md`).

| State | Meaning | Required in the body |
| --- | --- | --- |
| `open` | active, paused, or blocked | current result, or "outcome open"; for paused or blocked, the blocker and the restart condition |
| `shipped` | landed | what landed, PR or SHA, the verification command and result |
| `no-go` | rejected or falsified | what was tried, the mechanism, the numbers, a concrete reopen condition |
| `superseded` | replaced by another entry | `superseded_by` naming an entry that exists, and how it replaces this one |

Transitions: `open` to any terminal state; `shipped` or `no-go` to
`superseded` when a replacement exists. A terminal entry is never reopened in
place; open a new one that links it.

**Why fixed states.** Without them the status field fills with prose. In one
repository's 27 entries the status line read, among others: "closed (GO —
#274)", "NO-GO on the stated theory; the redirect it produced SHIPPED",
"shipped, default off", "phase 1 complete (192 arms, 189 gated in). Phases 2-4
open", and "NO-GO / retired". Each is accurate, and no index check can read
them. Keep the nuance in the first line of the body, and one of the four words
in frontmatter:

```markdown
---
status: shipped
---
# Direct-forward path, and gathering

Status: NO-GO on the stated theory (instr/byte 1.236 → 1.243); the gathering
change it led to shipped at +30% (1.236 → 0.906 instr/byte).
```

**A repository with a prose status line and no frontmatter** keeps its format.
Start new status lines with one of its own declared keywords (for example
`open | shipped | NO-GO | withdrawn`) so the index can still be checked, and
put the qualifier after an em dash. Do not migrate old entries.

**Mixed outcomes.** Record the state of what landed. A NO-GO on the original
theory that produced a shipped change is `shipped`, with the NO-GO in the
status line and body. If the NO-GO deserves its own ledger line, add it to the
backlog's ledger (`keep-backlog`).

## Headings

A new convention may start with:

```markdown
# <Effort title — a claim is better than a topic>

## Goal
## Decision Criteria      (GO/NO-GO; omit only when there is no gate)
## Scope
## Evidence
## Design and Implementation
## Outcome
## Ruled Out              (refuted hypotheses, knobs that did nothing)
## Deferred or Reopen Items
```

Titles that state the finding ("Prefaulting pays only when THP backs the
pool") let the index be read without opening entries.

Scale the entry to the effort. For a small effort three sections are enough:

```markdown
## What      (the effort or problem, one or two sentences)
## Decided   (what was decided and why)
## Open      (what is unresolved)
```

A short honest entry is better than a long reconstructed one.

## Index

`docs/journal/README.md`, newest first:

```markdown
# Engineering journal

One in-repo record per non-trivial effort. Entry frontmatter is authoritative
for state.

| Opened | Effort | Status | Result |
| --- | --- | --- | --- |
| 2026-09-17 | [Prefaulting the buffer pools](2026-09-17-prefault.md) | shipped | −32% ramp p999 at a 512 MiB ring; null at the default |
```

The Result column carries the headline number or the NO-GO mechanism in one
line. An index that shows only titles makes a reader open every entry to find
the one that answers their question.

Retrospective entries (reconstructed from history rather than written during
the work) say so in their status line.
