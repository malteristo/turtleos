"""turtleOS tool definitions and execution — practice file + turtleOS inspect tools."""

import json
import os
import re
import time
import threading

from mage import get_pd, get_registry
from practice_io import (
    read_safe, extract_section, list_headings, is_readable, is_writable,
)
from state import OLLAMA_URL, EDIT_DELEGATE_MODEL, EMBED_COLORS
from llm import chat_ollama
from core.capabilities import format_capability_index, read_capability
from shell_harness import TURTLEOS_ROOT, format_shell_result, run_shell_command
from tool_result import (
    TRANSIENT,
    classify_tool_text,
    format_tool_result as format_typed_tool_result,
    log_tool_result,
    make_tool_result,
)


# ─── Practice Path Resolution ────────────────────────────────────


_SIG_RE = re.compile(r"^(async\s+def|def|class)\s+\w+")


def _resolve_turtleos_path(filename: str):
    """Resolve a path under ~/turtleos. Returns (Path|None, error)."""
    from pathlib import Path

    raw = (filename or "").strip()
    if not raw or ".." in raw or raw.startswith("/"):
        return None, "path must be relative to ~/turtleos (no .. or absolute)"
    path = (TURTLEOS_ROOT / raw).resolve()
    try:
        path.relative_to(TURTLEOS_ROOT)
    except ValueError:
        return None, f"path escapes ~/turtleos: {filename}"
    if not path.is_file():
        return None, f"not a file: {filename}"
    return path, ""


_MAX_WINDOW_LINES = 400


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _inspect_turtleos_module(
    filename: str,
    head_lines=40,
    start_line=1,
    line_count=None,
) -> str:
    path, err = _resolve_turtleos_path(filename)
    if err:
        return err
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"read failed: {type(exc).__name__}: {exc}"

    lines = text.splitlines()
    # `line_count` is the window size; `head_lines` is the older name for the
    # same thing when the window always started at 1. Either may arrive.
    n_window = _coerce_int(
        line_count if line_count is not None else head_lines, 40
    )
    n_window = max(0, min(_MAX_WINDOW_LINES, n_window))
    first = max(1, _coerce_int(start_line, 1))

    imports = []
    signatures = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if len(imports) < 40:
                imports.append(f"{i}: {stripped}")
        if _SIG_RE.match(stripped):
            signatures.append(f"{i}: {stripped.rstrip(':')}")

    rel = str(path.relative_to(TURTLEOS_ROOT))
    parts = [
        f"# {rel}",
        f"size: {path.stat().st_size} bytes · {len(lines)} lines",
        "",
        "## Imports",
        ("\n".join(imports) if imports else "(none in first pass)"),
        "",
        "## Signatures (class / def)",
        ("\n".join(signatures[:80]) if signatures else "(none found)"),
    ]
    if len(signatures) > 80:
        parts.append(f"… {len(signatures) - 80} more signatures omitted")
    if n_window and first <= len(lines):
        last = min(len(lines), first + n_window - 1)
        body = "\n".join(
            f"{n}: {lines[n - 1]}" for n in range(first, last + 1)
        )
        parts.extend(["", f"## Lines {first}–{last} of {len(lines)}", body])
        # Say how to get the rest, so a truncated read is a next call rather
        # than a dead end. The blocked survey of 2026-08-14 recovered on its
        # own; it should not have had to.
        if last < len(lines):
            parts.append(
                f"… {len(lines) - last} more lines — call again with "
                f"start_line={last + 1}"
                + (
                    f" (window capped at {_MAX_WINDOW_LINES} lines)"
                    if n_window >= _MAX_WINDOW_LINES
                    else ""
                )
            )
    elif n_window:
        parts.append(
            f"\nstart_line={first} is past the end of the file ({len(lines)} lines)"
        )
    return "\n".join(parts)


EXA_MAX_RESULTS = 10

# `exa_py` accepts no timeout — not on the client, not on the call — and hands
# `requests` none either, so an unresponsive endpoint hangs forever. This
# constant existed from the start and was passed to nothing; the bound below is
# the mechanism it never had. Measured on the live host: 1.1s–1.6s for three
# results, so 8s is roughly five times the observed cost.
EXA_TIMEOUT_SECONDS = 8


