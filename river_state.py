"""Discord client for the River bot (acts-only identity, separate from Turtle)."""

import os

import discord

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

river_client = discord.Client(intents=intents)


def river_bot_token() -> str:
    return os.environ.get("RIVER_BOT_TOKEN", "").strip()


def river_bot_configured() -> bool:
    return bool(river_bot_token())
