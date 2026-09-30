---
name: write-technical-prose
description: Write or revise technical prose for a named reader — name the reader and what they lack, cold-read for phrases that resolve only for someone who was in the session, list every proposition before cutting so a shorter sentence does not become a different claim, keep requirement modality (`must`, `may not`, `never`), replace words that carry no fact with the fact, keep one name per thing, and stop at the least material that carries the fact. Use when asked to tighten, plain-language, de-slop or cold-read a commit body, PR body, README, doc comment, design note, issue or skill; when another skill defers here for wording; and before publishing prose written in the same session as the work it describes.
---

# Write technical prose

The writing rules in `~/.claude/CLAUDE.md` already apply to all output: no
metaphor, aphorisms, reframes, drumroll fragments or stock phrases. This skill
does not restate them. It adds what those rules do not cover: who the reader
is, which words change the claim, and how much material to write.

Comment placement and form belong to `sweep-comments`, which allows a comment
to be a fragment. That is a label under a declaration, not the dramatic-beat
fragment `CLAUDE.md` bans. This skill rules on words and on how many claims a
sentence carries; the calling skill rules on sentence shape.

## 1. Name the reader before changing a word

Say who will read this and what they lack that you hold now: the diff, the
thread, the session, the last hour. Take the reader from the user or the
calling skill if one is named; otherwise infer it from the artifact. A doc
comment is read by the file's next editor. A commit body is read by someone
with the log and the diff open. A backlog line or a grep hit is read with
nothing else. **If neither settles it, ask.** A guessed reader is the writer's
own assumption, and the writer is the one person who cannot check it.

## 2. Cold-read as that reader

Reread as the named reader. Every phrase that resolves only because you were
in the room gets its referent stated: "this arc" becomes the review it names,
"the fix" becomes what changed, "operator-chosen label" becomes what the label
is and where it is set.

Do this before the word pass. Tightening cannot find a missing noun. Two
successive rewrites of one commit body each passed every style rule and each
carried an unresolved referent through untouched ("operator-chosen label",
then "this arc"). A reader asking "what's that?" caught both.

## 3. If you are rewriting, check the claims against the source

Rewording re-asserts every claim under your name. Before rewriting a
paragraph about code, reread the code it describes. A comment saying "no
producer attaches metadata yet" went through a prose pass and a comment sweep
and survived both, in a crate whose own test asserted a producer did. A PR
body rewritten from its previous draft kept a "before" state that had never
existed, in well-formed sentences.

When a reader says a passage does not make sense, first check whether the
claim is wrong. Rewording is faster than rereading, which is why it is the
wrong first move.

## 4. List the propositions before cutting

For each passage you shorten, write down what it asserts:

- the actor and the action;
- conditions, timing and ordering;
- modality (`must`, `may`, `may not`, `never`);
- negations, exceptions and scope qualifiers (`only`, `at most`);
- ownership, side effects, failure behaviour and consequence;
- provenance (`measured`, `derived`, `given`, as in `publishing-findings`).

A cut is available only if every one survives. A smaller word count is not
the goal. Shortenings that changed the claim:

- "exceptions pending migration" cut to "sanctioned exceptions" turned an
  obligation into an endorsement;
- "a future shell would subclass X" cut to "a shell subclasses X" claimed a
  class that does not exist;
- "the 4 MiB ceiling is measured" cut to "the ceiling is 4 MiB" made an
  observation read as a definition, so nobody re-measures before raising it.

When half a sentence is narration and half is a fact, delete the clause, not
the sentence.

## 5. Word pass

**Modality.** A requirement written as `should` is a different claim, and a
reader who treats it as optional has read it correctly.

| Written | Write |
| --- | --- |
| `should` (requirement) | `must` |
| `should` (recommendation) | state the fact: "X is faster because Y" |
| `might`, `could`, `may` (possibility) | `can` |
| `would` (hypothetical) | "If X occurs, Y occurs." |

`may not` as a prohibition stays. Rewriting "callers may not hold the lock
across an await" to `cannot` claims the compiler prevents it; to `can`
inverts it. Obligations and prohibitions keep their modal in every shortened
form, because without it the sentence describes the present and permits the
edit it existed to prevent.

**Words that carry no fact.** Test: does deleting the word change what the
reader knows? "Gracefully handles" names a quality of the handling instead of
the handling; write what happens ("retries three times, then returns
`Timeout`"). "Robust", "performant", "fast" assert what the reader cannot
check; if the property is real it has a number. The substitution table is in
`${CLAUDE_SKILL_DIR}/references/word-table.md`.

**One name per thing.** Pick one term per object and keep it across the
document and every site that points back to it. "The executor", "the runner"
and "the scheduler" read as three objects. One name for two objects is worse
and harder to spot.

**Explain, then name.** Say what a thing does before using its name, most of
all for a term coined during this change's own design discussion. "Required
PR checks were part of the clean-run gate" became "a pull request runs
automatic checks before a change lands, and those were one of the four
conditions". Two PR bodies rewritten this way grew from 404 to 729 and 771
words, and the reader judged both clearer. Numbers, identifiers and quoted
errors stay exact.

**Also:** verbs instead of nominalisations ("compress", not "perform
compression of"); active voice unless the actor is unknown; one claim per
sentence, so a chain of three clauses joined by "and", "but" or a dash is
split; parallel items in parallel form; a condition before its command ("if
the network is slow, raise the timeout").

**One spelling system per document.** Match the repository. This library and
`CLAUDE.md` use British spelling (behaviour, characterisation).

## 6. Stop at the least material that carries the fact

Walk this before writing and again when cutting, and stop at the first rung
that carries the fact with every proposition from step 4 intact:

1. nothing — the named reader already has it, or a nearby sentence says it;
2. a word added to an existing sentence;
3. a clause;
4. a sentence;
5. a paragraph;
6. a section with a heading.

Drift is upward one step at a time, and no single step looks wrong. When a
paragraph and the example under it say the same thing, cut the paragraph and
keep the example.

A document that states a bar is held to it. A 376-word section was added to a
PR-body skill to say "use plain words"; cut to 151 words it lost nothing. What
went was an audience the rule implied, a metaphor restating the rule, and
sentences restating their own guards. Apply this skill to any skill or
`CLAUDE.md` text you write.

## 7. Report

Say what you changed, and list every referent you could not resolve and every
claim you could not check against the source. Those are questions for the
user, not edits.

## Untouchable

Never rewrite, even when they break every rule above: code, inline code,
identifiers, flags, commands, file paths, configuration keys, product names,
quoted error messages and log lines, quoted command output, and anything in a
code fence. A spelling inside an identifier is a name. A word pass that edits
one of these has damaged the evidence it was cleaning.

## Never

- **Never start the word pass before the reader is named** and the cold read
  is done.
- **Never shorten a sentence without listing its propositions first.**
- **Never rewrite `may not` to `cannot` or `can`**, or drop a modal to fit a
  line.
- **Never reword a claim you have not checked against the code** it
  describes.
- **Never edit inside an untouchable** to satisfy a style rule.
- **Never treat a shorter version as better** because it is shorter.
