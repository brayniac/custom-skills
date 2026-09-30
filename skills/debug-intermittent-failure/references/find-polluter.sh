#!/usr/bin/env bash
# Find the one test, among a list of candidates, whose run leaves behind the
# state that makes something else fail. Bisects the candidate list:
# at most about 2*log2(N) + 3 runs instead of N.
#
# Usage:
#   find-polluter.sh --list FILE --run 'CMD' [--check 'CMD'] [--reset 'CMD']
#
#   --list FILE   candidate test ids, one per line (blank lines ignored)
#   --run CMD     run a subset; the ids are appended as arguments.
#                 Its exit status is ignored when --check is given.
#   --check CMD   exit 0 when clean, non-zero when polluted. Omit it when the
#                 victim runs inside --run (in-process state); then --run's
#                 own non-zero exit means polluted.
#   --reset CMD   restore a clean state before every trial (rm the stray
#                 file, drop the scratch database). Required when the
#                 pollution persists across runs.
#
# Exit: 0 polluter found (printed on the last line as POLLUTER=<id>),
#       1 the full list does not pollute (nothing to bisect),
#       2 pollution needs more than one candidate together, or is not
#         reproducible (printed as INTERACTION=... or FLAKY=...),
#       64 usage error.
#
# Works in macOS bash 3.2: no associative arrays, no mapfile.
set -u

list="" run="" check="" reset=""
while [ $# -gt 0 ]; do
  case "$1" in
    --list) list="$2"; shift 2 ;;
    --run) run="$2"; shift 2 ;;
    --check) check="$2"; shift 2 ;;
    --reset) reset="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$list" ] && [ -n "$run" ] || { sed -n '2,25p' "$0" >&2; exit 64; }
[ -r "$list" ] || { echo "cannot read $list" >&2; exit 64; }

ids=()
while IFS= read -r line || [ -n "$line" ]; do
  [ -n "$line" ] && ids+=("$line")
done < "$list"
[ ${#ids[@]} -gt 0 ] || { echo "empty candidate list" >&2; exit 64; }

trials=0
# polluted <id>... : returns 0 when running these ids leaves pollution.
polluted() {
  trials=$((trials + 1))
  if [ -n "$reset" ]; then
    bash -c "$reset" >/dev/null 2>&1 || { echo "reset failed" >&2; exit 64; }
  fi
  if [ -n "$check" ]; then
    bash -c "$run \"\$@\"" _ "$@" >/dev/null 2>&1
    if bash -c "$check" >/dev/null 2>&1; then r=1; else r=0; fi
  else
    if bash -c "$run \"\$@\"" _ "$@" >/dev/null 2>&1; then r=1; else r=0; fi
  fi
  echo "trial $trials: $# candidate(s) -> $([ $r = 0 ] && echo polluted || echo clean)" >&2
  return $r
}

# Control: the clean state must be clean, or every later verdict is noise.
if [ -n "$check" ] && [ -n "$reset" ]; then
  bash -c "$reset" >/dev/null 2>&1
  bash -c "$check" >/dev/null 2>&1 || {
    echo "check reports pollution after reset, before any test ran" >&2; exit 64; }
fi

# In-process mode: the victim alone, with no candidate, must pass.
if [ -z "$check" ]; then
  if polluted; then
    echo "--run fails with no candidate appended; the victim fails alone" >&2
    exit 64
  fi
fi

polluted "${ids[@]}" || { echo "full list of ${#ids[@]} does not pollute" >&2; exit 1; }

set_=("${ids[@]}")
while [ ${#set_[@]} -gt 1 ]; do
  half=$(( ${#set_[@]} / 2 ))
  a=("${set_[@]:0:$half}")
  b=("${set_[@]:$half}")
  if polluted "${a[@]}"; then
    set_=("${a[@]}")
  elif polluted "${b[@]}"; then
    set_=("${b[@]}")
  else
    echo "INTERACTION=${set_[*]}"
    echo "neither half pollutes alone; the cause needs members of both" >&2
    exit 2
  fi
done

# Confirm the single survivor once more: a flaky polluter can steer the
# bisection into a candidate that only looked guilty.
if polluted "${set_[0]}"; then
  echo "found in $trials trials" >&2
  echo "POLLUTER=${set_[0]}"
  exit 0
fi
echo "FLAKY=${set_[0]}"
echo "the survivor did not reproduce on a second run; measure the rate first" >&2
exit 2
