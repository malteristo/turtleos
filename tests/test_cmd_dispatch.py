"""Tests for turtle-talk dispatch layer."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import cmd_dispatch as dispatch
from state import dialogue_histories


class TestInjectActDigest(unittest.TestCase):
    def setUp(self) -> None:
        dialogue_histories.clear()

    def test_appends_user_act_line(self) -> None:
        channel_id = 999001
        dialogue_histories[channel_id] = []
        dispatch.inject_act_digest(channel_id, "status", "3 sessions, 2 flows")
        history = dialogue_histories[channel_id]
        self.assertEqual(len(history), 1)
        self.assertIn("[Act: !status]", history[0]["content"])
        self.assertIn("3 sessions", history[0]["content"])
        self.assertEqual(history[0]["role"], "user")

    def test_uses_fallback_when_empty(self) -> None:
        channel_id = 999002
        dialogue_histories[channel_id] = []
        dispatch.inject_act_digest(channel_id, "help", "")
        history = dialogue_histories[channel_id]
        self.assertIn("inventory", history[0]["content"].lower())


class TestSeneschalRegistries(unittest.TestCase):
    def test_lifecycle_not_in_seneschal(self) -> None:
        overlap = dispatch.LIFECYCLE_BAR_COMMANDS & dispatch.SENESCHAL_ACTION_COMMANDS
        self.assertEqual(overlap, set())


class TestDispatchDirectCommand(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_calls_try_and_ensure(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.channel.id = 1
        message.channel.parent_id = None
        message.content = "!status"

        with patch.object(dispatch, "try_direct_command", new_callable=AsyncMock, return_value=True):
            with patch("bar_anchor._ensure_channel_bars_unlocked", new_callable=AsyncMock) as ensure:
                handled = await dispatch.dispatch_direct_command(message, bar_client=MagicMock())
                self.assertTrue(handled)
                ensure.assert_awaited_once()

    async def test_dispatch_defers_bar_for_artifacts(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.channel.id = 1
        message.content = "!artifacts"

        with patch.object(dispatch, "try_direct_command", new_callable=AsyncMock, return_value=True):
            with patch("bar_anchor._ensure_channel_bars_unlocked", new_callable=AsyncMock) as ensure:
                handled = await dispatch.dispatch_direct_command(message, bar_client=MagicMock())
                self.assertTrue(handled)
                ensure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
