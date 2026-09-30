---
name: capture-before-parsing
description: Record what a device, API, server, or tool actually emits into a committed, timestamped fixture before writing any code that parses it, then question the capture — terminal states, edge versus heartbeat, casing, per-model response shapes, frozen or wrong values, sub-second pulses, what it reports when disconnected — and drive a pure parse layer and its tests from the fixture. Use when integrating a new device, appliance, vendor API, MQTT topic, log format, CLI output, or job-runner state machine; before trusting vendor documentation or remembered state names; and when a parser returns nothing, never matches, or reports a state the thing is not in.
---

# Capture before parsing

Documentation says what a device or service was meant to emit. A capture says
what it emits. On a home-automation portal this was done for two devices, and
both times the capture contradicted the vendor documentation: four times for
the garage-door boards (ratgdo), five for an LG dryer. Several of the
differences produced no error: one would have made every poll parse to
nothing, forever.

The same failure appears with job runners. A watcher checking for
`completed`/`failed` never matched SystemsLab's `success` and reported
finished work as running for 40 minutes, twice (`watch-long-job` step 1). A
state name taken from memory is a parser written from documentation.

## Inputs

- The source: device, endpoint, topic, log, or command.
- The states the code will have to handle (for a door: opening, open,
  closing, closed, stopped, obstructed).
- Someone, or something, able to drive the source through those states.

## 1. Capture real output with timestamps

Record raw output to a file while the source is driven through every state
the code must handle: a full cycle, an interrupted cycle, the error case, the
idle state. For a door: open, close, break the photo-eye beam, stop part way.
For a job runner: one job that succeeds, one that fails, one that is
cancelled.

Keep a receive timestamp on every line. Gaps between messages are how you tell
a transition sent once from one sent thirty times, and that cannot be
recovered later.

## 2. Commit the capture as a fixture

Put it under the repository's fixture directory (`tests/fixtures/`), raw, with
timestamps. Trim trailing padding; keep repetition, because repetition may be
part of what the source does. Name it for the source and the scenario
(`ratgdo_topics.txt`, `lg_dryer_cycle.jsonl`).

## 3. Question the capture before designing anything

Ask every question. Each one produced a real finding on the portal:

| Question | Finding |
| --- | --- |
| Is there a terminal state, or does output just stop? | The washer emits `END`; the dryer goes `RUNNING` → `POWER_OFF` with no completion state. An alert waiting for a terminal state waits forever. |
| Does state change once, or repeat as a heartbeat? | ratgdo republishes `closing` about every 500 ms for the 15 s of travel, and the transition itself arrives twice at the same instant. One row per message is thirty identical rows per door cycle. |
| Is casing consistent? | ratgdo's `cover` state is lowercase, its binary sensors uppercase, and its commands uppercase. Correct code looks like a typo. |
| Does the response shape differ between models? | The dryer puts its state object directly under `"response"`; the washer wraps it in an array. `.as_array()?.first()` returned `None` for every dryer poll, with no error. |
| Do any values freeze or lie? | The dryer's remaining time counted 41 → 24, then stayed at 24 for 45 minutes of a 63-minute cycle; its advertised total was wrong by half. Show elapsed time instead of a countdown. |
| Are there sub-second pulses? | ratgdo's obstruction signal lasted 430 ms. Sampling misses it; store it as an event. |
| What does it report when not connected to what it measures? | An unwired ratgdo reports the door `open` at position 100. The field that proves the link is `openings`/`paired_devices` leaving `NA`, never the door state. |

Write down each answer for this source, including "no".

## 4. Write a pure parse layer driven by the fixture

The parse module takes bytes or strings and returns typed values: no I/O, no
network, no clock. Its tests read the committed fixture, with one explicit
test per finding from step 3 that applies. Apply `verify-by-breaking` to each:
revert the handling for that finding and confirm its test fails.

## 5. Build outward, reversible steps first

Parser, then the consumer that stores it, then the read API, then the display,
then control, then alerts. Each step is usable alone, and the one that acts on
the physical world comes last.

## 6. Model absence and plurality from the start

- **Never fabricate state.** A source not heard from is absent from the
  snapshot, not `closed`. A field that cannot be determined is `null`. "Not
  heard" and "beam clear" are different answers to "can I close this door".
- **Configure devices as a list** even with one. The garage was specified with
  two doors, had three, and the change cost nothing because the config was
  already an array.
- **One status and backoff per device**, so one failing appliance neither
  drops another's samples nor lets the source report `ok`.
- **Never rename an existing metric** to fit a new device's naming; the
  history is lost. Give the new device the prefix and comment the asymmetry.

## Stopping condition

Done when the fixture is committed, every question in step 3 has a written
answer, and each finding that applies has a test that was seen to fail.

## Never

- **Never write a parser from documentation or memory** without a capture.
- **Never apply one casing or shape rule to a whole vendor's devices.**
- **Never sample a signal that can pulse shorter than the sample interval.**
- **Never report a state for a source you have not heard from.**
- **Never strip timestamps from the raw fixture.**
