"""Tests for D1 resume eddy — history reload and native continuity hints."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])


class TestLoadThreadHistory(unittest.IsolatedAsyncioTestCase):
    async def test_loads_turtle_bot_messages_in_split_bot_mode(self) -> None:
        from helpers import load_thread_history
        from state import client

        turtle = MagicMock()
        turtle.id = 555001
        turtle.bot = True
        turtle.content = "Earlier reply from Turtle."
        turtle.author = turtle

        user = MagicMock()
        user.bot = False
        user.author = user
        user.display_name = "Kermit"
        user.content = "We were talking about the trip."

        river = MagicMock()
        river.id = 555002
        river.bot = True
        river.content = "River act digest"
        river.author = river

        async def _history(limit=50, oldest_first=True):
            for msg in (user, turtle, river):
                yield msg

        thread = MagicMock()
        thread.name = "trip planning"
        thread.history = _history

        other_bot = MagicMock()
        other_bot.id = 999999
        client.user = other_bot

        with patch("eddy_spawn.is_turtle_bot_message", side_effect=lambda m: m is turtle):
            loaded = await load_thread_history(thread)

        self.assertEqual(len(loaded), 2)
        self.assertIn("trip", loaded[0]["content"])
        self.assertEqual(loaded[1]["role"], "assistant")
        self.assertIn("Earlier reply", loaded[1]["content"])


class TestNativeRuntimeResume(unittest.TestCase):
    def setUp(self) -> None:
        self.thread_type = type("Thread", (), {})
        import discord_bot

        self._orig_thread = discord_bot.discord.Thread
        discord_bot.discord.Thread = self.thread_type

    def tearDown(self) -> None:
        import discord_bot

        discord_bot.discord.Thread = self._orig_thread

    def _thread_channel(self, name: str):
        channel = MagicMock()
        channel.__class__ = self.thread_type
        channel.name = name
        channel.parent = MagicMock(name="river")
        return channel

    def test_resume_hint_when_prior_history_exists(self) -> None:
        from discord_bot import _build_native_runtime_env

        message = MagicMock()
        message.channel = self._thread_channel("trip planning")

        history = [
            {"role": "user", "content": "[Kermit]: first"},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "[Kermit]: picking up again"},
        ]
        env = _build_native_runtime_env(message, {}, history)
        self.assertIn("**Resume:**", env)
        self.assertIn("Do not ask them to recap", env)

    def test_no_resume_hint_on_first_turn(self) -> None:
        from discord_bot import _build_native_runtime_env

        message = MagicMock()
        message.channel = self._thread_channel("new topic")

        history = [{"role": "user", "content": "[Kermit]: hello"}]
        env = _build_native_runtime_env(message, {"blank_eddy": True}, history)
        self.assertNotIn("**Resume:**", env)

    def test_injects_thread_card_when_present(self) -> None:
        from discord_bot import _build_native_runtime_env

        message = MagicMock()
        message.channel = self._thread_channel("saved thread")

        card = "# Thread Card: saved thread\n\n## Last User Move\npacking list\n"
        with patch("dialogue_runtime.read_thread_state", return_value=card):
            env = _build_native_runtime_env(message, {}, [{"role": "user", "content": "hi"}])
        self.assertIn("## Thread continuity", env)
        self.assertIn("packing list", env)


if __name__ == "__main__":
    unittest.main()
