"""River key claim ceremony for unclaimed hosted rivers (invite-to-claim, Option A).

A practice key — operator-assigned emoji the guest chose out of band — binds
their Discord account to a private claim room, which becomes their hosted river.
Not authentication; invitation token plus first-contact ritual.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import discord

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = Path(os.path.expanduser("~/turtleos/mage_registry.yaml"))


def _looks_like_single_key(text: str) -> bool:
    text = text.strip()
    if not text or text.startswith("!") or " " in text or "\n" in text:
        return False
    if text.startswith("<@") or text.startswith("http"):
        return False
    return len(text) <= 16 and any(ord(ch) > 127 for ch in text)


def _primary_operator_ids() -> set[int]:
    from mage import get_registry

    ids: set[int] = set()
    registry = get_registry()
    default_mage = registry.get("default_mage")
    for key, mage in registry.get("mages", {}).items():
        if key == default_mage or mage.get("primary"):
            raw = mage.get("discord_id")
            if raw:
                try:
                    ids.add(int(raw))
                except ValueError:
                    pass
    return ids


def _is_primary_operator(user_id: int) -> bool:
    ids = _primary_operator_ids()
    return bool(ids) and user_id in ids


def _channel_entry(channel_id: int) -> dict | str | None:
    from mage import get_registry

    return get_registry().get("channels", {}).get(str(channel_id))


def is_unclaimed_river(channel_id: int) -> bool:
    entry = _channel_entry(channel_id)
    return isinstance(entry, dict) and entry.get("type") == "unclaimed-river"


def _expected_river_key(channel_id: int) -> str | None:
    entry = _channel_entry(channel_id)
    if not isinstance(entry, dict):
        return None
    key = entry.get("river_key")
    if key:
        return str(key)
    mage_key = entry.get("mage")
    if not mage_key:
        return None
    from mage import get_registry

    mage = get_registry().get("mages", {}).get(mage_key, {})
    key = mage.get("river_key")
    return str(key) if key else None


def _normalize_mage_key(name: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", name.strip().lower())
    clean = re.sub(r"[\s-]+", "_", clean).strip("_")
    return clean or "guest"


def save_registry(registry: dict) -> None:
    import yaml

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.dump(registry, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    tmp.replace(REGISTRY_PATH)
    from mage import reload_mage_registry

    reload_mage_registry()


def load_claim_room_markdown(locale: str) -> str:
    locale = locale if locale in ("de", "en") else "en"
    path = os.path.join(REPO_ROOT, "template", "practitioner", f"claim_room_{locale}.md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    with open(
        os.path.join(REPO_ROOT, "template", "practitioner", "claim_room_en.md"),
        encoding="utf-8",
    ) as fh:
        return fh.read().strip()


def _claim_room_embed(body: str, *, locale: str) -> discord.Embed:
    from hosted_river_onboarding import _parse_onboarding_markdown

    title, description = _parse_onboarding_markdown(body)
    if not title:
        title = "Deinen Fluss beanspruchen" if locale == "de" else "Claim your river"
    color = discord.Color.from_rgb(120, 180, 200)
    return discord.Embed(title=title, description=description, color=color)


async def pin_claim_room_copy(channel: discord.TextChannel, *, locale: str = "en") -> None:
    body = load_claim_room_markdown(locale)
    embed = _claim_room_embed(body, locale=locale)
    try:
        msg = await channel.send(embed=embed, silent=True)
        await msg.pin()
    except discord.HTTPException as exc:
        print(f"Claim room pin failed for {channel.id}: {exc}")


def _river_bot_member(guild: discord.Guild) -> discord.Member | None:
    raw = os.environ.get("RIVER_BOT_USER_ID", "").strip()
    if raw:
        try:
            member = guild.get_member(int(raw))
            if member:
                return member
        except ValueError:
            pass
    for member in guild.members:
        if not member.bot or member.id == guild.me.id:
            continue
        if "river" in (member.name or "").lower():
            return member
    return None


def _bot_channel_perms() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        manage_channels=True,
        manage_messages=True,
        create_public_threads=True,
        send_messages_in_threads=True,
    )


def _guild_bot_overwrites(guild: discord.Guild) -> dict:
    """Permission overwrites for operator-only claim room (Turtle + River bots)."""
    everyone = guild.default_role
    overwrites = {
        everyone: discord.PermissionOverwrite(view_channel=False),
    }
    for op_id in _primary_operator_ids():
        member = guild.get_member(op_id)
        if member:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
            )
    me = guild.me
    if me:
        overwrites[me] = _bot_channel_perms()
    river = _river_bot_member(guild)
    if river:
        overwrites[river] = _bot_channel_perms()
    return overwrites


def _claimed_overwrites(
    guild: discord.Guild, claimer: discord.Member
) -> dict:
    everyone = guild.default_role
    overwrites = {
        everyone: discord.PermissionOverwrite(view_channel=False),
        claimer: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            create_public_threads=True,
            send_messages_in_threads=True,
        ),
    }
    for op_id in _primary_operator_ids():
        member = guild.get_member(op_id)
        if member and member.id != claimer.id:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )
    me = guild.me
    if me:
        overwrites[me] = _bot_channel_perms()
    river = _river_bot_member(guild)
    if river:
        overwrites[river] = _bot_channel_perms()
    return overwrites


async def complete_river_claim(
    message: discord.Message,
    client,
    *,
    mage_key: str,
    display_name: str,
) -> None:
    from hosted_river_onboarding import post_hosted_river_onboarding
    from mage import get_registry, set_practice_context_for_channel, get_pd
    from river_handler import _append_chronicle, ensure_bar_at_bottom

    channel = message.channel
    if not isinstance(channel, discord.TextChannel):
        return

    registry = get_registry()
    mage = registry.setdefault("mages", {}).setdefault(mage_key, {})
    mage["discord_id"] = str(message.author.id)
    if not mage.get("address"):
        mage["address"] = display_name

    ch_entry = registry.setdefault("channels", {}).setdefault(str(channel.id), {})
    if isinstance(ch_entry, dict):
        ch_entry["type"] = "hosted-river"
        ch_entry["mage"] = mage_key
        ch_entry.pop("river_key", None)
        ch_entry["description"] = f"Hosted practice surface for {display_name}"

    save_registry(registry)

    river_name = f"{mage_key.replace('_', '-')}-dialogue"
    try:
        await channel.edit(
            name=river_name[:100],
            overwrites=_claimed_overwrites(channel.guild, message.author),
            topic=f"Private practice river for {display_name}",
        )
    except discord.HTTPException as exc:
        print(f"Channel claim edit failed: {exc}")

    locale = (mage.get("locale") or "en").strip().lower()
    if locale not in ("de", "en"):
        locale = "en"
    ack = (
        f"**Gebunden.** Willkommen, {display_name}. Dies ist jetzt dein privater Fluss."
        if locale == "de"
        else f"**Bound.** Welcome, {display_name}. This is now your private river."
    )
    try:
        await channel.send(ack, silent=True)
    except discord.HTTPException:
        pass

    set_practice_context_for_channel(channel.id)
    _append_chronicle(
        get_pd(),
        f"river key claim — {display_name} bound to channel {channel.id}",
        {
            "event": "river_key_claim",
            "channel_id": channel.id,
            "discord_id": str(message.author.id),
            "mage_key": mage_key,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )

    await post_hosted_river_onboarding(channel, client)
    await ensure_bar_at_bottom(channel, client)
    print(f"River claimed: {display_name} → #{river_name}")


async def try_river_key_claim(message: discord.Message, client) -> bool:
    """Handle river key drop in an unclaimed-river channel. Returns True if consumed."""
    if isinstance(message.channel, discord.Thread):
        return False
    channel_id = message.channel.id
    if not is_unclaimed_river(channel_id):
        return False
    if message.author.bot:
        return False

    text = (message.content or "").strip()
    entry = _channel_entry(channel_id)
    if not isinstance(entry, dict):
        return False
    mage_key = entry.get("mage")
    if not mage_key:
        return False

    from mage import get_registry

    mage = get_registry().get("mages", {}).get(mage_key, {})
    bound_id = mage.get("discord_id")
    if bound_id:
        if str(message.author.id) == str(bound_id):
            return False
        try:
            await message.channel.send(
                "This river has already been claimed.",
                silent=True,
            )
        except discord.HTTPException:
            pass
        return True

    if _is_primary_operator(message.author.id):
        return False

    expected = _expected_river_key(channel_id)
    if not expected:
        return False

    if not _looks_like_single_key(text):
        try:
            locale = (mage.get("locale") or "en").strip().lower()
            hint = (
                "Sende deinen Fluss-Schlüssel als **ein einzelnes Emoji**."
                if locale == "de"
                else "Send your river key as **a single emoji message**."
            )
            await message.channel.send(hint, silent=True)
        except discord.HTTPException:
            pass
        return True

    if text != expected:
        locale = (mage.get("locale") or "en").strip().lower()
        wrong = (
            "Das ist nicht der Schlüssel für diesen Fluss. Prüfe bei deinem Host."
            if locale == "de"
            else "That is not the key for this river. Check with your host."
        )
        try:
            await message.channel.send(wrong, silent=True)
        except discord.HTTPException:
            pass
        return True

    display_name = (
        getattr(message.author, "global_name", None)
        or getattr(message.author, "display_name", None)
        or str(message.author)
    )
    await complete_river_claim(
        message,
        client,
        mage_key=mage_key,
        display_name=display_name,
    )
    return True


async def provision_unclaimed_river(
    guild: discord.Guild,
    *,
    mage_key: str,
    display_name: str,
    river_key: str,
    locale: str = "en",
) -> tuple[discord.TextChannel, discord.Invite]:
    """Create claim room, registry entries, pinned copy; return channel + invite."""
    from hosted_river_onboarding import seed_practitioner_workshop

    seed_practitioner_workshop(mage_key, locale=locale)

    from mage import get_registry

    registry = get_registry()
    registry.setdefault("mages", {})[mage_key] = {
        "discord_id": None,
        "address": display_name,
        "type": "practitioner",
        "locale": locale,
        "practice_dir": f"~/workshops/{mage_key}",
        "runtime_dir": f"~/workshops/{mage_key}",
        "river_key": river_key,
    }

    category = discord.utils.get(guild.categories, name="Practice")
    channel_name = f"claim-{mage_key.replace('_', '-')}"[:100]
    overwrites = _guild_bot_overwrites(guild)

    create_kwargs = {
        "name": channel_name,
        "overwrites": overwrites,
        "topic": f"Claim room for {display_name} — drop river key to open private river",
    }
    if category:
        create_kwargs["category"] = category

    channel = await guild.create_text_channel(**create_kwargs)

    registry.setdefault("channels", {})[str(channel.id)] = {
        "mage": mage_key,
        "type": "unclaimed-river",
        "river_key": river_key,
        "default_context": None,
        "description": f"Claim room for {display_name}",
    }
    save_registry(registry)

    await pin_claim_room_copy(channel, locale=locale)

    invite = await channel.create_invite(
        max_age=604800,
        max_uses=0,
        unique=True,
        reason=f"River key invite for {display_name}",
    )
    return channel, invite
