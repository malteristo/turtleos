"""Typed tool results for turtleOS harness reliability."""

import json
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


def classify_tool_text(tool: str, text: str) -> dict:
    """Convert legacy string tool output into a typed result."""
    raw = text or ""
    lower = raw.lower()
    summary = raw.strip() or "(empty tool result)"

    if tool == "list_turtle_capabilities":
        if summary.startswith("- `") or summary.startswith("No Turtle skills"):
            return make_tool_result(tool=tool, ok=True, kind=SUCCESS, summary=summary, retryable=False)

    if tool == "read_turtle_capability":
        if summary.startswith("[skill:") or summary.startswith("[procedure:"):
            return make_tool_result(tool=tool, ok=True, kind=SUCCESS, summary=summary, retryable=False)

    if "shell command blocked" in lower or "not allowed" in lower or "cannot read" in lower or "cannot write" in lower or "cannot patch" in lower or "cannot append" in lower or "cannot edit" in lower:
        return make_tool_result(tool=tool, ok=False, kind=BLOCKED, summary=summary, retryable=False)

    if "unknown tool" in lower:
        return make_tool_result(tool=tool, ok=False, kind=USER_ERROR, summary=summary, retryable=False)

    if "not found" in lower or "directory not found" in lower or " is empty" in lower or "old_text not found" in lower:
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
    if any(marker in lower for marker in transient_markers):
        return make_tool_result(tool=tool, ok=False, kind=TRANSIENT, summary=summary, retryable=True)

    if "failed" in lower or "error" in lower or "exception" in lower:
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
        with (runtime / "tool-actions.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"tool result log failed: {type(e).__name__}: {e}")
