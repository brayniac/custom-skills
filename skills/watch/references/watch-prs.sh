#!/bin/bash
# Wait until no PR in a list has a pending check, then print each PR's checks.
#
#   watch-prs.sh <list-file> [deadline-minutes]
#
# Each line of <list-file> is "<owner/repo> <number>". The file is re-read on
# every poll, so a PR can be added or removed while it runs. Prints one
# heartbeat line per poll to stderr, and on exit one line per PR to stdout:
#   <owner/repo>#<n> head=<sha7> merge=<mergeStateStatus> <check>=<state> ...
# Exits 0 when nothing is pending, 2 on the deadline (default 90 minutes).
# Written for bash 3.2 (macOS): no associative arrays.
set -u
list=$1
deadline=$(( $(date +%s) + ${2:-90} * 60 ))
while :; do
  pending=0
  out=""
  while read -r repo n; do
    [ -z "$repo" ] && continue
    s=$(gh pr view "$n" --repo "$repo" \
      --json headRefOid,statusCheckRollup,mergeStateStatus \
      -q '"head="+.headRefOid[0:7]+" merge="+.mergeStateStatus+" "+([.statusCheckRollup[] | (.name // .context)+"="+((.conclusion // .state)|tostring)] | join(" "))' 2>&1)
    if [ $? -ne 0 ]; then
      s="watcher-error: $s"
      pending=$((pending + 1))
    elif printf '%s' "$s" | grep -qE '=(PENDING|IN_PROGRESS|QUEUED|EXPECTED|null)( |$)|= '; then
      pending=$((pending + 1))
    fi
    out="$out$repo#$n $s"$'\n'
  done < "$list"
  echo "$(date -u +%H:%M:%S) pending=$pending" >&2
  if [ "$pending" -eq 0 ]; then printf '%s' "$out"; exit 0; fi
  if [ "$(date +%s)" -gt "$deadline" ]; then
    printf '%s' "$out"; echo "watcher-timeout pending=$pending"; exit 2
  fi
  sleep 60
done
