"""Roster sync: Discord humans ≡ turtleOS members.

Positive controls: empty humans with a leftover id is drift; a human
with no registry row is drift. Doctor must not call an empty-cache
guild 'clean'.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub()

from roster_sync import (
    admit_on_join,
    apply_admit_registry,
    apply_depart_registry,
    compute_roster_drift,
    depart_on_leave,
    find_community_space,
    format_roster_doctor_lines,
    is_practice_guild,
    unique_mage_key,
)


def _registry_with_house() -> dict:
    return {
        "mages": {
            "alex": {"discord_id": "1", "relation": "household"},
        },
        "channels": {
            "100": {"mage": "alex", "type": "river"},
            "200": {"mage": "family", "type": "shared-river"},
        },
        "spaces": {
            "family": {"members": ["alex"], "share_policy": "members_only"},
        },
    }


class RosterDriftTests(unittest.TestCase):
    def test_join_without_registry_is_drift(self) -> None:
        drift = compute_roster_drift(
            {"mages": {}, "channels": {}, "spaces": {}},
            human_ids=["99"],
        )
        self.assertEqual(drift.on_discord_not_registered, ("99",))
        self.assertFalse(drift.is_clean())

    def test_leftover_after_leave_is_drift(self) -> None:
        registry = {
            "mages": {"sam": {"discord_id": "42"}},
            "channels": {},
            "spaces": {},
        }
        drift = compute_roster_drift(registry, human_ids=[])
        self.assertEqual(drift.registered_not_on_discord, ("42",))
        self.assertIn("sam", drift.missing_private)

    def test_placeholder_discord_id_is_not_a_member(self) -> None:
        registry = {
            "mages": {"default": {"discord_id": "YOUR_DISCORD_USER_ID"}},
            "channels": {},
            "spaces": {},
        }
        drift = compute_roster_drift(registry, human_ids=[])
        self.assertEqual(drift.registered_not_on_discord, ())

    def test_departed_mage_drops_off_the_live_roster(self) -> None:
        registry = _registry_with_house()
        apply_depart_registry(registry, "alex")
        drift = compute_roster_drift(registry, human_ids=[])
        self.assertEqual(drift.registered_not_on_discord, ())
        self.assertTrue(registry["mages"]["alex"]["departed"])
        self.assertTrue(registry["channels"]["100"]["archived"])
        self.assertNotIn("alex", registry["spaces"]["family"]["members"])

    def test_admit_then_drift_is_clean_when_they_are_on_discord(self) -> None:
        registry = _registry_with_house()
        apply_admit_registry(
            registry,
            mage_key="sam",
            discord_id="42",
            display_name="Sam",
            channel_id=300,
        )
        self.assertEqual(registry["mages"]["sam"]["relation"], "kin")
        self.assertEqual(registry["channels"]["300"]["type"], "hosted-river")
        self.assertIn("sam", registry["spaces"]["family"]["members"])
        drift = compute_roster_drift(registry, human_ids=["1", "42"])
        self.assertTrue(drift.is_clean())
        self.assertEqual(drift.community_space, "family")

    def test_community_prefers_named_community_over_family(self) -> None:
        registry = _registry_with_house()
        registry["channels"]["201"] = {"mage": "community", "type": "shared-river"}
        registry["spaces"]["community"] = {"members": ["alex"]}
        self.assertEqual(find_community_space(registry), "community")

    def test_unique_key_avoids_space_and_mage_collision(self) -> None:
        registry = _registry_with_house()
        self.assertEqual(unique_mage_key("Alex", registry, discord_id="99"), "alex_99")
        self.assertEqual(unique_mage_key("Family", registry, discord_id="7"), "family_7")

    def test_doctor_lines_name_both_sides_of_the_bijection(self) -> None:
        drift = compute_roster_drift(
            {
                "mages": {"ghost": {"discord_id": "7"}},
                "channels": {},
                "spaces": {},
            },
            human_ids=["9"],
        )
        lines = "\n".join(format_roster_doctor_lines(drift))
        self.assertIn("on Discord not in turtleOS", lines)
        self.assertIn("in turtleOS not on Discord", lines)
        self.assertIn("`9`", lines)
        self.assertIn("`7`", lines)

    def test_practice_guild_is_where_a_registry_channel_lives(self) -> None:
        registry = _registry_with_house()
        home = MagicMock()
        home.get_channel.side_effect = lambda cid: MagicMock() if cid == 100 else None
        home.channels = []
        other = MagicMock()
        other.get_channel.return_value = None
        other.channels = []
        self.assertTrue(is_practice_guild(home, registry))
        self.assertFalse(is_practice_guild(other, registry))


class RosterAdmitDepartTests(unittest.IsolatedAsyncioTestCase):
    def _member(self, *, member_id: int = 42, name: str = "sam") -> MagicMock:
        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.id = member_id
        member.name = name
        member.display_name = name.title()
        guild = MagicMock()
        guild.categories = []
        guild.me = MagicMock()
        guild.default_role = MagicMock()
        guild.get_channel.side_effect = lambda cid: MagicMock() if cid in (100, 200) else None
        guild.channels = []
        channel = MagicMock()
        channel.id = 300
        channel.name = "river-sam"
        channel.send = AsyncMock()
        guild.create_text_channel = AsyncMock(return_value=channel)
        member.guild = guild
        return member

    async def test_join_provisions_private_and_community_without_invite(self) -> None:
        registry = _registry_with_house()
        member = self._member()
        family_ch = MagicMock()
        family_ch.id = 200
        member.guild.get_channel.side_effect = (
            lambda cid: family_ch if cid == 200 else (MagicMock() if cid == 100 else None)
        )

        with patch("mage.get_registry", return_value=registry), patch(
            "roster_sync.save_registry"
        ) as save, patch(
            "hosted_river_onboarding.seed_practitioner_workshop"
        ) as seed, patch(
            "discord_reconcile.expect_channel_registry_binding"
        ), patch(
            "mage.ensure_space_channel_access", new_callable=AsyncMock
        ) as seat:
            summary = await admit_on_join(member)

        self.assertIsNotNone(summary)
        self.assertIn("river-sam", summary or "")
        self.assertIn("family", summary or "")
        self.assertNotIn("invite", (summary or "").lower())
        seed.assert_called_once_with("sam")
        save.assert_called()
        seat.assert_awaited()
        self.assertEqual(registry["mages"]["sam"]["discord_id"], "42")
        self.assertIn("sam", registry["spaces"]["family"]["members"])
        member.guild.create_text_channel.assert_awaited_once()

    async def test_join_on_other_guild_does_nothing(self) -> None:
        registry = _registry_with_house()
        member = self._member()
        member.guild.get_channel.side_effect = None
        member.guild.get_channel.return_value = None
        member.guild.channels = []
        with patch("mage.get_registry", return_value=registry), patch(
            "roster_sync.save_registry"
        ) as save:
            summary = await admit_on_join(member)
        self.assertIsNone(summary)
        save.assert_not_called()
        member.guild.create_text_channel.assert_not_called()

    async def test_leave_archives_river_and_drops_community_seat(self) -> None:
        registry = _registry_with_house()
        apply_admit_registry(
            registry,
            mage_key="sam",
            discord_id="42",
            display_name="Sam",
            channel_id=300,
        )
        member = self._member()
        private = MagicMock()
        private.edit = AsyncMock()
        member.guild.get_channel.side_effect = (
            lambda cid: private if cid == 300 else (MagicMock() if cid in (100, 200) else None)
        )

        with patch("mage.get_registry", return_value=registry), patch(
            "roster_sync.save_registry"
        ) as save:
            summary = await depart_on_leave(member)

        self.assertIsNotNone(summary)
        self.assertIn("sam", summary or "")
        self.assertTrue(registry["mages"]["sam"]["departed"])
        self.assertTrue(registry["channels"]["300"]["archived"])
        self.assertNotIn("sam", registry["spaces"]["family"]["members"])
        save.assert_called()
        private.edit.assert_awaited()

    async def test_rejoin_restores_departed_member(self) -> None:
        registry = _registry_with_house()
        apply_admit_registry(
            registry,
            mage_key="sam",
            discord_id="42",
            display_name="Sam",
            channel_id=300,
        )
        apply_depart_registry(registry, "sam")
        member = self._member()
        private = MagicMock()
        private.edit = AsyncMock()
        member.guild.get_channel.side_effect = (
            lambda cid: private if cid == 300 else (MagicMock() if cid in (100, 200) else None)
        )

        with patch("mage.get_registry", return_value=registry), patch(
            "roster_sync.save_registry"
        ), patch("mage.ensure_space_channel_access", new_callable=AsyncMock):
            summary = await admit_on_join(member)

        self.assertIn("Restored", summary or "")
        self.assertFalse(registry["mages"]["sam"].get("departed"))
        self.assertNotIn("archived", registry["channels"]["300"])
        self.assertIn("sam", registry["spaces"]["family"]["members"])
        member.guild.create_text_channel.assert_not_called()

    async def test_already_a_member_does_not_mint_a_second_river(self) -> None:
        registry = _registry_with_house()
        member = self._member(member_id=1, name="alex")
        with patch("mage.get_registry", return_value=registry), patch(
            "roster_sync.save_registry"
        ) as save:
            summary = await admit_on_join(member)
        self.assertIn("Already a member", summary or "")
        member.guild.create_text_channel.assert_not_called()
        save.assert_not_called()


class RosterHookWiringTests(unittest.TestCase):
    def test_join_and_leave_hooks_call_roster_sync(self) -> None:
        src = Path(__file__).resolve().parents[1].joinpath("discord_bot.py").read_text()
        self.assertIn("admit_on_join", src)
        self.assertIn("depart_on_leave", src)
        join = src.split("async def on_member_join", 1)[1].split("async def on_member_remove", 1)[0]
        self.assertNotIn("Use `!admin invite", join)


if __name__ == "__main__":
    unittest.main()
