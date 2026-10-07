# Sweeping comments

Design changes during a session are the main source of false comments: a
comment written for the third iteration still sits on the code of the
twelfth. This sweep removes what should not be there, corrects what is false,
and restores what an editor at that site needs.

`rust-conventions` has what Rust comments in these repositories carry and how
dense they run. `write-technical-prose` owns wording. This skill owns where a
fact goes, whether it is true, and whether it belongs at all.

What has evidence behind it and what does not: the claim check (step 5) and
the vantage list (step 4) come from reviewed incidents. The tiers, the form
ladder and the two-pass split are the source skill's design and have not been
measured.

## Inputs

- **Scope**: the diff range (`git diff <base>...HEAD --name-only`) or a file
  list. If none is given, ask; do not sweep the repository.
- **Mode**: `audit` reports findings and edits nothing; `fix` applies them.
  Default to `audit` when the request is a review.

## The two readers

A human reader arrives through the file: module doc first, then the items. A
coding agent arrives at one function by grep or symbol lookup and edits with
only that in view. Both can read code, so neither needs the code restated.
The difference is reading order, and it changes one thing: **a fact that
constrains edits must be readable at the site where a wrong edit would be
made**, not only at the module doc.

## Where a fact lives

Every fact lives at the narrowest scope within which it is true: the crate or
package doc for the system model, a module doc for a subsystem's protocol, a
type doc for its invariants, a function doc for the call contract, an inline
comment for a point fact. Each subsystem has one **model home**, usually its
module doc, that states the model once. Other sites carry only:

- facts from outside the code (vendor behaviour, measured values, why a
  number is what it is, wire formats, a deliberate absence, a promise about
  code that does not exist yet);
- deviations from the model;
- **edit constraints** — one sentence stating what must stay true, where the
  retrieval test below says yes;
- a pointer to the home, where the link is not obvious.

A restatement of the model anywhere else is an echo and is deleted.

**Retrieval test.** If a reader saw this site and nothing else, could they
make a wrong edit here that the model would have prevented, and would it
compile and pass? If yes, keep one sentence with its `must`, `may not` or
`never`. Examples: a clone that aliases instead of copying; a sequence another
file assumes is dense from 1; a store that must follow a push; a teardown
nothing enforces. Not edit constraints: anything the type checker rejects,
performance notes, and the model's rationale.

**Form**, cheapest first, stopping at the first that keeps every proposition
(`write-technical-prose` step 4): no comment; a better name (a comment
explaining a name is a bug report against the name); a trailing comment on
the line it qualifies; one line above; a doc paragraph for a caller-facing
contract; the model home. Comments may be fragments, but a fragment never
drops the modal, the subject of the claim, a negation or a scope qualifier.

## Procedure

Do the sweep yourself, in one context. Whether a comment earns its place
depends on the model home, its neighbours and the session's design changes,
which no per-file subagent has.

### 1. Partition the files by bar

Production, test, and demo or tutorial. Write the partition down first. A test
doc comment that restates the model it enforces is kept: when the test fails,
it names the promise that broke. A comment explaining a deliberately odd
fixture (a capacity below the append count, a failure scripted on the second
send) is kept, or the next editor simplifies the coverage away. Demo files are
teaching sites and are held to "teaches each idea once".

### 2. Inventory the models

List every design principle the touched code relies on, with its home and
whether that home is in the diff. **Inventory the subsystem, not the changed
lines**: a change that adds a consumer usually has its models homed in what it
consumes or one branch down a stack, and from inside the diff every echo looks
like a local keeper. A principle stated nowhere is the first fix.

### 3. Pass 1: subtract

Classify every comment:

- **derivable at the point of reading** — restates the next line, narrates
  control flow, walks through visible algebra, or explains language semantics
  (a `Relaxed` ordering justified by a lock visibly held in the same function):
  delete;
- **derivable only across files** — state it at the home; elsewhere a pointer,
  one edit-constraint sentence, or nothing;
