# Byte-layout figures

For a memory or wire format that already exists in code: the byte anatomy of
one encoded instance, the per-variant conventions of a shared encoding, or the
linkage between blocks. The conventions come from one binary collection format
in one repository. The first three rules below are that format's author's; the
rest is inferred from the figures and carries less weight.

## Three rules

- **Position is the byte offset, so no layout engine.** Emit the drawing
  directly with integer geometry and fixed order. Routing the byte grid through
  a graph layout engine was tried and abandoned: clusters and edges moved
  cells.
- **Spans come from a golden fixture decoded by the shipping codec.** The
  generator walks a frozen test fixture through the production decoder and
  aborts when any drawn span disagrees with the bytes. A decoder written for
  the figure was deleted because it was a second source of truth.
- **Freshness is a deterministic regenerate-and-diff of the committed
  artifact.** A checksum of the source does not cover the file readers open.

## What the generator asserts

- Every span against the bytes: a length, a count, or a stored offset that
  does not land on the element it names aborts, naming the disagreement.
- **Re-encode and compare.** Re-encode each decoded value and compare bytes.
  This catches a tier table that has drifted from the encoder, which decoding
  alone does not.
- Cells past the drawing bounds abort. A figure that clips silently is worse
  than one that refuses to render.
- The fixture is one the tests already pin, and the figure names it.
- The regeneration command appears in the artifact's header and in the
  provenance table.

Choose the instance for coverage: the smallest encoding that has the header,
at least two entries, at least two width tiers, and every cross-reference the
format defines. A one-entry example shows only the header.

## Source format by kind of figure

| Figure | Source | Why |
| --- | --- | --- |
| byte anatomy | generated, emitted directly, committed as produced | a render step reintroduces a layout engine's freedom over positions that are addresses |
| relationship schematic (chaining, linkage, shipped vs reserved) | graph source, rendered | the claim is what connects to what, so a layout engine is correct |
| variant conventions and other design claims | hand-authored, dated, naming the review it came from | no code produces them; nothing will detect their drift |

A generated figure may not draw what does not exist. A schematic may, if the
unbuilt part is dashed, the shipped part solid, and the caption says which.

## Default visual language

- One cell per byte, fixed width, in offset order, value in hex.
- Fill by role (header, tag, payload, trailer), reused across entries.
- An offset ruler under the cells at reduced opacity.
- Brackets above for spans, staggered when labels collide, each carrying the
  field name and its decoded value, so a reader can check the figure against
  the bytes.
- An arrow from every stored offset to the element it addresses.
- A caption that states the claim ("the tail offset points at the last entry's
  first byte, so tail access is constant time"), not the contents.
- Fixed ink on an opaque ground. A host that embeds the figure as an image
  drops inherited page colors.
- An accessible label inside the figure and prose beside it stating the same
  claim.

The placement rules in `placement.md` apply as soon as the generator emits its
own geometry: a bracket label nearer a neighbouring span than its own, or an
offset arrow attached wherever the code reached first, is inside the frame and
is what a reader sees first.

## Tried and abandoned

- A graph layout engine for the byte grid.
- A second decoder to drive the figure.
- A grid drawn by hand from the specification: correct until the first
  encoder change, with nothing to detect it.
- "Regenerate when the format changes" as the freshness rule; until a
  regenerate-and-diff runs somewhere, assume the figure is stale.
- One undifferentiated figure for the shipped and the planned shape.
