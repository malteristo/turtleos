"""Tests for dialogue_routing — dispatch path (discord_bot decomposition Slice 1)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import dialogue_routing

try:
    import discord
except ImportError:
    discord = None  # type: ignore[assignment]


class ShouldSkipNativeStarterTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_thread_returns_false(self) -> None:
        message = MagicMock()
        message.channel = MagicMock(spec=[])  # not a Thread
        self.assertFalse(await dialogue_routing.should_skip_native_starter(message))

    async def test_non_native_prompt_returns_false(self) -> None:
        thread = MagicMock(spec=discord.Thread)
        thread.starter_message = MagicMock(id=1)
        message = MagicMock(channel=thread, id=1)
        with patch(
            "dialogue_routing.uses_native_turtle_prompt", return_value=False
        ), patch("dialogue_routing.resolve_dialogue_channel_id", return_value=99):
            self.assertFalse(await dialogue_routing.should_skip_native_starter(message))

    async def test_starter_message_skipped(self) -> None:
        thread = MagicMock(spec=discord.Thread)
        starter = MagicMock(id=42)
        thread.starter_message = starter
        message = MagicMock(channel=thread, id=42)
        with patch(
            "dialogue_routing.uses_native_turtle_prompt", return_value=True
        ), patch("dialogue_routing.resolve_dialogue_channel_id", return_value=99):
            self.assertTrue(await dialogue_routing.should_skip_native_starter(message))

    async def test_non_starter_not_skipped(self) -> None:
        thread = MagicMock(spec=discord.Thread)
        thread.starter_message = MagicMock(id=42)
        message = MagicMock(channel=thread, id=99)
        with patch(
            "dialogue_routing.uses_native_turtle_prompt", return_value=True
        ), patch("dialogue_routing.resolve_dialogue_channel_id", return_value=99):
            self.assertFalse(await dialogue_routing.should_skip_native_starter(message))


class RoutePracticeDialogueTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueues_handler_and_after_turn(self) -> None:
        message = MagicMock()
        message.channel = MagicMock(name="test-eddy", id=123)
        message.content = "hello practice"
        handler = AsyncMock()
        after = AsyncMock()

        with patch("dialogue_queue.enqueue_dialogue", new_callable=AsyncMock) as enqueue:
            await dialogue_routing.route_practice_dialogue(
                message, dialogue_handler=handler, after_turn=after
            )
            enqueue.assert_awaited_once_with(message, handler, after_turn=after)
