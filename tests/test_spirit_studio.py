"""Spirit coach studio — a private river that is not a roster seat."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
import sys

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from roster_sync import compute_roster_drift, live_mages
from scripts import provision_spirit_studio as provision


class SpiritStudioRegistryTests(unittest.TestCase):
    def test_bind_is_findable_and_not_a_member(self) -> None:
        registry = {
            "mages": {"alex": {"discord_id": "1"}},
            "channels": {"100": {"mage": "alex", "type": "river"}},
            "spaces": {},
        }
        provision.bind_spirit_studio_registry(
            registry, channel_id=900, discord_id="1487"
        )
        self.assertEqual(provision.existing_studio_channel(registry), "900")
        self.assertNotIn(provision.MAGE_KEY, live_mages(registry))
        drift = compute_roster_drift(registry, human_ids=["1"])
        self.assertTrue(drift.is_clean())
        self.assertEqual(registry["mages"][provision.MAGE_KEY]["roster"], False)

    def test_existing_ignores_a_member_row_with_the_same_key(self) -> None:
        registry = {
            "mages": {"spirit": {"discord_id": "1487"}},
            "channels": {"900": {"mage": "spirit", "type": "river"}},
        }
        self.assertIsNone(provision.existing_studio_channel(registry))
