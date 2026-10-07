#!/usr/bin/env python3
"""Refuse `gh pr merge` of a head commit nobody reviewed.

PreToolUse hook on Bash. For each `gh pr merge` in the command, resolve the
PR's current head with `gh pr view` and look for a record of that exact
commit in ~/.claude/cs-reviews/<owner>/<repo>/<sha> (CS_REVIEW_DIR overrides
the root), written by skills/review/references/record-review.sh after a
review, or as a waiver the user agreed to. A commit pushed after the review
is a new head and needs its own record.

A merge is `gh pr merge` as separate words (gh by basename), in the command
or in the argument of `bash -c` / `sh -c` / `eval`; a mention inside any other
quoted argument (`git log --grep "gh pr merge"`) is not one. Blocks (exit 2,
reason on stderr) when the record is missing, when the PR cannot be resolved,
or when a command mentioning a merge does not tokenise (unbalanced quotes): it
guards a merge, so not knowing is a refusal. Lets the command through on
an internal error in this script, so a bug here cannot stop all work.
"""
import json
import os
import re
import shlex
import subprocess
import sys

MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
SHELLS = {"bash", "sh", "zsh", "dash"}
OPERATORS = {";", "&&", "||", "|", "&", "\n", "(", ")"}
ROOT = os.environ.get("CS_REVIEW_DIR") or os.path.expanduser("~/.claude/cs-reviews")
RECORD = "bash " + os.path.join(
    os.environ.get("CLAUDE_PLUGIN_ROOT")
    or os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "review", "references", "record-review.sh")


def words_by_command(cmd):
    """The command's simple commands as word lists, split at unquoted shell
    operators. Quoted text stays one word, so `--body "a; b"` is not split."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""
    current, out = [], []
    for tok in lex:
        if set(tok) <= set(";&|()") or tok in OPERATORS:
            if current:
                out.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        out.append(current)
    return out


def invocations(cmd, depth=0):
    """(selector, repo) for each `gh pr merge` in the command, including one
    inside a `bash -c` or `eval` argument; None when the command does not
    tokenise."""
    try:
        commands = words_by_command(cmd)
    except ValueError:
        return None
    found = []
    for words in commands:
        # A merge run by a shell or eval is in the next word: `bash -c "..."`.
        # A merge merely mentioned in an argument (`echo "... gh pr merge"`)
        # is not followed.
        for k, w in enumerate(words[:-1]):
            if depth < 3 and ((w == "-c" and k > 0 and os.path.basename(words[k - 1]) in SHELLS)
                              or w == "eval") and MERGE.search(words[k + 1]):
                inner = invocations(words[k + 1], depth + 1)
                if inner is None:
                    return None
                found.extend(inner)
        for i in range(len(words) - 2):
            if os.path.basename(words[i]) != "gh" or words[i + 1:i + 3] != ["pr", "merge"]:
                continue
            sel, repo, rest = None, None, words[i + 3:]
            j = 0
            while j < len(rest):
                w = rest[j]
                if w in ("-R", "--repo") and j + 1 < len(rest):
                    repo = rest[j + 1]; j += 2; continue
                if w.startswith("--repo="):
                    repo = w.split("=", 1)[1]
                elif w in ("-h", "--help"):
                    break
                elif w in ("-b", "--body", "-F", "--body-file", "-t", "--subject",
                           "-A", "--author-email", "--match-head-commit"):
                    j += 2; continue
                elif not w.startswith("-") and sel is None:
                    sel = w
                j += 1
            else:
                found.append((sel, repo))
    return found


def head_of(sel, repo, cwd):
    args = ["gh", "pr", "view"] + ([sel] if sel else []) + (["--repo", repo] if repo else [])
    out = subprocess.run(args + ["--json", "headRefOid,url,number"],
                         capture_output=True, text=True, timeout=30, cwd=cwd or None)
    if out.returncode != 0:
        raise LookupError(out.stderr.strip() or "gh pr view failed")
    d = json.loads(out.stdout)
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/\d+", d["url"])
    return m.group(1).lower(), d["headRefOid"], d["number"]


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            return 0
        cmd = (data.get("tool_input") or {}).get("command", "")
        if not MERGE.search(cmd):
            return 0
        cwd = data.get("cwd")
        merges = invocations(cmd)
    except Exception:
        return 0

    if merges is None:
        print("BLOCKED: this command runs `gh pr merge` in a form the review gate "
              "cannot parse. Run the merge as a plain `gh pr merge <pr> --repo "
              "<owner/repo> ...` command.", file=sys.stderr)
        return 2

    for sel, repo in merges:
        try:
            full, sha, number = head_of(sel, repo, cwd)
        except Exception as e:
            print(f"BLOCKED: the review gate could not resolve the PR to merge "
                  f"({sel or 'current branch'}{' in ' + repo if repo else ''}): {e}. "
                  f"Name the PR and --repo explicitly.", file=sys.stderr)
            return 2
        if os.path.exists(os.path.join(ROOT, full, sha)):
            continue
        print(f"BLOCKED: {full}#{number} head {sha[:12]} has no recorded review.\n"
              f"Run /cs:review on this head (a fresh agent, the `review` skill), "
              f"answer its findings, then record it:\n"
              f"  {RECORD} {full} {sha} \"<verdict>\"\n"
              f"A commit pushed after a review is a new head and needs its own. "
              f"For a change with nothing to review, and only if the user agrees:\n"
              f"  {RECORD} {full} {sha} --waive \"<reason>\"",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
