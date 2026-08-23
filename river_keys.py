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
    """Administrator discord ids — `mage.admin_discord_ids` owns the rule."""
    from mage import admin_discord_ids

    return admin_discord_ids()


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


def hosted_river_channel_name(mage_key: str) -> str:
    """Discord channel name for a hosted/unclaimed river — stable for life (#river-<name>)."""
    return f"river-{mage_key.replace('_', '-')}"[:100]


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
    from river_handler import _append_chronicle, reconcile_river_bar_floor

    channel = message.channel
    if not isinstance(channel, discord.TextChannel):
        return

    registry = get_registry()
    mage = registry.setdefault("mages", {}).setdefault(mage_key, {})
    mage["discord_id"] = str(message.author.id)
    if not mage.get("address"):
        mage["address"] = display_name

    river_name = hosted_river_channel_name(mage_key)
    ch_entry = registry.setdefault("channels", {}).setdefault(str(channel.id), {})
    if isinstance(ch_entry, dict):
        ch_entry["type"] = "hosted-river"
        ch_entry["mage"] = mage_key
        ch_entry["name"] = river_name
        ch_entry["discord_name"] = river_name
        ch_entry.pop("river_key", None)
        ch_entry["description"] = f"Hosted practice surface for {display_name}"

    save_registry(registry)

    # Keep #river-<name> for life — permissions/topic update only.
    edit_kwargs = {
        "overwrites": _claimed_overwrites(channel.guild, message.author),
        "topic": f"Private practice river for {display_name}",
    }
    current_name = (getattr(channel, "name", None) or "").lower()
    if current_name != river_name.lower():
        edit_kwargs["name"] = river_name
    try:
        await channel.edit(**edit_kwargs)
    except discord.HTTPException as exc:
        print(f"Channel claim edit failed: {exc}")

    locale = (mage.get("locale") or "en").strip().lower()
    if locale not in ("de", "en"):
        locale = "en"
    ack = (
        f"**Gebunden.** Willkommen, {display_name}. Dies ist jetzt dein privater Fluss (`#{river_name}`)."
        if locale == "de"
        else f"**Bound.** Welcome, {display_name}. This is now your private river (`#{river_name}`)."
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
    await reconcile_river_bar_floor(channel, client)
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


async def grant_claim_room_member_access(
    channel: discord.TextChannel,
    member: discord.Member,
    *,
    reason: str = "Hosted claim-room visibility for invited guest",
) -> None:
    """Pre-grant view/send so an already-on-server guest can see the claim room."""
    await channel.set_permissions(
        member,
        overwrite=discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            create_public_threads=True,
            send_messages_in_threads=True,
        ),
        reason=reason,
    )


def find_unclaimed_channel_id(mage_key: str, registry: dict | None = None) -> str | None:
    """Return channel id string for an unclaimed-river bound to mage_key, if any."""
    from mage import get_registry

    reg = registry if registry is not None else get_registry()
    for cid, entry in (reg.get("channels") or {}).items():
        if isinstance(entry, dict) and entry.get("type") == "unclaimed-river" and entry.get("mage") == mage_key:
            return str(cid)
    return None


def list_unclaimed_river_hints(registry: dict | None = None) -> list[str]:
    """Short mage-key list for join notices."""
    from mage import get_registry

    reg = registry if registry is not None else get_registry()
    keys: list[str] = []
    for entry in (reg.get("channels") or {}).values():
        if isinstance(entry, dict) and entry.get("type") == "unclaimed-river" and entry.get("mage"):
            keys.append(str(entry["mage"]))
    return sorted(set(keys))


async def admit_member_to_unclaimed_river(
    guild: discord.Guild,
    *,
    mage_key: str,
    member: discord.Member,
    reason: str = "Admin rivers admit — claim-room visibility",
) -> tuple[discord.TextChannel, str]:
    """Grant a member view/send on an existing unclaimed claim room.

    Returns ``(channel, mage_key)``. Raises ``ValueError`` if no room / bad channel.
    """
    from mage import get_registry

    mage_key = _normalize_mage_key(mage_key)
    cid = find_unclaimed_channel_id(mage_key)
    if not cid:
        raise ValueError(f"No unclaimed claim room for `{mage_key}`.")
    try:
        channel = guild.get_channel(int(cid)) or await guild.fetch_channel(int(cid))
    except (TypeError, ValueError, discord.NotFound, discord.HTTPException) as exc:
        raise ValueError(f"Claim room for `{mage_key}` not found on Discord ({exc}).") from exc
    if not isinstance(channel, discord.TextChannel):
        raise ValueError(f"Claim room for `{mage_key}` is not a text channel.")
    await grant_claim_room_member_access(channel, member, reason=reason)
    return channel, mage_key


