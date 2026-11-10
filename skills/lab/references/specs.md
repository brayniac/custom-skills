# SystemsLab spec authoring

A spec is shell inside TOML inside a parameter interpolator, run on whichever
host the tags resolve to. Each layer has a failure that looks like the layer
below it.

Validate before submitting:

```sh
systemslab evaluate <spec> -p <each matrix axis>=<value>
```

It renders the substituted spec and catches the first two layers without
spending a host. It is also how you check what a step actually sends, which
settles arguments about reserved keys in one command.

**`anvil-vm` and the guests it builds are `vm.md`'s subject**, and that file
is the authority there. This one covers the spec mechanics underneath, which
apply to every job whether or not it builds a VM.

## The interpolator passes `{{` through verbatim

`{VAR}` and `${VAR}` are substituted from `[params]` and `[matrix]`. A literal
brace is escaped `{{` — but **the interpolator does not unescape it**, so `{{`
reaches the shell as `{{`.

```sh
echo "${{USED}} bytes"     # reaches bash as ${{USED}} — bad substitution
echo "$USED bytes"         # correct: no braces
awk '{{print $4}}'         # works BY ACCIDENT: a valid nested awk block
```

Write shell without brace expansions where you can. `${a:-0}` survives because
`a` is not a declared parameter and passes through untouched — but declare a
parameter named `a` and it is captured. The awk case is the dangerous one: it
works, so it gets copied somewhere it does not.

## Reserved step keys are four, and everything else is an argument

`uses`/`type`, `id`, `background`, `with`. Every other field is forwarded to the
action as an argument, so **`name` is not a step label**: it is the barrier's
name for `barrier`, the *artifact* name for `upload-artifact`, and a real
argument for `start-metrics`. A descriptive `name` on an upload step silently
renames the artifact, and a later step or a grep that looks for the file by its
own name will not find it. An action with `deny_unknown_fields` — `anvil-vm` —
fails outright instead, which is the kinder failure.

Use `id` when you want a label. Specs in circulation carry inline `name`, so it
copies easily into a step where it is wrong.

Also: prefer `systemslab/upload-artifact` to the deprecated `upload_artifact`.

## A shell step already runs under `set -ex`

Your own `set -uo pipefail` adds to that rather than replacing it. Any non-zero
command ends the step, including the ones that are not errors: `smartctl` exits
32 for "an attribute passed its threshold at some point", which killed a job at
the tenth of twenty-three disks with no error line and no verdict — the log just
stopped.

```sh
[ "$ok" = yes ] && REUSE=yes            # ok=no returns 1, and the step dies
if [ "$ok" = yes ]; then REUSE=yes; fi  # correct
```

The `&&` form is worth its own reflex because of *when* it fires: only on the
branch you wrote the code to handle. A guard designed to fall back gracefully
kills the job instead, and every passing run looks fine.

**A step that computes its own verdict needs an explicit `set +e`**, or it dies
before it can report one.

## The fleet is not one distro

Assume nothing optional is installed. Observed on one fleet between an Ubuntu
image and an EL image: `nc`, `git`, `dpkg-deb` and `unzip` present on one and
absent on the other; JVMs at `/usr/lib/jvm/java-N-openjdk` on EL and
`...-openjdk-amd64` on Debian; `sudo` on some hosts and not others.

```sh
(exec 3<>/dev/tcp/HOST/PORT) 2>/dev/null   # instead of nc -z
grep -q " $MNT " /proc/mounts               # instead of mountpoint -q
```

Detect rather than hard-code, and write the resolved value to a file — each step
is its own shell, so nothing survives between them except the filesystem:

```sh
echo "$JAVA" > $STAGE/java-path      # step 1
JAVA=$(cat $STAGE/java-path)         # step N
```

Where the agent lacks sudo, unpack rather than install: `dpkg-deb -x` on Debian,
`rpm2cpio | cpio -idm` on EL. And **attempt an install rather than probing for
one** — a probe that quietly answers "no" is indistinguishable from a box that
legitimately lacks the package.

## Getting a local file into a run

Upload to the **context**, not the experiment:

```sh
CTX=$(systemslab context new --name <name> --output-format short)
systemslab artifact upload ./myapp.jar --context "$CTX"
systemslab submit spec.toml --context "$CTX"
```

then, before the payload:

```toml
[[jobs.steps]]
uses = "systemslab/download-artifact"
[jobs.steps.with]
name = "myapp.jar"
path = "myapp.jar"
```

Upload before submitting. `submit` has no `--hold`, so uploading to the
experiment id after submitting races the scheduler — the job may already be
running. The download action searches the experiment first and then the
contexts the experiment is attached to, and that context fallback exists for
pre-staging.

Three constraints: it matches `type=user` only (the CLI's upload default, so
plain uploads are fine); it requires **exactly one** name match, anchored, so
two artifacts of that name in scope is a hard error rather than newest-wins;
and there is no `download_artifact()` jsonnet helper, only `upload_artifact()`,
so the raw `uses:` step is required.

