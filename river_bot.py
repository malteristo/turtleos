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
    get_actor_key,
    get_registry,
    get_channel_primitive,
    resolve_dialogue_channel_id,
    get_current_channel_primitive,
    get_pd,
    get_runtime_dir,
    is_practice_channel,
    is_river_message,
    maybe_reload_mage_registry,
    reload_mage_registry,
    set_practice_context,
    set_practice_context_for_channel,
)
from mage import _get_channel_type
from first_eddy_handoff import maybe_request_first_eddy_dialogue
from river_handler import ensure_river_eddy_bar, handle_eddy_first_message
from hosted_river_onboarding import ensure_hosted_river_onboarding
from river_keys import try_river_key_claim
from river_state import river_bot_token, river_client
from state import SPIRIT_BOT_ID, get_channel_lock
from spirit_voice import bind as bind_spirit_voice

bind_spirit_voice(
    lambda message: getattr(get_channel_primitive(resolve_dialogue_channel_id(message)), "name", None)
)


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
    from spirit_voice import is_own_voice

    if is_own_voice(message):
        return False  # a magic room's own reply (spirit_voice)
    return True


@river_client.event
async def on_ready():
    reload_mage_registry()
    try:
        from delegate_setup_ui import register_delegate_views

        register_delegate_views(river_client, get_registry)
    except Exception as exc:
        print(f"Delegate key view failed: {exc}")
    try:
        from boom_takeup import arm_takeup

        arm_takeup(river_client)
    except Exception as exc:
        print(f"Take this up button failed: {exc}")
    try:
        from dialogue_turn import open_trace_calls
        from trace_calls import arm_calls, bind_open

        bind_open(open_trace_calls)
        arm_calls(river_client)
        from cloud_stocked import arm_stocked, bind_resume
        from dialogue_turn import resume_stocked

        bind_resume(resume_stocked)
        arm_stocked(river_client)
    except Exception as exc:
        print(f"Calls button failed: {exc}")
    try:
        from room_models import arm_model_menu

        from river_handler import refresh_river_bar

        arm_model_menu(river_client, get_registry, resolve_dialogue_channel_id, refresh_river_bar)
    except Exception as exc:
        print(f"Model menu failed: {exc}")
    try:
        from backlog_feed_ui import arm_feed
        from eddy_spawn import spawn_blank_river_eddy
        from share_targets import practice_dir_for_mage

        arm_feed(river_client, get_registry, practice_dir_for_mage, spawn_eddy=spawn_blank_river_eddy)
    except Exception as exc:
        print(f"Backlog feed failed: {exc}")
    try:
        # Armed here, not in the native setup below: that setup awaits several things
        # before it would reach this, and a door that was never bound answers every
        # check with "nobody is signed in" (`outgoing_connections.shell`).
        from mage import get_current_channel_id, list_registered_runtime_dirs
        from outgoing_connect_ui import register_outgoing_views
        from outgoing_connections import Shell

        register_outgoing_views(
            river_client, Shell(get_registry, get_actor_key, get_runtime_dir, list_registered_runtime_dirs, get_current_channel_id)
        )
    except Exception as exc:
        print(f"Outgoing connections view failed: {exc}")
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
                from eddy_lifecycle_bar import (
                    rehydrate_lifecycle_bar_views,
                    withdraw_operator_lifecycle_bars,
                )

                hidden = await withdraw_operator_lifecycle_bars(river_client)
                print(f"Lifecycle bars hidden: {hidden}")
                restored = rehydrate_lifecycle_bar_views(river_client)
                print(f"Lifecycle bars restored: {restored}")
            except Exception as exc:
                print(f"River startup setup failed: {exc}")
            try:
                from mcp_access.registry import load_registry
                from mcp_connect_ui import rehydrate_connect_views

                print(f"MCP connect offers restored: {rehydrate_connect_views(river_client, load_registry)}")
            except Exception as exc:
                print(f"MCP connect rehydrate failed: {type(exc).__name__}: {exc}")
            try:
                from mcp_access.registry import load_registry
                from mcp_reveal_ui import restore_reveal_cards

                print(f"MCP reveal cards restored: {await restore_reveal_cards(river_client, load_registry)}")
            except Exception as exc:
                print(f"MCP reveal rehydrate failed: {type(exc).__name__}: {exc}")
            try:
                from health_checkin_ui import register_state_checkin_view

                register_state_checkin_view(river_client, get_registry)
                print("State check-in buttons registered")
            except Exception as exc:
                print(f"State check-in buttons failed: {type(exc).__name__}: {exc}")

        asyncio.create_task(_setup_native_river())
        _start_heartbeat_once()
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


