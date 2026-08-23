"""Tests for per-channel dialogue queue."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import dialogue_queue


class TestDialogueQueue(unittest.IsolatedAsyncioTestCase):
    async def test_serializes_same_channel(self) -> None:
        dialogue_queue._queues.clear()
        dialogue_queue._draining.clear()
        order: list[int] = []

        async def handler(message):
            order.append(message.id)
            await asyncio.sleep(0.05)

        m1 = MagicMock()
        m1.channel.id = 1
        m1.id = 1
        m2 = MagicMock()
        m2.channel.id = 1
        m2.id = 2

        await dialogue_queue.enqueue_dialogue(m1, handler)
        await dialogue_queue.enqueue_dialogue(m2, handler)
        await asyncio.sleep(0.2)
        self.assertEqual(order, [1, 2])


if __name__ == "__main__":
    unittest.main()
