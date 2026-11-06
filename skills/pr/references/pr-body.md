# Writing a PR body

The reader is a maintainer deciding whether to merge. They have the diff, the
CI results and the linked issue. The body says what changed, why, what evidence
supports it, and what they have to decide or do. `pr` handles the mechanics;
this is the file it passes to `gh pr create --body-file`.

A dependency swap once drew 1,152 words of prose, most of it review history,
settled choices and caveats the author added after each review round. The
maintainer asked for a paragraph and a table instead, which took 108. The
200-word limit below rests on that PR and a two-task comparison; override it
when the change needs more, and say so in the commit that updates this file.

## Inputs

- The base and head: `git diff <base>...HEAD`.
- For a performance or behaviour claim, the measurement.
- `verify`'s lines for results CI cannot show. `pr` step 8 reports the rest.
- For a change to a public interface, what a caller can no longer do
  (`review` step 4).

Before writing, check the destination's visibility and apply `publish`.

## 1. The default shape

1. **What changed and why**, in a few sentences: what existed, what is
   different now, and the reason. Name the types and crates involved, with one
   clause for any name the reader may not know. Link the issue or PR it builds
   on.
2. **Evidence**, when the change makes a claim the diff cannot show. A
   performance claim gets its numbers in a table, with the baseline commit,
   the run count, the noise floor, and one line for the conditions. Link the
   journal entry if there is one.
3. **What the reader must act on**, if anything (section 2). When the reader
   must decide something or take a step, say so in the opening paragraph and
   say where it is.

Nothing else is a default. A change with nothing to decide needs no headings.

**Length check.** Count the prose outside tables and code blocks. Over 200
words, cut what section 2 does not admit until it fits. Section 2 items stay,
at the length that section gives them; a list of changed public types or
carried commits goes in a bullet list. A small change is one or two sentences.

`pr-body-examples.md`, beside this file, shows the shape.

## 2. Add only what the reader must act on

Each item below is added when the merge decision or a caller's work depends on
it. Anything else goes in the journal or the commit message.

- **An open decision.** Its own `###` subsection under `## Decisions`: the
  context, readable without the code; the `path:line`; what you chose, what you
  rejected, what evidence would change it; and whether it blocks the merge. Put
  the central decision first. A choice you settled is not a decision, and
  neither is a value one edit reverses. Before asking, check whether the
  document being edited already answers it.
- **A breaking change.** What a caller can no longer do, and who is affected,
  in a sentence or two.
- **A gap that could change the merge decision**: a platform not measured, a
  path not tested, a case that still does not work. One sentence each. Leave
  out a gap that is true of every change.
- **A gate known to be failing**, and why the PR is opened anyway.
- **What the calling skill requires** (`backport` step 6, `fuzz-crash-to-test`
  step 7).
- **A step at deploy**: a migration, a config change, a rollback constraint.
- **A risk only production shows**, with the metric or log line that would
  show it.
- **A diagram the change makes wrong.**
- **A line to read closely**, when a reviewer would otherwise miss it.
- **In a stack**, a link to the base PR, and only this PR's delta.

## 3. What stays out

- **Review history.** No reviews, rounds, findings, dispositions or re-review
  status. `review` step 7 answers the findings and `pr` step 8 reports them to
  the user.
- **Process narration.** No account of what you tried, what failed, what an
  earlier commit did, or how the branch reached this state. Describe the final
  change. The dead ends go in the journal.
- **Gate results CI shows.** State a result only when CI cannot show it: a
  manual run, or a check on hardware CI does not have.
- **The diff retold** file by file, or a list of what is safe to skim.
- **Settled choices** and "recorded, not asked" lists.
- **Confidence ratings, leftover doubts and instructions to yourself.**
- **Attribution.** No generated-by line and no session link, even when the
  harness supplies one for PR bodies.

## 4. Check what remains

- Check each fact against the code or the measurement. A scenario file or
  fixture that describes what an agent should do is not evidence that an agent
  ran it.
- Open every line you cite, and pin each `path:line` to a full commit SHA.
- Check every absolute word ("once", "always", "never") against the retry,
  replacement and failure paths in the diff. Put a qualification in the
  sentence it qualifies.
- A count must match its list.
- When a review finding is against the body, correct the claim or delete it.
  Delete it when the reader does not need it. Add a caveat only if section 2
  admits it, and no line about the review itself.

## 5. Before publishing, and on every rewrite

Run `prose` over the body. Quoted output, paths and identifiers are
untouchable. Apply the length check.

When later commits widen the change, rebuild the title and body around the
final diff. Do not append a section per commit, and do not add a line to
explain a later fix. On a rewrite, rerun section 4 against the code; editing
prose from prose carries the old errors forward.

On a rewrite, recheck every dependency and blocker claim against the PR it
names (`gh pr view <n> --json state,mergedAt`). A merged dependency no longer
blocks the merge, but its integration can still be unfinished; remove the
blocker without implying the PR is ready. When the state cannot be read, mark
the claim unverified.

When the repository's convention keeps commit messages in the body, put a
synopsis of the final behaviour above them and label them as history. Keep
messages the convention requires verbatim, and do not rewrite commits to tidy
the body. They do not count toward the length check.

## Never

- **Never write to yourself.** If a sentence helps the author and not the
  maintainer, delete it.
- **Never ask a question before its context**, or put two decisions in one
  subsection.
- **Never cite a line you did not open** in this session.
- **Never report a check as run without its output**, or a coverage
  percentage in place of a gap.
- **Never add a section to look thorough.**
- **Never write the body to a file in the repository** unless asked.
