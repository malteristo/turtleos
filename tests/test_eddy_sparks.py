"""Eddy-note sparks: named, acted on, and read together by topic."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

from eddy_sparks import (
    SparkActError,
    apply_spark_act,
    cites_the_topic,
    parse_spark_lines,
    sparks_by_topic,
)
from practice_io import eddy_note_link
from story_entries import EddyEntry


NOTE = """---
thread: '7'
title: Evenings
trigger: idle
timestamp: '2026-10-03T18:00:00+02:00'
related-topics: []
proposed-themes: []
sparks:
- id: evening-game
  name: The evening game
  topic: evenings
  status: open
- id: hour-alone
  name: An hour alone
  topic: evenings
  status: open
---

The afternoon was about the two of them.
"""


class SparkTests(unittest.TestCase):
    def test_one_line_becomes_an_open_spark(self) -> None:
        sparks = parse_spark_lines("- The evening game | evenings\nnone\n")
        self.assertEqual(len(sparks), 1)
        self.assertEqual(sparks[0]["id"], "the-evening-game")
        self.assertEqual(sparks[0]["status"], "open")
        self.assertEqual(sparks[0]["topic"], "evenings")

    def test_open_is_not_an_act(self) -> None:
        with self.assertRaises(SparkActError):
            apply_spark_act(NOTE, "evening-game", "open")

    def test_missing_spark_is_refused(self) -> None:
        with self.assertRaises(SparkActError):
            apply_spark_act(NOTE, "not-there", "dropped")

    def test_drop_is_written_and_the_other_spark_stays(self) -> None:
        updated = apply_spark_act(NOTE, "evening-game", "dropped")
        self.assertIn("status: dropped", updated)
        self.assertIn("id: hour-alone", updated)
        self.assertIn("status: open", updated)

    def test_same_topic_is_read_together(self) -> None:
        entry = EddyEntry(
            thread="7",
            title="Evenings",
            trigger="idle",
            timestamp=datetime(2026, 10, 3, tzinfo=timezone.utc),
            related_topics=[],
            body="The afternoon was about the two of them.",
            source_path=Path("story/eddies/7-evenings.md"),
            sparks=parse_spark_lines(
                "- The evening game | evenings\n- An hour alone | evenings\n"
            ),
        )
        grouped = sparks_by_topic([entry])
        self.assertEqual(len(grouped["evenings"]), 2)
        ids = {spark["id"] for spark in grouped["evenings"]}
        self.assertTrue(cites_the_topic(grouped["evenings"], ids))
        one = {grouped["evenings"][0]["id"]}
        self.assertFalse(cites_the_topic(grouped["evenings"], one))

    def test_recent_notes_are_in_the_prompt(self) -> None:
        from story_notes import _build_prompt

        prompt = _build_prompt(
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "Ada",
            [],
            "idle",
            None,
            recent_notes=["Evenings: The evening game"],
        )
        self.assertIn("Evenings: The evening game", prompt)

    def test_a_reply_names_its_sparks(self) -> None:
        from story_notes import _parse_response

        raw = (
            "---HELD---\nThe eddy was about one afternoon.\n"
            "---RELATION---\nnone\n"
            "---RELATED-TOPICS---\nnone\n"
            "---PROPOSED-THEMES---\nnone\n"
            "---SPARKS---\n- The evening game | evenings\n"
            "---END---\n"
        )
        _held, _relation, _topics, _proposed, sparks = _parse_response(raw)
        self.assertEqual(sparks[0]["topic"], "evenings")
        self.assertEqual(sparks[0]["status"], "open")

    def test_the_card_is_a_link(self) -> None:
        text = eddy_note_link("story/eddies/1-a.md")
        self.assertIn("story/eddies/1-a.md", text)
        self.assertIn("](", text)
        self.assertNotEqual(text, "`story/eddies/1-a.md`")

    def test_the_card_shows_the_eddy_title(self) -> None:
        from practice_io import eddy_note_label

        text = eddy_note_link(
            "story/eddies/7-new-eddy.md",
            title="tool use and thinking traces",
        )
        self.assertTrue(text.startswith("[tool use and thinking traces]("))
        self.assertIn("story/eddies/7-new-eddy", text)
        self.assertEqual(
            eddy_note_label("new eddy", "story/eddies/7-new-eddy.md"),
            "story/eddies/7-new-eddy.md",
        )


if __name__ == "__main__":
    unittest.main()
