---
name: diagram
description: Draw a diagram of a program that already exists — a build-time structure chart, a runtime thread model or request flow, a dataflow or pipeline chart, or the byte layout of a memory or wire format — by generating it from the program's own structures with a generator that aborts on anything unclassified, asserts the chart's positive and negative claims against the source, emits a committed text source, is regenerated and diffed in CI, and is checked for placement and read by a person before it ships. Use when asked to diagram the architecture, the threads, the life of a request, the pipeline, the DAG, the dataflow, or a format's byte layout; when a design doc or PR needs a picture of running code; and when an existing diagram has drifted from the code, omits a node, has a legend that disagrees with the chart, or is a screenshot with no source.
---

# Draw a diagram from code

A diagram of a program is a set of claims about that program. Every claim it
draws must be one the code can be held to, and every claim the code makes that
the chart is about must appear. Both halves fail without an error: a
hand-drawn chart keeps rendering after the code changes, and a generator that
skips what it cannot classify still produces a complete-looking picture.

The rules here come from charts built for a multi-binary cache framework, an
io_uring runtime library, a binary collection format, and a reference page on a
recording format's writers and readers whose source lives in other repositories.
The principles held on the first three; the fourth is where step 1's transcribed
model, the embedding rule for colors, and the address arrow come from. The
visual conventions in the references were derived on one or two systems each and
are defaults to override with a stated reason. Step 9's repair limit and step
11's check record come from another diagram tool's delivery contract, not from a
chart built here.

## Inputs

- The question the chart answers, in one sentence.
- The repository, and whether you can add files to it.
- An existing generator, regeneration command, CI freshness check, or charter
  (`${CLAUDE_SKILL_DIR}/references/charter.md` is the template), if the
  repository has one.

## 1. Check there is a program to derive from

If the system does not exist yet (a design being discussed, a service being
sketched), draw freely and label the result a sketch. Nothing below applies
to a design with no code behind it.

If the program exists but its source is not available to the generator at
generation time (not vendored, not in the build's dependency graph, in another
repository), nothing can derive the chart. Build it from a model you
transcribe by reading the source, and ship three things with it:

- **A model file that says it is a transcription.** Each node and edge
  carries the source path and symbol it was read from. The generator still
  classifies through the tables in step 5 and still runs the placement
  checks; nothing checks the model against the program.
- **A provenance table the reader can see**, rendered beside the chart, not
  kept in the generator: one row per node naming the figure, the node, and
  where it was read from. A wrong reading can be caught only there.
- **An evidence baseline**: the revision read, if the reading was pinned to
  one, or the version range and a statement that it is not pinned. Say that
  freshness is not enforced and that a reader who relies on a row should
  re-derive it against the version they run.

Caption the chart as transcribed by reading. Step 4 does not apply: there is
no source to extract from or grep, so mark its source assertions not run in
step 11's check record. Step 7's diff holds the chart to the model, not to the
program.

## 2. Pick the chart by the question

| Question | Chart | Reference |
| --- | --- | --- |
| What are the units and what depends on what; what is each shipped binary made of | build-time structure chart | `${CLAUDE_SKILL_DIR}/references/architecture.md` |
| Which threads run and how they connect; what happens to one request, in order | runtime thread model, request flow | `${CLAUDE_SKILL_DIR}/references/architecture.md` |
| What moves where in one running pipeline, DAG, or stream topology | dataflow chart | `${CLAUDE_SKILL_DIR}/references/dataflow.md` |
| Which bytes hold which field; what a stored offset points at | byte layout | `${CLAUDE_SKILL_DIR}/references/byte-layout.md` |

Read the one you need. Structure and runtime claims go
on separate charts: on a dependency graph with runtime arrows added, a reader
cannot tell which kind of claim an edge makes.

## 3. Establish the bindings

Find, or decide: the generator's location, the one command that regenerates
every chart, the CI job that regenerates and fails on a diff, and who reads
the chart before it ships. If the repository keeps a charter, read it; it
records only where the project departs from the defaults.

For a chart in a repository you cannot add to, or a figure for a talk: keep
the generator script beside the artifact, stamp the chart with the commit it
was derived from, and present it as a dated snapshot. Nothing will detect its
drift, so say so in the caption. If the program's source is also elsewhere,
step 1's transcribed model applies too.

## 4. Write the extraction and the assertions before any geometry

- **Nodes and edges come from the program's structures**: the build manifest
  through the build system's own query (`cargo metadata`), the topic registry,
  the step declarations, the wiring function, the spawn sites. Never from a
  list kept beside the code, except step 1's transcribed model when the
  source is not available to the generator.
- **Runtime claims are source assertions**, grep-checked at generation time:
  the literal thread names at the spawn sites, the queue wiring, the ports.
  On the io_uring runtime, exact source markers asserted before rendering
  caught three stale claims on the first run.
- **Assert absences too.** "This variant spawns no signal-handler thread" is
  a check that aborts on drift. A failing absence check is often a finding
  about the system.
- **A byte layout is decoded by the shipping codec** from a fixture the tests
  already pin. A second decoder written for the figure is a second source of
  truth; one was written and deleted for that reason.

## 5. Classify through tables that abort

