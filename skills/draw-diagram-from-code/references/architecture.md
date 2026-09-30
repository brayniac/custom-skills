# Architecture charts: one build-time chart, one or two runtime charts

A system's architecture makes two kinds of claim with different ground truth:

- **Build-time**: what the code is — its units (crates, packages, modules),
  their layering, and what each shipped binary is composed of. Ground truth is
  the build manifest, read through the build system's own query interface.
- **Runtime**: what the program does — the threads it spawns, the queues
  between them, the path of one request. Ground truth is the source, held to
  the chart by assertions.

Draw them separately and link them with chips (below). These conventions were
derived on a multi-binary cache framework and carried to an io_uring runtime
library, whose reader supplied the placement rules in `placement.md`.

## Shared across the set

- **One visual-language module** owns the palette, type scale and drawing
  primitives for every chart, so the charts read as one set.
- **Chips link the halves.** A runtime container carries small chips naming
  the build-time modules that execute in it, in the build chart's layer colors,
  so a reader can follow a module from the layer chart to the thread that runs
  it. A difference between variants then shows as chips in different places.
- **Emit geometry directly** for the build chart's bands and nesting. Layout
  engines do not produce uniform sizes and computed grids, and the generator
  then owns every placement decision in `placement.md`.

## The build-time chart

- **Group units into a handful of blocks.** Unit-level arrows at whole-system
  scale were unreadable under every layout-engine setting tried (clustering,
  edge concentration, rank constraints).
- **Encode layering by position and composition by nesting.** Stacked
  full-width bands carry layering; each product box containing bars for its
  protocol, storage and core choices carries composition. Most arrows then
  disappear; any that remain are block-level aggregates.
- **Assert the position claim.** Arrange blocks so that row-major reading
  order is a topological order of the real dependency subgraph, and check that
  at generation time.
- **Prefer near-square grids** under that constraint: six units as 3×2, never
  5+1.
- **Show block-level cycles.** A strict stack that hides a back edge claims
  acyclicity the code does not have. Draw both directions, or put the
  mutually dependent blocks in one band.
- **Place external units by role.** An external storage engine sits in the
  storage band, external TLS in the foundation. Externals enter through a
  whitelist validated against the manifest and are marked quietly (italic,
  a registry link).
- **Derive composition, including what the manifest cannot record.** A
  product's bars come from its direct dependencies plus targeted source greps
  for wiring choices (which storage engine it instantiates). Abort when a
  product links a facade without wiring a concrete choice.
- **Distinctiveness is direct dependencies minus those all products share.**
  Transitive closures pull a shared facade's dependencies into every product
  and erase the difference.

## The runtime charts

Usually two: a **thread model** (who runs, how they connect) and a **request
flow** (what happens to one request, in order). Both are held to the source by
positive and negative assertions on spawn sites, queue wiring, signal
registration, ports and event-loop calls.

Thread model:

- **Thread boxes carry the literal registered names**, in monospace,
  grep-asserted against the spawn sites, so an operator can match a hot thread
  in `top -H` to the chart. Use monospace only for literal strings.
- **Leave ordinary threads unfilled** so the chips carry the color; fill only
  the unusual (non-default scheduler, pinning).
- **Externals are italic and dashed.** Omit a process-boundary frame if it
  would enclose an external.
- **Edge weight marks the process boundary.** Bytes crossing it draw heavier
  than internal queue traffic. Label edges with what travels, using the code's
  type names.
- **Queues are small segmented glyphs** between the threads they connect.
- **One panel per variant, stacked vertically**, annotated in the margin with
  the binaries it covers, with same-role elements aligned across panels.

Request flow:

- **Swimlanes are threads; a stage sits in the lane that runs it**, so thread
  hops show as geometry.
- **Number stages with drawn badges** (a circle plus a digit). Unicode circled
  digits failed in font fallback.
- **Stage labels use the code's verbs** (`receive`, `execute`, `send`,
  `flush`). Exception: when the code uses one verb for two things in the same
  chart, use neither. A stage labeled `wake_recv + poll owner task`, in a chart
  comparing readiness polling with task polling, named neither mechanism; the
  lifecycle word (`schedule`) fixed it.
- **Give each backend its own panel** when their operation names differ.
  Interleaving two backends in one flow made the stages they share look like
  shared mechanism. Repeat the shared stages in each panel and state what is
  shared in the prose.
- **Use one stage pitch across panels** so the only visual difference between
  variants is the real one.
- **Draw either the data plane or the control plane** on a request-flow chart,
  and let the thread model carry the other.

## Default visual language

Adopt all of it or replace all of it; record a replacement in the charter.

- Palette (pastel, for large filled areas): interface/protocol `#FBB4AE`,
  storage/state `#B3CDE3`, runtime/core `#CCEBC5`, foundation `#F2F2F2`,
  externals white.
- Type scale: 14 for chips, legends and edge labels; 16 sub-labels; 17 element
  labels; 20 panel titles.
- Style channels: monospace for literal runtime strings; italic plus dashed for
  external; an underline for a link, drawn as a line, because some SVG
  rasterizers ignore `text-decoration`.
- Edges: 2.4 across the process boundary, 1.4 internal; orthogonal only;
  labels above the line.

## Tried and abandoned

- Unit-level arrows at system scale, with any layout-engine tuning.
- A general-purpose layout engine for the band and nesting design.
- Transitive-closure intersection as the shared core.
- Unicode circled digits for stage numbers.
- Per-product dependency minicharts; composition nesting plus a table
  replaced them. Show that a companion chart carries a claim the main chart
  cannot before building one.
