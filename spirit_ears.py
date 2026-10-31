"""Spirit hears the press on a card, and does not hear the room.

One gateway, started by the turtle process. A second login would replace
this one, so the river process does not start it. There is no message handler.
"""

from __future__ import annotations

import asyncio
import os

import discord

_task = None


def listen() -> None:
    global _task
    token = os.environ.get("SPIRIT_BOT_TOKEN", "").strip()
    if not token or (_task is not None and not _task.done()):
        return
    client = discord.Client(intents=discord.Intents.none())

    @client.event
    async def on_ready():
        from cloud_stocked import arm_stocked
        from trace_calls import arm_calls

        arm_calls(client)
        arm_stocked(client)
        print("Spirit can hear the calls")

    _task = asyncio.create_task(client.start(token))
