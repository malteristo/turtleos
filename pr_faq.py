"""turtleOS PR/FAQ format — required headings and a check that can fail.

A feature is designed by writing an instance under ``docs/pr-faq/instances/``
before it is built. The headings are the ones drafted for this practice on
2026-08-18. An instance missing any of them is incomplete; the test suite
fails the real instances and, separately, asserts that a deliberately
incomplete fixture is rejected.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
INSTANCES_DIR = REPO / "docs" / "pr-faq" / "instances"

# Press release, then FAQ. Names must appear as markdown headings
# (``## Name`` or ``### Name``). The FAQ parent heading is not itself required;
# the five FAQ topics are.
REQUIRED_HEADINGS: tuple[str, ...] = (
    "Headline",
    "Problem",
    "Solution",
    "Benefits",
    "Practitioner quote",
    "Getting started",
    "UX",
    "Not in scope",
    "Approach",
    "Risks",
    "Success / UX verification",
)

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def heading_titles(text: str) -> set[str]:
    return {m.group(1).strip() for m in _HEADING.finditer(text or "")}


def missing_headings(text: str) -> list[str]:
    present = heading_titles(text)
    return [name for name in REQUIRED_HEADINGS if name not in present]


def instance_paths() -> list[Path]:
    if not INSTANCES_DIR.is_dir():
        return []
    return sorted(
        p for p in INSTANCES_DIR.glob("*.md") if not p.name.startswith("_")
    )
