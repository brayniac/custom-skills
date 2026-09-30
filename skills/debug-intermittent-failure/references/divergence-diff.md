# Finding the first divergent event

For a failure that affects one unit of several — one connection of many, one
worker, one thread, one rank — the fastest way to the mechanism is to record the
same events for every unit and find the first event where a failing unit
departs from a good one. Adapted from a method used for distributed-inference
hangs, where it applies per GPU rank; here the unit is whatever fails
independently.

## 1. One file per unit, one line per event

```text
ACCEPT     conn=17 slot=4 fd=33
SEND_OK    conn=17 op=112 bytes=4096
RECV       conn=17 op=112 res=-104 errno=ECONNRESET
PEER_CLOSE conn=17 after_ops=112 peer_saw=fin
```

- An uppercase event name first, then `key=value` fields, so `grep '^RECV'`
  extracts one event type and the fields can be compared by name.
- Write the raw value (`res=-104`, the `errno`), not a summary of it.
- Hash large values rather than dumping them: 8 hex characters of a hash of a
  buffer are enough to tell whether two units saw the same bytes.
- Flush after every line. A unit that hangs or aborts must leave its last
  events on disk.
- Gate the logging on an environment variable so it can stay in the code.

## 2. Compare counts, then diff

```sh
grep -c '^SEND_OK' unit-*.log            # counts differ → divergence already
grep '^RECV' unit-good.log > a; grep '^RECV' unit-bad.log > b; diff a b | head
```

The first differing line is the step where the units diverged. Everything
before it was identical, so the cause is at or before that step.

## 3. Recurse on the inputs of the divergent step

List every input to the operation at the first divergent step and log a hash
or value for each. Diff again. The input that differs is where the divergence
entered; trace where it was produced and repeat until the cause is found.

## 4. Watch what the instrumentation does to timing

Logging can move or hide a race. On a GPU, reading a tensor back to the host
synchronises the device; on a socket path, a `write(2)` per event adds a syscall
between operations. Log values already in hand (counts, ids, lengths, return
codes), and if the failure rate falls when instrumented, report that and reduce
the logging rather than concluding the bug is gone.

## Causes this has found

| Symptom in the diff | Usual cause |
| --- | --- |
| event counts differ before any error | one unit took a branch the others skipped: a condition evaluated on per-unit state |
| identical inputs, different derived value | floating-point or ordering non-determinism, or an unseeded random source |
| one unit's last line is a wait | the peer never issued the matching operation: compare the peer's file at the same step |
| every unit identical up to the error | the divergence is outside what was logged; move the logging one layer out |
