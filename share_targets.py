"""Share eddy registry targets — practitioner and space addressing (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from mage import get_registry


@dataclass(frozen=True)
class ShareTarget:
    mage_key: str
    address: str
    discord_id: str
    channel_id: int


@dataclass(frozen=True)
class SpaceShareTarget:
    space_key: str
    address: str
    channel_id: int


def river_channel_for_mage(mage_key: str) -> int | None:
    """Parent river / hosted-river channel id for a mage registry key."""
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("mage") != mage_key:
            continue
        if entry.get("type") not in ("river", "hosted-river"):
            continue
        try:
            return int(ch_id_str)
        except (ValueError, TypeError):
            continue
    return None


def runtime_dir_for_mage(mage_key: str) -> str:
    mage = get_registry().get("mages", {}).get(mage_key, {})
    raw = mage.get("runtime_dir") or mage.get("practice_dir") or f"~/workshops/{mage_key}"
    return os.path.expanduser(raw)


def practice_dir_for_mage(mage_key: str) -> str:
    mage = get_registry().get("mages", {}).get(mage_key, {})
    raw = mage.get("practice_dir") or f"~/workshops/{mage_key}"
    return os.path.expanduser(raw)


def list_practitioner_targets(
    sender_mage_key: str,
    sender_discord_id: str | int,
) -> list[ShareTarget]:
    """Slice 1 picker: every other registered mage with a sovereign river channel."""
    sender_id = str(sender_discord_id)
    targets: list[ShareTarget] = []
    for mage_key, mage in get_registry().get("mages", {}).items():
        if mage_key == sender_mage_key:
            continue
        discord_id = mage.get("discord_id")
        if not discord_id or str(discord_id) == sender_id:
            continue
        channel_id = river_channel_for_mage(mage_key)
        if not channel_id:
            continue
        targets.append(
            ShareTarget(
                mage_key=mage_key,
                address=mage.get("address", mage_key.replace("_", " ").title()),
                discord_id=str(discord_id),
                channel_id=channel_id,
            )
        )
    return sorted(targets, key=lambda t: t.address.lower())


def runtime_dir_for_space(space_key: str) -> str:
    space = get_registry().get("spaces", {}).get(space_key, {})
    raw = space.get("runtime_dir") or space.get("practice_dir") or f"~/workshops/{space_key}"
    return os.path.expanduser(raw)


def shared_river_channel_for_space(space_key: str) -> int | None:
    """Parent shared-river channel id for a registry space key."""
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "shared-river":
            continue
        if entry.get("archived"):
            continue
        if entry.get("mage") != space_key:
            continue
        try:
            return int(ch_id_str)
        except (ValueError, TypeError):
            continue
    return None


def _sender_may_share_to_space(sender_mage_key: str, space: dict[str, Any]) -> bool:
    policy = space.get("share_policy", "members_only")
    members = space.get("members") or []
    if policy == "all_practitioners":
        return True
    if policy == "members_only":
        return sender_mage_key in members
    if isinstance(policy, dict):
        explicit = policy.get("explicit")
        if isinstance(explicit, list):
            return sender_mage_key in explicit
    if isinstance(policy, list):
        return sender_mage_key in policy
    return sender_mage_key in members


def list_space_targets(sender_mage_key: str) -> list[SpaceShareTarget]:
    """Slice 3a picker: registry spaces where sender satisfies share_policy."""
    targets: list[SpaceShareTarget] = []
    for space_key, space in get_registry().get("spaces", {}).items():
        if not isinstance(space, dict):
            continue
        if not _sender_may_share_to_space(sender_mage_key, space):
            continue
        channel_id = shared_river_channel_for_space(space_key)
        if not channel_id:
            continue
        address = (space.get("address") or space_key.replace("_", " ").title())[:100]
        targets.append(
            SpaceShareTarget(
                space_key=space_key,
                address=address,
                channel_id=channel_id,
            )
        )
    return sorted(targets, key=lambda t: t.address.lower())


def space_member_discord_ids(
    space_key: str,
    *,
    exclude_id: str | int | None = None,
) -> list[str]:
    """Discord user ids for space members (optional exclude — e.g. sharer)."""
    exclude = str(exclude_id) if exclude_id is not None else None
    space = get_registry().get("spaces", {}).get(space_key, {})
    ids: list[str] = []
    for member_key in space.get("members") or []:
        mage = get_registry().get("mages", {}).get(member_key, {})
        uid = mage.get("discord_id")
        if not uid:
            continue
        uid_str = str(uid)
        if exclude and uid_str == exclude:
            continue
        ids.append(uid_str)
    return ids


def mage_is_space_member(mage_key: str, space_key: str) -> bool:
    space = get_registry().get("spaces", {}).get(space_key, {})
    return mage_key in (space.get("members") or [])


def mage_key_for_discord_id(discord_id: str | int) -> str | None:
    """Registry mage key for a Discord user id, if registered."""
    aid = str(discord_id)
    for mage_key, mage in get_registry().get("mages", {}).items():
        if str(mage.get("discord_id", "")) == aid:
            return mage_key
    return None
