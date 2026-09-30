---
name: drive-copilot-review
description: Drive a GitHub pull request to a clean GitHub Copilot review — fix or answer every unresolved thread, reply then resolve, push all fixes, re-request once, wait for the new review, and repeat until a review of the current head adds no threads. Carries the traps that make "clean" a false reading — thread pagination past 100, the `[bot]` suffix on the re-request, re-raised findings as new outdated threads, and fix commits that were never themselves reviewed. Use when asked to iterate with Copilot on a PR, resolve the Copilot threads, re-request Copilot until it is satisfied, or drive a PR's automated review to clean.
---

# Drive a Copilot review to clean

Copilot reviews in rounds: it comments, you fix and resolve, you re-request,
it reviews again. The loop ends only when **a Copilot review of the current
head commit adds no threads**. Resolving every thread does not end it: a fix
commit is new code that has not been reviewed.

The GraphQL is in `references/copilot_review.py` (fetch with `skill_resource`
and save it locally). Use it rather than writing the queries each round; the
pagination and the reply-then-resolve pair are easy to get wrong.

```sh
H=/path/to/copilot_review.py; R=owner/repo; N=<pr>
```

## 1. Baseline

```sh
python3 $H $R $N status   # last Copilot review time, commit, reviewed_head
python3 $H $R $N list     # every unresolved thread, all pages
```

Record `last_review_at`; the next review is the first one after it.

## 2. Triage each unresolved thread

Follow the repository's own review conventions if it has them. Otherwise:

- **Correctness, security, a broken invariant, a wrong exit code**: fix it in
  this PR.
- **The finding is wrong, or the behaviour is intended**: reply with the
  evidence (a test, a quoted line, command output) and resolve. Restating the
  code is not evidence. No code change.
- **Style or a minor improvement off the critical path**: open an issue (or add
  to an existing one), reply with its link and what would reopen it, resolve.

`answer-review` has the full disposition rules; this skill adds the
Copilot-specific mechanics.

Then reply and resolve, which the helper does as two mutations and checks:

```sh
python3 $H $R $N resolve <thread-id> "Fixed in <sha>: <what changed>"
```

A resolve without a reply loses the record of why.

## 3. Push every fix, then re-request once

Commit and push all fixes from the round (`open-pr` step 5 for staging and
attribution), then:

```sh
python3 $H $R $N rerequest
```

Copilot does not re-review on a push. Re-requesting while a review is in
progress makes it review an older head and re-raise findings already fixed.
One request per batch of fixes.

## 4. Wait for the review

Reviews take about 3–6 minutes. Poll with a heartbeat and a deadline
(`watch-long-job`):

```sh
for i in $(seq 1 26); do
  sleep 45
  python3 $H $R $N status | tee /dev/stderr | grep -q "reviewed_head=yes" \
    && { python3 $H $R $N list; exit 0; }
done
echo "watcher-timeout: no review of head after 20 min"; exit 1
```

## 5. Decide

- `reviewed_head=yes` and `UNRESOLVED: 0` with no new threads: **done**.
- Otherwise go to step 2.

Copilot often re-raises an already-fixed finding as a new thread marked
`outdated`. Reply "already addressed in `<sha>`" and resolve. If it re-raises
the same deferred item round after round, making the small change it asks for
usually costs less than another round.

## Getting ahead of it on a large PR

Copilot reports one to three findings per round, so a large PR can take twenty
rounds. Before the first request, run your own review (`adversarial-review`
and the repository's linters), fix what is real, and file the rest as issues.
If the review quality drops as the diff grows — vague findings, obvious misses
— the PR is too large: merge the reviewed core and move the rest to a
follow-up PR.

## Never

- **Never call it done while `reviewed_head=no`.** Check `status` immediately
  before reporting done or merging.
- **Never count threads from a single `first:100` query**; past 100 threads the
  unresolved ones are on the next page.
- **Never re-request as `copilot-pull-request-reviewer` without `[bot]`**; the
  request is accepted and does nothing.
- **Never resolve without replying.**
