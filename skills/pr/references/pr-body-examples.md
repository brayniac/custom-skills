# PR body examples

Each pair shows the same change written two ways. The domain is invented; the
failures are the ones reported against real bodies.

## The summary

The change splits one field on a stream's registry entry that was answering
two questions.

> **Describes the edit.** Splits `StreamEntry.topic`, which was answering both
> "which bus topic carries this" and "has the producer started wrapping
> records", into two fields.

> **Says why.** Each sensor is moving from publishing raw records to
> publishing through a relay that wraps each record in an envelope. The
> payloads are byte-identical either way, so nothing downstream can tell which
> path a record took. Using the presence of the envelope to tell them apart is
> what lets the sensors move one at a time.
>
> One decision wants your opinion and it blocks the merge; it is the first
> subsection under Decisions.

The second can be read by someone who has never opened the code. The first is
a diff summary with the field name loaded in front.

## A decision subsection

```markdown
## Decisions

### One repository-wide setting for a fact that differs by deployment

The registry is the same in every deployment: one row per stream. Whether a
sensor wraps its own records is not. It is true on the hardware and false in
the simulator, which publishes a sensor's topics without running the sensor.

`config/src/streams.rs:290`

I chose one flag stating the hardware's behaviour, plus an explicit override
for the simulator, over teaching the registry about deployment profiles. The
override stops scaling at a third deployment that differs again. This blocks
the merge and needs a decision.

**Is a single flag the right shape, or should the registry carry the
deployment dimension?**
```

Context, then the reference, then the question. The reference lets the
reviewer check the context instead of trusting it.

## A glossed "before" beat

> **Undefined.** `StreamEntry.topic` was answering two questions at once.

> **Glossed.** Every stream has a registry entry saying where it comes from
> and how it is carried, and one field on that entry named the bus topic it
> arrives on.

The identifier existed before this change, so no sentence in the diff
introduces it. The gloss gives its job, not its type.

## Before, problem, change

> When only one machine recorded, nothing needed to distinguish the topic a
> record arrived on from the sensor that produced it. As streams move to
> arriving over the link instead, the topic alone can no longer tell the two
> paths apart. So a second label is needed, and this change adds it.

Three beats, three sentences, each stated once.
