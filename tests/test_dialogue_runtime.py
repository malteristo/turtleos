"""Tests for dialogue_runtime — runtime env blocks (discord_bot decomposition Slice 5)."""

from __future__ import annotations

import unittest

import dialogue_runtime


class BuildSourceTraceTests(unittest.TestCase):
    def test_empty_flags(self) -> None:
        self.assertEqual(dialogue_runtime.build_source_trace([]), "")

    def test_deduplicates_and_joins(self) -> None:
        flags = ["attachment metadata (a.pdf)", "attachment metadata (a.pdf)", "bot-fetched URL"]
        self.assertEqual(
            dialogue_runtime.build_source_trace(flags),
            "Sources: attachment metadata (a.pdf); bot-fetched URL",
        )


class ThreadCardExcerptTests(unittest.TestCase):
    def test_short_text_unchanged(self) -> None:
        self.assertEqual(dialogue_runtime.thread_card_excerpt("hello world"), "hello world")

    def test_long_text_truncated(self) -> None:
        text = "word " * 200
        excerpt = dialogue_runtime.thread_card_excerpt(text, limit=50)
        self.assertLessEqual(len(excerpt), 55)
        self.assertTrue(excerpt.endswith("..."))
