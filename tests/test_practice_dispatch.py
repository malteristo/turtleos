"""Tests for practice_dispatch — on_message branch tree (discord_bot decomposition Slice 6)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import practice_dispatch


class DispatchIncomingMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_ignores_own_messages(self) -> None:
        message = MagicMock()
        message.author = practice_dispatch.client.user

        with patch("practice_dispatch.route_practice_dialogue", new_callable=AsyncMock) as route:
            await practice_dispatch.dispatch_incoming_message(message)
            route.assert_not_awaited()

    async def test_non_practice_channel_no_route(self) -> None:
        message = MagicMock()
        message.author = MagicMock(bot=False, id=123)
        message.author.bot = False
        message.type = practice_dispatch.discord.MessageType.default
        message.content = "hello"
        message.message_snapshots = []

        with patch("practice_dispatch.is_practice_channel", return_value=False), patch(
            "practice_dispatch.route_practice_dialogue", new_callable=AsyncMock
        ) as route:
            await practice_dispatch.dispatch_incoming_message(message)
            route.assert_not_awaited()

    async def test_practice_channel_routes_dialogue(self) -> None:
        message = MagicMock()
        message.author = MagicMock(bot=False, id=123)
        message.author.bot = False
        message.type = practice_dispatch.discord.MessageType.default
        message.content = "hello practice"
        message.message_snapshots = []
        message.id = 999001
        message.channel = MagicMock(spec=[])
        message.channel.id = 123
        message.channel.parent_id = None

        with patch("practice_dispatch.is_practice_channel", return_value=True), patch(
            "practice_dispatch.river_bot_enabled", return_value=False
        ), patch(
            "practice_dispatch.dispatch_direct_command", new_callable=AsyncMock, return_value=False
        ), patch(
            "practice_dispatch.try_founder_key_entry", new_callable=AsyncMock, return_value=False
        ), patch(
            "practice_dispatch.turtle_handles_native_river", return_value=False
        ), patch(
            "practice_dispatch.is_craft_intake_channel", return_value=False
        ), patch(
            "practice_dispatch.route_practice_dialogue", new_callable=AsyncMock
        ) as route, patch.object(practice_dispatch, "_processed_messages", []):
            await practice_dispatch.dispatch_incoming_message(message)
            route.assert_awaited_once_with(message)
