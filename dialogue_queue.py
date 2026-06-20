"""Per-channel dialogue queue — LLM turns run outside channel locks."""

from __future__ import annotations

import asyncio

import discord

_queues: dict[int, asyncio.Queue] = {}
_draining: set[int] = set()


async def enqueue_dialogue(
    message: discord.Message,
    handler,
    *,
    after_turn=None,
) -> None:
    """Serialize dialogue turns per channel without holding locks during LLM calls."""
    channel_id = message.channel.id
    queue = _queues.setdefault(channel_id, asyncio.Queue())
    await queue.put((message, handler, after_turn))
    if channel_id in _draining:
        return
    _draining.add(channel_id)
    asyncio.create_task(_drain(channel_id))


async def _drain(channel_id: int) -> None:
    queue = _queues[channel_id]
    try:
        while True:
            try:
                message, handler, after_turn = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                await handler(message)
            except Exception as exc:
                ch = getattr(message.channel, "name", channel_id)
                print(f"Dialogue failed [{ch}]: {type(exc).__name__}: {exc}")
            if after_turn:
                try:
                    await after_turn(message)
                except Exception as exc:
                    print(f"Dialogue after_turn failed: {type(exc).__name__}: {exc}")
            queue.task_done()
    finally:
        _draining.discard(channel_id)
        if not queue.empty():
            asyncio.create_task(_drain(channel_id))
