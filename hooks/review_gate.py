#!/usr/bin/env python3
"""Refuse a PR merge unless the merge is pinned to a reviewed head commit.

PreToolUse hook on Bash. A merge passes only in this form:

    gh pr merge <number-or-url> --repo <owner/repo> --match-head-commit <sha> ...

and only when a record for <sha> exists in ~/.claude/cs-reviews/<owner>/<repo>/
(CS_REVIEW_DIR overrides the root), written by
skills/review/references/record-review.sh after a review whose verdict was
merge, or as a waiver the user agreed to. `--match-head-commit` makes GitHub
refuse the merge if the head moved after the review; the gate needs no network.

The command is parsed the way the shell would split it, for the forms below.
Line continuations are joined; `#` comments (a `#` at the start of a word,
outside quotes) are dropped; the rest is split at `;`, `&`, `|`, parentheses,
redirections and newlines, with quotes and backslashes removed. In each simple
command, leading `VAR=value` assignments and the keywords `if then else elif do
while until ! { } time` are skipped; after a wrapper (`command`, `exec`, `env`,
`nohup`, `nice`, `sudo`) or a runner (`xargs`, `timeout`, `stdbuf`, `watch`,
`find`) any later `gh` word is the command. Then:

- `gh` (by basename), or a word that is a variable or a `$( )`/backtick
  substitution (`$GH`, `$(which gh)`), followed by `pr merge`: a merge, checked
  as above. `--repo` and `GH_REPO`, `-R` in any short-flag cluster and a
  `HOST/OWNER/REPO` value are read; a PR URL names its own repository, and one
  that disagrees with `--repo` is refused.
- `gh api` touching a pull's merge endpoint, a repository's `merges` endpoint,
  or the `mergePullRequest`, `enablePullRequestAutoMerge` or
  `enqueuePullRequest` mutations: refused, with the pinned form to use.
- a shell (`bash`, `sh`, `zsh`, `dash`, `ksh`) with `-c` among its options, or
  `eval`: its script is checked the same way, as is a here-string or a heredoc
  a shell or `ssh` reads. A shell reading a pipe, in a command that mentions a
  merge (a piped heredoc's body included), is refused.

`$( )` and backtick substitutions outside single quotes are checked too, also
inside a heredoc with an unquoted delimiter; other heredoc bodies and
single-quoted text are text. Nesting deeper than four levels around a merge is
refused. `--auto` is refused; `--disable-auto` and `--help` pass. Not seen: a
gh alias, gh run from another language
(`python3 -c "subprocess.run(['gh', ...])"`), or shell syntax outside these
forms (`case`, functions, arithmetic). This is a backstop for an agent
forgetting the review, not a sandbox.

Blocks with exit 2 and the reason on stderr. A command that mentions a merge
and does not tokenise (unbalanced quotes) is refused. An internal error in
this script lets the command through, so a bug here cannot stop all work.
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
WRAPPERS = {"command", "exec", "env", "nohup", "time", "nice", "sudo"}
SEPARATORS = set(";&|()<>\n")
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time"}
RUNNERS = WRAPPERS | {"xargs", "timeout", "stdbuf", "watch", "find"}
SHA = re.compile(r"^[0-9a-f]{40}$")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
SUBST = re.compile(r"`([^`]*)`|\$\(((?:[^()]|\([^()]*\))*)\)")
API_MERGE = re.compile(r"pulls/[^/\s]+/merge\b|repos/[^/\s]+/[^/\s]+/merges\b|"
                       r"mergepullrequest|enablepullrequestautomerge|enqueuepullrequest", re.I)
PLACEHOLDER = "__cs_subst__"
FORM = ("gh pr merge <number> --repo <owner/repo> --match-head-commit <reviewed-sha> "
        "--squash (or the repo's merge style)")


class Refuse(Exception):
    pass


def mentions_merge(text):
    # As the shell will read the words: `m\erge` and `"merge"` are merge.
    low = re.sub(r"[\\'\"]", "", text).lower()
    return "merge" in low or "enqueuepullrequest" in low


def single_quoted_spans(cmd):
    """(start, end) of each single-quoted string, read the way the shell reads
    quotes: a `'` inside double quotes or after a backslash does not open one."""
    spans, i, q, start = [], 0, None, 0
    while i < len(cmd):
        c = cmd[i]
        if q == "'":
            if c == "'":
                spans.append((start, i + 1)); q = None
        elif c == "\\":
            i += 2; continue
        elif q == '"':
            if c == '"':
                q = None
        elif c == "'":
            q, start = "'", i
        elif c == '"':
            q = '"'
        i += 1
    if q == "'":
        spans.append((start, len(cmd)))
    return spans


def strip_comments(cmd):
    """Drop `#` comments as the shell does: a `#` at the start of a word,
    outside quotes, to the end of the line."""
    out, i, q, prev = [], 0, None, "\n"
    while i < len(cmd):
        c = cmd[i]
        if q == "'":
            q = None if c == "'" else q
        elif c == "\\":
            out.append(cmd[i:i + 2]); prev = "x"; i += 2; continue
        elif q == '"':
            q = None if c == '"' else q
        elif c in "'\"":
            q = c
        elif c == "#" and prev in " \t\n;&|()":
            j = cmd.find("\n", i)
            i = len(cmd) if j < 0 else j
            continue
        out.append(c); prev = c; i += 1
    return "".join(out)


def simple_commands(cmd):
    """[(operator_before, words)], split where the shell splits commands."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    out, cur, op = [], [], ""
    for tok in lex:
        if tok and set(tok) <= SEPARATORS:
            if cur:
                out.append((op, cur))
            cur, op = [], tok.strip()
        else:
            cur.append(tok)
    if cur:
        out.append((op, cur))
    return out


