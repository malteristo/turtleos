#!/bin/bash
# Turtle Development Sprint
# Runs agent.py on Claude Opus 4.6 against a bridge command
# Usage: ./sprint.sh [brief-file]

set -e

SHELL_DIR=~/turtleos
BRIDGE=~/magic-bridge

cd "$SHELL_DIR"
source venv/bin/activate

# Load env but ensure we use Anthropic directly (not LiteLLM)
set -a
source .env
set +a
unset LITELLM_BASE_URL

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

# If a brief file is provided, stage it as a bridge command
BRIEF_FILE="${1:-briefs/standing.md}"
if [ -f "$BRIEF_FILE" ]; then
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    SLUG=$(basename "$BRIEF_FILE" .md)
    CMD_FILE="$BRIDGE/commands/sprint_${SLUG}.yaml"

    cat > "$CMD_FILE" << YAML
timestamp: "$TIMESTAMP"
channel: artifact_mail
from: dyad
to: turtle
category: development_sprint
priority: high
action: development_sprint
subject: "Development Sprint"
context: |
$(sed s/^/ / "$BRIEF_FILE")
YAML

    echo "Sprint brief staged: $CMD_FILE"
fi

echo "Running sprint on Claude Opus 4.6..."
echo "---"

python3 agent.py \
    --identity identity/sprint.md \
    --soul identity/soul.md \
    --bridge "$BRIDGE" \
    --workspace /Users/turtle \
    --model claude-opus-4-20250514 \
    --env .env \
    --once

echo "---"
echo "Sprint complete. Check ~/turtle-practice/proposals/ for the proposal."
echo "Signal written to $BRIDGE/signals/"
