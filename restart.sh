#!/bin/bash
# Self-restart for Turtle's self-development protocol / operator deploy ritual.
# Split-bot: always bounce Turtle + River together so shared modules stay in sync.
# Single-bot fallback: River label absent → Turtle only.

set -euo pipefail

REPO="${HOME}/turtleos"
LOG="${REPO}/logs/self-dev.log"
UID_GUI="$(id -u)"
TS="$(date '+%a %b %d %H:%M:%S %Z %Y')"

mkdir -p "${REPO}/logs"
echo "[${TS}] Self-restart initiated" >> "${LOG}"

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
