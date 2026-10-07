#!/bin/bash
# Record that a head commit was reviewed (or, with the user's agreement,
# waived), so the merge gate lets `gh pr merge` of that head through.
#
#   record-review.sh <owner/repo> <head-sha> "<verdict line>"
#   record-review.sh <owner/repo> <head-sha> --waive "<reason>"
#   record-review.sh <owner/repo> <pr-number> ...     # resolves the PR's current head
#
# The record is a file, $CS_REVIEW_DIR/<owner>/<repo>/<sha> (default
# ~/.claude/cs-reviews), holding the time and the verdict. It is per machine:
# the gate is a backstop against an agent forgetting the review, not an audit
# trail. hooks/review_gate.py in this plugin reads it.
set -euo pipefail

if [[ $# -lt 3 ]]; then
    sed -n '2,8p' "$0" >&2
    exit 2
fi
REPO=$1 REF=$2; shift 2
[[ $REPO =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "error: $REPO is not owner/repo" >&2; exit 2; }
if [[ $REF =~ ^[0-9]{1,9}$ ]]; then   # a PR number; a SHA is 40 hex digits, which can all be decimal
    REF=$(gh pr view "$REF" --repo "$REPO" --json headRefOid -q .headRefOid)
fi
[[ $REF =~ ^[0-9a-f]{40}$ ]] || { echo "error: $REF is not a full commit SHA" >&2; exit 2; }

KIND=reviewed
if [[ $1 == --waive ]]; then
    KIND=waived; shift
    [[ $# -ge 1 && -n $1 ]] || { echo "error: --waive needs a reason" >&2; exit 2; }
fi
VERDICT=$*

dir=${CS_REVIEW_DIR:-$HOME/.claude/cs-reviews}/$(tr "[:upper:]" "[:lower:]" <<<"$REPO")
mkdir -p "$dir"
printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$KIND" "$VERDICT" >> "$dir/$REF"
echo "recorded: $REPO $REF $KIND"
