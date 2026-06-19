import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from river_keys import (
    _looks_like_single_key,
    _normalize_mage_key,
    _expected_river_key,
    is_unclaimed_river,
    load_claim_room_markdown,
)


class RiverKeyTests(unittest.TestCase):
    def test_looks_like_single_key(self) -> None:
        self.assertTrue(_looks_like_single_key("🌿"))
        self.assertFalse(_looks_like_single_key("hello"))
        self.assertFalse(_looks_like_single_key("🌿 🌿"))

    def test_normalize_mage_key(self) -> None:
        self.assertEqual(_normalize_mage_key("Anna"), "anna")
        self.assertEqual(_normalize_mage_key("Anna-Marie"), "anna_marie")

    def test_is_unclaimed_river(self) -> None:
        with patch("river_keys._channel_entry") as mock_entry:
            mock_entry.return_value = {"type": "unclaimed-river", "mage": "anna"}
            self.assertTrue(is_unclaimed_river(123))
            mock_entry.return_value = {"type": "hosted-river", "mage": "anna"}
            self.assertFalse(is_unclaimed_river(123))

    def test_expected_river_key_from_channel(self) -> None:
        with patch("river_keys._channel_entry") as mock_entry:
            mock_entry.return_value = {"river_key": "🌿", "mage": "anna"}
            self.assertEqual(_expected_river_key(1), "🌿")

    def test_load_claim_room_en(self) -> None:
        text = load_claim_room_markdown("en")
        self.assertIn("Claim your river", text)


if __name__ == "__main__":
    unittest.main()