The generator maps program elements to roles through tables. An element no
table covers stops the run, and a table entry naming an element the program no
longer has stops it too. A curated display order is fine if it is validated
against the derived facts at generation time.

## 6. Draw every stateful component as its own node

A ring, queue, cache, store, or cursor named inside the label of the process
that uses it is invisible. If a box names both a unit and something that
outlives it, split it. On one chart this moved the central claim: two paths
drawn as separate pipelines met at a shared ring, so the paths were identical
from the ring down, one node earlier than the chart had said. Loss happens at
the component with a capacity, so a chart without that node has nowhere to
show loss, and readers conclude the path is lossless.

## 7. Generate a text source and hold it fresh

Build the generator in the project's own toolchain, so contributors need no new
dependency. Commit a text source (`.dot`, `.d2`, or SVG emitted directly), not
a raster. One command regenerates every chart; a CI job reruns it and fails on
any diff against the committed output. Keep a prose equivalent of every
embedded chart beside it.

## 8. Verify the rendering

- Rasterize the committed artifact with the tooling the publishing host uses.
  A byte-layout figure had two defects invisible in a browser: `--` inside an
  XML comment, which strict parsers reject, and a root style with maximum
  width and automatic height, which the rasterizer collapsed to zero height.
- After any change meant to move the layout, confirm the rendered geometry
  changed (bounding box, node positions). Layout engines ignore attributes
  they do not support, and the source still looks right.
- After refactoring the generator, byte-compare its output to the previous
  output.
- A bounds check proves containment and nothing else. Seven defects a reader
  reported on the io_uring runtime's charts all passed the bounds check. Run the
  placement checks in `${CLAUDE_SKILL_DIR}/references/placement.md` as generator
  assertions.
- Choose colors by how the chart is embedded. A chart shipped as an image
  uses fixed ink on an opaque ground, because a host that embeds an image
  drops the page's colors. A chart inlined in a page that defines a semantic
  palette uses the page's tokens, so a hue means the same in the chart as in
  the prose beside it and switches with the theme. When one chart ships both
  ways, generate both from one source. The palettes in the references are the
  fixed-ink defaults.

## 9. Repair a failed check, within a limit

Report each failed check with a stable rule name, the IDs of the elements it
names, the observed geometry or claim, the constraint it expected, and the
artifact checked. The generator's existing diagnostics are enough; do not
build a reporting framework for this.

Repair the generator around the implicated elements. A repair keeps the
chart's meaning: containment, the relationships and conditions drawn, what
each label says, and in a byte layout the offsets. Do not drop an element or
loosen a check to make the layout pass. After the repair, inspect the
rendered result and rerun every source and placement assertion it could
affect. Fewer diagnostics does not show the repair worked, because the repair
can introduce a new defect.

Keep the last passing artifact and test each candidate separately from it. If
the same diagnostic survives two repairs aimed at it, inspect its measurements
and the source contract it checks before one more attempt. If it still fails,
stop and report the unresolved constraint. The previous artifact may stay as a
labelled snapshot; it is not evidence that the current source passes. The
limit of two repairs is a draft default that no real repair has tested yet.

## 10. Have a person read it, then turn findings into assertions

Assertions catch drift; they do not catch a label naming the wrong thing or a
layout that suggests a difference the program lacks. Someone reads every new
chart and every visual change; approval of one revision does not cover the
next. If the raster preview the reading depends on is unavailable, say so and
name what stood in for it (markup validation, hash-compared regeneration,
bounds and collision checks, a reviewer reading the committed file).

Convert each reported defect into a generator assertion. A fix made in
coordinates returns at the next layout change.

## 11. Report

- The chart's claim in one sentence, used as the caption.
- One provenance row per chart: source, regeneration command, what the
  generator asserts.
- A check record for each rendered artifact, kept in the journal, the test
  output, or beside the artifact. It names the source revision and any dirty
  inputs (with a snapshot or diff of the uncommitted ones), the rendered
  file's path and content hash, and the regeneration command. It marks the
  source assertions, the rendering checks, the visual inspection and the
  person's approval each as passed, failed, or not run, with the reason for
  any not run, and names the renderer inspected and the person who approved.
  The record is valid only for that source and that artifact; after an edit,
  rerun the affected checks and get a new read.
- Every default you overrode and why. Record it in the charter or the
  project's journal (`journal`); that record is how these
  defaults improve.
- What was not checked, and why.

Labels, keys and captions follow the user's writing rules and
`prose`. Identifiers, type names and byte values are never
reworded to read better.

## Never

- **Never keep a node or edge list by hand** beside the code it describes.
  The one exception is step 1's transcribed model, for source the generator
  cannot read, labelled as a transcription.
- **Never let the generator skip an element it cannot classify**, or keep a
  table entry for an element that no longer exists.
- **Never draw structure and runtime claims on one chart.**
- **Never encode a value you had to guess**; leave it unencoded.
- **Never loosen a bounds check to admit an overflowing label**; fix the
  placement.
- **Never route a byte grid through a layout engine**; position is the
  address.
- **Never ship a chart nobody has read**, or a skipped read with no record of
  what replaced it.
- **Never commit a raster with no source beside it.**