_heartbeat_task: asyncio.Task | None = None


def _start_heartbeat_once() -> None:
    """on_ready fires again on every reconnect; one heartbeat, not one per reconnect."""
    global _heartbeat_task
    if _heartbeat_task is not None and not _heartbeat_task.done():
        return
    from helpers import log_activity
    from river_heartbeat import run_forever

    async def report(summary: str) -> None:
        from state import CHANNELS

        ch_id = CHANNELS.get("dialogue")
        channel = river_client.get_channel(int(ch_id)) if ch_id else None
        if channel is None:
            print(f"River heartbeat report (no ops channel): {summary}")
            return
        await log_activity(summary, "\U0001f493", channel=channel)

    _heartbeat_task = asyncio.create_task(run_forever(river_client, _house_chores(), report))


def _house_chores():
    """River's periodic chores. Each changes the registry only toward what Discord
    shows, re-applies access the registry grants, or does what an event handler
    would have done had the bot been up (missed joins). Renames and departs stay
    explicit admin acts and are only reported (house check)."""
    from river_heartbeat import Chore, live_channels, record_discord_state, report_if_changed

    async def connection_offers(client):
        from mcp_access.registry import load_registry
        from mcp_connect_ui import announce_pickups, post_pending_offers

        posted = await post_pending_offers(client, load_registry)
        announced = await announce_pickups(client, load_registry)
        if posted or announced:
            print(f"MCP connect offers posted: {posted}; pickups announced: {announced}")

    async def eddy_bars(client):
        from river_handler import sweep_river_bar_floors

        if get_attunement_profile() == "native":
            await sweep_river_bar_floors(client)

    async def discord_names(client):
        from admin_experience import iter_river_rows
        from river_keys import update_registry

        live = live_channels(client)
        if not live:
            return None
        changes: list[str] = []

        def mutate(registry: dict) -> bool:
            homes = {r.channel_id for r in iter_river_rows(registry) if r.ch_type != "unclaimed-river"}
            changes.extend(record_discord_state(registry, live, homes))
            return bool(changes)

        update_registry(mutate)
        return ("Recorded what Discord shows — " + "; ".join(changes)) if changes else None

    async def shared_access(client):
        from mage import sync_shared_river_channel_access

        await sync_shared_river_channel_access(client)

    async def house_check(client):
        from admin_experience import collect_doctor_findings
        from mage import maybe_reload_mage_registry

        guilds = getattr(client, "guilds", []) or []
        if not guilds:
            return None
        maybe_reload_mage_registry()
        lines = [
            line for line in collect_doctor_findings(get_registry(), guilds[0])
            if line.startswith("\u26a0")
        ]
        return report_if_changed(lines)

    async def cloud_credit(client):
        import anthropic

        from cloud_fallback import probe_hold
        from state import ANTHROPIC_API_KEY

        async def ask(model: str) -> None:
            aclient = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
            await aclient.messages.create(
                model=model, max_tokens=1, messages=[{"role": "user", "content": "."}]
            )

        return await probe_hold(ask)

    async def missed_joins(client):
        from roster_sync import admit_missed_joins

        guilds = getattr(client, "guilds", []) or []
        lines = await admit_missed_joins(guilds[0]) if guilds else []
        return "\n".join(lines) or None

    async def error_triage(client):
        from pathlib import Path

        from error_triage import run_nightly
        from llm import chat_ollama_json
        from state import REFLECTION_MODEL

        async def ask(prompt: str) -> str:
            return await chat_ollama_json(prompt, model=REFLECTION_MODEL, num_ctx=8192, timeout_s=600)

        root = Path(__file__).resolve().parent
        return await run_nightly(
            root / "logs", root / "issues", ask, report_json=root / "test-runs" / "ops-report-latest.json"
        )

    async def eddy_membership(client):
        if get_attunement_profile() == "native":
            await _rejoin_practice_threads(client)

    async def outgoing_health(client):
        import asyncio

        from outgoing_connections import tend_outgoing

        return await asyncio.to_thread(tend_outgoing)

    async def mcp_receipts(client):
        from mcp_access.registry import load_registry
        from mcp_receipt_post import post_pending

        n = await post_pending(client, load_registry)
        if n:
            print(f"MCP receipts posted: {n}")
        return None

    async def craft_feed(client):
        from backlog_feed_ui import feed_chore

        return await feed_chore(client)

    return [
        Chore("outgoing_health", 60, outgoing_health),
        Chore("mcp_receipts", 30, mcp_receipts),
        Chore("connection_offers", 60, connection_offers),
        Chore("eddy_bars", 180, eddy_bars),
        Chore("discord_names", 10 * 60, discord_names),
        # on_ready already ran these two; the first beat must not repeat them
        # (a doubled rejoin pass hit Discord's rate limit on 09-27).
        Chore("shared_access", 30 * 60, shared_access, first_after=30 * 60),
        Chore("eddy_membership", 30 * 60, eddy_membership, first_after=30 * 60),
        Chore("house_check", 6 * 3600, house_check),
        Chore("cloud_credit", 60, cloud_credit),
        Chore("missed_joins", 15 * 60, missed_joins, first_after=2 * 60),
        Chore("error_triage", 30 * 60, error_triage),
        # A row with no pitch gets one. The channel opts in with `push: true`.
        Chore("craft_feed", 10 * 60, craft_feed, first_after=2 * 60),
    ]


