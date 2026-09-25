"""The role-needs dest is a table, not a file that exists.

A dest that loses a status, or drops Turtle or River, has stopped
being the lens. The assertion is re-run against a mutated copy and
must fail.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "docs" / "design" / "role-needs.md"
STATUSES = ("exists", "partial", "missing")
INHABITANTS = ("Turtle", "River")
_ROW = re.compile(
    r"^\| (?P<need>[^|]+) \| (?P<source>[^|]+) \| (?P<status>exists|partial|missing) \|",
    re.MULTILINE,
)


def _need_rows(text: str) -> list[tuple[str, str]]:
    return [(m.group("need").strip(), m.group("status")) for m in _ROW.finditer(text)]


class RoleNeedsDestTests(unittest.TestCase):
    def test_turtle_and_river_rows_have_statuses(self) -> None:
        text = DEST.read_text(encoding="utf-8")
        for name in INHABITANTS:
            self.assertIn(f"### {name}", text)
        rows = _need_rows(text)
        self.assertGreaterEqual(len(rows), 5)
        self.assertTrue(any(s == "missing" for _, s in rows))
        for need, status in rows:
            self.assertIn(status, STATUSES, need)

    def test_stripped_status_fails(self) -> None:
        text = DEST.read_text(encoding="utf-8")
        self.assertTrue(_need_rows(text))
        mutated = text
        for status in STATUSES:
            mutated = mutated.replace(f"| {status} |", "| TBD |")
        self.assertEqual(_need_rows(mutated), [])
