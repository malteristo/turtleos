#!/usr/bin/env python3
"""Hermit Crab Shell — Tool Implementations

Four primitives that compose into everything the Turtle needs.
The guard on read_file preventing directory reads is load-bearing —
the 2026-03-05 loop incident was caused by calling Read on a directory.
"""

import os
import subprocess

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Always use full file paths, NEVER directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "shell",
        "description": "Execute a shell command and return its output. Use for git, curl, and system operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Directory to run in (optional)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory. Returns entries with / suffix for subdirectories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to directory",
                }
            },
            "required": ["path"],
        },
    },
]


def execute(tool_name, tool_input, workspace=None):
    """Execute a tool by name. Returns a string result."""
    handlers = {
        "read_file": lambda inp: _read_file(inp["path"]),
        "write_file": lambda inp: _write_file(inp["path"], inp["content"]),
        "shell": lambda inp: _shell(inp["command"], inp.get("working_directory", workspace)),
        "list_directory": lambda inp: _list_directory(inp["path"]),
    }
    handler = handlers.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"
    try:
        return handler(tool_input)
    except Exception as e:
        return f"Error in {tool_name}: {e}"


def _read_file(path):
    path = os.path.expanduser(path)
    if os.path.isdir(path):
        return (
            f"Error: '{path}' is a directory, not a file. "
            f"Use list_directory to see contents, then read_file on individual files."
        )
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    with open(path, "r") as f:
        content = f.read()
    return content if content else "(empty file)"


def _write_file(path, content):
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return f"Written: {path} ({len(content)} chars)"


def _shell(command, working_directory=None):
    cwd = os.path.expanduser(working_directory) if working_directory else None
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds"
    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += f"\n[stderr] {result.stderr}"
    if result.returncode != 0:
        output += f"\n[exit code: {result.returncode}]"
    return output.strip() or "(no output)"


def _list_directory(path):
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        return f"Error: Not a directory: {path}"
    entries = sorted(os.listdir(path))
    result = []
    for entry in entries:
        full = os.path.join(path, entry)
        marker = "/" if os.path.isdir(full) else ""
        result.append(f"{entry}{marker}")
    return "\n".join(result) if result else "(empty directory)"
