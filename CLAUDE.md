# custom-skills

A personal library of agent skills, packaged as a Claude Code plugin. The
repository root is both the plugin (`.claude-plugin/plugin.json`) and its
marketplace (`.claude-plugin/marketplace.json`, named `custom-skills`). Each
`skills/<name>/SKILL.md` is listed as `cs:<name>`: the prefix is the `name` in
`plugin.json`, kept short because it is typed before every skill, while the
marketplace and its entry stay `custom-skills`, so installs are
`custom-skills@custom-skills`. The Rust crate at
the root is not part of the plugin: it is `check-skills`, which refuses a skills
tree Claude Code would load wrongly.

Most work here is **writing skills**. README.md covers install, updating, and
moving from the old MCP server. This file covers what is not obvious from the
code.

## Checks

Run all of these before claiming a change is done:

```sh
cargo run --quiet                                  # check-skills over skills/
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
claude plugin validate .                           # manifests only
```

Changing `hooks/`, also run `python3 hooks/test_review_gate.py`.

rack-ci runs the first four and the hook test (`.rack-ci.toml`); the repository
is on its allowlist and every PR gets `rack-ci/check`, `rack-ci/lint` and
`rack-ci/test` statuses. `claude plugin validate` needs Claude Code, which the
CI guests do not have, so run it locally when a manifest changes. Its "No
version specified" warning is expected: see Invariants.

`claude plugin validate` does not look inside skills. It passed a copy of this
repository with a skill whose frontmatter was not valid YAML, a skill whose
`name` differed from its directory, and an empty skill directory. Claude Code
loads such a skill with empty metadata, so it drops out of the listing with no
error. That is why `check-skills` exists; keep it failing on those cases.

## Invariants

- **A skill must work on a host with only this plugin installed.** Ship the
  script, config values and endpoints in the skill (`references/`), and name
  them through `${CLAUDE_SKILL_DIR}`. Point at another repository only for work
  that has to happen there.
- **Sibling files are named `${CLAUDE_SKILL_DIR}/references/<file>`.** Claude
  Code substitutes the skill's absolute directory when it loads the body. A bare
  `references/<file>` resolves against the session's working directory. Another
  skill's file is `${CLAUDE_SKILL_DIR}/../<other>/references/<file>`.
  `check-skills` fails on a path that names no file; a path containing `<` is a
  placeholder and is skipped. The substitution happens only in a `SKILL.md`
  body: a file under `references/` names a sibling as "`<file>`, beside this
  file", and another skill's file by that skill's name and relative path, and
  `check-skills` does not check those names.
- **Skills do not act when loaded.** A skill returns instructions; a script
  beside it runs only when the body tells the agent to run it. Do not add hooks,
  monitors, or MCP servers to the plugin without deciding that deliberately.
  The plugin has one hook, `hooks/review_gate.py`: a PreToolUse hook on Bash
  that refuses a PR merge unless it is pinned with `--match-head-commit` to a
  head `review`'s `record-review.sh` recorded. It backs up `open-pr` and
  `drive-pr-to-green`, which run `review`; it is not the review, and it does
  not see a gh alias or gh run from another language.
  `python3 hooks/test_review_gate.py` tests it offline (rack-ci's `test` check
  runs it).
- **No `version` in `plugin.json`.** Without it, an install's version is the
  commit SHA, so `claude plugin update` and auto-update pick up every merge. A
  pinned version would hold every host on the old copy until someone changed
  the string.
- **Frontmatter holds exactly `name` and `description`.** `name` matches
  `[a-z0-9_-]{1,64}` and equals the directory name; `description` is at most
  1,536 characters. `check-skills` rejects any other key so a misspelled one
  fails instead of being ignored; add a key to `Frontmatter` in `src/skill.rs`
  when a skill needs one Claude Code supports.
- **The description listing has a budget.** Claude Code allots about 1% of the
  context window to all skill descriptions and drops the least-used past that.
  `check-skills` prints the total (19,762 characters for 34 skills on
  2026-10-07; at about 21,700 for 38, every description was listed under
  Sonnet 5.5 and Opus 5.5). If it grows a lot, check `/context` in a session.

## Adding or changing a skill

The `skill-authoring` skill (`skills/skill-authoring/SKILL.md`) is the
authoritative process; read it before writing one. In short:

1. `skills/<name>/SKILL.md`, verb-first hyphenated name, YAML frontmatter with
   `name` and `description`.
2. The `description` is the only text an agent sees when choosing a skill — it
   states what the skill does *and* ends with "Use when …". These run long (a
   few lines); that is deliberate, not sloppy.
3. The body is instructions to an agent: numbered steps, explicit inputs,
   explicit stopping conditions, and explicit "do not" lines.
4. Long material goes in `skills/<name>/references/`, named in the body as
   `${CLAUDE_SKILL_DIR}/references/<file>`, so the body stays short enough to
   read every time.
5. `cargo run --quiet`, and try it in a session: `claude --plugin-dir .`.

Conventions the existing skills follow:

- Prose wraps at 80 columns. Frontmatter `description` and Markdown tables are
  the exceptions and run long on one line.
- Skills cross-reference each other by name in backticks (`` `analyze-noise` ``,
  `` `measure-performance` step 5 ``) rather than restating the other skill.
  Keep those references accurate when a skill is renamed or its steps are
  renumbered.
- `skills/` is a flat list today, but nested directories are legal as grouping
  levels — a directory with a `SKILL.md` is a skill, one with only directories
  is a group.

### Iterating

On this machine the plugin is installed from the checkout as a local-directory
marketplace, so it loads in place: an edit takes effect at the next session or
after `/reload-plugins`. For a one-off session, `claude --plugin-dir .`.

## Layout

| Path | Responsibility |
| --- | --- |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | The `custom-skills` marketplace, with this repository as its one plugin (`"source": "./"`) |
| `skills/` | The skills |
| `hooks/` | `hooks.json` and the review gate (`review_gate.py`, its test) |
| `src/skill.rs` | The rules `check-skills` enforces, and their tests |
| `src/main.rs` | The `check-skills` command |

Tests live inline in `#[cfg(test)]` modules. A new rule in `src/skill.rs` gets a
test that fails without it.

## Commits

Subject lines are sentence-case statements of what changed and why it matters,
often `<verb> <thing>: <the point>` — "Add calibrate-to-source: what travels,
and what a local null costs", "Correct the W1 ratio's meaning, and add the
reading that replaces it". Not conventional-commit prefixes.

Bodies are substantial when the change is substantial: for a skill carrying an
empirical claim, the body records the evidence — what was measured, across
what, and what the numbers were — because that reasoning has no other home in
the repo. A correction says plainly what was wrong and what replaced it.
