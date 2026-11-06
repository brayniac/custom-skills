# PR body examples

## A change with evidence and nothing to decide

```markdown
#259 introduced a `ShardedHistogram` which was a big performance win. Since
then the `metriken` crate has implemented this as `ShardedCounterHistogram`.
This PR removes the implementation from cachecannon and migrates to using the
version in `metriken` itself.

Performance against `main` at `53242aa`, as median [min, max] of 8 rounds at
1.38M/s with 8 workers. The last column compares two identical `main` binaries
and shows the noise floor.

| Statistic | `main` | This PR / `main` | `main` / `main` |
|---|---|---|---|
| GET p50 | 286 µs | 1.0000 [0.993, 1.007] | 1.0000 [0.993, 1.007] |
| GET p99 | 942 µs | 1.0000 [0.983, 1.013] | 1.0000 [0.974, 1.021] |

Measured on one Zen 1 guest over loopback. ARM was not measured. Details are in
`docs/journal/2026-11-04-metriken-sharded-histogram.md`.
```

There are no headings, and the opening names the types. The reader sees what
changed, why, whether it costs anything, and the one gap that could change the
decision.

## Process narration

> **Written to yourself.** The first review found a wrong experiment citation,
> which I fixed. The second raised the bucket-equality test, which I reran on
> 0.11.7. The last fixes have not been re-reviewed, and no review is recorded
> for merge.

> **Written for the maintainer.** Buckets are identical to the old type's on
> 60M values at `(7, 64)`.

The first reports the author's review rounds. The second is the one fact the
reader can use. If the fact is not needed for the merge decision, delete it
too.

## A decision subsection

The domain is invented.

```markdown
## Decisions

### One repository-wide setting for a fact that differs by deployment

The registry is the same in every deployment: one row per stream. Whether a
sensor wraps its own records is not. It is true on the hardware and false in
the simulator, which publishes a sensor's topics without running the sensor.

`config/src/streams.rs:290` at `4f1c9a0e7b2d6358c1e0a9d47f3b8c6e2d5a1f70`

I chose one flag stating the hardware's behaviour, plus an explicit override
for the simulator, over teaching the registry about deployment profiles. The
override stops scaling at a third deployment that differs again, and a third
deployment profile would change the choice. This blocks the merge.

**Is a single flag the right shape, or should the registry carry the
deployment dimension?**
```

Context, then the reference, then the question. A choice with no open question
gets none of this.