async def _ensure_turtle_in_eddy(thread: discord.Thread) -> None:
    """Re-add Turtle when membership dropped — cheap no-op if already present.

    In a magic room, Spirit is added too. Turtle's process runs the turn;
    Spirit is the account that posts the reply.
    """
    try:
        from eddy_spawn import river_add_spirit_to_eddy, river_add_turtle_to_eddy
        from mage import get_channel_primitive

        await river_add_turtle_to_eddy(thread)
        parent = getattr(thread, "parent_id", None)
        primitive = get_channel_primitive(parent) if isinstance(parent, int) else None
        if getattr(primitive, "name", None) == "magic":
            await river_add_spirit_to_eddy(thread)
    except Exception as exc:
        print(f"River ensure Turtle in eddy failed: {type(exc).__name__}: {exc}")


async def _rejoin_practice_threads(client) -> None:
    """Join active eddy threads on every practice parent after restart.

    Operator dialogue alone is not enough — shared-river / hosted-river eddies
    (e.g. a shared sandbox eddy) go deaf if River never rejoins them.

    Uses guild.active_threads() rather than channel.threads: the cache only
    lists threads the bot already knows, so quiet shared-river eddies would
    otherwise be skipped forever after a cold restart.
    """
    from mage import practice_parent_channel_ids
    from river_handler import _resolve_client_channel

    parent_ids = set(practice_parent_channel_ids())
    if not parent_ids:
        return

    guild = None
    for ch_id in parent_ids:
        ch = await _resolve_client_channel(client, ch_id)
        if ch is not None and getattr(ch, "guild", None) is not None:
            guild = ch.guild
            break
    if guild is None:
        return

    try:
        active = await guild.active_threads()
    except discord.HTTPException as exc:
        print(f"River active_threads fetch failed: {exc}")
        return

    for thread in active:
        parent_id = getattr(thread, "parent_id", None)
        if parent_id not in parent_ids:
            continue
        parent = client.get_channel(parent_id) if parent_id else None
        parent_name = getattr(parent, "name", parent_id)
        try:
            await thread.join()
            print(
                f"River rejoined thread: {thread.name} ({thread.id}) "
                f"in #{parent_name}"
            )
            await asyncio.sleep(1)
        except discord.HTTPException as exc:
            print(f"River rejoin skipped {thread.name}: {exc}")
            await asyncio.sleep(2)


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

    # INT-046: context before catchup — ambient get_pd() falls to the primary.
    set_practice_context(message)
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id:
        set_practice_context_for_channel(message.channel.parent_id)
    else:
        set_practice_context_for_channel(message.channel.id)

    from story_daily import maybe_run_daily_note_catchup

    await maybe_run_daily_note_catchup()

    # Universal turtle-talk handler (river + eddies; Mage, Spirit, practitioners)
    if message.content.strip().startswith("!"):
        from commands import dispatch_direct_command

        if await dispatch_direct_command(message, bar_client=river_client):
            print(f"River act [!{message.content.split()[0][1:]}] in #{getattr(message.channel, 'name', message.channel.id)}")
        return

    if isinstance(message.channel, discord.Thread):
        parent_id = message.channel.parent_id
        if not parent_id:
            return
        from eddy_lifecycle_bar import (
            is_ellipsis_glance,
            is_go_breath,
            post_ellipsis_glance,
            post_ellipsis_memory,
        )

        if is_ellipsis_glance(message.content):
            await _ensure_turtle_in_eddy(message.channel)
            from magic_prompt import spirit_owns_the_pair

            if spirit_owns_the_pair(getattr(get_channel_primitive(parent_id), "name", None)):
                return  # Spirit arrives; this is not Turtle's Memory glance
            try:
                await post_ellipsis_glance(message.channel, river_client)
            except Exception as exc:
                print(f"Ellipsis glance failed: {type(exc).__name__}: {exc}")
            await post_ellipsis_memory(message.channel, river_client)
            return

        if is_go_breath(message.content):
            await _ensure_turtle_in_eddy(message.channel)
            from magic_prompt import spirit_owns_the_pair

            if spirit_owns_the_pair(getattr(get_channel_primitive(parent_id), "name", None)):
                return  # Spirit goes on; no Checkpoint / Share bar
            from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

            await touch_eddy_lifecycle_bar(message, from_practitioner=True)
            return
        from eddy_spawn import is_awaiting_title, is_awaiting_flow_intake

        if is_awaiting_flow_intake(message.channel.id, parent_id):
            from flow_intake_handler import practitioner_message_ends_intake_wait

            if not practitioner_message_ends_intake_wait(message.channel.id, parent_id):
                return
        if is_awaiting_title(message.channel.id, parent_id):
            lock = get_channel_lock(message.channel.id)
            async with lock:
                renamed = await handle_eddy_first_message(message)
                maybe_request_first_eddy_dialogue(
                    message, renamed=renamed, runtime_dir=get_runtime_dir()
                )
            from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

            await _ensure_turtle_in_eddy(message.channel)
            await touch_eddy_lifecycle_bar(message, from_practitioner=True)
            _maybe_schedule_contextual_offer(message)
            return

        from eddy_lifecycle_bar import touch_eddy_lifecycle_bar

        # Established eddy: re-ensure Turtle membership before acts so dialogue
        # does not stay silent after restart/membership drop (Galactic Adventure).
        await _ensure_turtle_in_eddy(message.channel)
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

    from bar_anchor import schedule_river_bar_reconcile
    from craft_intake import schedule_craft_intake
    from primitive_runtime import dispatch_parent_message
    from river_handler import handle_river_message

    primitive = get_current_channel_primitive()
    if primitive is not None and primitive.name == "health":
        from health_record_ui import maybe_capture_checkin
        from helpers import local_now

        async with get_channel_lock(message.channel.id):
            if await maybe_capture_checkin(
                message,
                primitive,
                practice_dir=get_pd(),
                actor=get_actor_key(),
                today=local_now().date(),
            ):
                return

    await dispatch_parent_message(
        message,
        river_client,
        primitive,
        lock=get_channel_lock(message.channel.id),
        craft_handler=schedule_craft_intake,
        river_handler=handle_river_message,
        reconcile_bar=schedule_river_bar_reconcile,
    )


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
    from turn_trace import install_timestamps

    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    install_timestamps()
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, force=True)
    river_client.run(token)


if __name__ == "__main__":
    main()
