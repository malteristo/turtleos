"""Discord humans ≡ turtleOS members.

Join admits (private river + community seat when a shared room exists).
Leave departs (archive the private river, drop space seats).
Doctor reads the same drift the hooks are supposed to keep empty.

Install still creates one river (§13.3). This module does not create a
community channel. It seats a new member in the house shared room if one
already exists (`community`, else the first live shared-river — on this
household that is often `family`, which we do not rename).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import discord

from river_keys import (
    _claimed_overwrites,
    _normalize_mage_key,
    hosted_river_channel_name,
    save_registry,
)
from space_provisioning import find_shared_river_channel

PRIVATE_RIVER_TYPES = frozenset({"river", "hosted-river"})
PREFERRED_COMMUNITY_KEYS = ("community",)
JOIN_RELATION = "kin"


@dataclass(frozen=True)
class RosterDrift:
    on_discord_not_registered: tuple[str, ...]
    registered_not_on_discord: tuple[str, ...]
    missing_private: tuple[str, ...]
    community_space: str | None
    community_missing_seats: tuple[str, ...]

    def is_clean(self) -> bool:
        return not (
            self.on_discord_not_registered
            or self.registered_not_on_discord
            or self.missing_private
            or self.community_missing_seats
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_live_mage(mage: Any) -> bool:
    """A registry row that should have a Discord human opposite it."""
    if not isinstance(mage, dict):
        return False
    if mage.get("departed") or mage.get("archived"):
        return False
    raw = str(mage.get("discord_id") or "").strip()
    return raw.isdigit()


def live_mages(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, mage in (registry.get("mages") or {}).items():
        if is_live_mage(mage):
            out[str(key)] = mage
    return out


def live_registered_ids(registry: dict[str, Any]) -> set[str]:
    return {str(mage["discord_id"]).strip() for mage in live_mages(registry).values()}


def has_private_river(registry: dict[str, Any], mage_key: str) -> bool:
    for entry in (registry.get("channels") or {}).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("archived"):
            continue
        if entry.get("mage") == mage_key and entry.get("type") in PRIVATE_RIVER_TYPES:
            return True
    return False


def find_private_river_channel_id(registry: dict[str, Any], mage_key: str) -> str | None:
    for ch_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("archived"):
            continue
        if entry.get("mage") == mage_key and entry.get("type") in PRIVATE_RIVER_TYPES:
            return str(ch_id)
    return None


def find_community_space(registry: dict[str, Any]) -> str | None:
    """House shared room. Prefer `community`; else first live shared-river."""
    from space_provisioning import list_active_spaces

    rows = list_active_spaces(registry)
    if not rows:
        return None
    keys = {row["space_key"] for row in rows}
    for preferred in PREFERRED_COMMUNITY_KEYS:
        if preferred in keys:
            return preferred
    return rows[0]["space_key"]


def unique_mage_key(
    display_name: str,
    registry: dict[str, Any],
    *,
    discord_id: str | int | None = None,
) -> str:
    base = _normalize_mage_key(display_name)
    taken = set(registry.get("mages") or {}) | set(registry.get("spaces") or {})
    if base not in taken:
        return base
    if discord_id is not None:
        candidate = f"{base}_{str(discord_id)[-4:]}"
        if candidate not in taken:
            return candidate
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def mage_key_for_live_id(registry: dict[str, Any], discord_id: str | int) -> str | None:
    aid = str(discord_id)
    for key, mage in live_mages(registry).items():
        if str(mage.get("discord_id", "")).strip() == aid:
            return key
    return None


def find_departed_mage(registry: dict[str, Any], discord_id: str | int) -> str | None:
    aid = str(discord_id)
    for key, mage in (registry.get("mages") or {}).items():
        if not isinstance(mage, dict):
            continue
        if not mage.get("departed"):
            continue
        if str(mage.get("discord_id") or "").strip() == aid:
            return str(key)
    return None


def compute_roster_drift(
    registry: dict[str, Any],
    *,
    human_ids: list[str] | tuple[str, ...],
) -> RosterDrift:
    humans = {str(i).strip() for i in human_ids if str(i).strip()}
    registered = live_registered_ids(registry)
    community = find_community_space(registry)
    missing_private: list[str] = []
    missing_seats: list[str] = []
    members: list[str] = []
    if community:
        space = (registry.get("spaces") or {}).get(community) or {}
        members = list(space.get("members") or [])
    for key, mage in live_mages(registry).items():
        if not has_private_river(registry, key):
            missing_private.append(key)
        if community and key not in members:
            missing_seats.append(key)
    return RosterDrift(
        on_discord_not_registered=tuple(sorted(humans - registered)),
        registered_not_on_discord=tuple(sorted(registered - humans)),
        missing_private=tuple(sorted(missing_private)),
        community_space=community,
        community_missing_seats=tuple(sorted(missing_seats)),
    )


def format_roster_doctor_lines(drift: RosterDrift) -> list[str]:
    lines: list[str] = []
    if drift.on_discord_not_registered:
        shown = ", ".join(f"`{i}`" for i in drift.on_discord_not_registered[:8])
        more = (
            f" (+{len(drift.on_discord_not_registered) - 8} more)"
            if len(drift.on_discord_not_registered) > 8
            else ""
        )
        lines.append(
            f"⚠️ Roster drift — {len(drift.on_discord_not_registered)} on Discord "
            f"not in turtleOS (join should have admitted): {shown}{more}"
        )
    if drift.registered_not_on_discord:
        shown = ", ".join(f"`{i}`" for i in drift.registered_not_on_discord[:8])
        more = (
            f" (+{len(drift.registered_not_on_discord) - 8} more)"
            if len(drift.registered_not_on_discord) > 8
            else ""
        )
        lines.append(
            f"⚠️ Roster drift — {len(drift.registered_not_on_discord)} in turtleOS "
            f"not on Discord (leave should have departed): {shown}{more}"
        )
    if drift.missing_private:
        shown = ", ".join(f"`{k}`" for k in drift.missing_private[:8])
        lines.append(
            f"⚠️ {len(drift.missing_private)} member(s) missing a private river: {shown}"
        )
    if drift.community_space is None:
        lines.append(
            "ℹ️ No community shared-room — join opens a private river only. "
            "A shared space (`community`, or any live shared-river) is the house seat."
        )
    elif drift.community_missing_seats:
        shown = ", ".join(f"`{k}`" for k in drift.community_missing_seats[:8])
        lines.append(
            f"⚠️ {len(drift.community_missing_seats)} member(s) not seated in "
            f"community (`{drift.community_space}`): {shown}"
        )
    return lines


def is_practice_guild(guild: Any, registry: dict[str, Any]) -> bool:
    """True when this guild already holds a turtleOS registry channel.

    Stops a join on a second server the bot happens to sit in from
    minting rivers.
    """
    if guild is None:
        return False
    cached = {str(getattr(ch, "id", "")) for ch in getattr(guild, "channels", []) or []}
    getter = getattr(guild, "get_channel", None)
    for ch_id in registry.get("channels") or {}:
        if str(ch_id) in cached:
            return True
        if getter is None:
            continue
        try:
            if getter(int(ch_id)) is not None:
                return True
        except (TypeError, ValueError):
            continue
    return False


def seat_in_community(registry: dict[str, Any], mage_key: str) -> bool:
    space_key = find_community_space(registry)
    if not space_key:
        return False
    space = registry.setdefault("spaces", {}).setdefault(space_key, {})
    members = list(space.get("members") or [])
    if mage_key in members:
        return False
    members.append(mage_key)
    space["members"] = members
    return True


def apply_admit_registry(
    registry: dict[str, Any],
    *,
    mage_key: str,
    discord_id: str | int,
    display_name: str,
    channel_id: int | str,
    locale: str = "en",
) -> None:
    registry.setdefault("mages", {})[mage_key] = {
        "discord_id": str(discord_id),
        "address": display_name,
        "type": "practitioner",
        "locale": locale,
        "practice_dir": f"~/workshops/{mage_key}",
        "runtime_dir": f"~/workshops/{mage_key}",
        "relation": JOIN_RELATION,
    }
    river_name = hosted_river_channel_name(mage_key)
    registry.setdefault("channels", {})[str(channel_id)] = {
        "mage": mage_key,
        "type": "hosted-river",
        "name": river_name,
        "discord_name": river_name,
        "description": f"Private practice river for {display_name}",
    }
    seat_in_community(registry, mage_key)


def apply_depart_registry(registry: dict[str, Any], mage_key: str, *, at: str | None = None) -> None:
    when = at or _now()
    mage = (registry.get("mages") or {}).get(mage_key)
    if isinstance(mage, dict):
        mage["departed"] = True
        mage["departed_at"] = when
    for space in (registry.get("spaces") or {}).values():
        if not isinstance(space, dict):
            continue
        members = list(space.get("members") or [])
        if mage_key in members:
            space["members"] = [m for m in members if m != mage_key]
    for entry in (registry.get("channels") or {}).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("mage") != mage_key:
            continue
        if entry.get("type") not in PRIVATE_RIVER_TYPES:
            continue
        if entry.get("archived"):
            continue
        entry["archived"] = True
        entry["archived_at"] = when


def apply_rejoin_registry(registry: dict[str, Any], mage_key: str) -> None:
    mage = (registry.get("mages") or {}).get(mage_key)
    if isinstance(mage, dict):
        mage.pop("departed", None)
        mage.pop("departed_at", None)
        mage.pop("archived", None)
    for entry in (registry.get("channels") or {}).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("mage") != mage_key:
            continue
        if entry.get("type") not in PRIVATE_RIVER_TYPES:
            continue
        entry.pop("archived", None)
        entry.pop("archived_at", None)
    seat_in_community(registry, mage_key)


def _hidden_private_overwrites(guild: discord.Guild) -> dict:
    everyone = guild.default_role
    overwrites = {
        everyone: discord.PermissionOverwrite(view_channel=False),
    }
    me = getattr(guild, "me", None)
    if me:
        from river_keys import _bot_channel_perms

        overwrites[me] = _bot_channel_perms()
        river = None
        try:
            from river_keys import _river_bot_member

            river = _river_bot_member(guild)
        except Exception:
            river = None
        if river:
            overwrites[river] = _bot_channel_perms()
    return overwrites


async def _ensure_community_access(guild: discord.Guild, registry: dict[str, Any]) -> None:
    space_key = find_community_space(registry)
    if not space_key:
        return
    binding = find_shared_river_channel(registry, space_key)
    if not binding:
        return
    ch_id, _ = binding
    try:
        channel = guild.get_channel(int(ch_id))
    except (TypeError, ValueError):
        return
    if channel is None:
        return
    from mage import ensure_space_channel_access

    await ensure_space_channel_access(channel, guild=guild)


async def _restore_private_visibility(
    guild: discord.Guild,
    registry: dict[str, Any],
    mage_key: str,
    member: discord.Member,
) -> None:
    ch_id = find_private_river_channel_id(registry, mage_key)
    if not ch_id:
        return
    try:
        channel = guild.get_channel(int(ch_id))
    except (TypeError, ValueError):
        return
    if channel is None:
        return
    try:
        await channel.edit(
            overwrites=_claimed_overwrites(guild, member),
            topic=f"Private practice river for {member.display_name}",
        )
    except discord.HTTPException as exc:
        print(f"roster_sync: restore private visibility failed: {exc}")


async def _hide_private_river(
    guild: discord.Guild,
    registry: dict[str, Any],
    mage_key: str,
) -> None:
    ch_id = find_private_river_channel_id(registry, mage_key)
    if not ch_id:
        return
    try:
        channel = guild.get_channel(int(ch_id))
    except (TypeError, ValueError):
        return
    if channel is None:
        return
    edit_kwargs: dict[str, Any] = {
        "overwrites": _hidden_private_overwrites(guild),
        "topic": "Departed — archived",
    }
    archived_category = discord.utils.get(getattr(guild, "categories", []) or [], name="Archived")
    if archived_category:
        edit_kwargs["category"] = archived_category
    try:
        await channel.edit(**edit_kwargs)
    except discord.HTTPException as exc:
        print(f"roster_sync: hide private river failed: {exc}")


async def admit_on_join(member: discord.Member) -> str | None:
    """Open or restore membership. None = not this house (or a bot)."""
    if getattr(member, "bot", False):
        return None
    from mage import get_registry

    registry = get_registry()
    guild = getattr(member, "guild", None)
    if not is_practice_guild(guild, registry):
        return None

    existing = mage_key_for_live_id(registry, member.id)
    if existing:
        seated = seat_in_community(registry, existing)
        if seated:
            save_registry(registry)
            await _ensure_community_access(guild, registry)
            return f"Already a member (`{existing}`); seated in community."
        return f"Already a member (`{existing}`)."

    departed = find_departed_mage(registry, member.id)
    if departed:
        apply_rejoin_registry(registry, departed)
        save_registry(registry)
        await _restore_private_visibility(guild, registry, departed, member)
        await _ensure_community_access(guild, registry)
        return f"Restored membership for `{departed}`."

    from hosted_river_onboarding import seed_practitioner_workshop
    from discord_reconcile import expect_channel_registry_binding

    display_name = member.display_name or member.name or "member"
    mage_key = unique_mage_key(display_name, registry, discord_id=member.id)
    seed_practitioner_workshop(mage_key)

    category = discord.utils.get(getattr(guild, "categories", []) or [], name="Practice")
    river_name = hosted_river_channel_name(mage_key)
    create_kwargs: dict[str, Any] = {
        "name": river_name,
        "overwrites": _claimed_overwrites(guild, member),
        "topic": f"Private practice river for {display_name}",
    }
    if category:
        create_kwargs["category"] = category

    try:
        channel = await guild.create_text_channel(**create_kwargs)
    except discord.HTTPException as exc:
        print(f"roster_sync: create private river failed for {display_name}: {exc}")
        raise

    expect_channel_registry_binding(channel.id)
    apply_admit_registry(
        registry,
        mage_key=mage_key,
        discord_id=member.id,
        display_name=display_name,
        channel_id=channel.id,
    )
    save_registry(registry)
    await _ensure_community_access(guild, registry)

    try:
        await channel.send(
            f"**Bound.** Welcome, {display_name}. This is your private river (`#{river_name}`).",
            silent=True,
        )
    except discord.HTTPException:
        pass

    space = find_community_space(registry)
    if space:
        return f"Opened `#{river_name}` and seated in community (`{space}`)."
    return f"Opened `#{river_name}` (no community shared-room yet)."


async def depart_on_leave(member: discord.Member) -> str | None:
    """Tear down membership. None = not this house, or nobody to remove."""
    if getattr(member, "bot", False):
        return None
    from mage import get_registry

    registry = get_registry()
    guild = getattr(member, "guild", None)
    if not is_practice_guild(guild, registry):
        return None

    key = mage_key_for_live_id(registry, member.id)
    if not key:
        return None

    await _hide_private_river(guild, registry, key)
    apply_depart_registry(registry, key)
    save_registry(registry)
    return f"Departed `{key}` — private river archived, community seat removed."
