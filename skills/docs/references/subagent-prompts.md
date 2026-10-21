# Prompts for the blind agents

Fill the `{{...}}` slots. Dispatch all of them in one turn as fresh agents.
Paste the rendered text inline; do not give a path.

## Blind user (one per frozen task)

```
You are an automation agent about to run a `{{tool}}` command. You have never
seen this tool's source or documentation beyond the text below. Do not search
the web, read files, or use prior knowledge of {{tool}}. Rely only on this
text.

--- BEGIN `{{tool}} {{subcommand}} --help` ---
{{rendered_help}}
--- END ---

Task: {{task_in_plain_english}}

Return exactly:
COMMAND: <the single command line you would run>
WHY: <one sentence citing the parts of the text that led you there>

If the text does not let you determine the command, return:
COMMAND: UNSURE
WHY: <what is missing or ambiguous>
```

Grade it yourself against the frozen command: right subcommand, every required
argument, right flags and values; ignore order and equivalent forms. `UNSURE`,
a wrong flag, a missing argument, or a plausible wrong reading is a fail and a
specific finding.

### Variant: MCP tools or skills

Replace the help block with the `tools/list` names and descriptions, and ask
for `TOOL: <name>` and `ARGS: <json>` instead of `COMMAND`.

### Variant: README reader

Replace the help block with the README text, and ask the frozen question for
one reader ("you want to install this and run it once on macOS; what do you
run, and what do you do if it fails?"). Grade against the frozen outcome.

## Critic (one)

```
You are an agent that has never used `{{tool}}`. Below is the entire text you
would have for this command. Judge whether it is enough for an agent to use
the command correctly on the first try. Rely only on this text.

--- BEGIN ---
{{rendered_help}}
--- END ---

Report findings in these categories, omitting any that is empty:
- AMBIGUOUS: arguments whose meaning or value format is unclear
- MISSING_EXAMPLE: where an example invocation is needed and absent
- JARGON: terms an outside agent would not know
- WHEN_TO_USE: unclear when to use this rather than an alternative

For each: quote the exact text, say why it is a problem for an agent, and give
the minimal fix. If the text is sufficient, say "NO MATERIAL FINDINGS".
```

`AMBIGUOUS`, `MISSING_EXAMPLE` and `JARGON` are material. `WHEN_TO_USE` is
material only when two commands or flags compete. A non-material finding does
not need a revision round.
