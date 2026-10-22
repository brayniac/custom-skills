---
name: evidence
description: Ground every factual claim before stating it — in chat, a skill, a commit message, a PR body, a review finding or a report — by naming its source, checking it on the live system, labelling what stays unchecked, and checking a reviewer's or subagent's claims and replacement text before acting on them. Use before stating how a tool, API, repository, host or service behaves; before writing a count, a version, a default, a setting or "X has no Y"; before acting on a review finding or a subagent's report; and when `review`, `bench`, `report` or `audit` asks for a claim's source.
---

# Evidence

Each claim below was written at the same confidence as claims checked minutes
earlier, and each rested on memory, one repository, a PR title, a reviewer, or
an inference. In one session of skill work, these were written as fact and
refuted by a check:

| Claim | It rested on | The check that refuted it |
| --- | --- | --- |
| metriken released more than one crate together in seven of its last 18 releases | a reviewer's tally | `git log 0c4d611 --format=%s \| grep '^release: ' \| head -18 \| grep -c ','` printed 9 |
| never backport a feature | one repository's habit | rezolus `release/5.x` carries the `tcp_mib` sampler as a backport of #1472 |
| C and C++ compiles in the guest images use the shared cache since infra #124 | the PR's title | its body says the image rebuild is the next step |
| an odd stack count in a CPU profile came from a leaf losing its caller | an inference from that one count | rebuilding the toy without debuginfo restored its known 9:1 split; debuginfo had moved samples into an inlined callee |
| `.conclusion // "pending"` catches a running check | memory of the REST API, which gives `null` | `gh pr view --json statusCheckRollup` prints `"conclusion":""` for a running check, and jq's `//` keeps an empty string |
| both Macs run their systemslab agent as a LaunchAgent | a reviewer's replacement text | macstudio's host file says its agent is started by hand |

Five of the six were one command or one file read away when they were written.

## 1. Name what the claim rests on

Before writing a factual sentence, name its source:

| Source | Standing |
| --- | --- |
| a command run now, its whole output read | observed |
| a file read at a known commit, at `path:line` | read |
| a document, `--help`, a changelog, an issue | documented: describes intent, can be stale |
| one repository, host or run | one case: says nothing about the others |
| memory, training data, an earlier session | recalled: check before stating |
| a step of reasoning from another fact | inferred: name the fact and the step |
| a reviewer, subagent, Copilot or person | reported: step 4 |

Only observed and read claims are stated without qualification. Everything
else is checked (step 2) or labelled (step 3).

## 2. Check what can be checked, now

- **A count:** count it (`git log --oneline <range> | wc -l`, `grep -c`,
  `jq length`), and give the denominator when the count is a share. Do not
  write "about", "several" or a number from memory for something a command
  counts.
- **An absence** ("nothing calls X", "the repo has no Y"): a grep, with the
  pattern and the paths, including generated code, other workspaces and
  known dependents.
- **What a tool does or prints**: run it on a case whose answer you know. A
  field's value in one state (in progress, empty, failed) is not the value in
  another.
- **A platform or service setting** (a ruleset, branch protection, a
  permission, a host's service manager): read the live setting through the
  API or on the host, not the documentation's description of the default.
- **A mechanism**: write the prediction that separates it from the
  alternative and test that prediction. A mechanism that fits the symptom is
  one candidate among the ones not yet ruled out (`debug`).
- **A rule across repositories or hosts**: check each, or name the one
  checked and scope the sentence to it.
- **State that changes** (a branch head, a PR's checks, a host's load, a
  file another session edits): recheck immediately before an action depends
  on it.

Record the command and what it returned, so the check can be repeated by the
reader (`bench` step 5 for numbers).

## 3. Label what is not checked

When a claim cannot be checked now, write its source into the sentence: "the
gh manual says", "in rezolus; the other repositories not checked", "from
memory of the 1.x API, not run". State uncertainty directly ("I don't know
whether X"). Never state an unchecked claim at the confidence of the checked
ones beside it. In a document that outlives the session, use `publish`'s
tags: observed or read is measured; arithmetic on those is derived;
documented, recalled, reported or one case is given, with the source named;
what cannot be checked is unknown. A mechanism counts as derived only with
the control `report` asks for.

## 4. Check others' claims before acting on them

A review finding, a subagent's report, a Copilot comment and a person's
assertion are claims with a source of "reported". Before applying one, or
relaying it to the user as fact:

1. The quoted text exists at the cited `file:line`, at the head being
   reviewed.
2. Each factual statement in it (a count, a behaviour, "X was removed") is
   checked as in step 2.
3. The proposed replacement is itself true. A replacement is new text with
   new claims.
4. A finding that claims a failure is reproduced (`review` step 6).

When there are more findings than you will check yourself, or the text is going
somewhere it will be quoted (a skill, reference docs, a report), give steps 1 to
3 to a fresh agent: `subagent_type` general-purpose on the default model, not a
fork, read-only (no edits, push or comment). Give it the findings verbatim, the
head to check against, and this instruction: "For each finding, mark each
factual statement and each sentence of its proposed replacement confirmed (with
the command or file:line that shows it), refuted (with the evidence), or
uncheckable (why). Do not judge whether the finding matters." Act only on
confirmed findings, and on replacements whose sentences are all confirmed.

## 5. Correct in place

When a claim already stated turns out wrong, correct it where it was stated:

- in a skill, reference doc or code comment, replace the wrong text and
  check it is gone (`review` step 6);
- in a journal entry or a published finding, leave the wrong text, mark it
  refuted, and write what replaced it and why (`journal`, `publish`);
- in a pushed commit message, which cannot change, state the correction in
  the PR body or the next commit's body;
- in chat, say what was wrong and what replaced it.

## Never

- **Never state a recalled or documented fact about a tool, API or system
  as observed.**
- **Never write a count or a measurement you did not take.**
- **Never generalise from one repository, host or run** without saying which
  one.
- **Never apply or relay a finding, or its replacement text,** whose claims
  you have not checked.
