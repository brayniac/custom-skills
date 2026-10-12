---
name: check-compared-numbers
description: Check how a document writes the numbers it compares — side-by-side pairs, before-and-after changes, table rows and columns, and prose that quotes a table — so each comparison can be read without conversion and every quoted figure matches its source. Use before publishing a report, results page, benchmark write-up or PR body that compares measurements, and when a reader says two numbers are hard to compare.
---

# Check compared numbers

Numbers set side by side are read as a comparison. When the two sides differ in
unit, scale suffix or digits, the reader converts before comparing; when prose
and its table disagree, the reader cannot tell which is right. Typical cases:
`12.4K against 8,310`, `523 µs / 4.7 ms`, and a summary quoting 44% where its
source table gives 39%.

## Rules

1. **One unit and one scale suffix per comparison, chosen by the larger value,**
   while both sides keep their digits: `12.4K / 8.31K`, `0.812M / 1.39M`,
   `0.523 / 4.7 ms`. A comparison is a sentence, a table cell, an `A / B` pair,
   or a table column read down its rows (rule 3 relaxes this for columns). Exception: when the two sides
   differ by more than about three orders of magnitude, give each its own unit
   (`12 ns / 1.5 ms`), because a shared unit would print `0.000012`.
2. **Keep the digits the data supports and no more.** Three significant figures
   is the default. Never pad: if the data says 0.97, do not write 0.970; look a
   third figure up in the raw data instead of inventing it. Use more figures
   when the difference being shown is in the fourth (`2.481M / 2.486M`), or
   state the noise floor beside the pair. Integers below 10,000 on both
   sides may stay plain (`2,140 / 865`); if either side is 10,000 or more, both
   take the suffix.
3. **Rows may differ from each other.** A table whose rows span orders of
   magnitude may use a different suffix per row; within one row's comparison
   rules 1 and 2 hold.
4. **One order and one separator per figure or table.** Fix which side comes
   first (A / B everywhere) and keep it. Use `/` for side-by-side values and
   `→` for a change (before → after); in running prose `against` reads as `/`.
   If the document's owner has asked for a particular order in a chart, that
   request wins for that chart.
5. **Prose matches its source exactly.** A figure quoted in text is the same
   characters as in the table it came from, and one quantity has one value
   across the whole document.

Conversions that change the claim, not just the notation:

- Percentages and percentage points: `12% → 15%` is `+3 percentage points`
  and `+25%`; never write `+3%`.
- Bits and bytes (`Gbit/s` and `GB/s` differ by 8), and decimal and binary
  prefixes (`GB` and `GiB` differ by 7%). Convert explicitly, with the factor,
  or keep the source's unit.

## Procedure

1. **Get the text a reader sees, with line numbers.** For HTML, remove
   `<script>` and `<style>` blocks and tags without removing newlines (for
   example, replace every tag with a space), so chart data and markup do not
   produce false pairs and hits can be located.

2. **Search for candidate pairs.** The pattern below uses ripgrep's default
   engine, so it runs without PCRE2:

   ```sh
   rg -n -o -e '[+−-]?\b\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?(?:\s?(?:[kKMGT]i?B/s|[kKMGT]i?B|[GM]bit/s|[kKMGT]?req/s|[KMGkT](?:\s?req/s)?|ns|us|[µμ]s|ms|s|%|×))?\s*(?:/|→|against|vs\.?|versus)\s*[+−-]?\b\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?(?:\s?(?:[kKMGT]i?B/s|[kKMGT]i?B|[GM]bit/s|[kKMGT]?req/s|[KMGkT](?:\s?req/s)?|ns|us|[µμ]s|ms|s|%|×))?' FILE
   ```
   Add the document's own units to both unit lists (`Gbps`, `Mops/s`, `x` for
   ratios). A match is only a candidate; read each hit. The search misses
   comparisons with a word between the separator and the second number
   (`against B's 8,310`, "from 12 to 15") and units outside its lists. It also
   hits fractions (`1/2`), dates (`2026/10`), mix labels (`80/20`) and version
   strings (`v1.2/1.3` matches as `2/1.3`).

3. **Judge each pair against the rules.** Flag a different suffix or unit (rule
   1), either side 10,000 or more without a suffix, and digits the data does
   not support (rule 2). These are
   not findings: ranges written with an en dash (`2.52–2.58M`, where the suffix
   covers both ends), mix labels, fractions, dates, and pairs of plain integers
   below 10,000.

4. **Check every table.** For each row, its compared cells (rules 1 and 2). For
   each column read as a comparison, one suffix unless rows span magnitudes
   (rule 3). One order across the table and across tables (rule 4). This step
   finds what step 2 cannot.

5. **Check prose against tables (rule 5).** For every number in prose that
   restates a table value, find the cell and compare character for character.
   Search the document for each headline quantity and confirm it has one value
   everywhere. Recompute stated differences and percentages from the table
   values.

6. **Fix, then repeat steps 2–5.** When a figure changes, change every place it
   appears. When a third figure is missing, take it from the raw data.

## Do not

- Do not round one side to make the two sides match; rewrite both in the shared
  suffix with the digits the data supports.
- Do not treat step 2 as the whole check. Comparisons spread over a sentence
  ("A serves 4.07M; B, 2.95M") and comparisons in tables are found by steps 4
  and 5.
