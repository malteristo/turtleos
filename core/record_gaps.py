"""Holes in the practice record — counted, not printed.

2026-08-07. The read-error investigation found the eddy-note write failing the
same way the dialogue did, and handled worse: ``sessions.py`` caught the
timeout, printed one line, and continued. Two of the operator's 2026-08-06
river eddies have no note on disk, and because ``_promote_proposed_themes``
runs *inside* ``write_eddy_note``, the same failure took the alive layer with
it — one exception, both layers, silently, on the densest conversations of
the day.

A degraded reply is visible to the person having the conversation. A dropped
record is visible to nobody. That asymmetry is the whole reason this file
exists: the failure needs somewhere to accumulate that a human actually reads,
which is the nightly ops report, not ``logs/discord.log``.

Same shape as ``offer_ledger`` deliberately — per-root JSONL under
``chronicle/``, a tally, a section renderer the ops runner calls. The lesson
that module paid for applies here too: **a zero row and a missing row mean
opposite things.** A kind that can fail and never has must still render, or
the instrument is blind in the direction it was built to see.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

GAPS_REL = "chronicle/record_gaps.jsonl"

# Every write path whose failure leaves a hole in the practice record.
# Listed here even when it has never failed — see the module docstring.
KINDS = (
    "eddy_note",
    "daily_note",
    "alive_promotion",
    "workspace_refresh",
)

# Why it failed. ``declined`` is not a gap — the model looked and had nothing
# worth writing — and is recorded separately so the two never get conflated in
# a count. ``failed`` is infrastructure: timeout, connection, disk.
REASONS = ("failed", "declined", "exhausted")


def gaps_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / GAPS_REL


def record(
    practice_dir: str | Path,
    *,
    kind: str,
    reason: str,
    channel_id: int | str | None = None,
    detail: str | None = None,
    attempts: int | None = None,
) -> None:
    """Append one gap event. Never raises into a checkpoint."""
    if reason not in REASONS:
        return
    try:
        path = gaps_path(practice_dir)
        os.makedirs(path.parent, exist_ok=True)
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": str(kind),
            "reason": reason,
        }
        if channel_id is not None:
            row["channel_id"] = str(channel_id)
        if attempts is not None:
            row["attempts"] = int(attempts)
        if detail:
            row["detail"] = str(detail)[:200]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # A failure to record a failure must never take down the checkpoint
        # that was already degrading.
        pass


def _rows(practice_dir: str | Path) -> list[dict[str, Any]]:
    path = gaps_path(practice_dir)
    if not path.exists():
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def default_window_start(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def tally(
    practice_dirs: Iterable[str | Path], *, since: str | None = None
) -> dict[str, dict[str, int]]:
    """Gap counts per kind across roots."""
    counts: dict[str, dict[str, int]] = {}
    for pd in practice_dirs:
        for row in _rows(pd):
            if since and str(row.get("ts", "")) < since:
                continue
            kind = str(row.get("kind", "?"))
            reason = str(row.get("reason", "?"))
            bucket = counts.setdefault(kind, {r: 0 for r in REASONS})
            if reason in bucket:
                bucket[reason] += 1
    return counts


def render_record_gaps_section(
    counts: dict[str, dict[str, int]],
    *,
    window_days: int,
    known_kinds: Iterable[str] = KINDS,
) -> str:
    """Markdown for the ops report. Any non-zero ``failed`` is the headline."""
    kinds = sorted(set(counts) | set(known_kinds))
    if not kinds:
        return ""
    total_failed = sum(counts.get(k, {}).get("failed", 0) for k in kinds)
    total_exhausted = sum(counts.get(k, {}).get("exhausted", 0) for k in kinds)

    lines = [
        f"## Record gaps (last {window_days}d)",
        "",
        "*Where the practice record failed to write. A conversation that "
        "produced no note is not in the twine, not on the shelf, and not in "
        "the room's memory — and nobody in the room can tell.*",
        "",
        "| Write path | Failed | Retried out | Declined |",
        "|------------|--------|-------------|----------|",
    ]
    for kind in kinds:
        c = counts.get(kind, {})
        failed = c.get("failed", 0)
        exhausted = c.get("exhausted", 0)
        declined = c.get("declined", 0)
        label = kind
        if exhausted:
            label = f"**{kind}**"
        lines.append(f"| {label} | {failed} | {exhausted} | {declined} |")

    lines.append("")
    if total_exhausted:
        lines.append(
            f"**{total_exhausted} record(s) lost after every retry.** These are "
            "holes, not delays — the conversation happened and nothing holds it."
        )
    elif total_failed:
        lines.append(
            f"{total_failed} write(s) failed and recovered on retry. No holes."
        )
    else:
        lines.append("No gaps. Every write path that ran, landed.")
    return "\n".join(lines)