def _exa_search(query: str, num_results: int = 5, search_type: str = "auto") -> str:
    """Search the web via Exa and return highlighted excerpts.

    `highlights` rather than full page text: roughly a tenth of the tokens, and
    the excerpts are what a research turn actually reasons over. Only reachable
    where the practitioner asked for it — see `_TOOL_SCOPES`.
    """
    query = (query or "").strip()
    if not query:
        return "exa_search needs a query"
    api_key = os.environ.get("EXA_API_KEY", "").strip()
    if not api_key:
        return (
            "EXA_API_KEY is not set on this host — web search is unavailable. "
            "Say so rather than guessing at what a search would have returned."
        )
    try:
        from exa_py import Exa
    except ImportError:
        return "exa-py is not installed on this host (pip install exa-py)"

    try:
        count = max(1, min(EXA_MAX_RESULTS, int(num_results)))
    except (TypeError, ValueError):
        count = 5

    def _call():
        return Exa(api_key).search_and_contents(
            query,
            type=(search_type or "auto"),
            num_results=count,
            highlights=True,
        )

    # Bounded on a **daemon** thread, because the tool loop calls this
    # synchronously from the bot's event loop: however long this takes, Turtle
    # answers nobody in any channel for that long. A `ThreadPoolExecutor` is the
    # obvious reach and the wrong one — `concurrent.futures` joins its workers at
    # interpreter exit, so an abandoned request would hold up the bot's shutdown
    # for whatever remained of it. A daemon thread is simply dropped.
    outcome: dict = {}

    def _worker():
        try:
            outcome["response"] = _call()
        except BaseException as exc:  # noqa: BLE001 — carried out, re-read below
            outcome["error"] = exc

    thread = threading.Thread(target=_worker, name="exa-search", daemon=True)
    thread.start()
    thread.join(EXA_TIMEOUT_SECONDS)
    if thread.is_alive():
        return (
            f"exa search timed out after {EXA_TIMEOUT_SECONDS}s — report that the "
            "search did not complete rather than answering from memory."
        )
    if "error" in outcome:
        # The message must not read like an answer.
        exc = outcome["error"]
        return f"exa search failed: {type(exc).__name__}: {exc}"
    response = outcome["response"]

    rows = []
    for result in getattr(response, "results", []) or []:
        rows.append(
            {
                "title": getattr(result, "title", None),
                "url": getattr(result, "url", None),
                "published": getattr(result, "published_date", None),
                "highlights": list(getattr(result, "highlights", []) or []),
            }
        )
    if not rows:
        return f"Found 0 results for {query!r}."
    return f"Found {len(rows)} result(s) for {query!r}.\n" + json.dumps(
        rows, indent=2, ensure_ascii=False
    )


