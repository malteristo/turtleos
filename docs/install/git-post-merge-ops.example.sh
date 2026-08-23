#!/usr/bin/env bash
# Optional git post-merge hook for turtleos — run ops gate after pull on Mini.
# Install: cp docs/install/git-post-merge-ops.example.sh .git/hooks/post-merge && chmod +x .git/hooks/post-merge
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ -x "$REPO_ROOT/venv/bin/python3" ]]; then
  "$REPO_ROOT/venv/bin/python3" "$REPO_ROOT/scripts/ops_runner.py" --job post-merge || true
fi
