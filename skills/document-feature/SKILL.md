---
name: document-feature
description: Write or update the documentation for a new or changed feature — CLI `--help`, README, docs-site reference, the repo's CLAUDE.md run block, or an MCP server's tool descriptions — and prove it works by handing only the rendered text to fresh agents that have never seen the code. Frozen tasks with exact expected invocations are written before any text is edited and never changed to fit a result, every mode gets a task, every command example is run, revision stops after three rounds, and a finding that recurs is reported as an interface problem. Use when adding or changing a subcommand, flag, default, config key, tool or mode; when the user says the help or README is thin, stale or confusing, or that an agent could not work out how to use it; and when restructuring a README.
---

# Document a feature

For an agent, `--help` or a tool description is the interface: it reads the
text and decides what to run. This skill treats that text as code under test.
Write the expected usage first, then show that an agent with only the rendered
text arrives at it.

Evidence from use: rezolus ran this on `record`, its command with the most
modes, and a blind agent produced the right command for 5 of 5 tasks; the
same loop then covered every remaining subcommand in one PR. Without the
procedure, two agents given a small CLI to document ran no blind check, and
after three repeated comprehension failures both proposed more documentation
work instead of stopping.

This is a development-time step before the PR. It needs model access and is
nondeterministic; do not wire it into CI.

## 1. Find the surfaces and the sources

List every place the feature is documented and must agree: the parser's help
text, README, a docs-site reference page and its index, the `CLAUDE.md` block
of canonical invocations, examples, and for an MCP server the `tools/list`
descriptions. Note how the help is written: clap's builder (`.about`,
`.long_about`, `.help`) or derive (doc comments and `#[arg]`).

For each claim you will write, name the file that is authoritative for it: the
parser for flags and defaults, the config loader for keys and formats, the
code and tests for behaviour and failures. **Read it before writing the
claim.** On rezolus `record` this caught a wrong TOML key (`[[endpoints]]`, not
`[[endpoint]]`) and a wrong claim about `--duration` under command wrapping; on
`parquet combine --ab` it showed the `baseline=` and `experiment=` values match
a file's embedded source name, not its filename.

## 2. Freeze the tasks before editing any text

List the feature's modes first: mutually exclusive inputs, output formats,
flags that change the shape of the run, deprecated forms. Then write 3–5 tasks
into a scratch file, each a plain-English goal with the exact correct
invocation or outcome, so that every mode has one. A blind agent can only
exercise a surface a task reaches; five single-endpoint tasks say nothing
about the multi-endpoint help.

Include:

- a **first successful use** — running the feature and seeing a correct
  result, separate from installing or configuring it;
- a **failure or recovery** path;
- for a README, one task per reader it serves (a user deciding whether to use
  it, an agent choosing how to invoke it, a developer or coding agent changing
  it), each with the outcome a reader must reach.

**The tasks do not change during the loop.** Changing the expected command to
match what an agent produced is the most common way this check stops meaning
anything. If a task's expected answer turns out wrong, that is a product or
design problem: stop and raise it.

## 3. Write the text

- One-line `about`; a longer description with inline example invocations for
  anything non-trivial.
- Per-argument help says what the value is and gives an example when the
  format is not obvious (paths, `key=value`, query snippets).
- Lead with the canonical form and label deprecated ones. rezolus `record`
  printed deprecation notes for positional `URL`/`OUTPUT` at runtime while its
  help still led with them.
- Carry the same terms and examples into every surface from step 1.
- **One document answers one question.** A guide to when a technology is the
  right choice, merged with how this implementation works, makes general
  claims read as properties of this implementation. Split on the question and
  link.

Word choice is `write-technical-prose`; doc comments on the code are
`sweep-comments`.

## 4. Check deterministically

- Render the real text from a build: `cargo run --quiet -- <cmd> --help`, or
  for an MCP server the `tools/list` response. The source strings are not what the reader gets.
- **Run every command example** in every edited surface, or mark it as not
  run and why. Four blind readers once recovered all seven frozen outcomes
  from a README and a critic passed it; a later review running the commands
  found it built `target/debug` and invoked `target/release`.
- Check changed links, a docs-site build if one was touched, and that any
  diagram renders from its source.

## 5. Run the blind agents

Dispatch in one turn, as fresh agents, never forks:

- **Blind user, one per task.** Only the rendered text and the task. It
  returns the command and one sentence citing which part of the text led
  there, or `UNSURE` with what is missing.
- **Critic, one.** The same text, returning findings as `AMBIGUOUS`,
  `MISSING_EXAMPLE`, `JARGON`, `WHEN_TO_USE`, each with the quoted text and a
  minimal fix.

Prompts are in `${CLAUDE_SKILL_DIR}/references/subagent-prompts.md`. Grade each
command against the frozen one semantically: right subcommand, every required
argument, right flags and values, any order. `UNSURE`, a wrong flag or a
plausible wrong reading is a fail. **If the WHY cites anything not in the text
you gave it, context leaked; rerun it clean.** Blind users find text that is
insufficient; the critic finds text a blind user passed by luck.

For an MCP server or a skill, the blind user gets the tool list and picks a
tool; `skill-authoring` step 7 is the same test for one skill's description.

## 6. Revise the specific finding, at most three rounds

Fix what the finding names, re-render, rerun steps 4 and 5. Stop when every
blind task passes and the critic has no material finding, or after three
rounds. `WHEN_TO_USE` is material only when two commands or flags compete.

**A finding that recurs across rounds is an interface problem.** When the
critic keeps saying three flags set the same thing, the CLI offers an agent
three ways to do one thing, and another paragraph will not fix it. Report it
to the user as a design issue.

## 7. Human review for what agents cannot judge

A diagram, a README restructure, navigation, or an onboarding path is judged
by a person; agent passes are comprehension evidence, not usability. Ask for
review of the exact revision. An approval covers that revision only: when a
README was corrected after approval (the debug/release path above), the
approval no longer applied and it went back for review.

## 8. Report

The frozen tasks; per task, pass or fail in each round; the critic's findings
and what each became; the deterministic commands and their results; the
diffs per surface; human review status; and any recurring finding reported as
a design issue.

## Never

- **Never edit the expected answer** to match an agent's output.
- **Never write a default, key or format you have not read in the source.**
- **Never grade from the source strings** instead of the rendered text.
- **Never give a blind agent the repository, a fork of your context, or
  hints.**
- **Never run a fourth round** on the same recurring finding.
- **Never claim a README is usable** on agent evidence alone.
