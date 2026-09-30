# Placement checks beyond bounds

Every element inside its panel is the weakest layout claim available, and it is
usually the only one a generator checks. On the io_uring runtime's topology and
request-lifecycle charts, a reader reported seven defects, and all seven passed
the bounds check. Each rule below is one of those defects. Implement each as a
generator assertion that runs beside the bounds check.

| Rule | Defect it came from | Assertion |
| --- | --- | --- |
| Place a label against the resolved shape: explicit anchor, centered on the box or segment it names, minimum padding from borders, arrow paths and other text | text clear of the panel edge still crossed a connector running past it | text bounding boxes do not intersect shapes, connectors, or other text |
| Center a multiline label as one group: measure the line group, center it, then place each baseline | a two-line label centered on its first baseline sat visibly high | the group's vertical center equals the shape's, within a tolerance |
| Place the connectors on one shape edge together: one at the midpoint, two symmetric about it, more evenly spread with corner padding | arrows attached one at a time left the first on the midpoint and the others pushed aside | connector offsets on each edge are symmetric about its midpoint |
| Route to the resolved border, not to the column the shape nominally sits in | a connector correct for a narrow box went through a wider sibling | every endpoint lies on the border of the shape it names; equivalent steps share one geometry |
| Label a parallel pair outward: upper label above the upper line, lower below the lower | both labels above their lines put the inner one nearer the arrow it did not describe | each label is nearer its own connector than any other |
| Check containment at every level: children inside the parent's content area, siblings apart, the parent's header in its own band | child shapes crossed the parent's border; parent and child labels shared one text rhythm | child bounds within parent content bounds; header band disjoint from children |

The durability rule: a visual defect fixed by changing coordinates comes back
at the next layout change. On the runtime charts the fixes held only because
each reported defect became an assertion.

For layout-engine output (Graphviz), the engine makes most of these decisions,
but the inset-key rule in `dataflow.md` and the containment check still apply,
and "the attribute was set" is not evidence the geometry moved.