def command_word(words):
    """(index of the command word, env assignments) after assignments and wrappers."""
    env, i = {}, 0
    while i < len(words):
        w = words[i]
        if ASSIGN.match(w):
            k, v = w.split("=", 1)
            env[k] = v
        elif w in KEYWORDS:
            pass
        elif w in WRAPPERS:
            # A wrapper's options can take values (`sudo -u x`, `nice -n 10`);
            # the command it runs is gh if any later word is.
            later = [j for j in range(i + 1, len(words)) if os.path.basename(words[j]) == "gh"]
            if later:
                return later[0], env
        elif w.startswith("-") and i > 0 and words[i - 1] in WRAPPERS:
            pass
        else:
            return i, env
        i += 1
    return None, env


def norm_repo(r):
    parts = [p for p in (r or "").strip("/").split("/") if p]
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else None


def short_flags(word, nxt, wanted):
    """Value of a short flag in `wanted` inside a cluster like -dR (value next) or -Rx/y."""
    for k, ch in enumerate(word[1:], 1):
        if ch in wanted:
            rest = word[k + 1:]
            return ch, (rest if rest else nxt), (0 if rest else 1)
    return None, None, 0


def check_gh(args, env):
    """args: the words after the gh command word."""
    repo = env.get("GH_REPO")
    i, pos = 0, []
    while i < len(args):
        w = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if w in ("-R", "--repo"):
            repo = nxt; i += 2; continue
        if w.startswith("--repo="):
            repo = w.split("=", 1)[1]
        elif w.startswith("-R") and len(w) > 2:
            repo = w[2:]
        elif not w.startswith("-"):
            pos.append(i)
            if len(pos) == 2:
                break
        i += 1
    if not pos:
        return
    first = args[pos[0]]
    if first == "api":
        if any(API_MERGE.search(x) for x in args[pos[0] + 1:]):
            raise Refuse(f"merging through `gh api` bypasses the review gate's pin. Use: {FORM}")
        return
    if first != "pr" or len(pos) < 2 or args[pos[1]] != "merge":
        return
    check_pr_merge(args[pos[1] + 1:], repo)


