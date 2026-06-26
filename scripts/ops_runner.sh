#!/usr/bin/env bash
# Thin wrapper for launchd / hooks — see docs/automation/registry.md
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./venv/bin/python3 scripts/ops_runner.py "$@"
