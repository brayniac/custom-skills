# Evaluating a skill against a baseline

The detail behind `skill` step 7. Dispatch every agent below as a fresh
agent (`subagent_type` general-purpose on the default model, not a fork), so
none of them has seen this session. The Agent tool returns only an agent's
final message; everything else you grade has to be in a file.

## 1. Freeze the outcomes first

Write the fixture before editing the skill (for a revision) or before running
any arm (for a new skill), and keep it in the scratchpad. One entry per task:

| Field | Contents |
| --- | --- |
| `prompt` | The text the worker receives, as a user would type it |
| `context` | The files, repository state or commit the worker starts from |
| `required` | Outcomes the result must show, each one visible in the worker's `commands.log` or files (section 3): "ran `git log` and wrote 9", "pinned the number to a commit" |
| `prohibited` | Outcomes that fail the task: "applied the reviewer's count", "edited a file outside the named section" |
| `should_trigger` | Whether the skill should be invoked on this prompt |

Every entry has at least one required and one prohibited outcome, and the
fixture has at least one entry with `should_trigger` false (section 5). An
outcome such as "was careful" or "followed the skill" cannot be seen in a log
or a file; write what the log or the file would show instead.

If a grade looks wrong after a result is in, record the grade and the reason
it looks wrong. Do not edit the outcome.

## 2. Build the task on what cannot be inferred

A task that rewards general care is passed by both arms. A baseline agent
checks facts, qualifies a measurement, and keeps a reviewer's claim apart from
an author's without being told. It cannot follow a convention it has never
seen: this repository's state vocabulary, which value pins a number, which
check a page needs, which past failure the skill records.

Put several such conventions in one task, so the arms can differ on more than
one outcome. Write the prompt as the request a user would make. A prompt that
asks for the behaviour ("say how you know each fact") invites the baseline to
do it, and the result then measures the prompt.

## 3. Run both arms by execution

Set up each arm in `<scratch>/<arm>/`: its own clone of the context
(`git clone --no-local <repo> <scratch>/<arm>/repo`, never a worktree, which
shares remotes and refs with the source), or a fixture directory. Give the
clone a bare repository as its only remote: `git init --bare
<scratch>/<arm>/remote.git`, then, inside the clone, `git remote set-url
origin` to it.

Both arms run with the plugin installed on this host, so both see its `cs:*`
listing. Record the `cs:*` names in the arm's own listing (or the
session's). `claude plugin list` reports the newest install, and a running
session keeps the copy it started with. The skill arm also gets the skill's
text (body and the references it names) pasted into its prompt; the baseline
arm gets none, or the current version's text for a revision. Pasting the
body measures the body given that the agent reads it. Only section 5 tests
whether the description gets it loaded. Neither arm gets the fixture, the
other arm's output, or earlier results.

Tell each worker:

- Use absolute paths under `<scratch>/<arm>/` in every command; each Bash
  call may start in a reset working directory.
- Do the task: edit the files, run the commands, commit to the scratch
  branch. A plan describing what you would do is not accepted.
- Append every command you run, with its output, to
  `<scratch>/<arm>/commands.log`.
- Do not push except to `origin` (the local bare repository). Do not open,
  comment on or merge a PR or issue, publish an artifact, or post anywhere.
  Where the task calls for one of those, write the exact command you would
  run to `<scratch>/<arm>/outward.txt` and stop there.

Run the arms in parallel. When each finishes, check its transcript
(`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`, the
path the Agent tool reports as its output file) for a `tool_use` block named
`Skill`, and record which `cs:` skill, if any, each arm invoked. Do not read
the whole transcript; parse it with a script.

Grade only `commands.log`, `outward.txt`, the files and the final message.
A required outcome that none of them shows is graded ungraded and reported
as such; it does not count as a pass.

## 4. Grade blind

A separate fresh agent grades. Assign arms to labels for each task with
`python3 -c 'import random;print(random.choice(["AB","BA"]))'` ("AB" means
the skill arm is A), and record the output. Give the grader the fixture and
both results under their labels. Ask, for each required and prohibited
outcome, for pass, partial, fail or ungraded on each result, with the
evidence (a file and line, or a `commands.log` entry). Do not tell it which
label is the skill.

Unblind after the grades are in. Where the grader separates the arms, confirm
the difference with a check of your own before reporting it: run the code,
reproduce the command. Keep the raw grades; report a partial as a partial.

## 5. Check triggering

Run each `should_trigger` prompt, and at least one near-miss, as a separate
Claude Code session with the worktree's plugin loaded. Run from an empty
scratch directory, so the repository's CLAUDE.md and code cannot answer the
prompt, and run each prompt at least three times:

```sh
cd <scratch>/trigger-empty && claude -p --plugin-dir <worktree> \
  --output-format stream-json --verbose --permission-mode plan \
  --max-turns 2 "<prompt>" < /dev/null > <scratch>/trigger-<n>.jsonl
```

Without `< /dev/null`, `claude -p` waits for stdin and reports "no stdin data
received in 3s".
`--output-format stream-json` with `-p` requires `--verbose`. The first line
is a `system` `init` event; its `plugins` array should name `cs` with the
worktree's path (source `cs@inline`). On 2026-10-22 it did, and the installed
copy was not listed beside it. An invocation shows as an `assistant` message
whose content holds a `tool_use` named `Skill` with `input.skill` set to
`cs:<name>`. `--max-turns 2` ends the session early and it exits 1. Treat no
call within the turn limit as no call within that limit, and say so. Run
from inside the repository, three of three runs made no `Skill` call and
answered from CLAUDE.md; from an empty directory the first call was `Skill`
`cs:skill`.

A near-miss is a prompt in the same domain, using the same words, that
another skill or no skill should handle. A `Skill` call to this skill on the
near-miss means the description is too broad. No call on its own task means
it is too narrow or another skill's description won; the call made instead
says which. An agent that acts on the task without calling `Skill` is
following the description, which is how a description that summarises the
steps gets followed instead of the body.

## 6. A revision that shortens a skill

A smaller word count shows the skill is shorter and says nothing about
behaviour. Report the count before and after (`wc -w SKILL.md references/*`).
Give a separate fresh agent the diff and every existing expectation of the
skill: earlier fixtures recorded in commit bodies, other skills' references
to its steps, and its own "do not" lines. Ask it to name each requirement the
diff removed or weakened. Restore any it finds, or record why it went.

## 7. Record the result

In the commit body, for each task: the prompt in one line, the outcomes, each
arm's grade, what each arm did that decided the grade, the installed plugin
version, and which `cs:` skills each arm invoked. Say how many runs per arm.
One run per arm checks the wording; it does not measure how often the skill
changes the behaviour. When step 7 ran the lighter test that `skill` step 7
allows, say so and say why.

When both arms pass (or both fail), say which kind of null it is:

- The baseline met the condition the skill addresses and handled it. The
  skill may be unnecessary for that condition; say so, and say whether
  another condition still justifies it.
- The task never presented the condition, or the prompt asked for the
  behaviour (section 2). The test did not exercise the skill; name the
  condition it missed and the task that would present it.

The `evidence` skill's commit (c0a98a4) has both. In its second task the
baseline met a reviewer's wrong count and checked it, so for a finding handed
over as the task, the skill may be unnecessary. Its first task asked how each
fact was known, so it measured the prompt (section 2) and says nothing about
the skill. Neither task reproduced the condition the skill's refuted claims
came from: claims written mid-session during multi-hour work.