- **from outside the code** — keep, one sentence per fact.

Then check each survivor against the current design: a comment naming
anything deleted or renamed is rewritten or deleted.

### 4. Remove the authoring session's vantage

Test each comment: could a reader at HEAD, with no access to the PR, the
review thread or the session, resolve every reference and verify every claim?
Restate the surviving fact in the present tense and delete the rest:

- change narration: "used to", "no longer", "the old X", "now" against a past
  state, "fixed the off-by-one";
- references only the author could see: "decision 3", "plan §4", "the
  approach above", "rejected in review", phase labels;
- argument with a reviewer: "this is safe because…" becomes the invariant;
- hedges: "should be enough for now" becomes the bound, or a `TODO` with an
  issue.

Keep issue references, present-tense counterfactuals ("without the fence, a
reader can observe a torn write"), measured bounds with the word "measured",
and runtime old/new ("the old connection drains before the new one accepts").
Grep probes for this step are in `sweep-comments-probes.md`, beside this file.

### 5. Check every surviving claim against the code

A comment can be well placed, terse, and false. A reviewer found three in a
change that had passed both a prose pass and this sweep:

- a test note said one direction was untestable because no producer attached
  metadata; four did, and a sibling test asserted one was forwarded. The claim
  was inherited from the old note and reworded without being checked;
- a field documented as "the hosts that read this stream" named hosts on which
  nothing read it; they consumed the data over another transport;
- a fixture "producing metadata the real producer could have written" took one
  field from the registry and hardcoded two, one invented.

For each kept or rewritten comment, list the claims a reader could check and
check each with one grep or one test name. Three shapes fail most: **absence
or exclusivity** ("no X yet", "only Y"); **equivalence** ("same as",
"mirrors"), where every field it covers needs checking; and **present-tense
who-does-what** ("reads", "consumes", "forwards"). A claim about the future
is written as one.

### 6. Report pass 1

One line per comment touched:

```
<file>:<line>: <tag> <what it said>. <what stands there now>.
```

Tags: `drop`, `point`, `shrink`, `inline`, `rename`, `correct` (the code
contradicted it), `restate` (vantage removed), `keep`. End with
`net: -N comment lines`. A clean result is stated the same way: "no
derivable or echoed comments in the touched files" is a claim that can be
checked.

### 7. Pass 2: restore

Walk the edit sites, meaning every place a future change could land, not only
where comments sit now. At each, run the retrieval test. Also add what a
caller needs and the code does not show: errors or panics, side effects,
ownership, timing, cancellation. This pass only keeps or adds; it does not
re-argue pass 1. Write down the sites and the sentence each now carries.
**An empty list on a diff that touches shared state is a pass that was not
run.**

### 8. Close

Check the commit message, the module docs and any diagram of the touched code
against the final design; they go stale on the same changes. Confirm the
sweep changed no behaviour: tests pass, and generated output is
byte-identical.

## Comments never to write

Commented-out code (git has it); a `TODO` with no issue or owner; section
banners (a file that needs them wants splitting); a doc comment written to
satisfy a linter on a trivial internal item (suppress the lint at the site); a
comment written to end a reviewer's question (answer in the thread); a
rationale you do not know to be true. Genericised examples of comments that
did not survive, and trims that changed a claim, are in
`sweep-comments-examples.md`, beside this file.

## Never

- **Never split the sweep across subagents.**
- **Never keep a comment because its topic sounds important.** The test is
  what it would cost to derive, not what it is about.
- **Never state one model in two places**; one home plus pointers, plus one
  sentence at each site that passes the retrieval test.
- **Never keep an absence, equivalence or who-does-what claim without a
  grep**, including one inherited from the comment you reworded.
- **Never drop a `must`, `may not`, `never`, `only` or negation** to shorten
  a comment.
- **Never report a sweep as prose**; one line per comment touched.
