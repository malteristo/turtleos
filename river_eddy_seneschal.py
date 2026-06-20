"""River-side eddy seneschal helpers.

Slice 2 (harness split): post-Turtle ``Save to library`` offers live here.
Pre-fetch on practitioner URL (``09bcbc0``) removed in Slice 1 — Turtle link-read
informs dialogue; River ``!fetch`` is opt-in persistence only.
"""

from __future__ import annotations

import re


def dedupe_fetch_actions(actions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """One Fetch button per row — backtick + plain-tail extraction can duplicate."""
    seen_fetch: set[str] = set()
    out: list[tuple[str, str]] = []
    for label, command in actions:
        cmd = command.lstrip("!").split(None, 1)[0].lower()
        if cmd == "fetch":
            key = re.sub(r"\s+", " ", command.strip().lower())
            if key in seen_fetch:
                continue
            seen_fetch.add(key)
        out.append((label, command))
    return out
