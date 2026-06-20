"""Tests for River-side seneschal helpers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import river_eddy_seneschal as res


class TestDedupeFetchActions(unittest.TestCase):
    def test_collapses_duplicate_fetch_commands(self) -> None:
        actions = [
            ("Fetch link", "!fetch https://example.com/a"),
            ("Fetch link", "!fetch https://example.com/a"),
        ]
        deduped = res.dedupe_fetch_actions(actions)
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
