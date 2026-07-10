"""Tests for share_targets — registry addressing (share_eddy decomposition Slice 1)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import share_targets


class ShareTargetTests(unittest.TestCase):
    def test_list_practitioner_targets_excludes_self(self) -> None:
        registry = {
            "mages": {
                "kermit": {
                    "discord_id": "111",
                    "address": "Kermit",
                    "type": "mage",
                },
                "nesrine": {
                    "discord_id": "222",
                    "address": "Nesrine",
                    "type": "practitioner",
                },
            },
            "channels": {
                "1001": {"mage": "kermit", "type": "river"},
                "1002": {"mage": "nesrine", "type": "hosted-river"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = share_targets.list_practitioner_targets("kermit", "111")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].mage_key, "nesrine")
        self.assertEqual(targets[0].channel_id, 1002)


class SpaceShareTargetTests(unittest.TestCase):
    FAMILY_CHANNEL = 1491163697278881836

    def test_list_space_targets_all_practitioners(self) -> None:
        registry = {
            "mages": {
                "kermit": {"discord_id": "111", "address": "Kermit", "type": "mage"},
                "nesrine": {"discord_id": "222", "address": "Nesrine", "type": "practitioner"},
                "alex": {"discord_id": "333", "address": "Alex", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["kermit", "nesrine"],
                    "share_policy": "all_practitioners",
                }
            },
            "channels": {
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = share_targets.list_space_targets("alex")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].space_key, "family")
        self.assertEqual(targets[0].channel_id, self.FAMILY_CHANNEL)

    def test_list_space_targets_members_only_excludes_guest(self) -> None:
        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
                "alex": {"discord_id": "333", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["kermit", "nesrine"],
                    "share_policy": "members_only",
                }
            },
            "channels": {
                "9001": {"type": "shared-river", "mage": "family"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertEqual(share_targets.list_space_targets("alex"), [])
            self.assertEqual(len(share_targets.list_space_targets("kermit")), 1)

    def test_space_member_discord_ids_excludes_sharer(self) -> None:
        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
            },
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        with patch("share_targets.get_registry", return_value=registry):
            ids = share_targets.space_member_discord_ids("family", exclude_id="111")
        self.assertEqual(ids, ["222"])


class RiverChannelTests(unittest.TestCase):
    def test_river_channel_for_mage(self) -> None:
        registry = {
            "channels": {
                "42": {"mage": "guest", "type": "hosted-river"},
                "43": {"mage": "guest", "type": "craft"},
            }
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertEqual(share_targets.river_channel_for_mage("guest"), 42)
            self.assertIsNone(share_targets.river_channel_for_mage("missing"))


class MageSpaceMembershipTests(unittest.TestCase):
    def test_mage_is_space_member(self) -> None:
        registry = {
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertTrue(share_targets.mage_is_space_member("kermit", "family"))
            self.assertFalse(share_targets.mage_is_space_member("lukas", "family"))

    def test_mage_key_for_discord_id(self) -> None:
        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertEqual(share_targets.mage_key_for_discord_id("222"), "nesrine")
            self.assertIsNone(share_targets.mage_key_for_discord_id("999"))

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import ShareTarget, list_practitioner_targets

        registry = {
            "mages": {
                "kermit": {"discord_id": "111", "address": "Kermit"},
                "nesrine": {"discord_id": "222", "address": "Nesrine"},
            },
            "channels": {
                "1002": {"mage": "nesrine", "type": "hosted-river"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = list_practitioner_targets("kermit", "111")
        self.assertEqual(len(targets), 1)
        self.assertIsInstance(targets[0], ShareTarget)
