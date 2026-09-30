# Grep probes for a comment sweep

These find candidates; every hit needs a reading. They miss cases by nature,
so also read the densest prose in scope (module docs, READMEs) without a
pattern in hand. Before trusting a zero-hit probe, run it once on a string you
know should match.

Scope each to the diff's files, and exclude vendored and generated trees at
the end of the command so a later include cannot re-admit them:

```sh
FILES=$(git diff --name-only <base>...HEAD)
```

## Authoring-session vantage (step 4)

```sh
# references only the session could resolve
rg -n '\(decision \d|\(audit [A-Z]?\d|plan §|design §|§\d' $FILES
# PR and stack vantage
rg -n -i 'this PR|this branch|this stack|later PR|previous commit' $FILES
# change narration
rg -n -i 'used to |no longer|previously|the old |was renamed|we changed' $FILES
# indexical stamps and hedges
rg -n -i '\bfor now\b|\btoday\b|this cut|should be enough|should suffice' $FILES
# review choreography and argument with a reviewer
rg -n -i 'rejected in review|reviewer|it simply|is safe because' $FILES
```

Known false positives, which stay:

- instrumental "used to" ("the key used to sign requests");
- runtime old/new ("the old connection drains before the new one accepts");
- `v1` as a path or protocol segment;
- `§N` of an external standard (RFC 9110 §10.1.5);
- "PR" in documentation about the PR process itself.

## Claims to check against the code (step 5)

```sh
rg -n -i '\bno \w+ (yet|currently)|\bonly\b|nothing else|\bnever\b' $FILES
rg -n -i 'same as|mirrors|matches|identical to|looks like' $FILES
rg -n -i '\b(reads|consumes|forwards|subscribes|owns|calls)\b' $FILES
```

For each hit in a comment, name the grep or test that confirms it, or correct
it.

## Leftovers that are never kept

```sh
rg -n 'TODO|FIXME|XXX' $FILES | rg -v -i '#\d+|TODO\(\w+\)|https?://'
rg -n '^\s*(//|#)\s*[-=*]{4,}' $FILES      # banners
```

Commented-out code needs a reading; a probe for it produces too many false
hits to be worth running.