async def try_auto_admit_on_member_join(member: discord.Member) -> str | None:
    """If the join used a tracked claim-room invite, grant channel access.

    Returns a short human summary for ops log, or None if nothing matched.
    Requires bot permission to list guild invites (Manage Guild / Administrator).
    """
    if member.bot or member.guild is None:
        return None

    from mage import get_registry

    registry = get_registry()
    tracked: list[tuple[str, dict]] = []
    for cid, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("type") != "unclaimed-river":
            continue
        code = entry.get("invite_code")
        if code:
            tracked.append((str(cid), entry))
    if not tracked:
        return None

    try:
        invites = await member.guild.invites()
    except discord.Forbidden:
        print("auto-admit: cannot list invites (missing Manage Guild)")
        return None
    except discord.HTTPException as exc:
        print(f"auto-admit: invite list failed: {exc}")
        return None

    by_code = {inv.code: inv for inv in invites if inv.code}
    matched: list[tuple[str, dict, discord.Invite]] = []
    for cid, entry in tracked:
        code = str(entry.get("invite_code"))
        inv = by_code.get(code)
        if inv is None:
            continue
        stored_uses = int(entry.get("invite_uses") or 0)
        live_uses = int(inv.uses or 0)
        if live_uses > stored_uses:
            matched.append((cid, entry, inv))

    if not matched:
        return None

    # Prefer the invite whose use count jumped; if several, take the largest delta.
    matched.sort(
        key=lambda row: int(row[2].uses or 0) - int(row[1].get("invite_uses") or 0),
        reverse=True,
    )
    cid, entry, inv = matched[0]
    mage_key = str(entry.get("mage") or "?")
    try:
        channel = member.guild.get_channel(int(cid)) or await member.guild.fetch_channel(int(cid))
    except (TypeError, ValueError, discord.NotFound, discord.HTTPException) as exc:
        print(f"auto-admit: channel {cid} fetch failed: {exc}")
        return None
    if not isinstance(channel, discord.TextChannel):
        return None

    try:
        await grant_claim_room_member_access(
            channel,
            member,
            reason=f"Auto-admit via claim invite {inv.code}",
        )
    except discord.HTTPException as exc:
        print(f"auto-admit: grant failed for {member.name} on #{channel.name}: {exc}")
        return None

    entry["invite_uses"] = int(inv.uses or 0)
    save_registry(registry)
    print(f"Auto-admitted {member.name} to #{channel.name} (mage={mage_key}, invite={inv.code})")
    return f"Auto-admitted **{member.display_name}** to `#{channel.name}` (`{mage_key}`) via invite."


def parse_invite_args(args: list[str]) -> tuple[str, str, str, str | None]:
    """Parse ``invite|river-key`` args after the subcommand.

    Returns ``(display_name, river_key, locale, member_token|None)``.
    """
    tokens = list(args)
    member_token: str | None = None
    if "--member" in tokens:
        idx = tokens.index("--member")
        if idx + 1 >= len(tokens):
            raise ValueError("Usage: `!admin invite <name> <emoji> [en|de] [--member @member|id|username]`")
        member_token = tokens[idx + 1]
        del tokens[idx : idx + 2]
    if len(tokens) < 2:
        raise ValueError("Usage: `!admin invite <name> <emoji> [en|de] [--member @member|id|username]`")
    display_name = tokens[0].strip()
    river_key = tokens[1].strip()
    locale = "en"
    if len(tokens) > 2 and tokens[2].lower() in ("de", "en"):
        locale = tokens[2].lower()
    return display_name, river_key, locale, member_token


async def provision_unclaimed_river(
    guild: discord.Guild,
    *,
    mage_key: str,
    display_name: str,
    river_key: str,
    locale: str = "en",
    guest_member: discord.Member | None = None,
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
    channel_name = hosted_river_channel_name(mage_key)
    overwrites = _guild_bot_overwrites(guild)

    create_kwargs = {
        "name": channel_name,
        "overwrites": overwrites,
        "topic": f"Claim room for {display_name} — drop river key to open private river",
    }
    if category:
        create_kwargs["category"] = category

    channel = await guild.create_text_channel(**create_kwargs)
    from discord_reconcile import expect_channel_registry_binding

    expect_channel_registry_binding(channel.id)

    if guest_member is not None:
        await grant_claim_room_member_access(channel, guest_member)

    await pin_claim_room_copy(channel, locale=locale)

    invite = await channel.create_invite(
        max_age=604800,
        max_uses=0,
        unique=True,
        reason=f"River key invite for {display_name}",
    )

    registry.setdefault("channels", {})[str(channel.id)] = {
        "mage": mage_key,
        "type": "unclaimed-river",
        "river_key": river_key,
        "name": channel_name,
        "discord_name": channel_name,
        "invite_code": invite.code,
        "invite_uses": int(invite.uses or 0),
        "default_context": None,
        "description": f"Claim room for {display_name}",
    }
    save_registry(registry)

    return channel, invite
