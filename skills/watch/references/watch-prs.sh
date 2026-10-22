#!/bin/bash
# Wait until every PR in a list has finished CI or closed, then print each.
#
#   watch-prs.sh <list-file> [deadline-minutes]
#
# Each line of <list-file> is "<owner/repo> <number>"; blank lines and lines
# starting with # are skipped. The file is re-read on every poll, so a PR can
# be added or removed while it runs. Each PR is read with the merge skill's
# pr_state.sh. A PR is done when it is MERGED or CLOSED, or its VERDICT is
# green or failing; pending and no-checks (CI has not registered yet) keep
# the watch going.
#
# stderr: one heartbeat per poll, "<time> pending=<n> errors=<n>".
# stdout, on exit: "<owner/repo>#<n> <PR line> | <VERDICT line>" per PR.
# Exit 0 when every PR is done; 2 on the deadline (default 90 minutes);
# 3 when the list cannot be read or names no PR, or a PR cannot be read on
# the first poll. Written for bash 3.2 (macOS): no associative arrays.
set -u
here=$(cd "$(dirname "$0")" && pwd)
state="$here/../../merge/references/pr_state.sh"
list=${1:?usage: watch-prs.sh <list-file> [deadline-minutes]}
deadline=$(( $(date +%s) + ${2:-90} * 60 ))
first=1
while :; do
  [ -r "$list" ] || { echo "watcher-error: cannot read $list"; exit 3; }
  pending=0 errors=0 count=0 out=""
  while read -r repo n || [ -n "${repo:-}" ]; do
    case "${repo:-}" in ''|'#'*) repo=; continue ;; esac
    count=$((count + 1))
    if s=$(/bin/bash "$state" "$n" "$repo" 2>&1); then
      pr=$(printf '%s\n' "$s" | grep '^PR ')
      v=$(printf '%s\n' "$s" | grep '^VERDICT ')
      case "$pr $v" in
        *state=MERGED*|*state=CLOSED*|*'VERDICT green'*|*'VERDICT failing'*) ;;
        *) pending=$((pending + 1)) ;;
      esac
      out="$out$repo#$n $pr | $v"$'\n'
    else
      errors=$((errors + 1))
      out="$out$repo#$n watcher-error: $(printf '%s' "$s" | tail -1)"$'\n'
    fi
    repo=
  done < "$list"
  echo "$(date -u +%H:%M:%S) pending=$pending errors=$errors" >&2
  if [ "$count" -eq 0 ]; then echo "watcher-error: $list names no PR"; exit 3; fi
  if [ "$first" -eq 1 ] && [ "$errors" -gt 0 ]; then printf '%s' "$out"; exit 3; fi
  first=0
  if [ $((pending + errors)) -eq 0 ]; then printf '%s' "$out"; exit 0; fi
  if [ "$(date +%s)" -gt "$deadline" ]; then
    printf '%s' "$out"
    echo "watcher-timeout pending=$pending errors=$errors"
    exit 2
  fi
  sleep 60
done
