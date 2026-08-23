"""Craft eddy model routing — frontier CRAFT_MODEL, not local Gemma."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
discord = sys.modules["discord"]
discord.HTTPException = type("HTTPException", (Exception,), {})
discord.ChannelType = MagicMock(public_thread="public_thread")
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import mage
from core import models


class CraftModelConfigTests(unittest.TestCase):
    def test_craft_model_defaults_to_claude(self) -> None:
        self.assertTrue(models.CRAFT_MODEL.startswith("claude-"))

    def test_state_exports_craft_model(self) -> None:
        from state import CRAFT_MODEL

        self.assertEqual(CRAFT_MODEL, models.CRAFT_MODEL)


class CraftBlankEddyModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_craft_spawn_stamps_api_model(self) -> None:
        from eddy_spawn import spawn_blank_river_eddy

        channel = MagicMock()
        channel.id = 99001
        channel.name = "craft-turtle"
        fake_thread = MagicMock()
        fake_thread.id = 42
        fake_thread.name = "new eddy"
        channel.create_thread = AsyncMock(return_value=fake_thread)

        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": "native",
                "channels": {
                    str(channel.id): {
                        "type": "craft",
                        "attunement": "craft",
                        "mage": "kermit",
                    }
                },
                "mages": {"kermit": {"discord_id": "1"}},
            }
        )

        with patch(
            "eddy_spawn._materialize_client_for_channel", return_value=MagicMock()
        ), patch(
            "mage.river_bot_enabled", return_value=False
        ), patch(
            "eddy_spawn.ensure_shared_river_parent_access", new=AsyncMock()
        ), patch(
            "eddy_spawn.add_users_to_thread", new=AsyncMock()
        ), patch(
            "thread_registry.register_thread"
        ), patch(
            "eddy_spawn.write_awaiting_title"
        ), patch(
            "commands.thread_configs", {}
        ) as configs, patch(
            "llm.resolve_model", return_value=("claude-sonnet-4-6", True)
        ) as resolve, patch(
            "mage.get_thread_member_ids", return_value=[]
        ):
            thread = await spawn_blank_river_eddy(channel)
            self.assertIs(thread, fake_thread)
            resolve.assert_called_with(models.CRAFT_MODEL)
            cfg = configs[42]
            self.assertEqual(cfg["model"], "claude-sonnet-4-6")
            self.assertTrue(cfg["use_api"])
            self.assertEqual(cfg["model_label"], "api")

    async def test_native_spawn_stays_local_turtle(self) -> None:
        from eddy_spawn import spawn_blank_river_eddy
        from state import TURTLE_MODEL

        channel = MagicMock()
        channel.id = 111
        channel.name = "river"
        fake_thread = MagicMock()
        fake_thread.id = 7
        fake_thread.name = "new eddy"
        channel.create_thread = AsyncMock(return_value=fake_thread)

        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": "native",
                "channels": {
                    "111": {"type": "river", "mage": "kermit"},
                },
                "mages": {"kermit": {"discord_id": "1"}},
            }
        )

        with patch(
            "eddy_spawn._materialize_client_for_channel", return_value=MagicMock()
        ), patch(
            "mage.river_bot_enabled", return_value=False
        ), patch(
            "eddy_spawn.ensure_shared_river_parent_access", new=AsyncMock()
        ), patch(
            "eddy_spawn.add_users_to_thread", new=AsyncMock()
        ), patch(
            "thread_registry.register_thread"
        ), patch(
            "eddy_spawn.write_awaiting_title"
        ), patch(
            "commands.thread_configs", {}
        ) as configs, patch(
            "mage.get_thread_member_ids", return_value=[]
        ):
            await spawn_blank_river_eddy(channel)
            cfg = configs[7]
            self.assertEqual(cfg["model"], TURTLE_MODEL)
            self.assertFalse(cfg["use_api"])
            self.assertEqual(cfg["model_label"], "local")


if __name__ == "__main__":
    unittest.main()
