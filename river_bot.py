#!/usr/bin/env python3
"""River bot — acts-only identity for native river channels (TURTLE_SPEC §5).

Separate Discord application from Turtle. Handles structured acts in the main
river channel; Turtle speaks only inside eddies.

Requires RIVER_BOT_TOKEN and attunement: native in mage_registry.yaml.
When RIVER_BOT_TOKEN is unset, discord_bot.py handles the River harness alone.
"""

from __future__ import annotations

import fcntl
import logging
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def load_env(env_path=None):
    path = env_path or os.environ.get("DOTENV_PATH", ".env")
    if not os.path.isabs(path):
        path = os.path.join(REPO_ROOT, path)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_env()

import discord

from mage import (
    get_attunement_profile,
    is_practice_channel,
    is_river_message,
    reload_mage_registry,
    set_practice_context,
    set_practice_context_for_channel,
)
from mage import _get_channel_type
from river_handler import ensure_river_eddy_bar, handle_eddy_first_message, handle_river_message
from hosted_river_onboarding import ensure_hosted_river_onboarding
from river_keys import try_river_key_claim
from river_state import river_bot_token, river_client
from state import get_channel_lock


def _ensure_single_instance() -> None:
    lock_path = os.path.join(REPO_ROOT, ".river_bot.lock")
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except OSError:
        print("Another river_bot.py is already running. Exiting.", file=sys.stderr)
        sys.exit(1)


@river_client.event
async def on_ready():
    reload_mage_registry()
    user = river_client.user
    name = user.name if user else "?"
    print(f"River online: {name}#{getattr(user, 'discriminator', '0')}")
    print(f"Attunement profile: {get_attunement_profile()}")
    if get_attunement_profile() == "native":
        try:
            await ensure_river_eddy_bar(river_client)
            await ensure_hosted_river_onboarding(river_client)
        except Exception as exc:
            print(f"River startup setup failed: {exc}")
    print("River bot ready — acts only in parent river channels")


@river_client.event
async def on_message(message: discord.Message):
    if message.author == river_client.user:
        return
    if message.author.bot:
        return
    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        return
    if not is_practice_channel(message):
        return
    if get_attunement_profile() != "native":
        return
    if message.content.strip().startswith("!"):
        return

    if isinstance(message.channel, discord.Thread):
        parent_id = message.channel.parent_id
        if not parent_id:
            return
        from eddy_spawn import is_awaiting_title, is_awaiting_flow_intake

        if is_awaiting_flow_intake(message.channel.id, parent_id):
            return
        if not is_awaiting_title(message.channel.id, parent_id):
            return
        set_practice_context(message)
        lock = get_channel_lock(message.channel.id)
        async with lock:
            await handle_eddy_first_message(message)
        from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

        await touch_eddy_lifecycle_bar(message, from_practitioner=True)
        return

    if _get_channel_type(message.channel.id) == "unclaimed-river":
        lock = get_channel_lock(message.channel.id)
        async with lock:
            if await try_river_key_claim(message, river_client):
                return
        return

    if not is_river_message(message):
        return

    print(f"River inbound [{message.author.display_name}]: {message.content[:80]!r}")

    set_practice_context(message)
    set_practice_context_for_channel(message.channel.id)

    lock = get_channel_lock(message.channel.id)
    async with lock:
        await handle_river_message(message)


@river_client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = (interaction.data or {}).get("custom_id", "")
        if custom_id.startswith("eddy:lifecycle:"):
            from eddy_lifecycle_bar import handle_lifecycle_bar_interaction

            await handle_lifecycle_bar_interaction(interaction)


def main() -> None:
    token = river_bot_token()
    if not token:
        print("Error: RIVER_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if "--test" in sys.argv:
        reload_mage_registry()
        print(f"River token: ...{token[-8:]}")
        print(f"Attunement: {get_attunement_profile()}")
        print("Configuration OK.")
        return

    _ensure_single_instance()
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, force=True)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    river_client.run(token)


if __name__ == "__main__":
    main()
