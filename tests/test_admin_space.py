import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import mage
from river_handler import _iter_river_channels
from share_eddy import shared_river_channel_for_space
from space_provisioning import (
    list_active_spaces,
    normalize_space_key,
    parse_space_create_args,
    parse_space_close_args,
    resolve_member_keys,
    validate_space_available,
)


class AdminSpaceParsingTests(unittest.TestCase):
    def test_normalize_space_key(self) -> None:
        self.assertEqual(normalize_space_key("lukas_play"), "lukas_play")
        self.assertEqual(normalize_space_key("Lukas-Play"), "lukas_play")
        with self.assertRaises(ValueError):
            normalize_space_key("9bad")

    def test_parse_space_create_args(self) -> None:
        opts = parse_space_create_args(
            [
                "create",
                "lukas_play",
                "--members",
                "<@111>",
                "nesrine",
                "--policy",
                "all_practitioners",
                "--context",
                "family",
                "--channel",
                "lukas-play",
            ]
        )
        self.assertEqual(opts.space_key, "lukas_play")
        self.assertEqual(opts.member_tokens, ["<@111>", "nesrine"])
        self.assertEqual(opts.share_policy, "all_practitioners")
        self.assertEqual(opts.default_context, "family")
        self.assertEqual(opts.channel_name, "lukas-play")

    def test_parse_space_create_args_from_admin_argv(self) -> None:
        """argv after cmd_admin subcmd slice: ['create', key, ...]."""
        opts = parse_space_create_args(
            ["create", "lukas_play", "--policy", "all_practitioners"]
        )
        self.assertEqual(opts.space_key, "lukas_play")
        self.assertEqual(opts.share_policy, "all_practitioners")

    def test_parse_space_close_args(self) -> None:
        opts = parse_space_close_args(["close", "lukas_play", "--confirm"])
        self.assertEqual(opts.space_key, "lukas_play")
        self.assertTrue(opts.confirm)


class AdminSpaceRegistryTests(unittest.TestCase):
    REGISTRY = {
        "spaces": {"family": {"members": ["kermit"]}},
        "channels": {
            "100": {"type": "shared-river", "mage": "family"},
            "101": {"type": "shared-river", "mage": "old", "archived": True},
        },
        "mages": {
            "kermit": {"discord_id": "1"},
            "nesrine": {"discord_id": "2"},
        },
    }

    def test_validate_space_available_rejects_duplicate(self) -> None:
        with self.assertRaises(ValueError):
            validate_space_available(self.REGISTRY, "family")

    def test_list_active_spaces_skips_archived(self) -> None:
        rows = list_active_spaces(self.REGISTRY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["space_key"], "family")

    def test_shared_river_channel_for_space_skips_archived(self) -> None:
        with patch("share_eddy.get_registry", return_value=self.REGISTRY):
            self.assertEqual(shared_river_channel_for_space("family"), 100)
            self.assertIsNone(shared_river_channel_for_space("old"))


class AdminSpaceArchivedHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved)

    def test_archived_shared_river_not_river_channel(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "channels": {
                    "555": {
                        "type": "shared-river",
                        "mage": "sandbox",
                        "archived": True,
                    }
                }
            }
        )
        self.assertFalse(mage._channel_is_river(555))

    def test_iter_river_channels_skips_archived(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": "native",
                "channels": {
                    "555": {"type": "shared-river", "mage": "sandbox", "archived": True},
                    "556": {"type": "shared-river", "mage": "live"},
                },
            }
        )
        active = MagicMock()
        active.id = 556
        client = MagicMock()
        client.get_channel.side_effect = lambda cid: active if cid == 556 else None
        channels = _iter_river_channels(client)
        self.assertEqual([c.id for c in channels], [556])


class AdminSpaceMemberResolutionTests(unittest.TestCase):
    REGISTRY = {
        "mages": {
            "kermit": {"discord_id": "1"},
            "lukas": {"discord_id": "3"},
        }
    }

    def test_resolve_members_from_mention(self) -> None:
        guild = MagicMock()
        member = MagicMock()
        member.id = 3
        member.display_name = "Lukas"
        guild.get_member.return_value = member
        guild.members = [member]

        keys = resolve_member_keys(
            guild,
            self.REGISTRY,
            member_tokens=["<@3>"],
            message_mentions=[],
            operator_id=1,
        )
        self.assertEqual(keys, ["lukas"])

    def test_resolve_members_from_registry_keys(self) -> None:
        guild = MagicMock()
        guild.members = []

        keys = resolve_member_keys(
            guild,
            self.REGISTRY,
            member_tokens=["kermit", "lukas"],
            message_mentions=[],
            operator_id=1,
        )
        self.assertEqual(keys, ["kermit", "lukas"])

    def test_resolve_at_tokens_via_message_mentions(self) -> None:
        guild = MagicMock()
        guild.members = []
        kermit = MagicMock()
        kermit.id = 1
        kermit.display_name = "Kermit"
        lukas = MagicMock()
        lukas.id = 3
        lukas.display_name = "Lukas"

        keys = resolve_member_keys(
            guild,
            self.REGISTRY,
            member_tokens=["@kermit", "@lukas"],
            message_mentions=[kermit, lukas],
            operator_id=1,
        )
        self.assertEqual(keys, ["kermit", "lukas"])

    def test_unregistered_member_rejected(self) -> None:
        guild = MagicMock()
        member = MagicMock()
        member.id = 9
        member.display_name = "Guest"
        guild.get_member.return_value = member
        guild.members = [member]

        with self.assertRaises(ValueError):
            resolve_member_keys(
                guild,
                self.REGISTRY,
                member_tokens=["<@9>"],
                message_mentions=[],
                operator_id=1,
            )


if __name__ == "__main__":
    unittest.main()
