# Writing a PR body

The reviewer already has the diff. The body does not summarise it. It says
why the change exists, where a reviewer's limited attention is best spent, and
what the author could not settle. `open-pr` handles the mechanics; this is
the body it passes to `gh pr create --body-file`.

The rules below came from one reader's reports on about a dozen bodies across
two repositories, each report against a specific body. Every one was invisible
to the author and to automated review. They have not been measured beyond
that; when one fights the change in front of you, override it and say so in
the commit that updates this file.

## Inputs

- The base and head: `git diff <base>...HEAD`, and the head SHA the body is
  pinned to.
- The per-gate lines from `verify-change`.
- For a change to a public interface, what a caller can no longer do
  (`review` step 4).

Before writing, check the destination's visibility and apply
`publishing-findings`.

## 1. Decide whether there is anything to guide

A body earns more than a sentence when it carries at least one thing the
reviewer cannot get from the diff:

- a reading order different from the diff's file order;
- a test gap;
- a judgement call;
- a risk that only production can show.

If all four are empty, write one sentence describing the change and one
saying you checked those four and found nothing. Silence reads the same as
not having looked.

Length follows what the change carries. A 32-line, one-file README change once
drew a 733-word body with seven headings; three drafts brought it to 216. Its
testing section said "no test covers README content", which is true of every
documentation change. **A heading is earned by its content**: an answer that
needs a clause is a clause in the opening paragraph.

## 2. Build the reviewer's model before naming anything

Six bodies for one stacked series each opened on a reading order and named
types the reviewer had not met. In the order below, before any section that
names a type, establish:

1. what the system does at the level this change touches, in the domain's
   terms;
2. the two or three concepts the change depends on, each named once and
   reused;
3. where this change sits among them.

State the starting point you assume, and name where to skip to by the
section's exact heading. Write every explanation as **before, problem,
change**: the arrangement that worked, what arrived or stopped being true, and
the change as the response. Each beat appears once; the common inflation is
stating the "before" a second time as the problem.

An identifier this change adds introduces itself. One that already existed
needs one clause in the "before" beat saying what its job is. A diagram goes
here when the concepts have a shape (a topology, a pipeline, a before and
after); link a checked-in one, or inline mermaid small enough to read without
scrolling. Say so when the change makes an existing diagram wrong.

In a stack, write the model once in the base PR's body, link it from each PR
above by number, and state only this PR's delta. The six stacked bodies above
carried five near-identical models, about 1,650 words of duplicate text.

## 3. Decisions

This is the section a reviewer cannot reconstruct alone. Order it by
centrality: first the decision the change exists to make, then one line
saying the rest is lower stakes, then the rest. Presented side by side, a
leftover doubt and the central question read as equal weight, and the
reviewer answers the easier one.

Each decision gets its own `###` subsection, in this order:

1. **context** — the arrangement and what forces a choice, readable without
   the code;
2. **reference** — `path:line` where the choice is made;
3. **question** — what was chosen, what was rejected, what evidence would
   change it, whether it blocks the merge, and whether it needs a decision, a
   confirmation of fact or an acceptance of risk.

A first attempt put the questions in a list at the top. In five of six bodies
the items used terms introduced two sections later, and each reappeared below
at greater length (854 words previewing 1,335). The reviewer cannot answer a
question before reading the context it depends on.

Not every question earns a subsection. Put in a one-line "recorded, not
asked" list any call whose context is already visible in the diff, and any
call about a value (a width, a name, a threshold) that one edit reverses. A
label-width question once took 323 words, 44% of its body. Before asking
anything, check whether the document being edited already answers it: a body
once asked whether an exception was justified when the skill it changed
granted that exception in two places.

Every item cites evidence (an ambiguous requirement quoted, an untested path,
an unverified assumption, a measurement not taken). Without the call, the
alternative and what would change it, drop it. Do not rate confidence. Do not
manufacture doubt, and do not present one reading of an ambiguous requirement
as the only one. If nothing was genuinely open, say so and why.

Worked examples of a summary, a decision subsection and a glossed "before"
beat are in `pr-body-examples.md`, beside this file.

## 4. Where to look more closely

Rank by the cost of a missed defect times the chance the reviewer misses it:

1. code carrying a judgement call;
2. code whose correctness depends on something outside the diff;
3. code no test covers;
4. code you are least sure of.

Then name what is safe to skim and why: generated output, mechanical renames,
formatting. Point at a line, not a module, and **open every line you cite in
this session**. One body cited three ranges each off by a section because the
numbers were estimated; another read four anchors and estimated the fifth,
which was wrong. State near the top which commit the line numbers are pinned
to.

## 5. Testing

For each surface the repository has (unit, integration, smoke, benchmark,
property or fuzz, manual): whether it ran, the real command and its real
result, and what it does not cover. "All tests pass" is not a report; "136
tests pass across seven binaries; none exercise the publish path" is. Take the
lines from `verify-change`. Never state a command ran when it did not; name a
skipped check and why. No coverage percentages.

## 6. Production-only risks

List what cannot show before deployment (scale, real data shape, timing and
partial failure across hosts, configuration drift, migration and rollback,
upstream behaviour) and, for each, what would surface it: a metric, a log
line, an alert. Say which risks want a judgement and which want an
acceptance.

## 7. Write the summary last, at the top

Above every heading, answer in order: why this change is needed, the one idea
it turns on, and what is true once it lands, including what still does not
work. A small change answers all three in one sentence. **No type, field,
function, flag or path in the summary**; the reviewer cannot resolve a name
before the model exists. Test: could someone who has not seen the codebase say
what problem the change solves?

Close with the ask as its own paragraph, pointing rather than restating:
"Two decisions want your opinion, one blocking; each is a subsection under
Decisions." When nothing needs the reviewer, say so. A count must match the
list; "two things want your opinion" once sat above three.

## 8. Before publishing, and on every rewrite

Run `write-technical-prose` over the body. Quoted output, paths and
identifiers are untouchable. When rewriting any section, reread the code
behind it first; a reader's confusion is evidence the claim may be wrong, and
editing prose from prose carries the old errors forward.

## Never

- **Never retell the diff file by file**, or order the reading list by path.
- **Never open with a heading**, or put an identifier in the summary.
- **Never ask a question before its context**, or put two decisions in one
  subsection.
- **Never cite a line you did not open** in this session.
- **Never report a check as run without its output**, or a coverage
  percentage in place of a gap.
- **Never pad to look thorough**; a padded body teaches the reviewer to skim
  the next one.
- **Never write the body to a file in the repository** unless asked.
