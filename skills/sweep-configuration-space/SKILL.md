---
name: sweep-configuration-space
description: Map a server's performance across a configuration space — process count, threads per process, CPU and IRQ placement, connection count, payload size — in tiers that go from a wide grid of short runs to long runs of the leading cells, gating every cell on whether it measured the server before ranking it, and labelling each limit as the host's (NIC queues, cores, link) or the software's (a main thread, a lock or wake handoff). The method applies to any lab; the bundled script and queries assume SystemsLab, rezolus recordings and cachecannon. Use when asked to find the best geometry or deployment shape for a server on given hardware, to characterise where and why throughput stops scaling, to produce data for charts or a report from many configurations, and before ranking any set of sweep results.
---

# Sweeping a configuration space

A sweep answers two questions: which configuration is best on this hardware,
and what limits it. It goes wrong in three ways:

- cells are ranked when some of them measured the load generator;
- an axis changes something besides itself;
- host state left by one run carries into the next.

This skill covers how to lay out a sweep and how to gate its results. The
neighbouring skills own the rest:

- `measure-performance`: producing one number, closed and open loop, Little's
  law, interleaving;
- `benchmark-validity`: whether one run measured its subject;
- `analyze-noise`: run length from the noise;
- `calibrate-to-source`: thresholds;
- `systemslab-spec-authoring`: spec mechanics.

Steps 2, 5 and 6 name SystemsLab, rezolus and cachecannon. On another lab,
keep each check and replace the tool.

## 1. Write the question and the fixed resources down first

Name the subject, which is the server under test. Name the resources every
cell shares:

- the host type;
- the CPUs set aside for interrupts;
- the offered concurrency (step 3);
- the payload size.

Name the axes and their ranges. Write which cells you expect to win, why, and
what result would refute each expectation (`measure-performance` step 5).
Record all of this beside the sweep file before submitting anything.

## 2. Build one parameterised spec and one sweep file per study

- **One spec takes every axis as a parameter.** A study is a JSON file listing
  its cells, kept beside the spec, so rerunning a study is one command.
  `systemslab sweep <spec>.toml <study>.json --name <study>` applies the
  file's parameters to a TOML spec.
- **One experiment per cell, each starting its own server processes.** Two
  cells that share a server share keys, allocator and in-process state, so the
  second cell measures what the first left behind.
- **The server runs as a background step of the job.** A daemon or a
  `systemd-run` unit survives a cancelled run and still holds its port when
  the next cell starts. A preflight step fails the run if a port is already
  in use.
- **Bracket the measured window with `systemslab/start-metrics` and
  `stop-metrics`** (`measure-performance` step 3). Otherwise the recording
  spans the whole job, and warmup and prefill load enter every per-request
  rate and gate. A prefill that saturates the server can then pass gate 2 for
  a window that did not.
- **Every run sets each host knob it depends on, at its start, in both
  directions.** That covers irqbalance on or off, the IRQ affinity of each NIC
  queue, and the CPU set of each process. Print the resulting state at the
  start and again at the end, and diff the two.
  - A knob that one cell sets and the next leaves alone is inherited by the
    next cell.
  - In one sweep comparing "irqbalance" with "dedicated IRQ CPUs", three of
    the four irqbalance cells started in the previous cell's dedicated layout,
    and irqbalance moved all 16 queues partway through each run.
  - Only the end-of-run diff showed this.

## 3. Hold the offered load constant across geometry axes

In a closed loop, throughput is the number of requests in flight divided by
mean latency. When an axis scales the in-flight count with it, a cell that
does not saturate reports the extra load as if the geometry produced it. One
example is "64 connections per process" with process count as the axis.

- **Hold connections and pipeline depth fixed, separately.** 1,024 × 1 and
  128 × 8 have the same product but different syscalls per request.
- **Hold the total fixed** when the processes share one client population:
  the question is how best to serve those clients with this host.
- **Hold the per-process count fixed** when each process is an independent
  instance with its own clients: the question is per-instance capacity.
- Say which one the study holds.

