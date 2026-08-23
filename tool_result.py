"""Typed tool results for turtleOS harness reliability."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from mage import get_runtime_dir


SUCCESS = "success"
USER_ERROR = "user_error"
NOT_FOUND = "not_found"
TRANSIENT = "transient"
BLOCKED = "blocked"
SYSTEM_ERROR = "system_error"


def make_tool_result(
    *,
    tool: str,
    ok: bool,
    kind: str,
    summary: str,
    detail: str = "",
    retryable: bool = False,
    action_taken: str | None = None,
) -> dict:
    return {
        "ok": ok,
        "kind": kind,
        "tool": tool,
        "summary": summary,
        "detail": detail,
        "retryable": retryable,
        "action_taken": action_taken,
    }


_LISTING_TOOLS = frozenset({
    "list_turtle_capabilities",
    "list_turtleos_modules",
    "list_practice_files",
})

_LISTING_FAILURE_OPENERS = (
    "cannot ",
    "unknown ",
    "directory not found",
    "path escapes",
    "not a directory:",
    "directory must be relative",
    "no query provided",
)


def classify_tool_text(tool: str, text: str) -> dict:
    """Convert legacy string tool output into a typed result.

    **Classify the status line, never the payload.** These markers used to be
    matched against the whole tool result, which meant a *successful* read was
    graded by its own contents: ``read_practice_file(CLAUDE.md)`` came back
    ``transient`` and retryable because the file says "connection" somewhere,
    ``list_practice_files(proposals)`` came back ``system_error`` because a
    filename in the listing says "error", and every ``inspect_turtleos_module``
    call on a module with exception handling was a failure by construction.
    Measured 2026-08-14 against the live ledger (10,920 recorded tool actions):
    of 76 results marked failed, **35 were successful reads** — and because
    ``read_practice_file`` and friends carry two attempts, the retryable ones
    ran the read twice before handing the model a lie about it. That is the
    ``tools are failing`` report of 2026-08-11 and a good share of the tool
    rounds craft-turtle was spending before it ran out of them.

    Every failure these tools emit is a single sentence and always the first
    line — ``Cannot read X``, ``Shell command blocked: …``, ``Section 'X' not
    found in Y``, ``Unknown tool: X``, ``Delegate edit failed — …``. Every
    success opens with a header the payload cannot forge: ``[filename]``,
    ``# module.py``, ``$ command``, ``Found N match(es)``, ``Done. …``, a path.
    So the first line is exactly the status, and the rest is evidence.
    """
    raw = text or ""
    summary = raw.strip() or "(empty tool result)"
    # The status line. Content below it is evidence, not a verdict.
    status = summary.split("\n", 1)[0].lower()

    # …except for the listing tools, whose *first* line is payload too — a bare
    # run of capability blurbs, module paths or filenames with no header above
    # it. They announce trouble by opening with it, and nothing else they emit
    # is a verdict. The two per-tool exemptions this replaces were the same
    # observation made twice, for two of the three tools that needed it.
    if tool in _LISTING_TOOLS and not status.startswith(_LISTING_FAILURE_OPENERS):
        return make_tool_result(tool=tool, ok=True, kind=SUCCESS, summary=summary, retryable=False)

    if (
        "shell command blocked" in status
        or "not allowed" in status
        or "cannot read" in status
        or "cannot write" in status
        or "cannot patch" in status
        or "cannot append" in status
        or "cannot edit" in status
    ):
        return make_tool_result(tool=tool, ok=False, kind=BLOCKED, summary=summary, retryable=False)

    if "unknown tool" in status or "unknown capability kind" in status:
        return make_tool_result(tool=tool, ok=False, kind=USER_ERROR, summary=summary, retryable=False)

    # `_list_turtleos_modules` refuses a bad directory in sentences that matched
    # no marker at all, so an escaped path read as a successful listing.
    if (
        "path escapes" in status
        or status.startswith("not a directory:")
        or status.startswith("directory must be relative")
    ):
        return make_tool_result(tool=tool, ok=False, kind=USER_ERROR, summary=summary, retryable=False)

    if (
        "not found" in status
        or "directory not found" in status
        or " is empty" in status
        or "old_text not found" in status
    ):
        return make_tool_result(tool=tool, ok=False, kind=NOT_FOUND, summary=summary, retryable=False)

    transient_markers = (
        "timeout",
        "timed out",
        "connection",
        "temporarily",
        "try again",
        "unreachable",
        "readtimeout",
        "httperror",
        "urlerror",
    )
    if any(marker in status for marker in transient_markers):
        return make_tool_result(tool=tool, ok=False, kind=TRANSIENT, summary=summary, retryable=True)

    if "failed" in status or "error" in status or "exception" in status:
        return make_tool_result(tool=tool, ok=False, kind=SYSTEM_ERROR, summary=summary, retryable=False)

    return make_tool_result(tool=tool, ok=True, kind=SUCCESS, summary=summary, retryable=False)


def format_tool_result(result: dict) -> str:
    """Return model-readable text while preserving typed failure semantics."""
    if result.get("ok"):
        return result.get("summary", "")

    parts = [
        f"ToolResult[{result.get('kind', SYSTEM_ERROR)}] {result.get('tool', 'unknown')}: {result.get('summary', '')}"
    ]
    if result.get("detail"):
        parts.append(str(result["detail"]))
    if result.get("action_taken"):
        parts.append(f"Action taken: {result['action_taken']}")
    if result.get("retryable"):
        parts.append("Retryable: yes")
    return "\n".join(p for p in parts if p)


_LOG_LOCK = threading.Lock()


def log_tool_result(result: dict, arguments: dict | None = None, attempts: int = 1) -> None:
    try:
        runtime = Path(get_runtime_dir()).expanduser()
        runtime.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": result.get("tool"),
            "kind": result.get("kind"),
            "ok": result.get("ok"),
            "retryable": result.get("retryable"),
            "attempts": attempts,
            "arguments": arguments or {},
            "summary": (result.get("summary") or "")[:1000],
            "action_taken": result.get("action_taken"),
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        # Serialised because tool execution moved off the event loop (2026-08-14),
        # so two channels' tools can now run at the same time — which they never
        # could before. A record carrying a large `arguments` blob exceeds the write
        # buffer and gets split into several syscalls; two of those interleaving
        # produce a line that no longer parses as JSON. Cheap lock, added with the
        # change that made it necessary rather than after the first unreadable line.
        with _LOG_LOCK:
            with (runtime / "tool-actions.jsonl").open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        print(f"tool result log failed: {type(e).__name__}: {e}")
