#!/usr/bin/env bash
# One snapshot of a pull request's CI and merge state, one line per check.
# Reads both GitHub check runs (Actions) and commit statuses (rack-ci).
# Needs an authenticated `gh` and `jq`. Read-only.
#
# Usage: pr_state.sh <pr-number|url> [OWNER/REPO]
#
# Output:
#   PR number=<n> state=<OPEN|MERGED|CLOSED> head=<sha12> mergeable=<...>
#      merge_state=<...> review=<...>
#   CHECK kind=<run|status> name=<...> result=<pass|fail|error|pending|skip>
#      secs=<duration or -> hint=<...> url=<...>
#   VERDICT <green|pending|failing|no-checks> pass=<n> fail=<n> error=<n>
#      pending=<n>
#
# hint=suspect-billing marks a failed check run that finished in under 15 s:
# on this account's private repos that is GitHub refusing to dispatch the job
# (use-rack-ci), not a test result. Confirm with `gh run view <id> --json jobs`
# (no steps) before treating it as such.
set -euo pipefail

[ $# -ge 1 ] || { sed -n '2,20p' "$0" >&2; exit 64; }
pr="$1"
repo_args=()
[ $# -ge 2 ] && repo_args=(-R "$2")

if [ -n "${PR_STATE_JSON:-}" ]; then   # offline: a saved `gh pr view --json` body
  json=$(cat "$PR_STATE_JSON")
else
  json=$(gh pr view "$pr" ${repo_args[@]+"${repo_args[@]}"} --json \
    number,state,headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup)
fi

jq -r '
  def secs(a; b):
    if (a // "") == "" or (b // "") == "" or b == "0001-01-01T00:00:00Z" then "-"
    else ((b | fromdateiso8601) - (a | fromdateiso8601) | tostring) end;
  def result:
    if .__typename == "StatusContext" then
      ({"SUCCESS":"pass","FAILURE":"fail","ERROR":"error",
        "PENDING":"pending","EXPECTED":"pending"}[.state] // "pending")
    elif .status != "COMPLETED" then "pending"
    else ({"SUCCESS":"pass","NEUTRAL":"pass","SKIPPED":"skip",
           "FAILURE":"fail","TIMED_OUT":"fail","STARTUP_FAILURE":"error",
           "CANCELLED":"error","ACTION_REQUIRED":"error",
           "STALE":"error"}[.conclusion] // "error") end;
  . as $pr
  | "PR number=\(.number) state=\(.state) head=\(.headRefOid[0:12]) mergeable=\(.mergeable) merge_state=\(.mergeStateStatus) review=\(if .reviewDecision == "" then "none" else .reviewDecision end)",
    ( (.statusCheckRollup // [])[]
      | (if .__typename == "StatusContext" then "status" else "run" end) as $kind
      | (if $kind == "status" then .context else .name end) as $name
      | result as $r
      | (if $kind == "run" then secs(.startedAt; .completedAt) else "-" end) as $s
      | (if $kind == "run" and $r == "fail" and $s != "-" and ($s | tonumber) < 15
           then "suspect-billing" else "-" end) as $hint
      | "CHECK kind=\($kind) name=\($name | gsub(" "; "_")) result=\($r) secs=\($s) hint=\($hint) url=\(.targetUrl // .detailsUrl // "-")" ),
    ( [ (.statusCheckRollup // [])[] | result ] as $rs
      | ($rs | map(select(. == "pass")) | length) as $p
      | ($rs | map(select(. == "fail")) | length) as $f
      | ($rs | map(select(. == "error")) | length) as $e
      | ($rs | map(select(. == "pending")) | length) as $w
      | (if ($rs | length) == 0 then "no-checks"
         elif $f + $e > 0 then "failing"
         elif $w > 0 then "pending"
         else "green" end) as $v
      | "VERDICT \($v) pass=\($p) fail=\($f) error=\($e) pending=\($w)" )
' <<<"$json"