**A matrix submit seals the context.** Multi-variant submits route through a
batch path that marks the context complete on success, after which it accepts
no artifacts. Single-variant submits do not. Upload inputs before submitting,
always.

Note also that `submit --context` auto-uploads the spec file itself as a `user`
artifact, so a context always holds at least one artifact you did not stage —
and a spec sharing a name with a staged file is an exactly-one collision.

## A study with more than one arm

An arm is one configuration, build or model load that a study compares with
another. Each arm is its own experiment, and a study is one context:

1. Write one spec whose job runs exactly one arm, every axis a `[params]`
   entry.
2. When the arms' numbers are compared by value, pin each job to one host with a
   `host:<name>` tag (`vm.md` section 1, beside this file): a different host per
   job, the same hosts for every arm. A tag that matches one host needs no pin;
   `macbook`, `macstudio`, `pi5`, `z1.baremetal` and `z2.baremetal` did when
   this was written, so check with `systemslab host list`. The scheduler places
   each experiment on its own, so under a tag that matches several hosts the
   arms run at the same time on different machines. A failure-rate sweep may
   spread across a pool.
3. List the arms in a JSON file beside it, one object of parameters per arm.
4. Create the context, upload each source to it once, then submit every arm
   into it:

   ```sh
   CTX=$(systemslab context new --name <study> --output-format short)
   systemslab artifact upload src.tgz --name src.tgz --context "$CTX"
   systemslab sweep spec.toml arms.json --context "$CTX"
   ```

   The spec fetches `src.tgz` with `systemslab/download-artifact` (above).
   `sweep --context` adds the experiments to the context and leaves it open,
   unlike a matrix submit or a `sweep --name`, so a later arm or rerun can
   join it. One `sweep` call does not fix the order its experiments run in;
   where order matters (an interleave), submit one variant per call, in
   order: `systemslab submit spec.toml -p <axis>=<value> --context "$CTX"`,
   with one `-p` per axis. A `[matrix]` spec closes the context unless `-p`
   gives every matrix axis, because more than one variant goes through the
   batch submit, which marks the context complete. Read each experiment's
   start time.
5. Compare the arms after downloading their artifacts, on your machine. No
   job reads another arm's output. When no further arm or rerun will join
   the context, `systemslab context complete "$CTX"` moves it to `pending`;
   the server marks it complete, and builds its reports, once every
   experiment in it has finished. No experiment can be added once it is
   `pending`.

Never run several arms as steps, or a loop, inside one job. One arm's failure
then hides the arms after it, its leftover state (a wired allocation, a server
still holding its port, a guest's page cache) enters the next arm's numbers,
and no single arm can be rerun alone. A ladder inside one arm, such as the
offered rates of an SLO search, is one job. A job with no `anvil-vm` step runs
on the host itself (the Macs and every `bare`-tagged host: the Pis, hv03,
delta) and keeps that host's page cache between experiments; drop it at the
start of each arm when it matters.

## Three things the CLI will not tell you

**`submit --wait` exits 0 whether the work succeeded or failed.** It reports
that the submission worked. Take the verdict from the experiment state, polled
until terminal — `--wait` can also return before the state settles.

**An experiment and a run have different state names.** Poll the experiment,
and match its states:

| Level | Non-terminal | Terminal |
| --- | --- | --- |
| experiment | `pending` | `success`, `failure`, `error`, `cancelled`, `timeout` |
| run (job) | `unscheduled`, `scheduled`, `running` | `complete`, `failed`, `cancelled`, `lost`, `error`, `timeout` |

A watch loop matching the run's `complete`/`failed` against the experiment's
state runs past the end — 40 minutes, twice in one day. Match on "not
`pending`" rather than on a list of terminal states, so a state you did not
list still ends the loop. The enums are `ExperimentState` and `RunState` in
`crates/data/schema/src/lib.rs` in the systemslab repo; read them there rather
than from memory.

**`artifact list` cannot see context artifacts.** It is scoped to the
experiment, so a file pre-staged on a context looks absent. List them with
`systemslab api "/api/v1/artifact?context=$CTX"`.

## Destructive steps

`blkdiscard`, `mkfs` and `umount` in a spec run unattended against a device path
from a parameter, and hosts keep state between jobs. One job per host means no
concurrent access; it does not stop a later run from destroying an earlier
one's data. If a run depends on data surviving between jobs, write a manifest
describing what was built and verify it on the next run, rebuilding on
mismatch rather than failing. Correctness is then independent of scheduling.

## Never

- **Never copy a `name =` out of an existing step** without checking what that
  action does with it.
- **Never let a step compute a verdict without `set +e`.**
- **Never upload an input after `submit`.**
- **Never read a job's exit status as the work's verdict** when the payload ends
  `exit 0` — see `vm.md`.
