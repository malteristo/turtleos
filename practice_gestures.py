"""The pair — glance and go. Leaf module; no platform imports.

`...` / `... [toward]` glances. `.` / `. [toward]` goes.
Four dots is not a glance. Two dots is not go.
"""

from __future__ import annotations


def is_ellipsis_glance(text: str | None) -> bool:
    """True for `...` or an aimed glance (`... later`, `... craft`)."""
    t = (text or "").strip()
    if t == "...":
        return True
    return (
        t.startswith("...")
        and len(t) > 3
        and t[3].isspace()
        and bool(t[4:].strip())
    )


def glance_toward(text: str | None) -> str:
    """The words after an aimed `...`, or empty for a bare glance."""
    t = (text or "").strip()
    if t == "..." or not is_ellipsis_glance(t):
        return ""
    return t[4:].strip()


def is_go_breath(text: str | None) -> bool:
    """True for `.` or `. [toward]`. Not `..`, not `...`."""
    t = (text or "").strip()
    if t == ".":
        return True
    return (
        t.startswith(".")
        and len(t) > 1
        and t[1].isspace()
        and bool(t[2:].strip())
    )
