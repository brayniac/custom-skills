# Bootstrapping from history, and publishing

## Retrospective bootstrap

For a repository with no journal and a history worth recording:

1. Cluster the commit history into arcs: a release, a campaign of related PRs,
   a design that took several attempts.
   `git log --reverse --format='%h %ad %s' --date=short` and the PR list are
   the inputs.
2. Write one entry per arc from its commit range, PRs, and any design or notes
   files. One drafting agent per arc works; review each draft against its
   sources before committing.
3. Every figure carries its source (SHA, PR, file). A figure found only in
   chat or memory is omitted or labelled unverified.
4. Mark each entry retrospective in its status line, with the reconstruction
   date: "shipped (retrospective, reconstructed 2026-07-06 from commit
   history)".
5. Write the index, noting which entries are retrospective. Absorb the design
   documents the entries consumed (`keep-engineering-journal` step 6).

Two repositories bootstrapped this way: one with 9 retrospective entries
covering February through v0.4.0, one with 12 covering its first six weeks.
Both then continued with entries written during the work, and both indexes say
where the reconstruction ends. The distinction matters because a reconstructed
entry cannot record what was believed before the result was known.

## Publishing as a site (optional)

Use whatever documentation toolchain the repository already has. The pattern:

1. The journal stays the source. A build step copies `docs/journal/*.md` into
   the site's source directory (gitignored), so nothing is edited twice.
2. Build, then fail the build on broken internal links.
3. For a private repository, publish as a CI artifact, not GitHub Pages. On a
   personal account, Pages from a private repository is either unavailable
   (Free) or public (Pro); access-controlled Pages needs Enterprise Cloud and
   an organization.

Internal link check, for sites where a full link checker misreads bracketed
prose:

```python
#!/usr/bin/env python3
"""Fail if an inline relative Markdown link in <src> names a missing file."""
import re, sys, pathlib
link_re = re.compile(r"\]\(([^)]+)\)")
src = pathlib.Path(sys.argv[1]).resolve()
errors, pages = [], sorted(src.rglob("*.md"))
for md in pages:
    for m in link_re.finditer(md.read_text(encoding="utf-8")):
        t = m.group(1).strip()
        if t.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = t.split("#", 1)[0]
        if path.endswith(".md") and not (md.parent / path).resolve().is_file():
            errors.append(f"{md.relative_to(src)}: broken link -> {t}")
if errors:
    print("Broken internal links:", *("  " + e for e in errors), sep="\n",
          file=sys.stderr)
    sys.exit(1)
print(f"Link check OK ({len(pages)} pages scanned).")
```

Mermaid diagrams: a syntax error renders a blank diagram and does not fail
the build. Check the built HTML for the render marker (`class="mermaid"`)
present and the unrendered fence (`language-mermaid`) absent.

Curated pages added to the site (overview, architecture) follow the entry
rules: flags, config fields, and numbers checked against source before they
land.