def check_pr_merge(args, repo):
    sel = sha = None
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
        elif w in ("--body", "--body-file", "--subject", "--author-email"):
            i += 2; continue
        elif w.startswith("--"):
            pass
        elif w.startswith("-") and len(w) > 1:
            ch, val, skip = short_flags(w, nxt, "RbFtA")
            if ch == "R":
                repo = val
            if "h" in w[1:] and ch is None:
                helpw = True
            i += 1 + skip
            continue
        elif sel is None:
            sel = w
        i += 1
    if helpw or disable:
        return
    url = re.match(r"https?://[^/]+/([^/]+/[^/]+)/pull/\d+", sel or "")
    if url:
        if repo and norm_repo(repo) != url.group(1).lower():
            raise Refuse(f"the PR URL names {url.group(1)} but --repo names {repo}; gh merges "
                         "the URL's PR. Give one repository.")
        repo = url.group(1)
    repo = norm_repo(repo)
    if auto:
        raise Refuse("`--auto` merges whatever head is current when checks pass, "
                     f"not the reviewed one. Wait for the checks, then run: {FORM}")
    if not sel or not repo or not sha:
        missing = [n for n, v in (("the PR", sel), ("--repo <owner/repo>", repo),
                                  ("--match-head-commit <sha>", sha)) if not v]
        raise Refuse(f"the merge does not name {', '.join(missing)}. The review gate merges "
                     f"only a pinned, reviewed head, with the SHA written out: {FORM}")
    if not SHA.match(sha):
        raise Refuse(f"--match-head-commit {sha} is not a full 40-character SHA written out "
                     "(a variable is not expanded before the gate reads it).")
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
    if not mentions_merge(cmd):
        return
    if depth > 4:
        raise Refuse("this command nests shells or substitutions more than four deep around a "
                     "merge. Run the merge as its own plain command.")
    cmd = cmd.replace("\\\n", "")  # a line continuation joins two lines into one command
    hidden_merge = False

    # Heredocs: a body a shell or ssh reads is commands; any other is text, but
    # an unquoted delimiter still runs the body's substitutions.
    def heredoc(m):
        nonlocal hidden_merge
        line_start = cmd.rfind("\n", 0, m.start()) + 1
        try:
            line = simple_commands(strip_comments(cmd[line_start:m.start()]))
        except ValueError:
            line = []
        words = line[-1][1] if line else []
        ci, _ = command_word(words)
        body = m.group(3)
        if ci is not None and os.path.basename(words[ci]) in SHELLS | {"ssh"} and \
                not any(re.match(r"^-[A-Za-z]*c[A-Za-z]*$", w) for w in words[ci + 1:]):
            check(body, depth + 1)
        else:
            if not m.group(1):
                for sm in SUBST.finditer(body):
                    check(sm.group(1) or sm.group(2) or "", depth + 1)
            hidden_merge = hidden_merge or mentions_merge(body)
        return m.group(0).split("\n", 1)[0]
    cmd = HEREDOC.sub(heredoc, cmd)
    cmd = strip_comments(cmd)

    # Substitutions outside single quotes are commands: check them, then stand
    # a placeholder in. Inside single quotes they are text.
    quoted = single_quoted_spans(cmd)
    pieces, last = [], 0
    for m in SUBST.finditer(cmd):
        if any(a <= m.start() < b for a, b in quoted):
            continue
        check(m.group(1) or m.group(2) or "", depth + 1)
        pieces.append(cmd[last:m.start()]); pieces.append(PLACEHOLDER); last = m.end()
    cmd = "".join(pieces) + cmd[last:]
    if not mentions_merge(cmd) and not hidden_merge:
        return

    try:
        commands = simple_commands(cmd)
    except ValueError:
        raise Refuse("this command mentions a merge and does not tokenise (unbalanced "
                     "quotes?). Run the merge as its own plain command.")
    prev_shell = False
    for op, words in commands:
        # The tokeniser splits at `<<<`: the words after it are a here-string,
        # which a shell before it runs.
        if op == "<<<" and prev_shell and words:
            check(words[0], depth + 1)
        ci, env = command_word(words)
        prev_shell = ci is not None and os.path.basename(words[ci]) in SHELLS
        if ci is None:
            continue
        cw, rest = words[ci], words[ci + 1:]
        base = os.path.basename(cw)
        if base in SHELLS:
            script = None
            for k, w in enumerate(rest):
                if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", w):
                    script = rest[k + 1] if k + 1 < len(rest) else ""
                    break
                if not w.startswith("-") and not w.startswith("+") and \
                        (k == 0 or rest[k - 1] not in ("-o", "+o", "-O", "+O")):
                    break
            if script is not None:
                check(script, depth + 1)
            elif op in ("|", "|&"):
                raise Refuse("this pipes text into a shell in a command that mentions a "
                             f"merge. Run the merge as its own plain command: {FORM}")
        elif cw == "eval":
            check(" ".join(rest), depth + 1)
        elif base == "gh" or cw.startswith("$") or cw == PLACEHOLDER:
            check_gh(rest, env)
        elif base in RUNNERS and any(os.path.basename(x) == "gh" for x in rest):
            j = next(j for j, x in enumerate(rest) if os.path.basename(x) == "gh")
            check_gh(rest[j + 1:], env)


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
