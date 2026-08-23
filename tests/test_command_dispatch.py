"""Tests for River-owned turtle-talk dispatch and act digests."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import commands


class TestActDigest(unittest.TestCase):
    def test_inject_act_digest_appends_user_act_line(self) -> None:
        channel_id = 999001
        commands.dialogue_histories[channel_id] = []
        commands.inject_act_digest(channel_id, "status", "3 sessions, 2 flows")
        history = commands.get_history(channel_id)
        self.assertEqual(len(history), 1)
        self.assertIn("[Act: !status]", history[0]["content"])
        self.assertIn("3 sessions", history[0]["content"])
        self.assertEqual(history[0]["role"], "user")

    def test_inject_uses_fallback_when_empty(self) -> None:
        channel_id = 999002
        commands.dialogue_histories[channel_id] = []
        commands.inject_act_digest(channel_id, "help", "")
        history = commands.get_history(channel_id)
        self.assertIn("inventory", history[0]["content"].lower())

    def test_fetch_act_digest_includes_excerpt(self) -> None:
        resonance = "# Time Emerges\n\n**Source:** x\n\n**Summary:**\n\n- Point one\n- Point two"
        digest = commands.fetch_act_digest("https://example.com/a", resonance)
        self.assertIn("Point one", digest)
        self.assertIn("example.com", digest)


class TestDispatchDirectCommand(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_calls_try_and_ensure(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.channel.id = 1
        message.channel.parent_id = None

        with patch("cmd_dispatch.try_direct_command", new_callable=AsyncMock, return_value=True):
            with patch("bar_anchor._ensure_channel_bars_unlocked", new_callable=AsyncMock) as ensure:
                handled = await commands.dispatch_direct_command(message, bar_client=MagicMock())
                self.assertTrue(handled)
                ensure.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
