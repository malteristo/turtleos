"""Parent-river turtle-talk commands use compact River acts, not Turtle panels."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import commands


class RiverParentCommandTests(unittest.IsolatedAsyncioTestCase):
    def _river_message(self) -> MagicMock:
        message = MagicMock()
        message.channel = MagicMock()
        message.channel.id = 1479428854513664030
        message.channel.parent_id = None
        message.reply = AsyncMock()
        return message

    async def test_help_on_parent_posts_command_act(self) -> None:
        message = self._river_message()
        with patch("commands.is_river_message", return_value=True):
            with patch("commands.post_command_act", new_callable=AsyncMock) as act:
                digest = await commands.cmd_help(message)
        message.reply.assert_not_called()
        act.assert_awaited_once()
        self.assertIn("full inventory", digest.lower())

    async def test_readiness_on_parent_posts_command_act(self) -> None:
        message = self._river_message()
        with patch("commands.set_practice_context"):
            with patch("commands.is_river_message", return_value=True):
                with patch("commands.assess_readiness", return_value={
                    "summary": "**Fresh.**",
                    "highest_leverage": None,
                    "dimensions": [],
                }):
                    with patch("commands.post_command_act", new_callable=AsyncMock) as act:
                        with patch("commands.save_readiness_trail"):
                            with patch("commands.get_mage_type", return_value="mage"):
                                with patch("commands.get_mage_key", return_value="kermit"):
                                    with patch("commands.get_registry", return_value={"spaces": {}}):
                                        await commands.cmd_readiness(message)
        message.reply.assert_not_called()
        act.assert_awaited_once()


class SpaceReadinessTests(unittest.TestCase):
    def test_empty_family_space_is_fresh_not_scored(self) -> None:
        from readiness import assess_space_substrate
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "boom.md"), "w").close()
            result = assess_space_substrate(tmp, space_key="family")
            self.assertIn("family is fresh", result["summary"].lower())
            self.assertIsNone(result["highest_leverage"])


if __name__ == "__main__":
    unittest.main()
