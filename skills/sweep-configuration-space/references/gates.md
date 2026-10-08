# Gate and mechanism queries

These are the PromQL queries behind the gates and the per-request rates in
`SKILL.md`, as run against a SystemsLab experiment's rezolus recordings.

```sh
systemslab promql --experiment <experiment-id> --job <job-uuid> --output summary '<query>'
```

`--job` takes the job's UUID from `systemslab api /api/v1/experiment/<id>`
(`.jobs[].id`), not its name. A name fails argument parsing.
`--output json` returns each series with its labels and per-second values,
which a script can parse without matching the summary text.

For a recording downloaded as a file, `rezolus mcp query <file.rez> '<query>'`
runs the same queries. Both engines take a bare metric name in
`histogram_quantile`, and both use the same query library, so
`histogram_quantile(q, irate(...))` is likely a parse error in both. It was
seen to fail in rezolus.

## Gates

| Gate | Query | Reading |
| --- | --- | --- |
| subject saturated | `sum by (id) (irate(scheduler_runqueue_wait[5s])) / 1e9`, summed over the application CPUs | core-equivalents of time spent runnable but not running. Well above 0 means the CPUs are contended. `sweep_report.py`'s default threshold of 1 core admits marginal cells (one ranked on 1.2), so read cells near it by hand |
| subject saturated, event-loop server | `sum(irate(syscall{op="poll"}[5s]))` / throughput | `op="poll"` counts the poll family, including `epoll_wait`, `epoll_pwait`, `epoll_ctl`, `poll`, `ppoll`, `select` and `pselect6`. Near 0 per request, with the busiest application CPU nearly fully busy, means each wait returns many ready requests. Only for a server that blocks in poll or epoll when idle: one that never blocks in poll reads near 0 at any load, and one that spins on `epoll_wait` with a zero timeout reads high |
| server-side ceiling | the server's `sum by (id) (irate(softirq_time{kind="net_rx"}[5s])) / 1e9`, max over CPUs, and the load generator's rx + tx bytes/s against the link rate | for cells where neither saturation test fires |
| load generator headroom | `histogram_quantile(0.99, scheduler_runqueue_latency) / 1000` on the client | µs. Calibrate on your rig. One client read 3–4 µs when pinned away from the IRQ CPUs, 23–26 µs unpinned and still healthy, and 61 µs when one of its queue CPUs was saturated |
| load generator headroom | `sum by (id) (irate(softirq_time{kind="net_rx"}[5s])) / 1e9` on the client | take the max over CPUs. Near 1.0 means a queue CPU is saturated, whatever the total CPU says |
| load generator headroom | `max(sum by (id) (irate(cpu_usage[5s]))) / 1e9` | the busiest CPU. On a host running polling threads this reads ~1.0 without meaning saturation, so use it with the two rows above. `sweep_report.py` prints it as `c_maxcpu` and does not gate on it |

## Mechanism rates

Divide the per-request rates by the measured throughput.

| Rate | Query |
| --- | --- |
| CPU µs per request | `sum(irate(cpu_usage[5s])) / 1e9` × 1e6 / throughput |
| futex calls per request | `sum(irate(syscall{op="lock"}[5s]))` |
| voluntary switches per request | `sum(irate(scheduler_context_switch{kind="voluntary"}[5s]))` |
| CPU migrations per second | `sum(irate(cpu_migrations{direction="to"}[5s]))`. rezolus records each migration once as `from` and once as `to`, so an unfiltered sum is twice the rate |
| futex latency | `histogram_quantile(0.5, syscall_latency{op="lock"})` and the p99. This metric is host-wide |

## Traps

- **A recording without `start-metrics` spans the whole job.** With no
  window, a query covers every recording of the job. In one attempt
  `systemslab promql --start/--end` returned no results, even for
  `cpu_usage`; the cause was not found. Bracket the measured window with
  `systemslab/start-metrics` and `stop-metrics` in the spec (SKILL.md step
  2), and record only that window. If a sweep ran without them, its means
  include startup, prefill and shutdown. Report them as whole-recording
  means, and do not trust gate 2 if the prefill could have saturated the
  server.
- **A filtered or ranked query can return no series.** `count(expr > 0.9)` and
  `avg(topk(16, ...))` returned no results when nothing matched. A script that
  prints 0 for a missing result reports a value that was never measured.
  Fetch the per-id series and filter in the script.
- **Host-wide metrics.** `syscall`, `syscall_latency`,
  `scheduler_context_switch`, `softirq` and `cpu_usage` cover every process on
  the host. `cgroup_*` metrics attribute by cgroup, but only for cgroups
  rezolus tracks. A process started by a job step may not get a cgroup of its
  own.
- **A busy CPU is not necessarily doing work.** Polling I/O threads keep a CPU
  near 100% whether or not they have work. Count them before reading a busy
  CPU as saturation.
