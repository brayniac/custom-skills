# Diagram charter template

Copy into the repository (for example `docs/diagrams/CHARTER.md`) when its
charts are meant to be kept. The charter records only what no default can
supply, plus each departure from the defaults with its reason. A convention it
does not mention uses the default.

## Chart inventory

| Chart | Kind (build / runtime / dataflow / byte layout) | Committed source and output | Generator module | Held to the code by |
| --- | --- | --- | --- | --- |
| `<name>` | `<kind>` | `<paths>` | `<path>` | `<manifest query, source assertions, codec fixture>` |

Where each chart is embedded, and where its prose equivalent lives: `<paths>`.

## Generator

- Regeneration command (one, for every chart): `<command>`
- Toolchain (the project's own; no new contributor dependency): `<...>`
- Output format and render command: `<.dot/.d2/direct SVG>`
- Layout engine and version, or "geometry emitted directly": `<...>`
- Shared visual-language module: `<path>`
- Where assertions live and how they fail: `<path>`

## Ground truth

- Build half: `<manifest query>`; wiring greps the manifest cannot see:
  `<patterns>`
- Runtime half: `<spawn sites and literal thread names, queue wiring, ports,
  absence checks>`
- Dataflow: `<registries, step declarations, wiring functions>`
- Byte layout: `<fixture path, codec entry point>`
- Tables that need maintenance when code changes (each aborts on an
  unclassified or stale entry): `<names and paths>`

## Freshness

- CI job that regenerates and fails on a diff: `<job>`
- When contributors run it locally: `<...>`

## Reader

- Who reads every new chart and every visual change: `<name>`

## Departures from the defaults

- `<departure, and the reason>` or "none"

## Filled by

- `<who, date, sources inspected, unresolved questions>`
