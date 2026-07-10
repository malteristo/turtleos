"""Share eddy delivery — async Discord paths (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import discord

from mage import set_practice_context_for_channel
from share_policy import _received_eddy_notify_config
from share_storage import (
    _share_dir,
    find_received_thread_for_share,
    load_inbox_bundle,
    mark_received_thread_notified,
    save_received_thread_config,
    supersede_stale_share_acts,
    write_inbox_bundle,
)
from share_targets import (
    ShareTarget,
    SpaceShareTarget,
    practice_dir_for_mage,
    river_channel_for_mage,
    runtime_dir_for_mage,
    shared_river_channel_for_space,
    space_member_discord_ids,
)
from share_transcript import (
    build_received_share_embed,
    build_reshare_transparency_embed,
    build_space_share_embed,
    filter_share_history,
    label_shared_history,
    share_label,
)

async def post_reshare_transparency_act(
    bundle: dict[str, Any],
    target: ShareTarget,
    space_key: str,
    *,
    client: discord.Client,
) -> discord.Message | None:
    """Transparency River act in space parent when re-sharing to a practitioner (S4 / Slice 3c)."""
    from bar_anchor import channel_for_client
    from river_handler import _river_client_for_channel

    channel_id = shared_river_channel_for_space(space_key)
    if not channel_id:
        return None

    space_channel = client.get_channel(channel_id)
    if space_channel is None:
        space_channel = await client.fetch_channel(channel_id)

    act_client = _river_client_for_channel(space_channel) or client
    ch = await channel_for_client(space_channel, act_client)
    embed = build_reshare_transparency_embed(bundle, target)
    return await ch.send(embed=embed)


async def _fetch_thread(client: discord.Client, thread_id: int) -> discord.Thread | None:
    ch = client.get_channel(thread_id)
    if ch is None:
        try:
            ch = await client.fetch_channel(thread_id)
        except discord.HTTPException:
            return None
    return ch  # type: ignore[return-value]


async def maybe_post_share_rename_offer(
    thread: discord.Thread,
    draft: dict[str, Any],
    client: discord.Client,
    *,
    suggested: str | None = None,
) -> None:
    """Contextual opt-in rename in the source eddy when title lags the share label."""
    from eddy_flow_library import post_flow_rename_offer

    proposed = (suggested or draft.get("display_title") or "").strip()[:100]
    current = (draft.get("title") or thread.name or "").strip()
    if not proposed or proposed.lower() == current.lower():
        return
    parent_id = thread.parent_id or draft.get("parent_id")
    if not parent_id:
        return
    await post_flow_rename_offer(thread, thread.id, parent_id, proposed, client)


async def notify_sharer_first_peer_reply(
    message: discord.Message,
    cfg: dict[str, Any],
) -> None:
    """@ + River act in sharer's river when recipient first speaks in received eddy."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel
    from state import client as turtle_client

    sharer_key = cfg.get("sharer_key")
    sharer_id = cfg.get("share_creator")
    if not sharer_key or not sharer_id:
        return

    sharer_channel_id = river_channel_for_mage(sharer_key)
    if not sharer_channel_id:
        return

    label = (cfg.get("topic") or message.channel.name)[:100]
    peer = message.author.display_name
    jump = message.channel.jump_url if isinstance(message.channel, discord.Thread) else ""

    client = turtle_client
    channel = client.get_channel(sharer_channel_id)
    if channel is None:
        channel = await client.fetch_channel(sharer_channel_id)

    act_client = _river_client_for_channel(channel) or client
    ch = await channel_for_client(channel, act_client)

    mention = f"<@{sharer_id}>"
    embed = discord.Embed(
        description=(
            f"💬 **{peer}** replied in shared eddy **{label}**"
            + (f" · [open thread]({jump})" if jump else "")
        ),
        color=0x3498DB,
    )
    await ch.send(
        mention,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    sender_pd = practice_dir_for_mage(sharer_key)
    _append_chronicle(
        sender_pd,
        f"💬 {peer} replied in shared eddy · {label}",
        {"thread_id": str(message.channel.id), "jump_url": jump},
    )


def should_notify_sharer_on_first_peer_reply(
    cfg: dict[str, Any],
    author_id: str | int,
) -> bool:
    """True when this practitioner message should trigger sharer notify (received or shared)."""
    if not cfg.get("share_notify_pending"):
        return False
    origin = cfg.get("origin")
    aid = str(author_id)
    if origin == "received":
        return aid == str(cfg.get("share_recipient_id", ""))
    if origin == "shared":
        if aid == str(cfg.get("share_creator", "")):
            return False
        space_key = cfg.get("space_key")
        if space_key:
            members = space_member_discord_ids(space_key)
            if members and aid not in members:
                return False
        return True
    return False


async def maybe_notify_sharer_on_first_peer_reply(message: discord.Message) -> None:
    from commands import thread_configs
    from eddy_lifecycle_bar import is_practitioner_input

    if not isinstance(message.channel, discord.Thread):
        return
    if message.author.bot or not is_practitioner_input(message):
        return

    parent_id = message.channel.parent_id
    cfg = _received_eddy_notify_config(message.channel.id, parent_id)
    if not cfg or cfg.get("origin") not in ("received", "shared"):
        return
    if not should_notify_sharer_on_first_peer_reply(cfg, message.author.id):
        return

    cfg["share_notify_pending"] = False
    in_memory = thread_configs.get(message.channel.id)
    if in_memory is not None:
        in_memory["share_notify_pending"] = False
    runtime_dir = None
    if parent_id:
        set_practice_context_for_channel(parent_id)
        from mage import get_runtime_dir

        runtime_dir = get_runtime_dir()
        mark_received_thread_notified(runtime_dir, message.channel.id)

    try:
        await notify_sharer_first_peer_reply(message, cfg)
    except Exception as exc:
        cfg["share_notify_pending"] = True
        if in_memory is not None:
            in_memory["share_notify_pending"] = True
        if runtime_dir:
            save_received_thread_config(runtime_dir, message.channel.id, cfg)
        print(f"Share sharer notify failed: {type(exc).__name__}: {exc}")


async def deliver_practitioner_share(
    bundle: dict[str, Any],
    target: ShareTarget,
    *,
    client: discord.Client,
) -> discord.Message | None:
    """Post recipient @+River act and write inbox bundle."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel

    bundle = dict(bundle)
    bundle["recipient_mage_key"] = target.mage_key
    bundle["recipient_discord_id"] = target.discord_id
    bundle["recipient_channel_id"] = str(target.channel_id)

    recipient_runtime = runtime_dir_for_mage(target.mage_key)
    write_inbox_bundle(recipient_runtime, bundle)

    recipient_channel = client.get_channel(target.channel_id)
    if recipient_channel is None:
        recipient_channel = await client.fetch_channel(target.channel_id)

    act_client = _river_client_for_channel(recipient_channel) or client
    ch = await channel_for_client(recipient_channel, act_client)

    label = share_label(bundle)
    embed = build_received_share_embed(bundle)
    view = ShareContinueView(bundle["share_id"], target.channel_id)
    act_client.add_view(view)

    mention = f"<@{target.discord_id}>"
    msg = await ch.send(
        f"{mention} — tap **Continue** when you are ready to pick this up in your river.",
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    await supersede_stale_share_acts(
        act_client,
        ch,
        recipient_runtime,
        keep_share_id=bundle["share_id"],
        keep_message_id=msg.id,
    )

    sender_pd = practice_dir_for_mage(bundle["sharer_key"])
    _append_chronicle(
        sender_pd,
        f"📤 Shared to {target.address}: \"{label}\"",
        {"share_id": bundle["share_id"], "target": target.mage_key},
    )

    space_key = bundle.get("transparency_space_key")
    if space_key:
        await post_reshare_transparency_act(
            bundle,
            target,
            space_key,
            client=client,
        )

    return msg


async def materialize_space_shared_eddy(
    channel: discord.abc.GuildChannel,
    bundle: dict[str, Any],
    *,
    client: discord.Client,
) -> discord.Thread:
    """Create space-tagged shared eddy at confirm — sibling thread; digest stays in parent."""
    from commands import thread_configs
    from eddy_spawn import (
        add_users_to_thread,
        ensure_shared_river_parent_access,
        river_add_turtle_to_eddy,
    )
    from helpers import sync_history
    from mage import (
        get_channel_default_context,
        get_effective_attunement,
        get_thread_member_ids,
        set_practice_context_for_channel,
    )
    from thread_registry import register_thread
    from state import EDDY_TYPES, TURTLE_MODEL, dialogue_histories

    set_practice_context_for_channel(channel.id)
    from mage import get_runtime_dir

    runtime_dir = get_runtime_dir()
    label = share_label(bundle)
    eddy_archive = EDDY_TYPES.get("standard", {}).get("archive_minutes", 10080)
    channel_att = get_effective_attunement(channel.id)
    if channel_att == "native":
        model_id = TURTLE_MODEL
        use_api = False
        attunement = "native"
    else:
        from llm import resolve_model

        model_id, use_api = resolve_model("local")
        attunement = "semi"

    thread = await channel.create_thread(
        name=label[:100],
        auto_archive_duration=eddy_archive,
        type=discord.ChannelType.public_thread,
    )

    await river_add_turtle_to_eddy(thread)

    context_type = get_channel_default_context(channel.id) or bundle.get("space_key")
    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": "standard",
        "context_type": context_type,
        "topic": label,
        "origin": "shared",
        "space_key": bundle.get("space_key"),
        "share_id": bundle.get("share_id"),
        "from_sharer": bundle.get("sharer_address", "someone"),
        "share_creator": bundle.get("sharer_id"),
        "sharer_key": bundle.get("sharer_key"),
        "share_notify_pending": True,
        "created": datetime.now(timezone.utc),
        "native_vanilla": channel_att == "native",
        "presence_posted": False,
    }

    history = filter_share_history(bundle.get("history") or [])
    sharer_address = bundle.get("sharer_address", "someone")
    history = label_shared_history(history, sharer_address)
    if history:
        dialogue_histories[thread.id] = list(history)
        sync_history(thread.id)

    await thread.send(embed=build_space_share_embed(bundle))
    await thread.send(
        f"-# 📤 From **{bundle.get('sharer_address', 'someone')}** · shared conversation ready — "
        "Turtle has the full thread; members can jump in when ready.",
        silent=True,
    )

    parent_name = channel.name if hasattr(channel, "name") else "river"
    register_thread(
        thread.id,
        label,
        parent_channel=parent_name,
        model="local",
        attunement=attunement,
        eddy_type="standard",
    )

    await ensure_shared_river_parent_access(channel)
    sharer_id = str(bundle.get("sharer_id", ""))
    member_ids = [
        uid
        for uid in get_thread_member_ids(channel.id)
        if str(uid) != sharer_id
    ]
    await add_users_to_thread(thread, member_ids)

    save_received_thread_config(runtime_dir, thread.id, thread_configs[thread.id])

    outbox = _share_dir(runtime_dir, "outbox") / f"{bundle.get('share_id')}.json"
    outbox.write_text(
        json.dumps(
            {
                **bundle,
                "shared_thread_id": str(thread.id),
                "space_key": bundle.get("space_key"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return thread


async def deliver_space_share(
    bundle: dict[str, Any],
    target: SpaceShareTarget,
    *,
    client: discord.Client,
) -> discord.Message | None:
    """Post space parent digest act, materialize shared eddy, notify members."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel

    bundle = dict(bundle)
    bundle["space_key"] = target.space_key
    bundle["target_kind"] = "space"

    space_channel = client.get_channel(target.channel_id)
    if space_channel is None:
        space_channel = await client.fetch_channel(target.channel_id)

    act_client = _river_client_for_channel(space_channel) or client
    if act_client is not client:
        resolved = act_client.get_channel(target.channel_id)
        if resolved is None:
            resolved = await act_client.fetch_channel(target.channel_id)
        space_channel = resolved

    set_practice_context_for_channel(target.channel_id)
    thread = await materialize_space_shared_eddy(
        space_channel,
        bundle,
        client=act_client,
    )

    ch = await channel_for_client(space_channel, act_client)

    label = share_label(bundle)
    embed = build_space_share_embed(bundle)
    if thread.jump_url:
        embed.add_field(name="Shared eddy", value=f"[Open thread]({thread.jump_url})", inline=False)

    member_ids = space_member_discord_ids(target.space_key, exclude_id=bundle.get("sharer_id"))
    mention = " ".join(f"<@{uid}>" for uid in member_ids)
    lead = (
        f"{mention} — **{bundle['sharer_address']}** shared **“{label}”** with **{target.address}**."
        if mention
        else f"**{bundle['sharer_address']}** shared **“{label}”** with **{target.address}**."
    )
    msg = await ch.send(
        lead,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    sender_pd = practice_dir_for_mage(bundle["sharer_key"])
    _append_chronicle(
        sender_pd,
        f'📤 Shared to {target.address}: "{label}"',
        {
            "share_id": bundle["share_id"],
            "target": target.space_key,
            "thread_id": str(thread.id),
            "jump_url": thread.jump_url,
        },
    )
    return msg


async def materialize_received_eddy(
    interaction: discord.Interaction,
    share_id: str,
    parent_channel_id: int,
) -> discord.Thread | None:
    """Open received eddy — sibling thread; river digest stays untouched.

    Uses channel.create_thread (not message.create_thread) so the digest act
    remains visible in the river on mobile. Digest is reposted inside the eddy.
    """
    from commands import thread_configs
    from eddy_spawn import river_add_turtle_to_eddy
    from helpers import sync_history
    from state import EDDY_TYPES, TURTLE_MODEL, dialogue_histories
    from thread_registry import register_thread

    set_practice_context_for_channel(parent_channel_id)
    from mage import get_runtime_dir

    runtime_dir = get_runtime_dir()
    bundle = load_inbox_bundle(runtime_dir, share_id)
    if not bundle:
        return None

    if str(interaction.user.id) != str(bundle.get("recipient_discord_id", "")):
        raise PermissionError("Only the recipient can continue this share.")

    label = share_label(bundle)
    eddy_archive = EDDY_TYPES.get("standard", {}).get("archive_minutes", 10080)

    existing_id = find_received_thread_for_share(runtime_dir, share_id)
    if existing_id:
        thread = await _fetch_thread(interaction.client, existing_id)
        if thread is not None:
            try:
                await thread.add_user(interaction.user)
            except discord.HTTPException:
                pass
            return thread

    channel = interaction.channel
    if channel is None or not hasattr(channel, "create_thread"):
        return None

    thread = await channel.create_thread(
        name=label[:100],
        auto_archive_duration=eddy_archive,
        type=discord.ChannelType.public_thread,
    )

    await river_add_turtle_to_eddy(thread)
    try:
        await thread.add_user(interaction.user)
    except discord.HTTPException:
        pass

    thread_configs[thread.id] = {
        "model": TURTLE_MODEL,
        "use_api": False,
        "attunement": "native",
        "model_label": "local",
        "eddy_type": "standard",
        "context_type": None,
        "topic": label,
        "origin": "received",
        "share_id": share_id,
        "from_sharer": bundle.get("sharer_address", "someone"),
        "share_creator": bundle.get("sharer_id"),
        "sharer_key": bundle.get("sharer_key"),
        "share_recipient_id": bundle.get("recipient_discord_id"),
        "share_notify_pending": True,
        "created": datetime.now(timezone.utc),
        "native_vanilla": True,
        "presence_posted": False,
    }

    history = filter_share_history(bundle.get("history") or [])
    sharer_address = bundle.get("sharer_address", "someone")
    history = label_shared_history(history, sharer_address)
    if history:
        dialogue_histories[thread.id] = list(history)
        sync_history(thread.id)

    await thread.send(embed=build_received_share_embed(bundle))
    await thread.send(
        f"-# 📥 From **{bundle.get('sharer_address', 'someone')}** · shared conversation ready — "
        "Turtle has the full thread; say hello when you want to continue.",
        silent=True,
    )

    parent_name = interaction.channel.name if interaction.channel else "river"
    register_thread(
        thread.id,
        label,
        parent_channel=parent_name,
        model="local",
        attunement="native",
        eddy_type="standard",
    )

    save_received_thread_config(runtime_dir, thread.id, thread_configs[thread.id])

    return thread


async def continue_received_share(
    interaction: discord.Interaction,
    share_id: str,
    parent_channel_id: int,
) -> discord.Thread | None:
    """Continue contract: thread chip on digest is success feedback; silent on happy path."""
    if interaction.channel and interaction.channel.id != parent_channel_id:
        await interaction.response.send_message("Wrong channel.", ephemeral=True)
        return None
    try:
        await interaction.response.defer(ephemeral=True)
        thread = await materialize_received_eddy(
            interaction,
            share_id,
            parent_channel_id,
        )
    except PermissionError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return None
    except Exception as exc:
        await interaction.followup.send(
            f"Could not open received eddy: {type(exc).__name__}: {exc}",
            ephemeral=True,
        )
        return None
    if not thread:
        return None
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        pass
    return thread


class ShareContinueView(discord.ui.View):
    def __init__(self, share_id: str, parent_channel_id: int):
        super().__init__(timeout=None)
        self._share_id = share_id
        self._parent_channel_id = parent_channel_id
        btn = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.primary,
            emoji="▶️",
            custom_id=f"share:go:{share_id}:{parent_channel_id}",
        )
        btn.callback = self._on_continue
        self.add_item(btn)

    async def _on_continue(self, interaction: discord.Interaction):
        await continue_received_share(
            interaction,
            self._share_id,
            self._parent_channel_id,
        )
