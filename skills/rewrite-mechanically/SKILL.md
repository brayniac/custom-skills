---
name: rewrite-mechanically
description: Apply a pattern-based edit across many files without damaging code that only resembles the target — literal matching, a bounded region, a match count asserted against an expectation before writing, a line-based transform instead of a multi-line regex for source code, a diff of files that should not have changed, and a check that the replaced text is gone. Use when a sed, perl, regex, or scripted rewrite touches more than a couple of files; when replacing an API call pattern or a doc section repo-wide; and when searching for a literal string containing `.`, `(`, `[`, `*` or `?`.
---

# Rewrite mechanically

A scripted rewrite fails in two ways, and neither reports an error: it matches
something it should not, or it skips something it should have changed. Every
step below closes one of those.

For a change to a single site, use an editor. This is for rewrites across
files.

## 1. Write the target as a literal and bound the region

- Search with `grep -F` / `rg -F`. `grep "verify.log"` matched
  `verify logs.json`, because `.` is a wildcard.
- Include enough context to be unique. A replacement for
  `.build().expect(...)` also matched `ConfigBuilder::build().expect(...)` and
  damaged eleven unrelated files; the target was `Client::builder()…build()`.
- Bound the region: the list of files, and within a file the enclosing item
  (`impl Foo`, `fn bar`, the `# Errors` section). Do not run a rewrite over the
  whole tree when the target lives in one crate.

## 2. Count matches and write down the expected count before writing

```sh
rg -F -c '<literal>' <paths> | sort
```

Write the expected number per file next to the command, from what you know of
the code, before reading the output. If the counts differ, stop and find out
why. A count you did not predict is how the eleven extra files would have been
caught.

## 3. For source code, use a line-based transform, not a clever regex

A multi-line regex with backreferences failed to compile, then silently skipped
the cases whose arms were formatted slightly differently. A short script that
finds the opening line, tracks brace depth, and rebuilds the block handled every
variant and was easier to check:

```python
out, inside = [], False
for line in src.splitlines(keepends=True):
    if not inside and OPENER in line:
        inside, opened, depth, block = True, False, 0, []
    if inside:
        block.append(line)
        depth += line.count("{") - line.count("}")
        opened = opened or "{" in line
        if opened and depth == 0:          # the block's closing brace
            out.append(rewrite(block)); inside = False
        continue
    out.append(line)
```

Have the script count what it changed and assert that count equals the step 2
expectation before it writes any file.

For Rust, check whether the change can be expressed as a compiler-driven edit
first (rename the item and follow the errors, `cargo fix`, clippy's
`--fix`), which cannot match the wrong text.

## 4. Dry-run to a diff and read the files you did not intend to touch

```sh
git diff --stat
git diff --name-only | grep -v -F -f intended-files.txt   # must print nothing
```

Every file outside the intended set is damage until shown otherwise.

## 5. Assert the old text is gone, not only that the new text is present

```sh
rg -F '<old literal>' <paths> && echo "OLD TEXT REMAINS"
```

A "this cannot fail" note was appended to an existing `# Errors` section instead
of replacing it, so two crates shipped docs that said a function fails with
`EBUSY` and, three lines later, that it cannot fail. For prose, read each edited
section once to confirm it does not now say both things.

## 6. Verify the build, including the code this platform cannot compile

A rewrite that changes ownership or types can break a use inside a
`#[cfg(...)]` block the local compiler never sees. Hand off to `verify-change`
(steps 4 and 5) before pushing.

## Never

- **Never use an unanchored regex for a literal string.**
- **Never write before the match count agrees with the prediction.**
- **Never accept a diff that touches a file outside the intended set** without
  reading that hunk.
- **Never check only for the new text** after replacing prose.
