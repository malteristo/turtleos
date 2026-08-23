#!/bin/bash
# Self-restart for Turtle's self-development protocol / operator deploy ritual.
# Split-bot: always bounce Turtle + River together so shared modules stay in sync.
# Single-bot fallback: River label absent → Turtle only.

set -euo pipefail

REPO="${HOME}/turtleos"
LOG="${REPO}/logs/self-dev.log"
UID_GUI="$(id -u)"
TS="$(date '+%a %b %d %H:%M:%S %Z %Y')"

FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p "${REPO}/logs"
echo "[${TS}] Self-restart initiated" >> "${LOG}"

# Never interrupt a live conversation (operator's rule, 2026-08-15).
#
# A restart is not a pause: the bot identifies fresh, Discord does not replay what it
# missed, and nothing backfills practitioner messages at boot — so a message sent in
# the ~15s window is never seen and never answered. The person gets silence and no
# explanation.
#
# This is a check rather than an approval prompt on purpose. Approval was the previous
# arrangement and it failed in the ordinary way: asked once, granted once, then read as
# standing for the rest of the evening — four both-bot restarts on one "deploy now",
# on a Friday with family channels live. A question a human has to remember to ask is
# not a guard.
#
# `--force` is for the case the rule does not cover: deploying a fix for something
# already broken, where fifteen seconds of gap beats leaving it broken.
if [ "$FORCE" -eq 0 ]; then
    if ! python3 "${REPO}/scripts/deploy_guard.py"; then
        echo "[${TS}] ABORT: practice is live (deploy guard)" >> "${LOG}"
        exit 1
    fi
else
    echo "[${TS}] Deploy guard bypassed (--force)" >> "${LOG}"
    echo "Deploy guard bypassed — restarting into a possibly live conversation."
fi

# Validate syntax of top-level Python files before restarting
for f in "${REPO}"/*.py; do
    if ! python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null; then
        echo "[${TS}] ABORT: Syntax error in $f" >> "${LOG}"
        echo "Syntax error in $f — aborting restart"
        exit 1
    fi
done

kickstart_label() {
    local label="$1"
    launchctl kickstart -k "gui/${UID_GUI}/${label}"
}

echo "[${TS}] Syntax check passed, restarting…" >> "${LOG}"

kickstart_label com.turtle.discord
echo "[${TS}] Restarted com.turtle.discord" >> "${LOG}"

if launchctl list "com.turtle.river" >/dev/null 2>&1; then
    kickstart_label com.turtle.river
    echo "[${TS}] Restarted com.turtle.river" >> "${LOG}"
    echo "Restarted Turtle + River (split-bot deploy unit)"
else
    echo "[${TS}] com.turtle.river not loaded — Turtle only (single-bot fallback)" >> "${LOG}"
    echo "Restarted Turtle (River label not loaded — single-bot fallback)"
fi
