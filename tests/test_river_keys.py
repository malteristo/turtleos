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
    find_unclaimed_channel_id,
    hosted_river_channel_name,
    is_unclaimed_river,
    list_unclaimed_river_hints,
    load_claim_room_markdown,
    parse_invite_args,
)


class RiverKeyTests(unittest.TestCase):
    def test_looks_like_single_key(self) -> None:
        self.assertTrue(_looks_like_single_key("🌿"))
        self.assertFalse(_looks_like_single_key("hello"))
        self.assertFalse(_looks_like_single_key("🌿 🌿"))

    def test_normalize_mage_key(self) -> None:
        self.assertEqual(_normalize_mage_key("Anna"), "anna")
        self.assertEqual(_normalize_mage_key("Anna-Marie"), "anna_marie")

    def test_hosted_river_channel_name(self) -> None:
        self.assertEqual(hosted_river_channel_name("fares"), "river-fares")
        self.assertEqual(hosted_river_channel_name("anna_marie"), "river-anna-marie")

    def test_parse_invite_args_with_member(self) -> None:
        name, key, locale, member = parse_invite_args(["fares", "👽", "en", "--member", "216.guest"])
        self.assertEqual(name, "fares")
        self.assertEqual(key, "👽")
        self.assertEqual(locale, "en")
        self.assertEqual(member, "216.guest")

    def test_parse_invite_args_member_mid_tokens(self) -> None:
        name, key, locale, member = parse_invite_args(["--member", "99", "fares", "🌿"])
        self.assertEqual(name, "fares")
        self.assertEqual(key, "🌿")
        self.assertEqual(locale, "en")
        self.assertEqual(member, "99")

    def test_find_unclaimed_and_hints(self) -> None:
        registry = {
            "channels": {
                "1": {"type": "unclaimed-river", "mage": "brother", "invite_code": "abc"},
                "2": {"type": "hosted-river", "mage": "fares"},
            }
        }
        self.assertEqual(find_unclaimed_channel_id("brother", registry), "1")
        self.assertIsNone(find_unclaimed_channel_id("fares", registry))
        self.assertEqual(list_unclaimed_river_hints(registry), ["brother"])

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
