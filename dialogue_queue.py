"""Per-channel dialogue queue — LLM turns run outside channel locks.

Serialization per channel was here from the start and was never the problem.
The 2026-08-07 read-error investigation found the contention one level up:
four *different* eddies each correctly serialized, all four arriving at a
single Ollama slot (``-np 1``) at once. That gate now lives in ``llm``.

What this module gained is **coalescing**. It used to answer every queued
message in its own turn, so three messages sent in a row while Turtle was
thinking produced three replies — each generated against the conversation as
it stood when that message arrived, and each costing a full turn on a
congested slot. The Mage's ask was exact: *"deal with them one after the
other, while trying to keep the latest state of the conversation in mind
while working off the queue."*

So the drain now looks ahead. When more messages are already queued for the
channel, the handler runs with ``reply=False``: the message is still absorbed
in order — history, attachments, links, activity — and only the generation is
deferred. The last arrival answers, seeing all of them. Nothing is dropped;
the replies collapse, not the record.
"""

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


def _supports_deferred_reply(handler) -> bool:
    """Only defer for handlers that know how to absorb without answering.

    A handler that does not take ``reply`` would silently answer anyway, which
    is the current behaviour and safe — but it must not be *told* to defer, or
    it raises. Tests inject bare handlers; production passes
    ``dialogue_turn.handle_dialogue``.
    """
    import inspect

    try:
        return "reply" in inspect.signature(handler).parameters
    except (TypeError, ValueError):
        return False


async def _drain(channel_id: int) -> None:
    queue = _queues[channel_id]
    try:
        while True:
            try:
                message, handler, after_turn = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            # Look ahead: another message from this channel is already waiting,
            # so absorb this one and let the newer one answer for both.
            coalesced = not queue.empty() and _supports_deferred_reply(handler)
            try:
                if coalesced:
                    await handler(message, reply=False)
                else:
                    await handler(message)
            except Exception as exc:
                ch = getattr(message.channel, "name", channel_id)
                print(f"Dialogue failed [{ch}]: {type(exc).__name__}: {exc}")
            if after_turn and not coalesced:
                try:
                    await after_turn(message)
                except Exception as exc:
                    print(f"Dialogue after_turn failed: {type(exc).__name__}: {exc}")
            queue.task_done()
    finally:
        _draining.discard(channel_id)
        if not queue.empty():
            asyncio.create_task(_drain(channel_id))
