"""Tests for cross-process Turtle turn signals."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())

import river_turn_signal as rts


class RiverTurnSignalTests(unittest.TestCase):
    def setUp(self) -> None:
        rts.clear_turtle_turn_signal()

    def tearDown(self) -> None:
        rts.clear_turtle_turn_signal()

    def test_mark_and_consume_matching_turn(self) -> None:
        with patch("mage.get_runtime_dir", return_value="/tmp/turtleos-test-signals"):
            rts.mark_turtle_turn_complete(42, 1001)
            self.assertTrue(rts.consume_turtle_turn_complete(42, 1001))
            self.assertFalse(rts.consume_turtle_turn_complete(42, 1001))

    def test_consume_requires_matching_message_id(self) -> None:
        with patch("mage.get_runtime_dir", return_value="/tmp/turtleos-test-signals"):
            rts.mark_turtle_turn_complete(42, 1001)
            self.assertFalse(rts.consume_turtle_turn_complete(42, 9999))


if __name__ == "__main__":
    unittest.main()
