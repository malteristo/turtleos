"""Nightly reader for discord.log and river.log.

The report already watches write-path ratios and record gaps. Until 2026-09-13
it never opened the bot logs, so four live defects spent their lives in a
caught exception nobody read. Recurrence across threads is the signal; volume
on one evening is weather. A class absent from the previous report is **new**.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

WINDOW_HOURS = 24
LOG_NAMES = ("discord.log", "river.log")
DISPLAY_CAP = 15

TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*")
EXC = re.compile(r"^([A-Za-z][^:]{0,80} failed): ([A-Za-z][A-Za-z0-9]+):")
SKIP = re.compile(r"Contextual offer skip \(([^)]+)\)")
SKIP_CHANNEL = re.compile(r" in #(.+)$")
DIALOGUE_ERR = re.compile(r"Dialogue error \(([^)]+)\):\s*(.*)$")
DIALOGUE_UP = re.compile(r"Dialogue gave up")
REFLECT_FAIL = re.compile(r"Reflection loop failed for (\d+): ([A-Za-z][A-Za-z0-9]+):")
REFLECT_EMPTY = re.compile(r"Reflection loop empty for (\d+)")
# `state._note_zombie_access` prints to stderr with no timestamp. It fired 18
# times between 2026-09-16 and 09-21 naming the exact defect that broke craft
# intake dereference, and this reader dropped every one of them — first because
# nothing classified the line, then because a line with no timestamp never
# entered the window. A detector this reader cannot see is a detector nobody has.
WRONG_CLIENT = re.compile(r"^WRONG-CLIENT: the River process (constructed|asked)")

# `wrong_client:asked` is the *refused* path (`state.get_channel` returning None
# in River by design, after every checkpoint offer) — deliberate, harmless, and
# documented on that function. It stays visible so the decision stays visible;
# `wrong_client:constructed` is the one that means a zombie client exists.
WEATHER = frozenset({"skip:pre_poll", "wrong_client:asked"})


def default_log_dir(repo: Path) -> Path:
    return repo / "logs"


def default_log_paths(repo: Path) -> list[Path]:
    root = default_log_dir(repo)
    return [root / name for name in LOG_NAMES]


def parse_ts(line: str) -> datetime | None:
    m = TS.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _dialogue_class(body: str) -> str:
    low = body.lower()
    if "credit balance is too low" in low or "purchase credits" in low:
        return "credit"
    if any(
        tok in low
        for tok in (
            "invalid x-api-key",
            "invalid api key",
            "authentication",
            "unauthorized",
            "error code: 401",
        )
    ):
        return "auth"
    if "overloaded" in low or "error code: 529" in low:
        return "overload"
    if "readtimeout" in low or "timeout" in low:
        return "timeout"
    return "other"


def classify_line(line: str) -> tuple[str, str] | None:
    """Return (class_id, thread_key) or None.

    Tool-result noise and source dumps are not classes. pre_poll skips collapse
    to one weather row — the URL is not the recurrence.
    """
    raw = TS.sub("", line).rstrip()
    if "Tool (" in raw or raw.lstrip().startswith("Tool"):
        return None

    m = SKIP.search(raw)
    if m:
        payload = m.group(1)
        kind, _, rest = payload.partition(":")
        class_id = "skip:pre_poll" if kind == "pre_poll" else f"skip:{kind}:{rest}"
        ch = SKIP_CHANNEL.search(raw)
        return class_id, (ch.group(1).strip() if ch else "?")

    m = REFLECT_FAIL.search(raw)
    if m:
        return f"reflection:{m.group(2)}", m.group(1)

    m = REFLECT_EMPTY.search(raw)
    if m:
        return "reflection:empty", m.group(1)

    m = DIALOGUE_ERR.search(raw)
    if m:
        return f"dialogue:{_dialogue_class(m.group(2))}", m.group(1)

    if DIALOGUE_UP.search(raw):
        return "dialogue:gave_up", "?"

    m = WRONG_CLIENT.match(raw)
    if m:
        return f"wrong_client:{m.group(1)}", "?"

    m = EXC.match(raw)
    if m:
        stem = m.group(1).strip()
        return f"exception:{stem}:{m.group(2)}", "?"

    return None


def scan_lines(
    lines: Iterable[str],
    *,
    since: datetime,
    previous_ids: Iterable[str] = (),
) -> dict[str, Any]:
    prev = set(previous_ids)
    buckets: dict[str, dict[str, Any]] = {}
    # stderr prints (WRONG-CLIENT, tracebacks) carry no timestamp; they sit
    # between two timestamped lines and belong to that moment. Inherit it.
    last_when: datetime | None = None
    for line in lines:
        when = parse_ts(line)
        if when is None:
            when = last_when
        else:
            last_when = when
        if when is None or when < since:
            continue
        hit = classify_line(line)
        if not hit:
            continue
        class_id, thread = hit
        row = buckets.setdefault(
            class_id,
            {
                "class_id": class_id,
                "count": 0,
                "threads": set(),
                "first": when,
                "last": when,
                "weather": class_id in WEATHER,
                "new": class_id not in prev,
            },
        )
        row["count"] += 1
        row["threads"].add(thread)
        if when < row["first"]:
            row["first"] = when
        if when > row["last"]:
            row["last"] = when
    return buckets


def _sort_key(row: dict[str, Any]) -> tuple:
    # Recurrence first (threads), then volume. Weather last.
    return (row["weather"], -len(row["threads"]), -row["count"], row["class_id"])


def render_section(
    buckets: dict[str, dict[str, Any]],
    *,
    window_hours: int = WINDOW_HOURS,
    logs_found: int,
    logs_expected: int = 2,
) -> str:
    lines = [
        f"## Log watch (last {window_hours}h)",
        "",
        "*Exception classes, dialogue failures, reflection misses, wrong-client "
        "detector hits, and offer-skip reasons from `discord.log` / `river.log`. "
        "Recurrence across threads is "
        "the signal; volume on one evening is weather. **new** was not in the "
        "previous report.*",
        "",
    ]
    if logs_found < logs_expected:
        lines += [
            f"*Logs found: {logs_found}/{logs_expected} — unmeasured where a file is missing.*",
            "",
        ]
    if not buckets:
        lines += ["*No classes in the window.*", ""]
        return "\n".join(lines)

    rows = sorted(buckets.values(), key=_sort_key)
    shown, hidden = rows[:DISPLAY_CAP], rows[DISPLAY_CAP:]
    lines += [
        "| Class | n | threads | first | last | |",
        "|-------|---|---------|-------|------|---|",
    ]
    for row in shown:
        first = row["first"].strftime("%H:%M")
        last = row["last"].strftime("%H:%M")
        mark = "weather" if row["weather"] else ("**new**" if row["new"] else "")
        lines.append(
            f"| `{row['class_id']}` | {row['count']} | {len(row['threads'])} | "
            f"{first} | {last} | {mark} |"
        )
    lines.append("")
    if hidden:
        lines += [f"*{len(hidden)} more class(es) under the cap.*", ""]
    return "\n".join(lines)


def collect_log_watch(
    paths: Iterable[Path],
    *,
    now: datetime | None = None,
    window_hours: int = WINDOW_HOURS,
    previous_ids: Iterable[str] = (),
) -> dict[str, Any]:
    now = now or datetime.now()
    since = now - timedelta(hours=window_hours)
    found = 0
    lines: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        found += 1
        try:
            lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
    buckets = scan_lines(lines, since=since, previous_ids=previous_ids)
    serial = []
    for row in sorted(buckets.values(), key=_sort_key):
        serial.append(
            {
                "class_id": row["class_id"],
                "count": row["count"],
                "threads": len(row["threads"]),
                "first": row["first"].isoformat(sep=" "),
                "last": row["last"].isoformat(sep=" "),
                "weather": row["weather"],
                "new": row["new"],
            }
        )
    return {
        "window_hours": window_hours,
        "logs_found": found,
        "class_ids": [r["class_id"] for r in serial],
        "classes": serial,
        "section": render_section(
            buckets, window_hours=window_hours, logs_found=found
        ),
    }
