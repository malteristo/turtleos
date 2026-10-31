"""What a press on the calls shows.

The card in the channel names the act. This text is that list again, for the
person who pressed. A command sits under the line only where the card hides
it. An edit names the path, not the paragraphs. The tool's name stays out.
Submitting the window posts nothing.
"""

from __future__ import annotations

_LIMIT = 1900
_COMMAND_CHARS = 240
QUIET = "-# Submit closes this. Nothing is posted."
CALLS_ID = "trace:calls"
CALLS_LABEL = "What was opened"


def calls_components() -> list:
    """The button on Spirit's card. The press is heard by Spirit, not by Turtle."""
    return [{
        "type": 1,
        "components": [{
            "type": 2,
            "style": 2,
            "label": CALLS_LABEL,
            "custom_id": CALLS_ID,
        }],
    }]


def calls_for_message(events: list, message_id) -> list | None:
    """The call this button inspects, or the turn that followed an older card.

    A dressed card names one call (``tool`` is its index) on the turn already
    written above it. An older card has no index, and the turn follows it.
    None when that turn is not written yet.
    """
    if message_id is None:
        return None
    want = str(message_id)
    for index, event in enumerate(events):
        if not isinstance(event, dict) or event.get("kind") != "trace":
            continue
        if str(event.get("message") or "") != want:
            continue
        which = event.get("tool")
        if isinstance(which, int):
            for earlier in reversed(events[:index]):
                if isinstance(earlier, dict) and earlier.get("kind") == "turn":
                    tools = earlier.get("tools")
                    if not isinstance(tools, list) or which < 0 or which >= len(tools):
                        return []
                    return [tools[which]]
            return None
        for later in events[index + 1 :]:
            if isinstance(later, dict) and later.get("kind") == "turn":
                tools = later.get("tools")
                return tools if isinstance(tools, list) else []
        return None
    return None


def reveal_calls(tools: list, link_for=None) -> str:
    """The act in the card's words. The command, only where that line hides it.

    A file body — the result, or the old and new text of an edit — stays in
    the record. A link is added only when ``link_for`` returns one. A repeat
    collapses when the act and the command are the same. If the window cannot
    hold every line, the first act and the last stay.
    """
    rows: list[tuple[str, str]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "call")
        raw = tool.get("arguments")
        args = raw if isinstance(raw, dict) else {}
        summary = str(tool.get("summary") or "")
        act = _act(name, args, summary)
        path = _path(args)
        url = _link(path, link_for)
        if url and path and f"`{path}`" in act:
            act = act.replace(f"`{path}`", f"[{path}]({url})", 1)
        elif url and path:
            act = f"{act}\n-# [Open {path}]({url})"
        detail = _detail(args, act)
        refusal = _refusal(summary)
        if refusal and refusal not in act and refusal not in detail:
            detail = f"{detail}\n-# refused: {refusal}".strip()
        rows.append((act, detail))
    blocks = [_block(act, detail) for act, detail in _collapse(rows)]
    if not blocks:
        return f"{QUIET}\n\nNothing was opened."
    return _fit(blocks)


def _act(name: str, args: dict, summary: str) -> str:
    try:
        from turn_trace import describe_tool

        text = describe_tool(name, args, summary).text.strip()
        if text:
            return text
    except Exception:
        pass
    return name


def _path(args: dict) -> str:
    for key in ("path", "filename", "file"):
        value = str(args.get(key) or "").strip()
        if value and "\n" not in value and len(value) < 240:
            return value
    return ""


def _link(path: str, link_for) -> str:
    if not path or link_for is None:
        return ""
    try:
        url = str(link_for(path) or "").strip()
    except Exception:
        return ""
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def _detail(args: dict, act: str) -> str:
    """The command, or a line range. Never the tool's name, and never the file."""
    command = " ".join(str(args.get("command") or "").split())
    if command and command not in act:
        return f"-# {_clip(command, _COMMAND_CHARS)}"
    start = _whole(args.get("start_line"))
    count = _whole(args.get("max_lines"))
    if start is None:
        return ""
    if count is None or count <= 1:
        line = f"line {start}" if count == 1 else f"from line {start}"
    else:
        line = f"lines {start}-{start + count - 1}"
    if line in act:
        return ""
    return f"-# {line}"


def _whole(value) -> int | None:
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return (cut or text[: limit - 1]).rstrip() + "…"


def _collapse(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The same act and the same command, however many times, is one line."""
    counts: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []
    for row in rows:
        if row in counts:
            counts[row] += 1
            continue
        counts[row] = 1
        order.append(row)
    out = []
    for act, detail in order:
        count = counts[(act, detail)]
        if count > 1:
            act = f"{act} × {count}"
        out.append((act, detail))
    return out


def _block(act: str, detail: str) -> str:
    return f"{act}\n{detail}" if detail else act


def _fit(blocks: list[str]) -> str:
    """Every act, or the first and the last. Never a cut through a line."""

    def render(parts: list[str]) -> str:
        return QUIET + "\n\n" + "\n\n".join(parts)

    whole = render(blocks)
    if len(whole) <= _LIMIT:
        return whole
    best = ""
    count = len(blocks)
    for tail in range(1, count):
        for head in range(1, count - tail + 1):
            skipped = count - head - tail
            parts = list(blocks[:head])
            if skipped:
                parts.append(f"-# {skipped} more, in the record")
            parts.extend(blocks[-tail:])
            text = render(parts)
            if len(text) <= _LIMIT and len(text) > len(best):
                best = text
    if best:
        return best
    kept = [blocks[0]] + ([blocks[-1]] if count > 1 else [])
    text = render(kept)
    if len(text) <= _LIMIT:
        return text
    cut = text[: _LIMIT - 1]
    if "\n" in cut:
        cut = cut.rsplit("\n", 1)[0]
    return cut.rstrip() + "\n…"


def _refusal(summary: str) -> str:
    first = summary.strip().splitlines()[0] if summary.strip() else ""
    if "blocked" not in first.lower():
        return ""
    if ":" in first:
        first = first.split(":", 1)[-1].strip()
    return first[:200]
