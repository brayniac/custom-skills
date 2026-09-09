# Reading a rezolus recording

## The chain

A systemslab job records; the recording arrives as an artifact; the rezolus MCP
tools read it. Each link has a name that has to match the previous one.

1. **`systemslab/start-metrics`** with `name` and `source`. `source` is the label
   you will select the recording by, so name it after the thing being measured
   (`redis`, not `run1`).
2. **`systemslab/stop-metrics`** with the same `name`. Bracket only the measured
   region — setup and teardown inside the window are noise you will have to
   reason around.
3. **`download_artifact`** (MCP) to get the `.rez` or parquet file locally, or
   `systemslab api /api/v1/experiment/<id>` to list `.artifacts[]` and
   `systemslab api /api/v1/artifact/<id>` to fetch one.

   **Do not use `systemslab artifact download-all` or `list --experiment`.** On
   CLI 160 they ignore the experiment filter and return other experiments'
   files. For a measurement that is not a nuisance — it is analysing the wrong
   run and reporting it as this one, with nothing in the output to say so.
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
