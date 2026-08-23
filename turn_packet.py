"""The context packet a turn used — practitioner-readable file, and ``!context``.

TURTLE_SPEC §3.2 line 1: the inject a turn used MUST persist as a file. That file
is not ``state/current.yaml`` (the Continuity Engine's debounce write of composed
coordinates). It is the named blocks the shell actually prepended, plus the tools
and files that turn loaded.

``!context`` renders that file. It names only injection slots (loaded or not).
It never names the alive layer, ``confirmed_by``, or another member's unconfirmed
checkpoint — those are not injection slots, and listing them as "not loaded"
would teach the names this surface exists to keep off a turn.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# Closed catalog of shell-injectable blocks. A slot missing from ``injected``
# or whose value is blank is "not loaded this turn". Anything not in this
# catalog is dropped on persist — it is not an injection slot.
INJECT_SLOTS: tuple[tuple[str, str], ...] = (
    ("practice_substrate", "Practice substrate"),
    ("runtime_environment", "Runtime environment"),
    ("home_working_plan", "Home working plan"),
    ("absorbed_threads", "Absorbed threads"),
    ("url_content", "URL content"),
    ("attachments", "Attachments"),
    ("forwarded_messages", "Forwarded messages"),
    ("discord_context", "Discord context"),
)

SLOT_KEYS: frozenset[str] = frozenset(key for key, _ in INJECT_SLOTS)
SLOT_LABELS: dict[str, str] = dict(INJECT_SLOTS)

# Tools whose args name a file the model actually read this turn.
_READ_FILE_TOOLS = frozenset(
    {
        "read_practice_file",
        "read_turtle_capability",
        "inspect_turtleos_module",
    }
)

_NO_PACKET = (
    "No turn has been recorded in this eddy yet. "
    "Speak once, then `!context` will show what that turn injected."
)


def packet_path(practice_dir: str | Path, channel_id: int | str) -> Path:
    return Path(practice_dir) / "state" / "packets" / f"{channel_id}.md"


def persist_turn_packet(
    practice_dir: str | Path,
    channel_id: int | str,
    *,
    injected: dict[str, str],
    tools_executed: Iterable[dict[str, Any]] | None = None,
    recorded_at: datetime | None = None,
    considered: Iterable[dict[str, Any]] | None = None,
) -> Path | None:
    """Write the packet this turn used. No-op if the practice root is not a directory.

    Refuses to mkdir a bogus path (trunk tests point ``get_pd`` at a nonexistent
    sentinel). Unknown inject keys are dropped, not written — they are not slots.
    """
    root = Path(practice_dir)
    if not root.is_dir():
        return None
    body = build_packet_markdown(
        channel_id,
        injected=injected,
        tools_executed=list(tools_executed or []),
        recorded_at=recorded_at,
        considered=list(considered or []),
    )
    path = packet_path(root, channel_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def read_turn_packet(practice_dir: str | Path, channel_id: int | str) -> str | None:
    path = packet_path(practice_dir, channel_id)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def render_context_command(practice_dir: str | Path, channel_id: int | str) -> str:
    """What ``!context`` posts — the persisted packet, or an honest empty."""
    body = read_turn_packet(practice_dir, channel_id)
    return body if body else _NO_PACKET


def build_packet_markdown(
    channel_id: int | str,
    *,
    injected: dict[str, str],
    tools_executed: list[dict[str, Any]] | None = None,
    recorded_at: datetime | None = None,
    considered: list[dict[str, Any]] | None = None,
) -> str:
    """Compose the practitioner-readable packet. Unknown keys are ignored."""
    clean = {
        key: (injected.get(key) or "").strip()
        for key, _ in INJECT_SLOTS
    }
    when = (recorded_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    tools = list(tools_executed or [])
    lines = [
        "# Context this turn",
        "",
        f"Recorded: {when}",
        f"Eddy: `{channel_id}`",
        "",
        "## Injected",
        "",
    ]
    loaded = [(key, text) for key, text in clean.items() if text]
    if loaded:
        for key, text in loaded:
            lines.append(f"### {SLOT_LABELS[key]}")
            lines.append("")
            lines.append(text)
            lines.append("")
    else:
        lines.append("None of the injection slots carried content this turn.")
        lines.append("")

    lines.extend(_considered_section(considered or []))

    lines.append("## Tools this turn")
    lines.append("")
    names = tools_called(tools)
    if names:
        for name in names:
            lines.append(f"- `{name}`")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Files loaded")
    lines.append("")
    files = files_loaded(tools)
    if files:
        for name in files:
            lines.append(f"- `{name}`")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Not loaded this turn")
    lines.append("")
    missing = [SLOT_LABELS[key] for key, text in clean.items() if not text]
    if missing:
        for label in missing:
            lines.append(f"- {label}")
    else:
        lines.append("None of the injection slots were empty.")
    lines.append("")
    return "\n".join(lines)


def _considered_section(considered: list[dict[str, Any]]) -> list[str]:
    """What room memory could have carried, and what it did.

    The rest of this file records the road taken. This records the road that
    was on offer, because those are different measurements and only one of them
    can be reconstructed later. With five carried out of five available the
    section is trivia; the moment selection is a choice, it is the only way to
    tell a good retrieval from a lucky one — and it is also the practitioner's
    answer to "what else did you have and not use?".
    """
    if not considered:
        return []
    lines = ["## Room memory considered", ""]
    carried = sum(1 for row in considered if row.get("selected"))
    lines.append(f"{carried} of {len(considered)} notes in the window reached this turn.")
    lines.append("")
    for row in considered:
        mark = "x" if row.get("selected") else " "
        when = str(row.get("when") or "")[:10]
        title = str(row.get("title") or "a conversation")
        score = row.get("score")
        suffix = f" · matched {score}" if isinstance(score, int) else ""
        lines.append(f"- [{mark}] {when} {title}{suffix}")
    lines.append("")
    return lines


def tools_called(tools_executed: Iterable[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in tools_executed:
        name = str(item.get("name") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def files_loaded(tools_executed: Iterable[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in tools_executed:
        name = str(item.get("name") or "").strip()
        if name not in _READ_FILE_TOOLS:
            continue
        args = item.get("args") or {}
        filename = (
            args.get("filename")
            or args.get("path")
            or args.get("name")
            or args.get("module")
        )
        if filename:
            text = str(filename).strip()
            if text and text not in seen:
                seen.append(text)
    return seen