def _list_turtleos_modules(directory: str = "") -> str:
    from pathlib import Path

    raw = (directory or "").strip()
    if ".." in raw or raw.startswith("/"):
        return "directory must be relative to ~/turtleos"
    if raw in {"", "."}:
        root = TURTLEOS_ROOT
        recursive = raw == "."
    else:
        root = (TURTLEOS_ROOT / raw).resolve()
        try:
            root.relative_to(TURTLEOS_ROOT)
        except ValueError:
            return f"path escapes ~/turtleos: {directory}"
        if not root.is_dir():
            return f"not a directory: {directory}"
        recursive = True

    paths = []
    if recursive:
        candidates = root.rglob("*.py")
    else:
        candidates = root.glob("*.py")
    for path in sorted(candidates):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & {".git", "__pycache__", "venv", ".venv"}:
            continue
        paths.append(str(path.relative_to(TURTLEOS_ROOT)))
        if len(paths) >= 400:
            paths.append("… truncated at 400")
            break
    if not paths:
        return "(no .py modules found)"
    return "\n".join(paths)


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
                "Practice artifacts: sessions/, state/notes/, state/current.yaml, thread-archive/, chronicle/surface.md, box/intake/."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "File path relative to practice dir, e.g. 'state/notes/navigator-2026.md', 'sessions/2026-07-09.md'",
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
                "Use for surgical edits to practice notes, session files, or state/notes."
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
                "applies the edit, and writes the result. FREE — no API tokens spent. "
                "Prefer patch_practice_file for small Live-state / section updates. "
                "If this tool fails, use patch_practice_file or write_practice_file — "
                "never treat a chat paste as a durable write."
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
                    "directory": {"type": "string", "description": "Limit to any subdirectory path, e.g. 'state/notes', 'sessions', or '' for all"},
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
                    "directory": {"type": "string", "description": "Directory path: '' (practice root), 'sessions', 'state/notes', 'state', 'chronicle'"},
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
                "Allowed: pwd; ls (-l/-a/-1); head/tail (-n N, max 200); rg (-n/-i/-l/-c/--files/--glob/"
                "--type, regex patterns OK; rg searches recursively already, and -r means --replace, so "
                "never pass it); read-only git (status/diff/log/show/branch/rev-parse — log accepts "
                "-N, --max-count, --name-only, --stat); python -m py_compile. "
                "For module orientation prefer inspect_turtleos_module. "
                "Cannot commit, edit files, restart services, pipe commands, or run arbitrary Python."
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
            "name": "inspect_turtleos_module",
            "description": (
                "Architecture-survey helper for a turtleOS source file. Returns path, size, "
                "import lines, and class/def signatures with line numbers, plus a numbered "
                "window of the source that can start anywhere in the file. Use the signature "
                "line numbers to place the window — this is how to read the middle of a file. "
                "Prefer this over shell head/rg when orienting on a module. "
                "Read-only; path must stay under ~/turtleos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Path relative to ~/turtleos, e.g. dialogue_runtime.py or docs/live-runtime.md",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line of the window, 1-indexed (default 1).",
                    },
                    "line_count": {
                        "type": "integer",
                        "description": (
                            "How many lines to return from start_line (max 400, default 40). "
                            "Set 0 to skip the source window and return only the outline."
                        ),
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "exa_search",
            "description": (
                "Search the web with Exa (semantic search built for agents). Use during "
                "craft and architecture work to find documentation, package references, "
                "prior art, or current information. Returns highlighted excerpts rather "
                "than full pages. If the key is missing, say the search was unavailable — "
                "never present a guess as a search result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Results to return (1–10, default 5).",
                    },
                    "search_type": {
                        "type": "string",
                        "description": (
                            "auto (default), fast, or instant. Start with auto; "
                            "drop to fast only if latency hurts the conversation."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_turtleos_modules",
            "description": (
                "List .py modules under ~/turtleos (optionally a subdirectory). "
                "One path per line — the clean module list craft surveys need when ls mixes directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Subdirectory relative to ~/turtleos, or '' for the repo root only (non-recursive). Use '.' for recursive from root.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offer_river_act",
            "description": (
                "Ask River to post one contextual act button after this reply (split-bot). "
                "Use when a platform act would help and the practitioner should confirm — "
                "checkpoint to save progress, or save to library for a URL worth keeping. "
                "Does not execute the act. Do not invent commands outside checkpoint/save. "
                "Mentioning `!checkpoint` in prose does NOT spawn buttons — use this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Allowlisted act: 'checkpoint' or 'save' (library distill).",
                    },
                    "url": {
                        "type": "string",
                        "description": "Required for action=save — the http(s) URL to distill.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short why (logged; optional).",
                    },
                },
                "required": ["action"],
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
    {
        "type": "function",
        "function": {
            "name": "survey_space",
            "description": (
                "List registered turtleOS channels with type, attunement, mage key, "
                "and member count. Use to orient before answering questions about "
                "which channels exist and what they are for. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "include_quiet": {
                        "type": "boolean",
                        "description": (
                            "Accepted for compatibility. Channel quietness is not "
                            "in the registry; use survey_eddies for eddy recency."
                        ),
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "survey_eddies",
            "description": (
                "List known eddies with status (active/quiet/cooled), age, message "
                "count, and parent channel. Use to find where conversations are "
                "happening and which eddies are stale. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": (
                            "Filter to this eddy id or parent channel name. "
                            "Omit for all eddies."
                        ),
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "quiet", "cooled", "all"],
                        "description": "Filter by lifecycle status. Default all.",
                    },
                },
            },
        },
    },
]


# ─── Tool Scoping ────────────────────────────────────────────────
#
# `TOS_TOOLS` was a flat list handed to every surface, which means a capability
# added for one room arrives in all of them. That is fine for reading a practice
# file and wrong for reaching the open internet: the operator asked for web
# search *in the craft channel*, and a family conversation about a hard evening
# should not be able to trigger one. Same lesson as the seneschal register gate
# of 2026-08-06 — the question nobody asked there was *what kind of
# conversation is this*, and this is the same question one layer up.
#
# Default is unscoped. A tool named here is offered only in the attunements
# listed, and because scoping decides what the model is *shown*, a tool it was
# never offered cannot be called.

_TOOL_SCOPES: dict[str, frozenset[str]] = {
    "exa_search": frozenset({"craft"}),
}


def tool_scopes(name: str) -> frozenset[str] | None:
    """Attunements a tool is offered in, or None when it is unscoped."""
    return _TOOL_SCOPES.get(name)


def tools_for_attunement(attunement: str) -> list[dict]:
    allowed = []
    for tool in TOS_TOOLS:
        name = (tool.get("function") or {}).get("name") or tool.get("name") or ""
        scopes = _TOOL_SCOPES.get(name)
        if scopes is None or attunement in scopes:
            allowed.append(tool)
    return allowed


