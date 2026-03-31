#!/bin/bash
# Self-restart script for Turtle's self-development protocol
# Turtle can call this after making code changes to deploy them

echo "[Tue Mar 31 18:58:57 CEST 2026] Self-restart initiated by Turtle" >> ~/turtle-shell/logs/self-dev.log

# Validate syntax of changed Python files before restarting
for f in ~/turtle-shell/*.py; do
    python3 -c "import py_compile; py_compile.compile('', doraise=True)" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[Tue Mar 31 18:58:57 CEST 2026] ABORT: Syntax error in $f" >> ~/turtle-shell/logs/self-dev.log
        echo "Syntax error in $f — aborting restart"
        exit 1
    fi
done

echo "[Tue Mar 31 18:58:57 CEST 2026] Syntax check passed, restarting..." >> ~/turtle-shell/logs/self-dev.log
launchctl kickstart -k gui/$(id -u)/com.turtle.discord
echo "[Tue Mar 31 18:58:57 CEST 2026] Restart command issued" >> ~/turtle-shell/logs/self-dev.log
