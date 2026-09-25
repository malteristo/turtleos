"""Practitioner context — the twine row that says where they are.

``state/context.md`` is the file. This module is the only reader.
Presence of the file is not load; empty and missing are the same.
"""

from __future__ import annotations

from pathlib import Path

CONTEXT_REL = Path("state") / "context.md"
CONTEXT_CHAR_BUDGET = 2000
CONTEXT_HEADER = "## Current context"


def context_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / CONTEXT_REL


def load_practitioner_context(practice_dir: str | Path | None) -> str:
    if not practice_dir:
        return ""
    path = context_path(practice_dir)
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def practitioner_context_loaded(practice_dir: str | Path | None) -> bool:
    return bool(load_practitioner_context(practice_dir))


def practitioner_context_block(practice_dir: str | Path | None) -> str:
    text = load_practitioner_context(practice_dir)
    if not text:
        return ""
    body = text[:CONTEXT_CHAR_BUDGET]
    return (
        f"{CONTEXT_HEADER}\n\n{body}\n\n"
        "Honour this. Do not recite it unless it serves the turn."
    )
