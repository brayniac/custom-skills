---
name: profile-gpu-kernels
description: Profile GPU work to find where time goes — capture CUDA activity with Nsight Systems and query the exported SQLite for top kernels, memcpy by direction, CPU-side runtime API cost, and the GPU idle gap; or, on Apple silicon, a Metal frame capture scoped to one steady-state step plus an xctrace system trace. Use when a GPU workload is slower than expected, when choosing which kernel to optimise next, when a change should have reduced kernel or transfer time, and before quoting any per-kernel figure.
---

# Profile GPU kernels

A profile answers where time goes; it does not produce a performance number.
Capture adds overhead (a full CPU backtrace adds about 30% under nsys; Metal
frame capture slows decode substantially), so take throughput and latency
figures from an unprofiled run (`measure-performance`), and use the profile to
decide what to change.

On the lab rack a GPU is only reachable from inside a VM; `vm-job` covers
getting a GPU guest and pulling artifacts out.

## CUDA

### 1. Scope the workload

Profile one steady-state unit of work, past warm-up: a single prefill, a fixed
number of decode steps, one layer. If the binary cannot be limited that way,
write a small test or bench target that does exactly one thing and point the
profiler at it.

### 2. Capture

```sh
nsys profile -f true -o /tmp/prof --stats=false \
  -t cuda --cudabacktrace=none \
  <binary> <args>
```

`-t cuda --cudabacktrace=none` traces CUDA activity without CPU backtraces. On
`CUPTI_ERROR_INSUFFICIENT_PRIVILEGES`, add `--use-cupti-events=off` or run as
root.

### 3. Export and query

```sh
nsys export --type sqlite --force-overwrite true -o /tmp/prof.sqlite \
  /tmp/prof.nsys-rep
```

Fetch `references/nsys-queries.py` with `skill_resource` and run it against the
`.sqlite` (it uses Python's `sqlite3`, since the `sqlite3` CLI is often not
installed). It prints:

- top kernels by total GPU time, with count and mean;
- memcpy time and count by direction (HtoD, DtoH, DtoD);
- top CUDA runtime API calls by CPU time;
- the GPU idle gap: wall span minus kernel and memcpy time.

### 4. Read it in this order

1. **GPU idle gap.** A large gap means the CPU side dominates — per-call
   compilation, host synchronisation, launch overhead, no graph capture — and
   no kernel optimisation will help until it is closed.
2. **Runtime API CPU cost.**
   - `cuMemcpyHtoDAsync` dominating: data (often weights) re-uploaded per call.
   - `cuMemAllocAsync` dominating: many small per-call allocations; pool them.
   - `cuMemsetD8Async` in the hot path: zeroing buffers that are then fully
     overwritten; allocate them uninitialised.
3. **Top kernels.** GEMMs usually lead. A non-GEMM kernel at the top is a
   custom kernel worth optimising first.
4. **DtoD memcpy count.** A high count per step usually means gather/scatter
   loops materialising contiguous tiles that a strided batched call could
   read in place.

After a change, profile again and compare the same four readings.

## Apple silicon (Metal / MLX)

- **Frame capture** scoped to one steady-state step (for example decode step
  10). `METAL_CAPTURE_ENABLED=1` must be set on the same invocation, before
  the Metal device is created. Open the `.gputrace` in Xcode for per-kernel
  timing and dispatch counts; many tiny dispatches point to fusion
  opportunities.
- **System trace** for the whole run:
  `xcrun xctrace record --template 'Metal System Trace' --output /tmp/t.trace
  --launch -- <binary> <args>`. Steady-state GPU utilisation below about 60%
  points to CPU-GPU synchronisation. Compare memory bandwidth with the device
  peak (M3 Ultra: 819 GB/s).
- **Thermal state.** A downclocked device invalidates any throughput reading
  taken during the same run.

## Never

- **Never quote throughput or latency from a profiled run.**
- **Never optimise a kernel while the idle gap dominates.**
- **Never profile the warm-up** and read it as steady state.
