---
name: watch-long-job
description: Write a watcher, monitor, or poll loop for a long-running job so that it ends when the job ends and fails loudly when it breaks — terminal states taken from what the server actually emits, one machine-readable verdict line read only after the job exits, postconditions asserted rather than setup exit codes, fields parsed by name, and a heartbeat. Use when backgrounding a build, test sweep, or experiment; when writing a Monitor, until-loop, or poll script; when a job runner reports success; and whenever a watcher has been silent for longer than the job should take.
---

# Watch a long job

Every watcher bug seen so far presented the same way: "nothing has happened
yet". A missing terminal state, a field that moved between two log formats, and
a `grep -v` exiting 1 on empty input all produced silence and no error. That is
why this skill starts from the assumption that a silent watcher is broken.

For SystemsLab state names and `submit --wait`, see
`systemslab-spec-authoring`; for VM jobs, `vm-job` step 5.

## 1. Take the terminal states from the source, not from memory

Read the states from the server's code or from a job that has already
finished, and write them into the watcher. A watcher checking for
`completed`/`failed` never matched SystemsLab's `success`, so finished work
looked like it was still running, for 40 minutes, twice.

Prefer "ended when the state is no longer one of the non-terminal states" over
"ended when the state is one of these terminal ones". An unlisted terminal
state then ends the loop instead of hanging it. Enumerate what the watcher can
report — `running`, `ended:<state>`, `watcher-error` — and handle each.

## 2. Make the job emit one verdict line

A job that runs several gates prints exactly one machine-readable line at the
end, and that line is the only thing read:

```sh
echo "RESULT all_gates_ok=$ok tests=$n failed=$f"
```

A SystemsLab experiment reported `success` while its own summary said
`all_gates_ok=no`, because the payload ended `exit 0`. The runner's state says
the job ran; the verdict line says what it found. Read the runner's `success`
as "the verdict line is now available", never as a pass.

## 3. Assert postconditions, not the exit status of setup

```sh
sudo prlimit --pid $$ --nofile=1000000:1000000 || ulimit -n 65536
[ "$(ulimit -Sn)" -ge 65536 ] || { echo "RESULT setup_failed=nofile"; exit 1; }
```

`prlimit` against a hard limit of 524288 returned 0 and applied nothing, so the
`||` fallback never ran, and the test binary aborted 40 minutes later on the
limit it was meant to have raised. Check the state you needed, immediately
after establishing it.

The same applies outside job scripts. `gh pr edit --base` failed without an
error, and the merge that followed went to the wrong branch and was reported
as merged. After any step whose effect a later step depends on, read the
effect back (`gh pr view --json baseRefName`, `git log origin/main..`), not the
command's exit status.

## 4. Parse by name, and know how each filter exits on empty input

- Parse `key=value` or JSON fields by name (`jq -r .state`, `sed -n
  's/.*state=\([a-z]*\).*/\1/p'`), never by column position. A field-position
  shift between two log formats made a watcher read the wrong column forever.
- `grep` and `grep -v` exit 1 when they output nothing, so `grep -v x f >
  g && mv g f` never runs the `mv` on an empty result, and under `set -e` the
  script ends there.
- Match literals with `grep -F`. `grep "verify.log"` matched `verify logs.json`
  and downloaded the wrong artifact, which printed "no RESULT line" — identical
  to a failed job.
- Monitor's shell is zsh (no word-splitting of unquoted variables) and macOS
  `bash` is 3.2 (no `declare -A`). Test the script in the shell that will run
  it.

## 5. Emit a heartbeat and a deadline

Print one line per poll with the time and the observed state, so silence can
only mean the watcher died. Give the watcher a deadline of about twice the
job's expected duration, after which it reports `watcher-timeout` and exits
non-zero rather than polling forever.

## 6. Test the watcher on a finished job before arming it

Point it at a job that has already ended — one that passed and, if you have
one, one that failed — and confirm it exits with the right verdict on the first
poll. This catches the terminal-state and field-parsing bugs in seconds.

## 7. Read the result only after the job has exited

- Read the complete output file after the process or experiment has ended.
  "491 passed, 0 failed" was once read from a file a background `cargo test`
  was still writing; the finished total was 874 with three failures.
- Take the verdict line (step 2), then the exit code; a count scraped from the
  output is a third check, never the first.
- If the verdict line is missing, the job did not finish its work. That is a
  failure, not an unknown.

## 8. When nothing has happened for too long

Debug the watcher before the job. Query the job's state by hand, once, with the
same command the watcher uses, and compare. In every case so far the job had
finished and the watcher had not noticed.

## Never

- **Never match terminal states you have not seen the server emit.**
- **Never read a runner's `success` as the work's verdict.**
- **Never trust the exit status of a command that was supposed to establish a
  state**; check the state.
- **Never leave a watcher without a heartbeat and a deadline.**
- **Never report a result from a file a process is still writing.**
