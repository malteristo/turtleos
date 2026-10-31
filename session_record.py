"""One magic session, inspectable after the fact.

A turn appends one line: what the practitioner said, the reply that was posted,
and the tools that ran (name, arguments, a short result). A later agent reads
that file. ``render_key_ground`` is the text a practice key is walked from:
the practitioner's words and the tool calls.

The model's reasoning is not a field here. A caller that passes one has it
dropped, and a test plants a string that must not survive. This record is the
practitioner's own session. It is not a capture of a provider's chain of
thought, and it is not material for training a model.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUMMARY_MAX = 1000
ARGS_MAX = 2000

# Never written. Visible reply text is kept even if it happens to contain one
# of these words; only a separate field under the name is dropped.
_DROPPED_FIELDS = frozenset({
    "thinking",
    "reasoning",
    "redacted_thinking",
    "chain_of_thought",
})

_LOCK = threading.Lock()


def session_path(practice_dir: str | Path, eddy: int | str) -> Path:
    return Path(practice_dir) / "state" / "sessions" / f"{eddy}.jsonl"


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _arguments(args: Any) -> Any:
    if not isinstance(args, dict):
        return {}
    raw = json.dumps(args, ensure_ascii=False, default=str)
    if len(raw) <= ARGS_MAX:
        return args
    return {"_truncated": True, "preview": raw[:ARGS_MAX] + "…"}


def _tool_row(tool: dict) -> dict:
    result = tool.get("result")
    if not isinstance(result, str):
        result = "" if result is None else str(result)
    return {
        "name": str(tool.get("name") or ""),
        "arguments": _arguments(tool.get("args")),
        "summary": _cap(result, SUMMARY_MAX),
    }


def turn_record(
    *,
    eddy: int | str,
    practitioner: str,
    reply: str,
    tools: list | None = None,
    model: str = "",
    usage: dict | None = None,
    recorded_at: datetime | None = None,
    **extra: Any,
) -> dict:
    """One turn. Unknown fields are ignored; a reasoning field is dropped."""
    del extra  # a reasoning trace passed by name never reaches the line
    when = recorded_at or datetime.now(timezone.utc)
    counts = {
        key: value
        for key, value in (usage or {}).items()
        if key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "calls")
        and isinstance(value, int)
    }
    record = {
        "ts": when.isoformat(),
        "eddy": str(eddy),
        "kind": "turn",
        "model": model,
        "practitioner": practitioner,
        "reply": reply,
        "tools": [_tool_row(t) for t in (tools or []) if isinstance(t, dict)],
        "usage": counts,
    }
    leaked = _DROPPED_FIELDS.intersection(record)
    if leaked:
        raise RuntimeError(f"session record tried to write {sorted(leaked)}")
    return record


def append_turn(practice_dir: str | Path, eddy: int | str, **fields: Any) -> Path | None:
    """Append one turn. No-op when the practice root is not a directory."""
    root = Path(practice_dir)
    if not root.is_dir():
        return None
    # Fixed keys only. A reasoning field passed in ``fields`` is discarded by
    # ``turn_record`` and never reaches this line. The test plants one.
    line = json.dumps(turn_record(eddy=eddy, **fields), ensure_ascii=False) + "\n"
    path = session_path(root, eddy)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return path


def append_event(
    practice_dir: str | Path,
    eddy: int | str,
    *,
    kind: str,
    actor: str,
    text: str,
    briefing: str = "",
    message: str = "",
    tool: int | None = None,
    recorded_at: datetime | None = None,
) -> Path | None:
    """One thing that happened in the chat and was not a model turn.

    Greeting, a join, a trace, a release. The same file as the turns, in order.
    A reasoning field is not a parameter here, so it cannot be written.
    """
    root = Path(practice_dir)
    if not root.is_dir():
        return None
    when = recorded_at or datetime.now(timezone.utc)
    record = {
        "ts": when.isoformat(),
        "eddy": str(eddy),
        "kind": kind,
        "actor": actor,
        "text": text,
    }
    if briefing:
        record["briefing"] = briefing
    if message:
        record["message"] = str(message)
    if tool is not None:
        record["tool"] = int(tool)
    leaked = _DROPPED_FIELDS.intersection(record)
    if leaked:
        raise RuntimeError(f"session record tried to write {sorted(leaked)}")
    path = session_path(root, eddy)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return path


def is_greeted(practice_dir: str | Path, eddy: int | str) -> bool:
    """True once a greeting event was written.

    An empty file, a turn-only file, and a missing file were not opened by this
    check. Their lack of a release line does not make them an open session.
    """
    return any(turn.get("kind") == "greeting" for turn in read_turns(practice_dir, eddy))


def is_released(practice_dir: str | Path, eddy: int | str) -> bool:
    """True once a release event was written. An empty or turn-only file has none."""
    return any(turn.get("kind") == "release" for turn in read_turns(practice_dir, eddy))


def read_turns(practice_dir: str | Path, eddy: int | str) -> list[dict]:
    path = session_path(practice_dir, eddy)
    if not path.is_file():
        return []
    turns = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            turns.append(json.loads(raw))
    return turns


def render_session(practice_dir: str | Path, eddy: int | str) -> str:
    """The whole session, for a person reading it back."""
    turns = read_turns(practice_dir, eddy)
    lines = [f"# Session {eddy}", ""]
    if not turns:
        lines.append("No turns recorded.")
        return "\n".join(lines)
    lines.append(f"{len(turns)} turn(s). Last model: {turns[-1].get('model') or 'unknown'}.")
    lines.append("")
    for index, turn in enumerate(turns, start=1):
        lines.append(f"## {index} · {turn.get('ts', '')}")
        kind = turn.get("kind") or "turn"
        if kind != "turn":
            lines.append(f"**{kind}** ({turn.get('actor', '')}): {turn.get('text', '')}")
            lines.append("")
            continue
        lines.append(f"**Practitioner:** {turn.get('practitioner', '')}")
        lines.append("")
        tools = turn.get("tools") or []
        if tools:
            lines.append("**Tools:**")
            for tool in tools:
                lines.append(f"- `{tool.get('name')}` {json.dumps(tool.get('arguments'), ensure_ascii=False)}")
                summary = (tool.get("summary") or "").strip()
                if summary:
                    lines.append(f"  → {summary}")
            lines.append("")
        lines.append(f"**Reply:** {turn.get('reply', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_key_ground(practice_dir: str | Path, eddy: int | str) -> str:
    """What a practice key is walked from.

    The practitioner's words and the tool calls. The replies stay in the
    session file for inspection and are not repeated here, so a key is a
    reading of the practice rather than a compression of a model's answers.
    """
    turns = read_turns(practice_dir, eddy)
    lines = [
        f"# Key ground · session {eddy}",
        "",
        "The practitioner's words and the tools that ran. Model replies are not included.",
        "",
    ]
    if not turns:
        lines.append("No turns recorded.")
        return "\n".join(lines) + "\n"
    for index, turn in enumerate(turns, start=1):
        if turn.get("kind") not in (None, "turn"):
            continue
        lines.append(f"## {index}")
        lines.append(turn.get("practitioner", ""))
        for tool in turn.get("tools") or []:
            lines.append(
                f"- tool `{tool.get('name')}` {json.dumps(tool.get('arguments'), ensure_ascii=False)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