Size a fixed total for the geometry you expect to have the highest
throughput. That is often the one with the most processes: it gives each
process the fewest connections, so it is the hardest to saturate. By Little's law the total must
be at least that geometry's expected peak throughput × its latency at
saturation. Confirm in step 5 that it saturated.

A closed-loop ranking is valid only among cells whose ceiling is the subject.
Confirm the leaders open-loop or with an SLO search (`measure-performance`
step 3).

## 4. Tier 1: a coarse grid

Cover the whole range with large steps: every process count that divides the
application CPUs evenly, threads per process at 1, 2 and 4, and so on. Use a
short measurement window (30 s) and one run per cell.

Keep the same warmup in every tier, including any settle time the load
generator adds after prefill. It must last until per-second throughput has
flattened before the window opens (`benchmark-validity`). Check that on the
slowest-warming cell of tier 1.

A shortened warmup leaves some cells still warming during the window and not
others. That bias varies across the grid and changes the shape of the
results. If the sweep has to be smaller, cut cells, not warmup.

## 5. Gate every cell before ranking it

`${CLAUDE_SKILL_DIR}/scripts/sweep_report.py` prints a verdict per cell from
gate 1 (except Little's law), gate 2, and gate 3's run-queue and `net_rx`
tests. Check Little's law, the client's busiest CPU and gate 4 by hand, using
the queries in `${CLAUDE_SKILL_DIR}/references/gates.md`. The script compares
active connections with the total the client opens, read from
`--planned-conns`. For a study that holds the per-process count fixed
(step 3), pass the product, such as `--planned-conns CONNS_PER_PROC*INSTANCES`.

1. **The run measured what was planned.**
   - It finished, with no errors, no failed connections and no dropped
     requests.
   - The active connections at the end match the plan.
   - Little's law closes with the mean latency and connections × pipeline
     depth (`measure-performance` step 5). It checks that throughput,
     latency and in-flight count agree with each other. In a closed loop it
     holds whether or not the server saturated, so it says nothing about
     gate 2.
2. **A limit of the subject was reached.** One of these holds:
   - **CPU contention.** Run-queue wait summed over the application CPUs is
     well above zero.
   - **A single thread.** A single-thread limit leaves most CPUs idle and
     shows no run-queue wait. For a server that blocks in poll or epoll when
     idle, it shows as poll-family syscalls per request near zero with at
     least one application CPU fully busy: each wait returns many ready
     requests. The poll-family count includes `epoll_wait`, `epoll_pwait`,
     `epoll_ctl`, `poll`, `ppoll`, `select` and `pselect6`.
     - A server that calls `epoll_ctl` per request reads 1 or more, so the
       test cannot fire for it.
     - In one sweep the cells at 4 processes had zero run-queue wait and 0.03
       polls per request, with half the host idle. Each process's main thread
       was the limit.
     - A server that never blocks in poll (io_uring, kernel-bypass busy
       polling, a thread per connection) reads near zero at any load. One
       that spins on `epoll_wait` with a zero timeout reads high. The test
       does not apply to either; pass `--no-poll-gate` to the script.
   - **Something else.** A cell where neither fires is not ranked. Classify
     its limit by hand in step 6. A server that parks in futex on a lock or a
     wake handoff gives neither signal. Neither does a server capped by its
     NIC queues or the link. Check the server's busiest `net_rx` CPU and
     rx + tx against the link rate.
3. **The load generator had headroom, judged per CPU.**
   - Total client CPU can be low while one client CPU is saturated, so check:
     - the client's run-queue p99;
     - its busiest CPU;
     - its busiest CPU's share of `net_rx` softirq.
   - With RPS off, `net_rx` runs on the CPU that takes each queue's interrupt,
     so a few CPUs carry all of it.
   - In one sweep the client used 37 of 64 cores while one queue CPU spent 97%
     of its time in `net_rx`. That cell measured the client's receive path.
4. **The state was what the cell said it was.** The start and end diffs of
   IRQ affinity and CPU sets are empty. Each process's recorded CPU set
   matches the plan.

State which CPUs each busy figure covers, and check it against the thread
count. A per-process figure above the number of threads that can run, such
as 1.4 cores for a single-threaded process, includes something else, such as
softirq on the interrupt CPUs.

Host-wide metrics are not per-process metrics. `syscall_latency`, context
switches and softirq count every process on the host. A tail you cannot tie
to the subject's threads belongs to the host.

## 6. Explain the ranking from the recording before reading source

For each cell, read these from the rezolus recording
(`${CLAUDE_SKILL_DIR}/references/gates.md`) before opening the server's
source:

- per request: CPU microseconds, futex syscalls, voluntary context switches,
  polls;
- per second: CPU migrations.

These rates narrow down the mechanism; reading the source then confirms it.
Read how each rate changes with load, not its value in one cell:

- **Futex calls per request.** If they fall as load rises, threads are
  parking and waking. On a contended lock they rise with load.
- **Busy CPUs at about 97% with others idle.** These can be polling threads
  spinning. Count the polling threads before concluding the host is
  saturated.
- **Placement changes.**
  - A placement change that cuts migrations several-fold and raises
    throughput points to cache locality.
  - A placement change that changes nothing means placement was not the
    limit.

Label each limit as the host's or the software's:

- **Host limits:** NIC queue count, softirq capacity per queue CPU, core count,
  link bandwidth.
- **Software limits:** a single main thread, a lock or wake handoff per
  request, polling threads that take CPU from workers.

The report needs both. The software limits are the ones the server's
developers can change.

## 7. Tier 2: refine around the best region

Use finer steps around the leaders:

- the neighbours of the best process count;
- intermediate thread counts;
- placement variants;
- the interrupt-CPU count.

Repeat a few tier 1 cells unchanged as controls. If a control moves by more
than the differences you are ranking, the session drifted. Do not use the
refined ranking until you know why.

## 8. Tier 3: extended runs of the top 10–20

Rerun the top 10–20 cells that passed all four gates in tiers 1 and 2, with a
5-minute window. These runs give the chart data and the time series.

- **Run length.** A run of length T characterises noise out to an averaging
  time of about T/10 (`analyze-noise`), so 30 s for a 5-minute run. If the
  Allan deviation is still falling at 30 s, give the leader one run of about
  20 minutes.
- **Repeats.** Any number quoted as a result needs the interleaved repeats
  that `measure-performance` step 5 sets. Size the repeats from the spread
  between these extended runs.
- **Burst and baseline.** On hosts with credit-based network or CPU limits, a
  30 s run measures the burst rate and a 5-minute run the baseline. Check the
  allowance counters (`benchmark-validity`) before comparing tier 1 ranks
  with tier 3.
- **Open-loop confirmation.** Confirm the top few open-loop or with an SLO
  search.

## 9. Report

For each tier, give:

- the sweep file;
- the context ID;
- a table of every cell, with:
  - the gate result: ranked, unclassified, loadgen-bound, link-bound,
    no-data, failed, not-finished, error, or state mismatch (gate 4, checked
    by hand);
  - throughput, p50 and p99;
  - CPU per request;
  - the limit label.

State which numbers come from one 30 s run and which from repeated 5-minute
runs. State each prediction from step 1 and whether the data refuted it.

## Never

- **Never rank a cell that failed a gate.** Keep it in the table and give the
  reason it is not ranked.
- **Never let a geometry axis change the offered concurrency.**
- **Never share a server process between cells.**
- **Never rely on a host knob a previous cell set.** Set it, record it at the
  start and the end, and diff.
- **Never judge load-generator headroom from total CPU.** Use the busiest CPU
  and the per-CPU softirq share.
- **Never attribute a host-wide metric to the subject** without tying it to
  the subject's threads.
- **Never shorten the warmup to fit more cells.** Cut cells instead.
- **Never read an empty query result as zero.** `count(x > 0.9)` and `topk`
  return no series when nothing matches. `sweep_report.py` reads per-CPU
  series and filters them in Python for that reason.
