"""A home feed starts a session. Every other room does not, and the workshop stays shut."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from channel_primitives import resolve_primitive  # noqa: E402


def _primitive(name: str):
    return resolve_primitive(
        {
            "mages": {"ada": {}},
            "channels": {"7": {"primitive": name, "mage": "ada"}},
        },
        "7",
    )


class WhoMayStartOne(unittest.TestCase):
    def test_only_a_home_offers_it(self):
        import river_handler

        with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("private")):
            self.assertTrue(river_handler.offers_session(7))
        for name in ("shared", "magic", "craft", "partnership", "health"):
            with patch("mage.get_channel_primitive", side_effect=lambda _cid, name=name: _primitive(name)):
                self.assertFalse(river_handler.offers_session(7), name)

    def test_the_home_bar_has_the_button_and_another_room_does_not(self):
        import discord
        import river_handler

        with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("private")):
            home = river_handler.RiverEddyBarView(7)
        labels = [child.label for child in home.children if isinstance(child, discord.ui.Button)]
        self.assertEqual(labels, ["new eddy", "session"])
        self.assertIn("river:bar:session:7", [child.custom_id for child in home.children])

        with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("shared")):
            shared = river_handler.RiverEddyBarView(7)
        shared_labels = [child.label for child in shared.children if isinstance(child, discord.ui.Button)]
        self.assertNotIn("session", shared_labels)


class ThePress(unittest.IsolatedAsyncioTestCase):
    def _interaction(self):
        interaction = MagicMock()
        interaction.channel.id = 7
        interaction.user = MagicMock()
        interaction.message.delete = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.client = MagicMock()
        return interaction

    async def test_it_opens_in_this_channel_and_does_not_summon(self):
        import river_handler

        interaction = self._interaction()
        thread = MagicMock()
        thread.id = 99
        thread.edit = AsyncMock()
        thread.send = AsyncMock()
        with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("private")), patch(
            "river_handler._spawn_eddy_from_anchor", new=AsyncMock(return_value=thread)
        ) as spawn, patch(
            "river_handler._greet_summon", new=AsyncMock()
        ) as greet, patch(
            "river_handler.reconcile_river_bar_floor", new=AsyncMock()
        ), patch("eddy_spawn.pop_awaiting_title"), patch("thread_registry.update_thread_name"), patch(
            "workshop_tools.room_checkout", side_effect=AssertionError("the workshop opened")
        ):
            await river_handler._open_home_session(interaction)
        spawn.assert_awaited_once()
        self.assertIs(spawn.await_args.args[0], interaction.channel)
        greet.assert_not_awaited()
        thread.send.assert_awaited_once_with(river_handler.HOME_SESSION)
        thread.edit.assert_awaited_once_with(name="session")
        interaction.followup.send.assert_not_awaited()

    async def test_a_press_outside_home_opens_nothing(self):
        import river_handler

        interaction = self._interaction()
        with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("shared")), patch(
            "river_handler._spawn_eddy_from_anchor", new=AsyncMock()
        ) as spawn:
            await river_handler._open_home_session(interaction)
        spawn.assert_not_awaited()
        interaction.followup.send.assert_awaited_once()
        self.assertIn("home", interaction.followup.send.await_args.args[0])

    async def test_the_owners_session_can_work_on_the_platform(self):
        import river_handler
        from boom_takeup import is_platform_session

        interaction = self._interaction()
        thread = MagicMock()
        thread.id = 99
        thread.edit = AsyncMock()
        thread.send = AsyncMock()
        with TemporaryDirectory() as tmp:
            shop = Path(tmp) / "workshop"
            shop.mkdir()
            (shop / ".git").mkdir()
            registry = {
                "mages": {"ada": {"workshop": {"checkout": str(shop)}}},
                "channels": {"7": {"primitive": "private", "mage": "ada"}},
            }
            with patch("mage.get_channel_primitive", side_effect=lambda _cid: _primitive("private")), patch(
                "mage.get_registry", return_value=registry
            ), patch("mage.get_runtime_dir", return_value=tmp), patch(
                "river_handler._spawn_eddy_from_anchor", new=AsyncMock(return_value=thread)
            ), patch("river_handler._greet_summon", new=AsyncMock()) as greet, patch(
                "river_handler.reconcile_river_bar_floor", new=AsyncMock()
            ), patch("river_handler._name_session", new=AsyncMock()) as name, patch(
                "workshop_tools.room_checkout", side_effect=AssertionError("the workshop opened")
            ):
                await river_handler._open_home_session(interaction)
            self.assertTrue(is_platform_session(tmp, 99))
        greet.assert_not_awaited()
        name.assert_awaited_once()
        thread.edit.assert_not_awaited()
        thread.send.assert_awaited_once_with(river_handler.HOME_SESSION_PLATFORM)
