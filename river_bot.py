#!/usr/bin/env python3
"""River bot — acts-only identity for native river channels (TURTLE_SPEC §5).

Separate Discord application from Turtle. Handles structured acts in the main
river channel and turtle-talk `!` commands everywhere in practice channels;
Turtle speaks only inside eddies (prose, not acts).

Requires RIVER_BOT_TOKEN and attunement: native in mage_registry.yaml.
When RIVER_BOT_TOKEN is unset, discord_bot.py handles the River harness alone.
"""

from __future__ import annotations

import fcntl
import logging
import os
import sys
import asyncio

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
    maybe_reload_mage_registry,
    reload_mage_registry,
    set_practice_context,
    set_practice_context_for_channel,
)
from mage import _get_channel_type
from river_handler import ensure_river_eddy_bar, handle_eddy_first_message, handle_river_message
from hosted_river_onboarding import ensure_hosted_river_onboarding
from river_keys import try_river_key_claim
from river_state import river_bot_token, river_client
from state import SPIRIT_BOT_ID, get_channel_lock


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


def _maybe_schedule_contextual_offer(message: discord.Message) -> None:
    from river_eddy_seneschal import schedule_contextual_offer_after_practitioner_turn

    schedule_contextual_offer_after_practitioner_turn(message)


def _accept_message_author(message: discord.Message) -> bool:
    if message.author == river_client.user:
        return False
    if message.author.bot and message.author.id != SPIRIT_BOT_ID:
        return False
    return True


@river_client.event
async def on_ready():
    reload_mage_registry()
    user = river_client.user
    name = user.name if user else "?"
    print(f"River online: {name}#{getattr(user, 'discriminator', '0')}")
    print(f"Attunement profile: {get_attunement_profile()}")
    if get_attunement_profile() == "native":
        async def _setup_native_river() -> None:
            try:
                await ensure_river_eddy_bar(river_client)
                await ensure_hosted_river_onboarding(river_client)
                from share_eddy import register_persistent_share_views

                register_persistent_share_views(river_client)
                from eddy_flow_library import retire_standing_flow_library_bars

                await retire_standing_flow_library_bars(river_client)
            except Exception as exc:
                print(f"River startup setup failed: {exc}")

        asyncio.create_task(_setup_native_river())
        try:
            from mage import sync_shared_river_channel_access

            await sync_shared_river_channel_access(river_client)
        except Exception as exc:
            print(f"Shared-river channel sync failed: {exc}")
    print("River bot ready — acts + turtle-talk in practice channels")
    if get_attunement_profile() == "native":
        try:
            await _rejoin_practice_threads(river_client)
        except Exception as exc:
            print(f"River thread rejoin failed: {exc}")


async def _rejoin_practice_threads(client) -> None:
    """Join active eddy threads so River receives practitioner messages after restart."""
    from mage import _resolve_dialogue_channel_id

    dialogue_id = _resolve_dialogue_channel_id()
    if not dialogue_id:
        return
    dialogue = client.get_channel(dialogue_id)
    if dialogue is None:
        try:
            dialogue = await client.fetch_channel(dialogue_id)
        except discord.HTTPException:
            return
    for thread in dialogue.threads:
        try:
            await thread.join()
            print(f"River rejoined thread: {thread.name} ({thread.id})")
        except discord.HTTPException as exc:
            print(f"River rejoin skipped {thread.name}: {exc}")


@river_client.event
async def on_message(message: discord.Message):
    if message.author == river_client.user:
        return

    if not _accept_message_author(message):
        return
    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        return
    maybe_reload_mage_registry()
    if not is_practice_channel(message):
        return
    if get_attunement_profile() != "native":
        return

    # Universal turtle-talk handler (river + eddies; Mage, Spirit, practitioners)
    if message.content.strip().startswith("!"):
        set_practice_context(message)
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id:
            set_practice_context_for_channel(message.channel.parent_id)
        else:
            set_practice_context_for_channel(message.channel.id)
        from commands import dispatch_direct_command

        if await dispatch_direct_command(message, bar_client=river_client):
            print(f"River act [!{message.content.split()[0][1:]}] in #{getattr(message.channel, 'name', message.channel.id)}")
        return

    if isinstance(message.channel, discord.Thread):
        parent_id = message.channel.parent_id
        if not parent_id:
            return
        set_practice_context(message)
        set_practice_context_for_channel(parent_id)
        from eddy_spawn import is_awaiting_title, is_awaiting_flow_intake

        if is_awaiting_flow_intake(message.channel.id, parent_id):
            return
        if is_awaiting_title(message.channel.id, parent_id):
            lock = get_channel_lock(message.channel.id)
            async with lock:
                renamed = await handle_eddy_first_message(message)
            from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

            await touch_eddy_lifecycle_bar(message, from_practitioner=True)
            _maybe_schedule_contextual_offer(message)
            return

        from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

        await touch_eddy_lifecycle_bar(message, from_practitioner=True)
        _maybe_schedule_contextual_offer(message)
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
