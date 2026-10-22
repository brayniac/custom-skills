# Operating the hosts

What has gone wrong running jobs on the Macs, shipping a new version of a
rack service, and editing a host's configuration by hand. Each item was seen
in a session; none of it is in the code where a reader would find it.

`brayniac/infra` declares the fleet: `fleet/hosts/<host>.toml` (a host's role,
services, SystemsLab tags and guest `images`) and `fleet/versions.toml`. It is
private; read it with `gh api repos/brayniac/infra/contents/<path>` when there
is no checkout.

## Jobs on the Macs

`macbook` and `macstudio` run jobs directly on macOS, with no VM, so nothing
tears the job's processes down for you.

- **Cancelling a job does not stop what it started.** A server the payload
  launched and its Docker containers kept running after a cancel on both Macs,
  and the agent took the next queued job while they still held the CPU; the two
  runs did not collide on a port only because the second was still downloading.
  A leftover shell also kept a Mac marked busy. After a cancel or a timeout,
  list the agent's child processes and the containers and stop them (`pkill -P
  <agent pid>`, `docker rm -f <container>`) before the host takes another job.
- **A Mac that sleeps loses its job twice.** The server drops the host and
  requeues the job, while the job keeps running on the Mac; on wake the agent
  refuses to register while it runs (`the server no longer has a live host`).
  One laptop slept on a thermal emergency mid-run and its job ran on for about
  11 hours unseen. Stop the local job processes; the agent then registers and
  the requeued job starts again from the beginning.
- **`experiment_timeout` caps every job.** It is set in
  `~/Library/Application Support/systemslab/agent.toml` and defaults to 12
  hours (43,200 s); a spec's own timeout does not lift it. An edit takes effect
  only when the agent restarts, and the restarted agent registers under a new
  host ID with the same tag. A long run was reported to have died at 43,200 s
  because the raised value was on disk but never loaded.
- **An agent started by hand outlives an upgrade.** One Mac ran an agent
  process started weeks earlier outside `launchd`, with new binaries on disk;
  the registry showed it idle. Restart it under `launchd`.

## Shipping a new version of a rack service

Merging changes no host. The sequence is:

1. Release: tag, and `rack-ci/release` publishes the packages to delta's apt
   repository.
2. An infra PR bumps the version in `fleet/versions.toml` (or the host's file
   under `fleet/hosts/`).
3. `host-setup/converge-package <package> --dry-run`, then without
   `--dry-run`. It skips hosts SystemsLab reports busy.
4. Verify the running binary, not the package.

Two things make step 3 and 4 report success wrongly:

- **converge-package's busy check asks SystemsLab about the host it installs
  on.** delta reads idle while rack-ci builds run on the hypervisors, so a
  rack-ci converge restarts it under running builds. Check rack-ci's `/health`
  shows `builds:0` first; `builds` is the number in flight.
- **An upgraded package can leave the old process running** from a deleted
  file (`/proc/<pid>/exe` ends `(deleted)`), and `infra diff` compares declared
  against installed, not running. Compare `sha256sum /proc/<pid>/exe` with the
  binary on disk, or restart and check `--version`.

converge-package has also reported a clean install as failed when its own
post-install check failed; read the version on the host before retrying.

## Editing a host's live configuration

- **Read the live file and splice the change in place**, next to the block it
  relates to. Never restore a backup wholesale: a backup taken before a change
  someone else made (one predated an authentication cutover) reverts that
  change too. Name backups so nobody restores one by habit.
- **Validate a candidate copy with the real binary** before replacing the live
  file (for rack-ci, `rack-ci build --config /tmp/candidate.toml`), diff live
  against candidate, and keep the file's owner and mode.
- **Check nothing is in flight before restarting** (rack-ci: `/health`
  `builds:0`). An edit does nothing until the service restarts.
- **Know the empty value's meaning.** In rack-ci an empty `include = []` means
  no restriction: 28 targets planned all 240 repositories instead of 3, and
  the ledger's gave-up rows rose from 79 to 503 over about 11 hours.
