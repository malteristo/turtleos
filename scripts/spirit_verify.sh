#!/usr/bin/env bash
# Spirit maintenance gate — run before/after repo chapters (Forge or Mini).
# See docs/automation/functional-gate-protocol.md for full deploy suite.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi

echo "=== turtleOS Spirit verify (unit) ==="
echo "python: $PY"
"$PY" -m unittest discover -s tests -q
echo "=== OK: unit suite green ==="
