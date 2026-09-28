"""Discord humans ≡ turtleOS members.

Join admits (private river + community seat when a generic shared room exists).
Leave departs (archive the private river, drop space seats).
Doctor reads the same drift the hooks are supposed to keep empty.

Install still creates one river (§13.3). This module does not create a
community channel. It never treats a partnership, health, or team practice as
the house-wide room merely because they use shared topology.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import discord

from river_keys import (
    _claimed_overwrites,
    HOME_CATEGORY,
    _normalize_mage_key,
    hosted_river_channel_name,
    save_registry,
)
from space_provisioning import find_shared_river_channel

PRIVATE_RIVER_TYPES = frozenset({"river", "hosted-river"})
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
    """A registry row that should have a Discord human opposite it.

    ``roster: false`` is a coach studio or other house-bot identity.
    Bots that run the house are not members. A numeric discord_id
    without this flag *is* owed a human — that is the positive control.
    """
    if not isinstance(mage, dict):
        return False
    if mage.get("departed") or mage.get("archived") or mage.get("offboarded"):
        return False
    if mage.get("roster") is False:
        return False
    raw = str(mage.get("discord_id") or "").strip()
    return raw.isdigit()


def live_mages(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, mage in (registry.get("mages") or {}).items():
        if is_live_mage(mage):
            out[str(key)] = mage
    return out


def offboarded_ids(registry: dict[str, Any]) -> set[str]:
    """Discord ids the house decided not to admit — no join path re-admits them."""
    return {
        str(m.get("discord_id") or "").strip()
        for m in (registry.get("mages") or {}).values()
        if isinstance(m, dict) and m.get("offboarded")
    }


def apply_offboard_registry(registry: dict[str, Any], mage_key: str, *, at: str | None = None) -> list[str]:
    """Reduce a member to a marker: their Discord id and when. Returns their channel ids.

    Unlike a departure this keeps nothing to restore — the row, channel rows and
    seats go. The id stays so a join (or the missed-joins chore) does not
    re-admit someone the house decided to remove; readmission is an admin act.
    """
    mages = registry.get("mages") or {}
    mage = mages.get(mage_key)
    if not isinstance(mage, dict):
        raise KeyError(mage_key)
    mages[mage_key] = {"discord_id": str(mage.get("discord_id") or ""), "offboarded": at or _now()}
    channels = registry.get("channels") or {}
    gone = [cid for cid, e in channels.items() if isinstance(e, dict) and e.get("mage") == mage_key]
    for cid in gone:
        del channels[cid]
    for space in (registry.get("spaces") or {}).values():
        if isinstance(space, dict) and mage_key in (space.get("members") or []):
            space["members"] = [m for m in space["members"] if m != mage_key]
    return [str(c) for c in gone]


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
    """House shared room. Fail-closed: only an explicit ``community`` key.

    Partnership, health, team, and any other shared-river are not a fallback
    seat. Untagged ``shared-river`` is not a seat.
    """
    from channel_primitives import resolve_primitive
    from space_provisioning import list_active_spaces

    for row in list_active_spaces(registry):
        if row["space_key"] != "community":
            continue
        primitive = resolve_primitive(registry, row["channel_id"])
        if primitive is not None and primitive.name == "shared":
            return "community"
    return None


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
        if not mage.get("departed") or mage.get("offboarded"):
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
        on_discord_not_registered=tuple(sorted(humans - registered - offboarded_ids(registry))),
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
            f"⚠️ {len(drift.missing_private)} member(s) missing a home channel: {shown}"
        )
    if drift.community_space is None:
        lines.append(
            "ℹ️ No community shared-room — join opens a home channel only. "
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
        "discord_category": HOME_CATEGORY,
        "description": f"Home channel for {display_name}",
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
            topic=f"Home channel for {member.display_name}",
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
        print(f"roster_sync: hide home channel failed: {exc}")


async def _post_join_first_run(channel) -> object | None:
    """First-run, then mark posted so the hosted welcome embed does not follow."""
    from hosted_river_onboarding import is_onboarding_posted, mark_onboarding_posted
    from member_first_run import post_member_first_run

    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        return None
    if is_onboarding_posted(channel_id):
        return None
    msg = await post_member_first_run(channel)
    if msg is not None:
        mark_onboarding_posted(channel_id, getattr(msg, "id", None))
    return msg


async def admit_on_join(member: discord.Member) -> str | None:
    """Open or restore membership. None = not this house (or a bot)."""
    if getattr(member, "bot", False):
        return None
    from mage import get_registry

    registry = get_registry()
    guild = getattr(member, "guild", None)
    if not is_practice_guild(guild, registry):
        return None

    if str(member.id) in offboarded_ids(registry):
        return "Offboarded earlier — not admitted. Readmitting is an admin decision."

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

    category = discord.utils.get(getattr(guild, "categories", []) or [], name=HOME_CATEGORY)
    river_name = hosted_river_channel_name(mage_key)
    create_kwargs: dict[str, Any] = {
        "name": river_name,
        "overwrites": _claimed_overwrites(guild, member),
        "topic": f"Home channel for {display_name}",
    }
    if category:
        create_kwargs["category"] = category

    try:
        channel = await guild.create_text_channel(**create_kwargs)
    except discord.HTTPException as exc:
        print(f"roster_sync: create home channel failed for {display_name}: {exc}")
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
        await _post_join_first_run(channel)
    except ValueError as exc:
        print(f"roster_sync: first-run copy invalid: {exc}")

    space = find_community_space(registry)
    if space:
        return f"Opened `#{river_name}` and seated in community (`{space}`)."
    return f"Opened `#{river_name}` (no community shared-room yet)."


MISSED_JOIN_LIMIT = 3


async def admit_missed_joins(guild: Any) -> list[str]:
    """Admit people who joined while the bots were down, as ``on_member_join`` would.

    More than ``MISSED_JOIN_LIMIT`` at once is not a missed join — it is a member
    cache or registry that is wrong — so that case is reported and nothing opens.
    """
    from mage import get_registry, maybe_reload_mage_registry
    from river_keys import try_auto_admit_on_member_join

    maybe_reload_mage_registry()
    registry = get_registry()
    if not is_practice_guild(guild, registry):
        return []
    humans = [m for m in getattr(guild, "members", []) or [] if not getattr(m, "bot", False)]
    if len(humans) <= 1:
        return []
    registered = live_registered_ids(registry)
    skip = registered | offboarded_ids(registry)
    missed = [m for m in humans if str(m.id) not in skip]
    if not missed:
        return []
    if len(missed) > MISSED_JOIN_LIMIT:
        return [
            f"\u26a0\ufe0f {len(missed)} people on Discord are not in turtleOS — more than a missed "
            "join, so nothing was opened. `!admin doctor` shows who."
        ]
    lines = []
    for member in missed:
        admitted = await try_auto_admit_on_member_join(member) or await admit_on_join(member)
        name = getattr(member, "display_name", None) or member.name
        lines.append(f"Joined while I was away: **{name}**. {admitted or 'Not admitted — see logs.'}")
    return lines


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
    return f"Departed `{key}` — home channel archived, community seat removed."
