---
name: keep-backlog
description: Maintain a repository's backlog and NO-GO ledger in the place the repository already keeps them — check the ledger before starting work or accepting a proposal, answer a re-proposal with the recorded mechanism and reopen condition, give each item its source and state and each ordering its reason, change the backlog in the same PR as the journal entry that changes it, delete finished items instead of marking them done, and never delete a NO-GO. Use when deciding what to work on next; when someone proposes something that may already have been tried; when a journal entry opens, closes, or defers work; when grooming a backlog or roadmap file; and when asked to set up a backlog in a repository that has none.
---

# Keep a backlog

A backlog orders possible work; a NO-GO ledger records what was measured dead
so it is not tried again without new evidence. Both are indexes over the
journal: the reasoning for each item lives in a journal entry
(`keep-engineering-journal`), and the backlog points at it.

The failure this skill is built from is growth. One repository's roadmap
reached 3,508 lines, with three dated "Now" blocks kept "as history" and 78
items marked done; another's backlog reached 1,692 lines with 54 items marked
DONE or Closed, in a repository whose own journal skill said to remove them.
A finished item left in the file reads as open work to anyone who skims it,
and each one makes the file longer for every later reader.

## Inputs

- The repository and its `CLAUDE.md` / `AGENTS.md`.
- The question: what to do next, a proposal to check, a journal change to
  mirror, or a grooming request.

## 1. Find where the backlog lives

Check `CLAUDE.md`, then the tree: `docs/backlog.md`, `docs/ROADMAP.md`,
`ROADMAP.md`, a ledger section inside the journal index, or GitHub issues if
`CLAUDE.md` says issues are the backlog.

- **One exists:** use it and its format. Do not start a second one; a board
  and a file kept side by side diverge, and an agent reading the tree never
  sees the board.
- **None exists:** do not create one unasked. The journal's deferred items and
  `no-go` entries are the backlog until the user asks for a file. If asked,
  use the format below.

## 2. Check the ledger before starting or accepting work

Before picking up an item or answering a proposal:

```sh
grep -n -i '<topic>' docs/backlog.md docs/ROADMAP.md 2>/dev/null
grep -rl '^status: no-go' docs/journal/ | xargs grep -li '<topic>'
```

If the proposal matches a NO-GO, answer with the ledger line, the journal
path, and the reopen condition. Reopen only when the new evidence meets that
condition (new hardware, new data, a new regime, a measured threshold). A
preference is not new evidence. Reopening means a new journal entry that links
the old one.

## 3. Write each item with its source, state, and reason

```markdown
- **<item>** — <intent, one line>. State: Open | Next | Later | By design.
  Source: [entry](journal/YYYY-MM-DD-slug.md) or <origin: issue, request>.
  Reopen / start when: <condition, if gated>.
```

Order `Next` by the repository's axes (usually impact against cost) and write
the reason beside each item. A written order stands until new information
changes it, which stops the same list being re-argued at every planning
session.

NO-GO ledger lines carry what was tried, the mechanism, the evidence path,
and the reopen condition:

```markdown
- **Narrowing the compressed gather to top-k** — no effect at reachable
  contexts: dropping 83% of the key set at T=12000 moved decode +0.08%, inside
  a ±1% null. Evidence: <journal entry path>. Reopen when a same-context
  saving of 13% or more is measured; rerun at T≈32k first.
```

A reopen condition that names a measurement is the kind that can be checked.
"Revisit later" cannot.

An optional "operating discipline" section at the top holds the repository's
standing gates for starting work, each with the incident behind it (for
example: quality claims need at least 1,200 paired questions, because batch
nondeterminism was ±9.4 points at 64).

## 4. Change the backlog in the same PR as the journal

- An entry opens or updates with deferred items: add them, each linking the
  entry.
- An entry closes and completes or deprecates an item: **delete the item.**
  The journal entry and `git log` hold its history. Do not mark it done.
- An entry closes `no-go`: add a ledger line.
- A shipped entry resolves a ledger line's reopen condition: move the line to
  the new entry's outcome and remove it from the ledger, citing the entry.

A backlog that still lists finished work sends people to redo it.

## 5. Groom

When asked, or when a PR touches the file: merge duplicates, delete finished
items, drop dated "Now" blocks that a newer one replaced, re-check each
`Next` reason against current state, and confirm each source link resolves.
Groom by PR so the change is reviewed. Do not delete ledger lines or `By
design` limitations; those stay until their condition changes.

## 6. Hand off

Take the top `Next` item and open it with `keep-engineering-journal`: scope,
GO/NO-GO criteria, plan. The backlog item then points at that entry.

## Never

- **Never delete a NO-GO ledger line** except to move it to the entry that met
  its reopen condition.
- **Never reopen a NO-GO on preference**; name the new evidence and the
  condition it meets.
- **Never mark an item done and leave it**; delete it and let the journal hold
  the history.
- **Never create a backlog file or a second backlog** without the user asking.
- **Never add an item without a source** (journal entry, issue, or named
  request).
- **Never record a rejected idea only as a closed issue**; it gets re-proposed
  because nobody reading the tree finds it.
