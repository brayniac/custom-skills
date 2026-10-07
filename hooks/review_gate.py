#!/usr/bin/env python3
"""Refuse a PR merge unless the merge is pinned to a reviewed head commit.

PreToolUse hook on Bash. A merge passes only in this form:

    gh pr merge <number-or-url> --repo <owner/repo> --match-head-commit <sha> ...

and only when a record for <sha> exists in ~/.claude/cs-reviews/<owner>/<repo>/
(CS_REVIEW_DIR overrides the root), written by
skills/review/references/record-review.sh after a review whose verdict was
merge, or as a waiver the user agreed to. `--match-head-commit` makes GitHub
refuse the merge if the head moved after the review, so a push between the
review and the merge cannot slip through; the gate needs no network.

A merge is recognised as `gh ... merge` in one simple command (gh by basename,
flags anywhere, quotes and backslashes removed), in the argument of a shell's
`-c` option (`bash -c`, `-lc`, `-ec`) or `eval`, or in a backtick or `$( )`
substitution. Heredoc bodies are ignored: text being written is not run.
Refused outright, with the form to use instead: `gh api` calls to a pull's
merge endpoint or the `mergePullRequest` mutation, and `--auto`. Allowed:
`--disable-auto` and `--help`. Not recognised: a gh alias, or gh run from
another language (`python3 -c "subprocess.run(['gh', ...])"`). This is a
backstop for an agent forgetting the review, not a sandbox.

Blocks with exit 2 and the reason on stderr. A command that mentions a merge
and does not tokenise (unbalanced quotes) is refused. An internal error in this
script lets the command through, so a bug here cannot stop all work.
"""
import json
import os
import re
import shlex
import sys

ROOT = os.environ.get("CS_REVIEW_DIR") or os.path.expanduser("~/.claude/cs-reviews")
PLUGIN = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
RECORD = '"' + os.path.join(PLUGIN, "skills", "review", "references", "record-review.sh") + '"'
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SHA = re.compile(r"^[0-9a-f]{40}$")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
SUBST = re.compile(r"`([^`]*)`|\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
API_MERGE = re.compile(r"pulls/\d+/merge\b|mergePullRequest|enablePullRequestAutoMerge")
MAYBE = re.compile(r"\bgh\b.*\bmerge\b|pulls/\d+/merge|mergePullRequest", re.S)


class Refuse(Exception):
    pass


def strip_heredocs(cmd):
    # Keep the line with the `<<` operator, drop the body and terminator.
    return HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)


def simple_commands(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    out, cur = [], []
    for tok in lex:
        if tok and set(tok) <= set(";&|()<>"):
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def check_pr_merge(args):
    """args: the words after `gh`, which contain `merge` after `pr`."""
    sel = repo = sha = None
    auto = disable = helpw = False
    i = 0
    while i < len(args):
        w = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if w in ("-R", "--repo"):
            repo = nxt; i += 2; continue
        if w.startswith("--repo="):
            repo = w.split("=", 1)[1]
        elif w == "--match-head-commit":
            sha = nxt; i += 2; continue
        elif w.startswith("--match-head-commit="):
            sha = w.split("=", 1)[1]
        elif w == "--auto":
            auto = True
        elif w == "--disable-auto":
            disable = True
        elif w in ("-h", "--help"):
            helpw = True
        elif w in ("-b", "--body", "-F", "--body-file", "-t", "--subject", "-A", "--author-email"):
            i += 2; continue
        elif w in ("pr", "merge") or w.startswith("-"):
            pass
        elif sel is None:
            sel = w
        i += 1
    if helpw or disable:
        return
    if sel:
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", sel)
        if m:
            repo = repo or m.group(1)
    form = ("gh pr merge <number> --repo <owner/repo> --match-head-commit <reviewed-sha> "
            "--squash (or the repo's merge style)")
    if auto:
        raise Refuse("`--auto` merges whatever head is current when checks pass, "
                     f"not the reviewed one. Wait for the checks, then run: {form}")
    if not sel or not repo or not sha:
        missing = [n for n, v in (("the PR number", sel), ("--repo", repo),
                                  ("--match-head-commit <sha>", sha)) if not v]
        raise Refuse(f"the merge does not name {', '.join(missing)}. The review gate "
                     f"merges only a pinned, reviewed head: {form}")
    if not SHA.match(sha):
        raise Refuse(f"--match-head-commit {sha} is not a full 40-character SHA.")
    repo = repo.lower()
    if not os.path.exists(os.path.join(ROOT, repo, sha)):
        raise Refuse(
            f"{repo} {sha[:12]} has no recorded review.\n"
            f"Run /cs:review on this head (a fresh agent, the `review` skill), answer every "
            f"finding, and when its verdict is merge, record it:\n"
            f"  bash {RECORD} {repo} {sha} merge \"<summary>\"\n"
            f"A commit pushed after the review is a new head and needs its own. For a change "
            f"with nothing to review, and only if the user agrees:\n"
            f"  bash {RECORD} {repo} {sha} --waive \"<reason>\"")


def check(cmd, depth=0):
    cmd = strip_heredocs(cmd)
    # The quick filter sees the words as the shell will: `m\erge` and `"merge"`
    # are merge.
    if not MAYBE.search(re.sub(r"[\\'\"]", "", cmd)):
        return
    if depth < 4:
        for m in SUBST.finditer(cmd):
            check(m.group(1) or m.group(2) or "", depth + 1)
    try:
        commands = simple_commands(cmd)
    except ValueError:
        raise Refuse("this command mentions a merge and does not tokenise (unbalanced "
                     "quotes?). Run the merge as its own plain command.")
    for words in commands:
        for k, w in enumerate(words[:-1]):
            base = os.path.basename(words[k - 1]) if k > 0 else ""
            if depth < 4 and ((base in SHELLS and re.match(r"^-[a-z]*c[a-z]*$", w)) or w == "eval"):
                check(words[k + 1], depth + 1)
        for i, w in enumerate(words):
            if os.path.basename(w) != "gh":
                continue
            rest = words[i + 1:]
            if "api" in rest[:3] and any(API_MERGE.search(x) for x in rest):
                raise Refuse("merging through `gh api` bypasses the review gate's pin. Use: "
                             "gh pr merge <number> --repo <owner/repo> --match-head-commit "
                             "<reviewed-sha>")
            if "pr" in rest and "merge" in rest and rest.index("pr") < rest.index("merge"):
                check_pr_merge(rest)


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            return 0
        cmd = (data.get("tool_input") or {}).get("command", "")
        if not cmd:
            return 0
    except Exception:
        return 0
    try:
        check(cmd)
    except Refuse as r:
        print(f"BLOCKED by the review gate: {r}", file=sys.stderr)
        return 2
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
