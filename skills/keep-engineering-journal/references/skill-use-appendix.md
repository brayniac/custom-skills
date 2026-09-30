# Skills-invoked appendix and skill feedback

Keep this only in a repository whose entries already end with
`## Appendix: Skills Invoked`, or whose `CLAUDE.md` asks for it. Do not add it
to a repository that does not use it, and never backfill it into older
entries.

It exists so a later survey can find which skills were used on real work and
where a skill's instructions misfired. That survey reads what the entries say;
it cannot tell an observed roster from a reconstructed one. The rules below
are there to make an honest roster easier to write than an invented one.

## The roster

```markdown
## Appendix: Skills Invoked

- `architecture-diagram` (beta) — derivation and render checks for figures.
- `verify-change` — gates before the close-out push.
```

- The roster covers the whole effort. On update, append; do not rewrite it
  down to what this session remembers.
- List only skills actually invoked.
- After a compaction, a handoff, or a resumed effort, say in one line that the
  earlier record is incomplete. Do not infer a plausible list.
- Omit the appendix when no skill was invoked.

## Beta-skill feedback

A skill is beta when its own text or manifest says so, or the user says so.
One bad result does not make a skill beta. For each beta skill: mark it
`(beta)` in the roster, list it in `beta_skills:` frontmatter, and add:

```markdown
## Skill Feedback

### architecture-diagram (beta)

- **Friction** — what was asked, which instruction misfired, what was done
  instead.
- **Confirmation** — a default that held under real use.
```

Record confirmations as well as friction; a list of complaints alone biases
the decision to promote or drop the skill. Drop any friction item that cannot
name the ask, the instruction, and the deviation. A usable example from one
entry: the skill's dead-end list warned only about Unicode circled digits in
SVG text, and the failing class was any non-ASCII symbol (`≤`, `→`, `∧`)
rendering as missing glyphs under the fallback font.

The record is advisory. Do not edit the skill, open an issue, or send the
feedback anywhere unless the user asks separately.

## Reconciliation checks

- `beta_skills` matches the `###` subsections under `## Skill Feedback`.
- Every skill named in the feedback appears in the roster.
- An entry with `## Skill Feedback` has a non-empty `beta_skills`.
