"""Tests for share_targets — registry addressing (share_eddy decomposition Slice 1).

Fixtures use role keys (`operator`, `partner`, `sibling`, `friend`), not the
names of real people on any node.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import share_targets


class ShareTargetTests(unittest.TestCase):
    def test_list_practitioner_targets_excludes_self(self) -> None:
        registry = {
            "default_mage": "operator",
            "mages": {
                "operator": {
                    "discord_id": "111",
                    "address": "Operator",
                    "type": "mage",
                    "admin": True,
                    "relation": "household",
                },
                "partner": {
                    "discord_id": "222",
                    "address": "Partner",
                    "type": "practitioner",
                    "relation": "household",
                },
            },
            "channels": {
                "1001": {"mage": "operator", "type": "river"},
                "1002": {"mage": "partner", "type": "hosted-river"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = share_targets.list_practitioner_targets("operator", "111")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].mage_key, "partner")
        self.assertEqual(targets[0].channel_id, 1002)


class RelationScopedReachTests(unittest.TestCase):
    """Reach is relation-governed — docs/design/relations-and-membership.md."""

    REGISTRY = {
        "default_mage": "operator",
        "mages": {
            "operator": {
                "discord_id": "1",
                "address": "Operator",
                "admin": True,
                "relation": "household",
            },
            "partner": {"discord_id": "2", "address": "Partner", "relation": "household"},
            "nephew": {"discord_id": "3", "address": "Nephew", "relation": "kin"},
            "friend": {"discord_id": "4", "address": "Friend", "relation": "guest"},
            "stranger": {"discord_id": "5", "address": "Stranger"},
        },
        "channels": {
            "101": {"mage": "operator", "type": "river"},
            "102": {"mage": "partner", "type": "hosted-river"},
            "103": {"mage": "nephew", "type": "hosted-river"},
            "104": {"mage": "friend", "type": "hosted-river"},
            "105": {"mage": "stranger", "type": "hosted-river"},
        },
    }

    def _keys(self, sender_key: str, sender_id: str) -> set[str]:
        with patch("share_targets.get_registry", return_value=self.REGISTRY):
            targets = share_targets.list_practitioner_targets(sender_key, sender_id)
        return {t.mage_key for t in targets}

    def test_admin_reaches_everyone(self) -> None:
        self.assertEqual(
            self._keys("operator", "1"), {"partner", "nephew", "friend", "stranger"}
        )

    def test_household_reaches_household_and_kin_not_guests(self) -> None:
        self.assertEqual(self._keys("partner", "2"), {"operator", "nephew"})

    def test_kin_reaches_household_and_kin(self) -> None:
        self.assertEqual(self._keys("nephew", "3"), {"operator", "partner"})

    def test_guest_reaches_the_operator_only(self) -> None:
        self.assertEqual(self._keys("friend", "4"), {"operator"})

    def test_unclassified_member_is_treated_as_a_guest(self) -> None:
        self.assertEqual(self._keys("stranger", "5"), {"operator"})

    def test_guests_and_kin_cannot_reach_each_other(self) -> None:
        self.assertNotIn("nephew", self._keys("friend", "4"))
        self.assertNotIn("friend", self._keys("nephew", "3"))


class SpaceShareTargetTests(unittest.TestCase):
    FAMILY_CHANNEL = 9100

    def test_list_space_targets_all_practitioners(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "111", "address": "Operator", "type": "mage"},
                "partner": {"discord_id": "222", "address": "Partner", "type": "practitioner"},
                "guest": {"discord_id": "333", "address": "Guest", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["operator", "partner"],
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
            targets = share_targets.list_space_targets("guest")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].space_key, "family")
        self.assertEqual(targets[0].channel_id, self.FAMILY_CHANNEL)

    def test_list_space_targets_members_only_excludes_guest(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "111"},
                "partner": {"discord_id": "222"},
                "guest": {"discord_id": "333", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["operator", "partner"],
                    "share_policy": "members_only",
                }
            },
            "channels": {
                "9001": {"type": "shared-river", "mage": "family"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertEqual(share_targets.list_space_targets("guest"), [])
            self.assertEqual(len(share_targets.list_space_targets("operator")), 1)

    def test_space_member_discord_ids_excludes_sharer(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "111"},
                "partner": {"discord_id": "222"},
            },
            "spaces": {"family": {"members": ["operator", "partner"]}},
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

    def test_archived_river_is_not_addressable(self) -> None:
        """A retired river is one its member can no longer see."""
        registry = {
            "channels": {
                "42": {"mage": "retired", "type": "hosted-river", "archived": True},
            }
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertIsNone(share_targets.river_channel_for_mage("retired"))

    def test_member_with_only_a_retired_river_is_not_a_share_target(self) -> None:
        registry = {
            "default_mage": "operator",
            "mages": {
                "operator": {"discord_id": "1", "admin": True, "relation": "household"},
                "retired": {"discord_id": "2", "relation": "kin"},
            },
            "channels": {
                "101": {"mage": "operator", "type": "river"},
                "102": {"mage": "retired", "type": "hosted-river", "archived": True},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = share_targets.list_practitioner_targets("operator", "1")
        self.assertEqual(targets, [])


class MageSpaceMembershipTests(unittest.TestCase):
    def test_mage_is_space_member(self) -> None:
        registry = {
            "spaces": {"family": {"members": ["operator", "partner"]}},
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertTrue(share_targets.mage_is_space_member("operator", "family"))
            self.assertFalse(share_targets.mage_is_space_member("friend", "family"))

    def test_mage_key_for_discord_id(self) -> None:
        registry = {
            "mages": {
                "operator": {"discord_id": "111"},
                "partner": {"discord_id": "222"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertEqual(share_targets.mage_key_for_discord_id("222"), "partner")
            self.assertIsNone(share_targets.mage_key_for_discord_id("999"))

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import ShareTarget, list_practitioner_targets

        registry = {
            "default_mage": "operator",
            "mages": {
                "operator": {"discord_id": "111", "address": "Operator", "admin": True},
                "partner": {"discord_id": "222", "address": "Partner"},
            },
            "channels": {
                "1002": {"mage": "partner", "type": "hosted-river"},
            },
        }
        with patch("share_targets.get_registry", return_value=registry):
            targets = list_practitioner_targets("operator", "111")
        self.assertEqual(len(targets), 1)
        self.assertIsInstance(targets[0], ShareTarget)
