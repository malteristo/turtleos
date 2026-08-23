#!/usr/bin/env bash
# Post-deploy shakedown — run on Mac Mini after turtleOS pull + service restart.
# See docs/automation/functional-gate-protocol.md
set -euo pipefail

cd ~/turtleos
PY=~/turtleos/venv/bin/python3

echo "=== unittest ==="
$PY -m unittest discover -s tests -q

echo "=== shake: river (offline) ==="
$PY scripts/shake_river.py

echo "=== shake: flow navigator (offline) ==="
$PY scripts/shake_flow.py navigator

echo "=== shake: eddy bar (offline) ==="
$PY scripts/shake_eddy_bar.py

echo "=== shake: link read (offline) ==="
$PY scripts/shake_link_read.py

echo "=== shake: lifecycle (offline) ==="
$PY scripts/shake_lifecycle.py

echo "=== shake: discord ref (offline) ==="
$PY scripts/shake_discord_ref.py

if [[ "${SHAKE_LIVE:-0}" == "1" ]]; then
  echo "=== shake: flow navigator (live Discord) ==="
  $PY scripts/shake_flow.py navigator --live --wait "${SHAKE_WAIT:-45}"
  echo "=== shake: eddy bar blank eddy (live Discord) ==="
  $PY scripts/shake_eddy_bar.py --live --wait "${SHAKE_WAIT:-50}"
fi

echo "=== canary ==="
$PY canary.py

echo "=== shake report ==="
$PY scripts/shake_report.py --write --strict || {
  echo "shake_after_deploy: functional gate FAILED — see shake_report"
  exit 1
}

echo "shake_after_deploy: functional gate pass"