def tools_for_channel(channel_id=None) -> list[dict]:
    """The tool set a given surface may see.

    Pass the channel or eddy thread id — `get_effective_attunement` resolves a
    thread to its parent, so an eddy under `#craft-turtle` gets the craft set.
    Falls back to the unscoped-only set when the attunement cannot be resolved,
    which fails closed: a scoped capability stays absent rather than leaking.
    """
    if channel_id is None:
        return tools_for_attunement("")
    try:
        from mage import get_effective_attunement

        return tools_for_attunement(get_effective_attunement(channel_id))
    except Exception:
        return tools_for_attunement("")


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

    if name == "inspect_turtleos_module":
        return _inspect_turtleos_module(
            str(arguments.get("filename") or ""),
            head_lines=arguments.get("head_lines", 40),
            start_line=arguments.get("start_line", 1),
            line_count=arguments.get("line_count"),
        )

    if name == "exa_search":
        return _exa_search(
            str(arguments.get("query") or ""),
            num_results=arguments.get("num_results", 5),
            search_type=str(arguments.get("search_type") or "auto"),
        )

    if name == "list_turtleos_modules":
        return _list_turtleos_modules(str(arguments.get("directory") or ""))

    if name == "offer_river_act":
        from act_offer_signal import propose_act_offer_from_tool

        return propose_act_offer_from_tool(
            str(arguments.get("action") or ""),
            url=arguments.get("url"),
            reason=str(arguments.get("reason") or ""),
        )

    if name == "list_turtle_capabilities":
        kind = (arguments.get("kind") or "").strip() or None
        return format_capability_index(kind)

    if name == "read_turtle_capability":
        kind = (arguments.get("kind") or "").strip()
        capability_name = (arguments.get("name") or "").strip()
        return read_capability(kind, capability_name)

    if name == "survey_space":
        from space_survey import survey_space

        rows = survey_space(
            get_registry(),
            include_quiet=bool(arguments.get("include_quiet")),
        )
        if not rows:
            return "No registered channels."
        return json.dumps(rows, indent=2)

    if name == "survey_eddies":
        from space_survey import survey_eddies

        rows = survey_eddies(
            channel_id=arguments.get("channel_id") or None,
            status=arguments.get("status") or "all",
        )
        if not rows:
            return "No eddies match."
        return json.dumps(rows, indent=2)

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
        # Restored 2026-08-14, later the same day it was removed. A third-party
        # network call flakes in a way a local read does not, so a retry is worth
        # more here than anywhere on this list — but while the tool loop ran on the
        # event loop, two attempts turned one bounded 8-second stall into sixteen
        # seconds of a Turtle that answered nobody, and one lost turn was the
        # cheaper failure. Tool execution now runs on a daemon thread
        # (`offload.run_blocking`), so the worst case costs *this* turn's latency
        # and no one else's. The condition the removal named has been met.
        "exa_search",
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


def _delegate_num_ctx(content_chars: int) -> int:
    """Size context for a whole-file rewrite: input + output + prompt overhead.

    Hard-coding 8192 left mid-size surfaces (~10k chars) with no room to
    return the edited file. Cap at 32k so a huge file fails loudly rather than
    thrashing the Mini.
    """
    # ~3 chars/token for mixed markdown; leave headroom for the instruction
    # and a full rewritten body in the same window.
    estimated = (content_chars // 3) + 2048
    return min(32768, max(8192, estimated * 2))


def _delegate_edit_sync(path, filename, content, instruction):
    """Delegate a file edit to a fast local model (synchronous).

    Uses keep_alive to prevent cold-start latency on subsequent calls.

    ``think: False`` is load-bearing for qwen3.5: with thinking left on, the
    model can return empty ``content`` and put the whole rewrite in
    ``thinking`` — measured 2026-08-11 (craft Live-state updates). That
    failure mode looked like "tools are down" while Turtle pasted the intended
    write into chat and called it preserved. Chat paste is not a write.
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

    num_ctx = _delegate_num_ctx(len(content))
    payload = json.dumps({
        "model": EDIT_DELEGATE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "temperature": 0.1},
        "keep_alive": "30m",
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        # Deadline after the call starts — this path still bypasses
        # ``_InferenceGate`` (sync tool inside an async turn). Same class as
        # the pre-08-08 theme/register gates; wire through the gate when a
        # sync-safe entry exists. Until then: think:False is the empty-content fix.
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            message = data.get("message", {}) or {}
            result = (message.get("content") or "").strip()
            thinking = (message.get("thinking") or "").strip()

        if not result or len(result) < 10:
            hint = (
                "Use patch_practice_file or write_practice_file instead; "
                "do not paste the intended edit into chat as if the file were updated."
            )
            if thinking and not result:
                return (
                    f"Delegate edit failed \u2014 local model returned empty content "
                    f"(thinking consumed the reply). {hint}"
                )
            return f"Delegate edit failed \u2014 local model returned empty/short result. {hint}"

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
        return (
            f"Delegate edit failed: {type(e).__name__}: {e}. "
            f"Use patch_practice_file or write_practice_file instead; "
            f"do not paste the intended edit into chat as if the file were updated."
        )


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
