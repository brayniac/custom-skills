# Reading a rezolus recording

## The chain

A systemslab job records; the recording arrives as an artifact; the rezolus MCP
tools read it. Each link has a name that has to match the previous one.

1. **`systemslab/start-metrics`** with `name`, and `metadata` for anything you
   will select on later. `name` identifies the recording within the experiment
   and names its artifact (`metrics-<name>`).

   **`start-metrics`'s `source` is not a label.** The runner parses it as a
   socket address and scrapes that rezolus endpoint instead of the local one, so
   `source = "redis"` fails the step with `invalid source address`. The labels
   you select by come from `metadata`, which the runner forwards to
   `rezolus record --metadata key=value`. There, `source` and `host` are
   auto-populated and a supplied `source` wins — so `metadata = { source =
   "redis" }` is what makes `recording: {"source": "redis"}` work downstream.
   Name it after the thing being measured (`redis`, not `run1`).

   `--metadata` applies to every recording in the run and so cannot tell two
   endpoints apart; that is `--endpoint url,source=name`.

2. **`systemslab/stop-metrics`** with the same `name`. Bracket only the measured
   region — setup and teardown inside the window are noise you will have to
   reason around.
3. **`download_artifact`** (MCP) to get the `.rez` or parquet file locally, or
   `systemslab api /api/v1/experiment/<id>` to list `.artifacts[]` and
   `systemslab api /api/v1/artifact/<id>` to fetch one.

   `artifact list --experiment` and `download-all` scope correctly — verified
   on the rack against CLI 160.0.0, two sibling experiments with identical
   artifact names and zero id overlap. They do exclude **context-attached**
   artifacts by design, so a pre-staged file is absent from an
   experiment-scoped list without anything saying so.
4. **`describe_recording`** with no `recording` argument first, to list what the
   file holds. A `.rez` can carry several recordings; the tools require exactly
   one, selected as `recording: {"source": "redis"}`.
5. **`describe_metrics`** before any query. This is not optional — see below.
6. **`query`** with PromQL, or `detect_anomalies` / `analyze_correlation`.

## Metric type decides the query, and getting it wrong is silent

`describe_metrics` groups metrics by type. The type dictates the query form, and
the wrong form returns a number rather than an error:

| Type | Query form | What the wrong form gives you |
| --- | --- | --- |
| **counter** (monotonically increasing) | `rate(metric[1m])`, then `sum()` | the raw cumulative total — a large, smoothly rising number that looks like a metric and answers nothing |
| **gauge** (point-in-time) | query directly | wrapping it in `rate()` gives a near-zero derivative that reads as "no activity" |
| **histogram** | `histogram_quantile(0.99, metric)` | querying directly returns bucket series, and an aggregate over buckets is meaningless |

**Never write a label selector you have not seen in `describe_metrics`.** A
selector that matches nothing returns an empty result, and an empty result reads
exactly like a legitimate zero. If a query returns zero or nothing, confirm the
labels exist before believing it.

## `detect_anomalies` needs one series

It takes a single time series. Aggregate first:

```
sum(rate(cpu_usage[1m]))
histogram_quantile(0.99, scheduler_runqueue_latency)
```

Handing it a query that expands to many series is an error at best and a
meaningless answer at worst. It reports MAD, CUSUM, and FFT findings — useful for
locating *when* something changed and whether it is periodic.

## What these tools are and are not for

`detect_anomalies` and `analyze_correlation` find mechanisms and narrow a search.
Neither decides a verdict. A correlation between two metrics across one run is
consistent with a shared cause, a coincidence, and a measurement artifact, and
it distinguishes none of them.

The verdict comes from Step 5 of the skill: interleaved runs, enough of them, and
a spread that does not cover the difference.

## Reporting a number read this way

Say which recording (`source`), which metric and its type, and the exact query.
A figure quoted without its query cannot be re-derived later, and measured
constants get written into thresholds and commit messages where they are read as
facts.
