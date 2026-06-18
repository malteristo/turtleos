#!/usr/bin/env bash
# Post-deploy shakedown — run on Mac Mini after turtleOS pull + service restart.
set -euo pipefail

cd ~/turtleos
PY=~/turtleos/venv/bin/python3

echo "=== shake: river (offline) ==="
$PY scripts/shake_river.py

echo "=== shake: flow shelter (offline) ==="
$PY scripts/shake_flow.py shelter

echo "=== shake: eddy bar flow menu (offline) ==="
$PY scripts/shake_eddy_bar.py

echo "=== shake: link read (offline) ==="
$PY scripts/shake_link_read.py

if [[ "${SHAKE_LIVE:-0}" == "1" ]]; then
  echo "=== shake: flow shelter (live Discord) ==="
  $PY scripts/shake_flow.py shelter --live --wait "${SHAKE_WAIT:-45}"
  echo "=== shake: eddy bar flow menu (live Discord) ==="
  $PY scripts/shake_eddy_bar.py --live --wait "${SHAKE_WAIT:-50}"
fi

echo "=== canary ==="
$PY canary.py

echo "shake_after_deploy: pass"
