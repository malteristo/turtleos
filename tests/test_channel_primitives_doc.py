"""The channel-primitives chapter is a contract, not a file that exists.

2026-08-17. The chapter's confirmed target condition was "a specification
exists that ...", and this repo's characteristic defect is a check that
verifies presence where function was meant. "The markdown file is on disk"
is exactly that check, so it is not the one made here.

Two things are asserted instead, both of which stop being true if someone
replaces the chapter with plausible prose:

1. The decision table exists and still uses its three-valued status
   vocabulary, and at least one row is genuinely ``open``. A table whose
   open cells have all been filled in is either finished work or a model
   answering its own questions, and on this axis those look identical from
   the outside — so the day the last ``open`` disappears, this test asks
   for it to be justified out loud rather than let it pass silently.

2. ``design-topic-channels.md`` declares itself superseded and names the
   chapter that supersedes it. Without that, the two documents both read
   as current and the reversal is invisible to the next reader.

Both checks carry a positive control below: the assertion is re-run against
a mutated copy of the text and must fail, because a doc test that cannot
fail is a decoration.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs" / "chapters"
PRIMITIVES = DOCS / "design-channel-primitives.md"
TOPICS = DOCS / "design-topic-channels.md"

# The row-status vocabulary the chapter commits to. `open` is the load-bearing
# one: it is what lets a question stay unanswered instead of being resolved by
# whoever wrote last.
STATUSES = ("decided", "open", "contradicts-prior")

_SUPERSEDE = re.compile(
    r"supersede[d]?\b[^\n]*design-channel-primitives\.md|"
    r"design-channel-primitives\.md[^\n]*supersede",
    re.IGNORECASE,
)


def _has_decision_table(text: str) -> bool:
    """A table with the status vocabulary, and at least one live open row."""
    if "## Decision table" not in text:
        return False
    if not all(s in text for s in STATUSES):
        return False
    # An open row is a table cell, not a mention in prose: pipe, optional
    # bold/emphasis, the word, then a cell or clause boundary.
    return bool(re.search(r"\|\s*\*\*open\*\*", text))


def _declares_supersession(text: str) -> bool:
    return bool(_SUPERSEDE.search(text))


class ChannelPrimitivesChapterTests(unittest.TestCase):
    def test_chapter_carries_a_decision_table_with_open_rows(self) -> None:
        self.assertTrue(PRIMITIVES.exists(), f"missing chapter: {PRIMITIVES}")
        text = PRIMITIVES.read_text(encoding="utf-8")
        self.assertTrue(
            _has_decision_table(text),
            "design-channel-primitives.md must carry a '## Decision table' using "
            f"the statuses {STATUSES}, with at least one row still **open**. "
            "If every question is genuinely answered, say so in the chapter and "
            "update this test deliberately — do not delete the requirement.",
        )

    def test_superseded_chapter_says_so_and_names_its_successor(self) -> None:
        self.assertTrue(TOPICS.exists(), f"missing chapter: {TOPICS}")
        text = TOPICS.read_text(encoding="utf-8")
        self.assertTrue(
            _declares_supersession(text),
            "design-topic-channels.md must declare itself superseded and name "
            "design-channel-primitives.md. Two chapters that both read as "
            "current is how the reversal becomes invisible.",
        )

    # --- positive controls -------------------------------------------------
    # Each check is re-run against text that should fail it. Without these,
    # a predicate that returned True unconditionally would pass every test
    # above and the file would be decoration.

    def test_decision_table_check_fails_without_a_table(self) -> None:
        self.assertFalse(_has_decision_table("# Chapter\n\nSome prose.\n"))

    def test_decision_table_check_fails_when_no_row_is_open(self) -> None:
        closed = (
            "## Decision table\n\n"
            "| # | Claim | Status |\n|---|---|---|\n"
            "| S1 | a | **decided** |\n| S2 | b | **contradicts-prior** |\n"
            # the words are present in the legend, but no row is open
            "\nStatuses: decided, open, contradicts-prior.\n"
        )
        self.assertFalse(_has_decision_table(closed))

    def test_decision_table_check_passes_on_the_real_shape(self) -> None:
        live = (
            "## Decision table\n\n"
            "| # | Claim | Status |\n|---|---|---|\n"
            "| S1 | a | **decided** |\n| S4 | b | **open** — not shipped |\n"
            "| S6 | c | **contradicts-prior** |\n"
        )
        self.assertTrue(_has_decision_table(live))

    def test_supersession_check_fails_on_a_bare_mention(self) -> None:
        self.assertFalse(
            _declares_supersession("See also design-channel-primitives.md for context.")
        )

    def test_supersession_check_passes_on_a_real_notice(self) -> None:
        self.assertTrue(
            _declares_supersession(
                "**Status:** SUPERSEDED in its surface recommendation by "
                "[design-channel-primitives.md](design-channel-primitives.md)."
            )
        )


if __name__ == "__main__":
    unittest.main()
