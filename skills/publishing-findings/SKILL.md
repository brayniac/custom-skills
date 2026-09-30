---
name: publishing-findings
description: Write technical findings that a reader can trust and that carry nothing they shouldn't — check the destination before writing, strip what must not travel, never furnish a detail, and correct in place. Use before creating any GitHub issue, PR, comment or gist, before publishing an artifact or posting to a channel, and whenever a report or bug report draws its motivation from customer work, a benchmark, or a third party's software.
---

# Publishing findings

Work becomes outward-facing the moment someone else will read it and act on it,
and outward-facing work carries two obligations that inward work does not:
**everything in it must be true**, because the reader cannot check it, and
**nothing must be in it that should not travel**, because you cannot take it
back.

Both fail the same way. The draft does not look risky. It looks like the best
thing you have written all week — specific, quantified, motivated by real work,
persuasive *because* it is concrete. The impulse to write a good report and the
impulse to disclose are the same impulse, and the impulse to make a correction
land gently is what furnishes a detail to soften it. That is why the check has
to be mechanical and attached to the destination, rather than triggered by a
feeling that something is sensitive.

Whether the numbers themselves are sound is `benchmark-validity`.

## Check the destination before writing the content

```bash
gh repo view OWNER/REPO --json visibility,nameWithOwner \
  -q '.nameWithOwner + " — " + .visibility'
```

Two questions, in order. **Is it public?** — private-to-your-org is not
private-to-you, but public is categorically different. **Do you own it?** — an
upstream you contribute to is outward-facing even when it feels like home, and
`origin` pointing at your fork says nothing about where an issue lands.

Per artifact, not per session. Filing three issues against a private repo earns
no licence on the fourth against a public one; that is exactly how the habit
carries across.

## What must not travel

When the destination is public or not yours, strip:

- **Customer and engagement names**, including inside quoted material.
- **Third-party proprietary software by name**, and anything about its internals
  learned by working on it — design, data structures, key formats. "A
  disk-backed cache" carries the technical argument; the product name adds
  nothing and is not yours to publish.
- **Measured performance of anything you do not own.** Miss rates, latencies,
  throughput. Often the most persuasive material in the draft, which is why it
  survives edits.
- **A customer's targets and plans**: SLOs, fleet sizing, instance types,
  capacity models, timelines.
- **Workload parameters specific enough to fingerprint.** A key count, value
  size and request rate together identify an engagement with every name removed.

**Keep the argument, replace the evidence.** A feature request needs a
motivating example, not *your* motivating example. Round illustrative numbers,
labelled as illustrative, are as persuasive and generalize better — a reader can
map them onto their own system instead of decoding yours.

## Never furnish a detail

Not to overstate a result — that temptation is obvious and gets resisted. The
one that gets through is the small self-deprecating fact invented to make a
correction land softly: *"it took us a day to notice."* If it did not happen it
is a fabrication, sitting in a document whose entire value is that its contents
were observed.

Tone problems are real. Fix them by **removing** framing, never by adding
invented content. Neutral statement of a fact is always available and never
requires a story.

## Do not characterize someone else's setup unread

Before writing that a run lacks something, read that run. A list of four "traps
worth knowing" once went to a colleague whose configuration already handled
three of them — he had inherited them from the shared spec. Thirty seconds in
his logs would have caught it; as written it read as an audit of correct work.
This is the same error as citing a file you have not opened, and it costs the
credibility of the items that *were* right.

## Tag claims by basis, and keep the tags

- **measured** — observed in a run, with the rig noted
- **derived** — arithmetic from measured or given values
- **given** — a requirement or input, not established here
- **unknown** — the interesting list

A model result and a measurement look identical in a table, and readers act on
tables. A fleet-sizing figure derived from one access pattern reads as a plan
unless it is labelled a worst-case bound with its unmeasured input named.

The tags matter most when the document outlives the session that wrote it.
Once a figure sits in the same prose as a measured one, nobody downstream can
tell which was which.

## Correcting after the fact

**Editing does not undo publication.** GitHub keeps full edit history on issues,
PRs and comments; anyone can open the "edited" dropdown and read the original.
An edit makes the artifact correct going forward and leaves the disclosure
retrievable.

For a disclosure:

1. Edit immediately anyway — it bounds what a casual reader sees.
2. Get the exposure window:
   `gh issue view N -R OWNER/REPO --json createdAt,updatedAt,url,author`
3. **State plainly what was disclosed**, itemized, unsoftened. Whoever owns the
   relationship decides, and can only decide from the list.
4. **Recommend deleting and refiling.** Deletion removes the edit history; an
   edit cannot. The cost is an issue number.
5. **Do not delete unilaterally.** Destructive, outward-facing, and not your
   call.

For a wrong number: say which number, what it is now, and why it changed — then
continue. No burying, no extended apology, and no leaving the old figure
standing because the new one is inconvenient. If the document was already
shared, put the correction where the original was read, not only where it is
convenient to write.

Correct in place rather than editing the error out. The wrong reasoning is
usually the useful part: a reader who can see what was concluded and why can
check whether they made the same move.

## Recording what did not work

A refuted hypothesis narrows the answer, and a knob that did nothing will be
tuned again by the next person if nobody wrote it down. When a finding closes,
record in the same place as the finding:

- each hypothesis ruled out, the evidence that ruled it out, and the condition
  under which it should be reopened ("reopen if the failure appears with
  io_uring disabled");
- each setting varied with no effect, and the range tried;
- what was lost, not only what was gained, when the finding led to a change: a
  CHANGELOG or PR line that describes the diff's shape can be accurate and
  still hide a removed capability.
