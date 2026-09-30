# Dataflow charts

For one running program's pipeline, DAG, stream topology or service graph.
These conventions were distilled from one project's charts and have been
applied to one other since. Before adopting them, ask three questions and
record the answers:

- Does compute-versus-data partition this system's nodes, or is there a third
  kind?
- Does the palette survive the medium the chart will be read in?
- Does the reader need a distinction no channel here carries?

## Every visual property is a claim

A reader who sees two things drawn differently looks for the difference, so
spend each channel on one distinction:

| Channel | Carries |
| --- | --- |
| shape | what kind of thing it is (holds history, computes, fixed value) |
| fill | which family within a kind (role of an operation, boundary of a topic) |
| line style | conditionality: solid always, dashed sometimes, dotted a non-dataflow dependency |
| decoration (a frame) | a property layered on a kind, such as "recorded by a run" |

- A glyph asserts its own structure. A six-celled queue claims a history a
  reader can look back over; drawn on a write-once parameter it claims
  something false.
- Make absence visible. When a property is encoded, elements without it must
  read as lacking it. One input with no recording frame is a finding only
  because the others are visibly framed.
- Do not encode a value you had to guess. An unknown drawn as a plausible mark
  is worse than a gap.

## Compute and data get different outlines

- **Compute** (operations, stages, transforms): rounded corners,
  `shape=box, style="rounded,filled"`.
- **Data** (queues, topics, buffers, parameters, stores): square corners.
- Within data: **a history** is a segmented glyph (cells in a row); **a single
  value** is an unsegmented glyph, such as `shape=note` for a parameter fixed
  before the run.

## Add a shape only for a new kind of thing

Every shape costs every reader a lookup. When the thing is an existing kind
with a property, annotate the existing shape: fill for family, a frame for a
layered property, the frame's line style for whether it always holds. The
test: would a reader who knows the base shape still recognize it? A framed
queue is a queue; a folded-corner page is not, and appears only because a
parameter is not a history.

## Default palette

Adopt it whole or replace it whole.

Operation fills (ColorBrewer Accent, pastel):

| Role | Hex |
| --- | --- |
| sensing / ingest | `#BEAED4` |
| estimation | `#7FC97F` |
| detection / decision | `#FFFF99` |
| control / output | `#FDC086` |

Data tints, lighter than the operation fills:

| Kind | Hex |
| --- | --- |
| external input | `#E6DEF2` |
| derived | `#EDEDED` |
| state carried across ticks | `#FBE3CB` |
| parameter | `#DDE4CF` |

Edges: `#4D4D4D` for ordinary dataflow; `#CC79A7` and `#D55E00` (Okabe–Ito,
colorblind-safe) for the two paths worth separating. Keep those two if you
change everything else, because edge color has no shape to fall back on. Key
panel: `#F2F2F2` fill, `#9E9E9E` border.

## Edge vocabulary

| Style | Means |
| --- | --- |
| solid | dataflow that constrains evaluation order |
| dashed, `constraint=false` | a value crossing a cycle boundary: real flow, no ordering claim |
| dotted | a dependency that is not dataflow, such as a parameter reaching an operation |
| `penwidth=2` | the product the pipeline exists to emit |

Dashed and unconstrained deferred reads keep a cyclic program readable as a
DAG. Frames on glyphs use the same grammar: solid frame for a property that
always holds, dashed for conditional, none for absent. Scale the frame with
the glyph, or it becomes a slab on the key's smaller copy.

## Position

- Lay out along the flow (`rankdir=LR`) and pin each topological level to one
  rank, so columns are levels.
- Where a boundary matters (asynchronous arrival on one side, deterministic
  evaluation on the other), pin the inputs into one column so the boundary is
  one rule.
- Number compute nodes by evaluation order only when order is a fact of the
  program. If the chart is emitted directly rather than through Graphviz, draw
  the badges (`architecture.md`).
- Two implementations of one flow get separate panels, top and bottom.

## The key

- Draw the key with the chart's own generator and shapes, as its own graph
  merged at render time. A key built from table cells can only approximate a
  shape.
- Order entries by channel: shapes, then line styles, then symbols.
- Show the glyph, never a color's name. "Lilac means input" fails a
  colorblind reader.
- Add a key only once the chart has more than about two orthogonal channels.
  A three-node chain with one edge style needs none, and adding one implies
  distinctions the chart does not draw.
- Keep it smaller than the chart, placed in the chart's own whitespace.

## Placement of an inset key

Check the key's position against the laid-out graph's node boxes **and** edge
splines, and fail the build on overlap. An edge routed through empty space is
invisible to a box-only check. A warning about a chart nobody is looking at is
not read.
