#!/bin/bash
# Wait for the deploy guard, then restart already-applied code.
#
# Last night this lived as a nohup one-liner in a shell history. The 2026-09-03
# release queued it as a script. It does not pull, fetch, or checkout — those
# are how an unattended waiter restarts the wrong tree. It pins an expected
# HEAD, times out non-zero, and propagates restart.sh's exit code.
#
#   ./scripts/deploy_when_quiet.sh --expect-sha <full-or-prefix>
#   ./scripts/deploy_when_quiet.sh                  # pins current HEAD
#
set -euo pipefail

REPO="${TURTLEOS_REPO:-${HOME}/turtleos}"
GUARD="${DEPLOY_GUARD_BIN:-${REPO}/scripts/deploy_guard.py}"
RESTART="${RESTART_BIN:-${REPO}/restart.sh}"
EXPECT_SHA=""
TIMEOUT_HOURS=4
POLL_SECONDS=60
LOG=""

usage() {
  cat <<'EOF'
Usage: deploy_when_quiet.sh [--expect-sha SHA] [--timeout-hours N] [--poll-seconds N] [--log FILE]

Polls the quiet guard and runs restart.sh only when:
  - the checkout HEAD still matches --expect-sha (current HEAD if omitted)
  - the guard reports quiet

Does not git pull, fetch, or checkout. Times out non-zero. Propagates restart.sh.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --expect-sha) EXPECT_SHA="${2:-}"; shift 2 ;;
    --timeout-hours) TIMEOUT_HOURS="${2:-}"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="${2:-}"; shift 2 ;;
    --log) LOG="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -d "${REPO}/.git" ]]; then
  echo "not a git checkout: ${REPO}" >&2
  exit 2
fi

HEAD="$(git -C "${REPO}" rev-parse HEAD)"
if [[ -z "${EXPECT_SHA}" ]]; then
  EXPECT_SHA="${HEAD}"
fi

# Prefix match so a short sha on the command line is enough.
if [[ "${HEAD}" != "${EXPECT_SHA}"* && "${EXPECT_SHA}" != "${HEAD}"* ]]; then
  echo "HEAD ${HEAD} is not the expected ${EXPECT_SHA} — refusing to wait on the wrong tree." >&2
  exit 3
fi

if [[ -z "${LOG}" ]]; then
  mkdir -p "${REPO}/logs"
  LOG="${REPO}/logs/deploy_wait_$(date '+%Y-%m-%d').log"
fi
mkdir -p "$(dirname "${LOG}")"

log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "[${ts}] $*" | tee -a "${LOG}"
}

DEADLINE=$(( $(date +%s) + $(python3 -c "print(int(float('${TIMEOUT_HOURS}') * 3600))") ))
log "waiting for quiet · expect ${EXPECT_SHA} · timeout ${TIMEOUT_HOURS}h · poll ${POLL_SECONDS}s · repo ${REPO}"

while true; do
  NOW="$(date +%s)"
  if (( NOW >= DEADLINE )); then
    log "TIMEOUT — still busy after ${TIMEOUT_HOURS}h; HEAD $(git -C "${REPO}" rev-parse HEAD). Gave up."
    exit 1
  fi

  CURRENT="$(git -C "${REPO}" rev-parse HEAD)"
  if [[ "${CURRENT}" != "${EXPECT_SHA}"* && "${EXPECT_SHA}" != "${CURRENT}"* ]]; then
    log "ABORT — HEAD moved from ${EXPECT_SHA} to ${CURRENT}. Not restarting the unexpected revision."
    exit 3
  fi

  if python3 "${GUARD}"; then
    log "quiet — restarting at ${CURRENT}"
    set +e
    "${RESTART}"
    RC=$?
    set -e
    log "restart exit ${RC} · revision ${CURRENT}"
    exit "${RC}"
  fi

  sleep "${POLL_SECONDS}"
done
