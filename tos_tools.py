"""turtleOS tool definitions and execution — 9 practice file tools."""

import json
import os
import re
import time

from mage import get_pd
from practice_io import (
    read_safe, extract_section, list_headings, is_readable, is_writable,
)
from state import OLLAMA_URL, EDIT_DELEGATE_MODEL, EMBED_COLORS
from llm import chat_ollama
from capabilities import format_capability_index, read_capability
from shell_harness import format_shell_result, run_shell_command
from tool_result import (
    TRANSIENT,
    classify_tool_text,
    format_tool_result as format_typed_tool_result,
    log_tool_result,
    make_tool_result,
)


# ─── Practice Path Resolution ────────────────────────────────────


def _resolve_read_path(filename):
    """Resolve a filename to its absolute path for reading (practice root only)."""
    return os.path.join(get_pd(), filename), False


def _resolve_search_base(directory):
    """Resolve a search directory under practice root."""
    base = os.path.join(get_pd(), directory) if directory else get_pd()
    return base, get_pd()


# ─── Tool Definitions ────────────────────────────────────────────

TOS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_practice_file",
            "description": (
                "Read an allowlisted practice artifact (internal context). "
                "In Discord replies: quote at most ~3 lines from an artifact; point to `!read <path>` for the full note — do not paste full bodies (§11.5.5). "
                "Practice artifacts: sessions/, state/notes/, thread-archive/, chronicle/surface.md, "
                "intentions/, box/intake/, surface files (boom.md, bright.md, …)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "File path relative to practice dir, e.g. 'bright.md', 'intentions/turtle.md'",
                    },
                    "section": {
                        "type": "string",
                        "description": "Optional: heading name to extract just that section, e.g. 'Actions' or 'Body'",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_practice_file",
            "description": (
                "Make a surgical edit to a practice file. PREFERRED over write_practice_file for small changes. "
                "Finds exact match of old_text and replaces with new_text. "
                "Use for toggling checkboxes, replacing lines, updating status fields. "
                "Example: old_text='- [ ] My task', new_text='- [x] My task'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File path relative to practice dir"},
                    "old_text": {"type": "string", "description": "Exact text to find (must match precisely, including whitespace)"},
                    "new_text": {"type": "string", "description": "Text to replace it with. Use empty string to delete."},
                },
                "required": ["filename", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_practice_file",
            "description": (
                "Append content to the end of a practice file. "
                "PREFERRED over write_practice_file for adding entries. "
                "Use for adding boom items, bright items, new sections."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File path relative to practice dir"},
                    "content": {"type": "string", "description": "Content to append"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_edit",
            "description": (
                "Delegate a complex file edit to a fast local model. "
                "Use when the edit is too complex for patch (multiple changes, restructuring) "
                "but you don't want to regenerate the entire file yourself. "
                "Provide a clear natural-language instruction; the local model reads the file, "
                "applies the edit, and writes the result. FREE — no API tokens spent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File path relative to practice dir"},
                    "instruction": {"type": "string", "description": "Clear instruction for the edit"},
                },
                "required": ["filename", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_practice_file",
            "description": (
                "Write COMPLETE content to a practice file (full overwrite). "
                "Use ONLY when creating new files or when patch/append/delegate won't work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File path relative to practice dir"},
                    "content": {"type": "string", "description": "Complete file content to write"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_practice_files",
            "description": (
                "Search across practice or workshop files for a text pattern. "
                "Returns matching lines with file paths and line numbers. "
                "Use directory='library' or 'system' to search workshop knowledge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex pattern to search for (case-insensitive)"},
                    "directory": {"type": "string", "description": "Limit to any subdirectory path, e.g. 'intentions', 'sessions', or '' for all"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_practice_files",
            "description": "List files in a practice directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path: '' (practice root), 'sessions', 'intentions', 'library', 'system', 'system/flows'"},
                },
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_turtleos_shell",
            "description": (
                "Run a constrained, audited shell command inside ~/turtleos for self-development. "
                "Allowed commands are read-only inspection and verification: pwd, ls, rg, git status/diff/log/show/branch/rev-parse, "
                "and python -m py_compile for .py files. Use this to inspect the turtleOS source tree, check git state, "
                "search code, or verify syntax. It cannot commit, edit files, restart services, change permissions, or run arbitrary Python."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run, e.g. 'git status --short' or 'python3 -m py_compile commands.py'",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory inside ~/turtleos, relative or absolute.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short reason for the action; logged for transparency.",
                    },
                },
                "required": ["command", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_turtle_capabilities",
            "description": (
                "List Turtle's local skills and procedures. Use this when deciding how to approach "
                "self-development, diagnostics, tool shakedowns, or recurring operating tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "Optional filter: 'skill' or 'procedure'. Leave blank for all.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_turtle_capability",
            "description": (
                "Read the full text of one Turtle skill or procedure before following it. "
                "Names are slugs from list_turtle_capabilities, e.g. kind='procedure', name='tool-shakedown'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "Capability kind: 'skill' or 'procedure'.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Capability slug, with or without .md.",
                    },
                },
                "required": ["kind", "name"],
            },
        },
    },
]


