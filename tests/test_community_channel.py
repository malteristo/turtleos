"""House #community — explicit seat, not a practice fallback."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from channel_primitives import resolve_primitive
from roster_sync import apply_admit_registry, find_community_space
from scripts import provision_community_channel as provision


class CommunityRegistryTests(unittest.TestCase):
    def test_write_declares_shared_community_contract(self) -> None:
        registry: dict = {}
        with patch("river_keys.save_registry") as save:
            provision.write_community_registry(
                registry, channel_id=501, member_keys=["operator", "partner", "guest"]
            )
        self.assertEqual(registry["channels"]["501"]["primitive"], "shared")
        self.assertEqual(registry["channels"]["501"]["discord_category"], "Community")
        self.assertEqual(
            registry["spaces"]["community"]["members"],
            ["operator", "partner", "guest"],
        )
        primitive = resolve_primitive(registry, 501)
        self.assertIsNotNone(primitive)
        self.assertEqual(primitive.name, "shared")
        self.assertEqual(find_community_space(registry), "community")
        save.assert_called_once_with(registry)

    def test_admit_seats_community_not_family(self) -> None:
        registry: dict = {
            "mages": {"operator": {"discord_id": "1", "relation": "household"}},
            "channels": {
                "200": {
                    "mage": "family",
                    "type": "shared-river",
                    "primitive": "partnership",
                }
            },
            "spaces": {"family": {"members": ["operator", "partner"]}},
        }
        with patch("river_keys.save_registry"):
            provision.write_community_registry(
                registry, channel_id=501, member_keys=["operator"]
            )
        apply_admit_registry(
            registry,
            mage_key="newcomer",
            discord_id="99",
            display_name="Newcomer",
            channel_id=80,
        )
        self.assertIn("newcomer", registry["spaces"]["community"]["members"])
        self.assertNotIn("newcomer", registry["spaces"]["family"]["members"])
        self.assertEqual(registry["mages"]["newcomer"]["relation"], "kin")

    def test_live_member_keys_skip_departed(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "1"},
                "departed_guest": {"discord_id": "2", "departed": True},
                "ghost": {"discord_id": "YOUR_DISCORD_USER_ID"},
            },
            "channels": {
                "100": {"mage": "operator", "type": "river"},
            },
        }
        self.assertEqual(provision.live_member_keys(registry), ["operator"])

    def test_live_member_keys_skip_archived_river(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "1"},
                "retired_guest": {"discord_id": "2", "relation": "kin"},
            },
            "channels": {
                "100": {"mage": "operator", "type": "river"},
                "200": {
                    "mage": "retired_guest",
                    "type": "hosted-river",
                    "archived": True,
                },
            },
        }
        self.assertEqual(provision.live_member_keys(registry), ["operator"])

    def test_existing_community_is_detected(self) -> None:
        registry: dict = {}
        with patch("river_keys.save_registry"):
            provision.write_community_registry(
                registry, channel_id=501, member_keys=["operator"]
            )
        self.assertEqual(provision.existing_community_channel(registry), "501")
