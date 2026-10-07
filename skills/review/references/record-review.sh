#!/bin/bash
# Record that a head commit was reviewed with a verdict of merge, or waived
# with the user's agreement, so the merge gate lets
# `gh pr merge <n> --repo <owner/repo> --match-head-commit <sha>` through.
#
#   record-review.sh <owner/repo> <head-sha> merge "<summary>"
#   record-review.sh <owner/repo> <head-sha> --waive "<reason>"
#
# <head-sha> is the full SHA the reviewer read, not a PR number: the PR's head
# can move between the review and the record. Record only after every finding
# has a disposition and none that blocks the merge is open; a review whose
# verdict is "fix first" is not recorded.
#
# The record is a file, $CS_REVIEW_DIR/<owner>/<repo>/<sha> (default
# ~/.claude/cs-reviews), holding the time and the summary. It is per machine.
# hooks/review_gate.py in this plugin reads it.
set -euo pipefail

if [[ $# -lt 4 ]]; then
    sed -n '2,8p' "$0" >&2
    exit 2
fi
REPO=$1 SHA=$2 KIND=$3; shift 3
[[ $REPO =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "error: $REPO is not owner/repo" >&2; exit 2; }
[[ ! $REPO =~ (^|/)\.\.?(/|$) ]] || { echo "error: $REPO is not owner/repo" >&2; exit 2; }
[[ $SHA =~ ^[0-9a-f]{40}$ ]] || { echo "error: $SHA is not a full 40-character commit SHA" >&2; exit 2; }
case $KIND in
    merge) KIND=reviewed ;;
    --waive) KIND=waived ;;
    *) echo "error: the verdict is 'merge' or '--waive'; a review that found blocking problems is not recorded" >&2; exit 2 ;;
esac
[[ -n $* ]] || { echo "error: give a summary (merge) or a reason (--waive)" >&2; exit 2; }

dir=${CS_REVIEW_DIR:-$HOME/.claude/cs-reviews}/$(tr "[:upper:]" "[:lower:]" <<<"$REPO")
mkdir -p "$dir"
printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$KIND" "$*" >> "$dir/$SHA"
echo "recorded: $REPO $SHA $KIND"
