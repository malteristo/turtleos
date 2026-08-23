"""Discord client for the River bot (acts-only identity, separate from Turtle)."""

import os

import discord

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
# Required for !admin members / onboard / space --members (parity with Turtle).
# Enable "Server Members Intent" on the River Discord application too.
intents.members = True

# Constructed on first access — see the long note in `state.py`. The mirror image
# of the same problem: the Turtle process imports this module too (via
# `home_plan_ui`), so at import time it built River's client and never logged in,
# leaving a second zombie in every process. Two modules, one defect, so both get
# the same shape rather than a fix here and a comment there.
_river_client: "discord.Client | None" = None
_river_client_constructions = 0


def _ensure_river_client() -> "discord.Client":
    global _river_client, _river_client_constructions
    if _river_client is None:
        _river_client = discord.Client(intents=intents)
        _river_client_constructions += 1
    return _river_client


def __getattr__(name: str):
    if name == "river_client":
        return _ensure_river_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def river_bot_token() -> str:
    return os.environ.get("RIVER_BOT_TOKEN", "").strip()


def river_bot_configured() -> bool:
    return bool(river_bot_token())