# ─── Tool Execution ──────────────────────────────────────────────

def _execute_tos_tool_raw(name, arguments):
    if name == "read_practice_file":
        filename = arguments.get("filename", "")
        if not is_readable(filename):
            return f"Cannot read {filename} — not a readable practice file"
        section = arguments.get("section", "")
        path, is_workshop = _resolve_read_path(filename)
        content = read_safe(path)
        if not content.strip():
            return f"{filename} is empty"
        if section:
            extracted = extract_section(content, section)
            if extracted:
                return f"[{filename} §{section}]\n\n{extracted[:8000]}"
            return f"Section '{section}' not found in {filename}. Available headings: {list_headings(content)}"
        return f"[{filename}]\n\n{content[:12000]}"

    if name == "search_practice_files":
        query = arguments.get("query", "")
        directory = arguments.get("directory", "")
        if not query:
            return "No query provided"
        from artifact_viewer import collect_artifact_search_hits, format_search_results

        hits = collect_artifact_search_hits(query, directory=directory or "")
        if hits:
            return format_search_results(hits, query)
        return f"No matches for '{query}'"

    if name == "list_practice_files":
        directory = arguments.get("directory", "")
        target, _ = _resolve_search_base(directory)
        if not os.path.isdir(target):
            return f"Directory not found: {directory or '(root)'}"
        entries = []
        for item in sorted(os.listdir(target)):
            full = os.path.join(target, item)
            if item.startswith("."):
                continue
            if os.path.isdir(full):
                count = len([f for f in os.listdir(full) if f.endswith(".md")])
                entries.append(f"  {item}/ ({count} files)")
            elif item.endswith(".md"):
                size = os.path.getsize(full)
                filepath = f"{directory}/{item}" if directory else item
                if not is_readable(filepath):
                    continue
                entries.append(f"  {filepath} ({size} bytes)")
        return "\n".join(entries) if entries else "(empty)"

    if name == "run_turtleos_shell":
        command = arguments.get("command", "")
        cwd = arguments.get("cwd", "")
        reason = arguments.get("reason", "")
        result = run_shell_command(command, cwd=cwd or None, reason=reason, requester="turtle-llm")
        return format_shell_result(result)

    if name == "list_turtle_capabilities":
        kind = (arguments.get("kind") or "").strip() or None
        return format_capability_index(kind)

    if name == "read_turtle_capability":
        kind = (arguments.get("kind") or "").strip()
        capability_name = (arguments.get("name") or "").strip()
        return read_capability(kind, capability_name)

    if name == "patch_practice_file":
        filename = arguments.get("filename", "")
        old_text = arguments.get("old_text", "")
        new_text = arguments.get("new_text", "")
        if not is_writable(filename):
            return f"Cannot patch {filename} — not a writable practice file"
        path = os.path.join(get_pd(), filename)
        content = read_safe(path)
        if not content:
            return f"{filename} is empty — nothing to patch"
        count = content.count(old_text)
        if count == 0:
            return f"old_text not found in {filename}. Read the file first to get exact text."
        if count > 1:
            return f"old_text matches {count} locations in {filename}. Provide more context to match uniquely."
        new_content = content.replace(old_text, new_text, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return f"Done. Patched {filename}."

    if name == "append_to_practice_file":
        filename = arguments.get("filename", "")
        content = arguments.get("content", "")
        if not is_writable(filename):
            return f"Cannot append to {filename} — not a writable practice file"
        path = os.path.join(get_pd(), filename)
        parent = os.path.dirname(path)
        if parent and parent != get_pd():
            os.makedirs(parent, exist_ok=True)
        with open(path, "a") as f:
            f.write("\n" + content + "\n")
        return f"Done. Appended to {filename}."

    if name == "delegate_edit":
        filename = arguments.get("filename", "")
        instruction = arguments.get("instruction", "")
        if not is_writable(filename):
            return f"Cannot edit {filename} — not a writable practice file"
        path = os.path.join(get_pd(), filename)
        content = read_safe(path)
        if not content.strip():
            return f"{filename} is empty — nothing to edit. Use write_practice_file to create."
        return _delegate_edit_sync(path, filename, content, instruction)

    if name == "write_practice_file":
        filename = arguments.get("filename", "")
        content = arguments.get("content", "")
        if not is_writable(filename):
            return f"Cannot write to {filename} — not a writable practice file"
        path = os.path.join(get_pd(), filename)
        parent = os.path.dirname(path)
        if parent and parent != get_pd():
            os.makedirs(parent, exist_ok=True)
        old_content = read_safe(path)
        is_new = not old_content.strip()
        with open(path, "w") as f:
            f.write(content)
        if is_new:
            return f"Done. Created {filename} ({len(content)} chars)."
        return f"Done. Wrote {filename} ({len(old_content)}→{len(content)} chars)."

    return f"Unknown tool: {name}"


def _max_tool_attempts(name: str) -> int:
    if name in (
        "read_practice_file",
        "search_practice_files",
        "list_practice_files",
        "run_turtleos_shell",
        "list_turtle_capabilities",
        "read_turtle_capability",
    ):
        return 2
    return 1


def execute_tos_tool_reliable(name, arguments):
    """Execute a tOS tool with typed failure classification and minimal retries."""
    attempts = _max_tool_attempts(name)
    last_result = None
    for attempt in range(1, attempts + 1):
        try:
            raw = _execute_tos_tool_raw(name, arguments)
            result = classify_tool_text(name, raw)
        except Exception as e:
            result = make_tool_result(
                tool=name,
                ok=False,
                kind=TRANSIENT if isinstance(e, (TimeoutError, ConnectionError)) else "system_error",
                summary=f"{type(e).__name__}: {e}",
                retryable=isinstance(e, (TimeoutError, ConnectionError)),
            )

        last_result = result
        if result.get("ok") or not result.get("retryable") or attempt == attempts:
            log_tool_result(result, arguments, attempts=attempt)
            return format_typed_tool_result(result)
        time.sleep(0.25 * attempt)

    log_tool_result(last_result, arguments, attempts=attempts)
    return format_typed_tool_result(last_result)


def execute_tos_tool(name, arguments):
    return execute_tos_tool_reliable(name, arguments)


def _delegate_edit_sync(path, filename, content, instruction):
    """Delegate a file edit to a fast local model (synchronous).

    Uses keep_alive to prevent cold-start latency on subsequent calls.
    """
    import urllib.request

    prompt = (
        f"You are a precise text editor. Apply this edit to the file below.\n\n"
        f"INSTRUCTION: {instruction}\n\n"
        f"RULES:\n"
        f"- Output ONLY the complete edited file content, nothing else\n"
        f"- No explanations, no markdown fences, no preamble\n"
        f"- Preserve all formatting, whitespace, and structure not affected by the edit\n"
        f"- If the instruction is unclear, make your best interpretation\n\n"
        f"FILE ({filename}):\n{content}"
    )

    payload = json.dumps({
        "model": EDIT_DELEGATE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_ctx": 8192, "temperature": 0.1},
        "keep_alive": "30m",
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            result = data.get("message", {}).get("content", "").strip()

        if not result or len(result) < 10:
            return f"Delegate edit failed \u2014 local model returned empty/short result"

        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            result = "\n".join(lines)

        with open(path, "w") as f:
            f.write(result)

        return f"Done. Edited {filename} ({len(content)}\u2192{len(result)} chars)."

    except Exception as e:
        return f"Delegate edit failed: {type(e).__name__}: {e}"


# ─── Tool Report Builder ────────────────────────────────────────

def build_tool_report(tools_executed):
    """Build a minimal report of write operations only."""
    from practice_io import obsidian_link
    if not tools_executed:
        return ""
    write_ops = []
    for t in tools_executed:
        name = t["name"]
        args = t["args"]
        if name in (
            "read_practice_file",
            "search_practice_files",
            "list_practice_files",
            "list_turtle_capabilities",
            "read_turtle_capability",
        ):
            continue
        if name == "run_turtleos_shell":
            command = args.get("command", "")
            write_ops.append(f"ran shell `{command[:80]}`")
            continue
        fname = args.get("filename", "")
        if not fname:
            continue
        link = obsidian_link(fname)
        if name == "patch_practice_file":
            write_ops.append(f"patched `{fname}` {link}")
        elif name == "append_to_practice_file":
            write_ops.append(f"appended to `{fname}` {link}")
        elif name == "write_practice_file":
            write_ops.append(f"wrote `{fname}` {link}")
        elif name == "delegate_edit":
            write_ops.append(f"edited `{fname}` {link}")
    if not write_ops:
        return ""
    return " · ".join(write_ops)
