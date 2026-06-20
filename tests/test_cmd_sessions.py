"""Tests for session lifecycle command handlers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import cmd_sessions as cs
from sessions import CheckpointResult, DissolveResult


class _FakeEmbed:
    def __init__(self, *, title=None, description=None, color=None):
        self.title = title
        self.description = description
        self.color = color

    def set_footer(self, *, text):
        self.footer = text

    def add_field(self, *, name, value, inline=False):
        pass


class _FakeThread:
    pass


class TestCmdCheckpoint(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_short_history(self) -> None:
        message = MagicMock()
        message.channel.id = 1
        message.reply = AsyncMock()

        with patch("cmd_sessions.get_history", return_value=[{"role": "user", "content": "hi"}]), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "hi"}]
        ):
            await cs.cmd_checkpoint(message)

        message.reply.assert_awaited_once()
        self.assertIn("Not enough", message.reply.await_args[0][0])

    async def test_posts_embed_on_success(self) -> None:
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        result = CheckpointResult(session_note="2026-06-20.md")

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch("sessions.checkpoint_session", new_callable=AsyncMock, return_value=result):
            await cs.cmd_checkpoint(message)

        embed = message.reply.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Checkpoint saved")


class TestCmdRelease(unittest.IsolatedAsyncioTestCase):
    async def test_clears_history(self) -> None:
        from state import active_sessions, dialogue_histories

        channel_id = 3
        dialogue_histories[channel_id] = [{"role": "user", "content": "a"}]
        active_sessions[channel_id] = {"closed": False}
        message = MagicMock()
        message.channel.id = channel_id
        message.reply = AsyncMock()

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=dialogue_histories[channel_id] * 2
        ), patch("sessions.checkpoint_session", new_callable=AsyncMock, return_value=CheckpointResult()), patch(
            "cmd_sessions.clear_history"
        ) as clear_mock, patch(
            "cmd_sessions.read_safe", return_value=""
        ), patch("cmd_sessions.get_mage_name", return_value="Kermit"):
            await cs.cmd_release(message)

        clear_mock.assert_called_once_with(channel_id)
        self.assertNotIn(channel_id, active_sessions)

    async def test_release_embed_honest_when_nothing_captured(self) -> None:
        message = MagicMock()
        message.channel.id = 5
        message.reply = AsyncMock()

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        ), patch(
            "sessions.checkpoint_session",
            new_callable=AsyncMock,
            return_value=CheckpointResult(),
        ), patch("cmd_sessions.clear_history"), patch("cmd_sessions.read_safe", return_value=""), patch(
            "cmd_sessions.get_mage_name", return_value="Kermit"
        ):
            await cs.cmd_release(message)

        embed = message.reply.await_args_list[-1].kwargs["embed"]
        self.assertIn("No new resonance captured", embed.description)


class TestCmdDissolve(unittest.IsolatedAsyncioTestCase):
    async def test_requires_thread(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.reply = AsyncMock()

        with patch.object(cs.discord, "Thread", _FakeThread):
            await cs.cmd_dissolve(message, [])

        message.reply.assert_awaited_once()
        self.assertIn("inside an eddy thread", message.reply.await_args[0][0])

    async def test_archives_thread(self) -> None:
        from state import dialogue_histories

        channel_id = 4
        dialogue_histories[channel_id] = [{"role": "user", "content": "hi"}]
        message = MagicMock()
        thread = _FakeThread()
        thread.id = channel_id
        message.channel = thread
        message.reply = AsyncMock()
        result = DissolveResult(thread_name="test-eddy", entry_count=2, jump_url="https://discord.example/jump")

        with patch.object(cs.discord, "Thread", _FakeThread), patch(
            "cmd_sessions.discord.Embed", _FakeEmbed
        ), patch("cmd_sessions.is_practice_channel", return_value=True), patch(
            "cmd_sessions.get_history", return_value=dialogue_histories[channel_id]
        ), patch("sessions.dissolve_eddy", new_callable=AsyncMock, return_value=result):
            await cs.cmd_dissolve(message, [])

        self.assertNotIn(channel_id, dialogue_histories)
        embed = message.reply.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Eddy dissolved")


if __name__ == "__main__":
    unittest.main()
