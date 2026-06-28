"""Tier-2 structural adapters — channel/registry reconciliation from Gateway events.

Unregistered channel notices, permission drift, orphan marking — shared with blessed
!admin paths via expect_channel_registry_binding. See design-discord-native-ui-reconciliation.md (S4).
"""

from __future__ import annotations

from typing import Any

import discord

from mage import get_registry

PRACTICE_CATEGORY_NAME = "Practice"

# Blessed paths call this before create_text_channel to suppress duplicate S3 notices.
_pending_registry_channel_ids: set[int] = set()


def expect_channel_registry_binding(channel_id: int) -> None:
    """Mark a channel about to be registered by a blessed command (onboard, !admin space)."""
    _pending_registry_channel_ids.add(int(channel_id))


def _channel_is_category(channel: discord.abc.GuildChannel) -> bool:
    try:
        return channel.type == discord.ChannelType.category
    except AttributeError:
        return isinstance(channel, discord.CategoryChannel)


def _channel_is_text_like(channel: discord.abc.GuildChannel) -> bool:
    try:
        return channel.type in (
            discord.ChannelType.text,
            discord.ChannelType.news,
            discord.ChannelType.forum,
        )
    except AttributeError:
        return hasattr(channel, "overwrites") and not _channel_is_category(channel)


def _is_practice_channel(channel: discord.abc.GuildChannel) -> bool:
    cat = getattr(channel, "category", None)
    return bool(cat and getattr(cat, "name", None) == PRACTICE_CATEGORY_NAME)


def _channel_binding_hint(channel: discord.abc.GuildChannel) -> str:
    """Suggest how an unregistered channel might join practice topology (no auto-bind)."""
    name = (getattr(channel, "name", "") or "").lower()
    hints: list[str] = []
    if _is_practice_channel(channel):
        hints.append("Practice category — consider `!admin space create` or `!admin onboard`")
    if name.endswith("-dialogue"):
        hints.append("`*-dialogue` name — hosted river via `!admin onboard`")
    elif name.startswith("river-"):
        hints.append("`river-*` name — claim room via `!admin river-key`")
    elif "play" in name or name.endswith("-play"):
        hints.append("play sandbox — `!admin space create <key>`")
    if not hints:
        hints.append("link with `!admin space create` / `!admin onboard`, or ignore if Discord-only")
    return "; ".join(hints)


def _permission_drift_issues(
    channel: discord.abc.GuildChannel,
    entry: dict,
    registry: dict,
) -> list[str]:
    """Read-only permission audit for a registry-bound channel (mirrors `!admin audit` heuristics)."""
    guild = getattr(channel, "guild", None)
    if guild is None:
        return []

    ch_type = entry.get("type")
    if ch_type not in ("river", "hosted-river", "shared-river", "unclaimed-river"):
        return []

    overwrites = getattr(channel, "overwrites", None) or {}
    everyone = guild.default_role
    issues: list[str] = []

    ow_everyone = overwrites.get(everyone)
    if ow_everyone is None or ow_everyone.pair()[1].view_channel is not True:
        if ow_everyone is None or ow_everyone.view_channel is not False:
            issues.append("@everyone can view (expected private practice channel)")

    mage_key = entry.get("mage")
    if ch_type == "hosted-river" and mage_key:
        mage = registry.get("mages", {}).get(mage_key, {})
        raw = mage.get("discord_id")
        if raw:
            try:
                member = guild.get_member(int(raw))
            except (TypeError, ValueError):
                member = None
            if member and member not in overwrites:
                issues.append(f"practitioner `{mage_key}` has no explicit overwrite")

    if ch_type == "shared-river" and mage_key:
        space = registry.get("spaces", {}).get(mage_key, {})
        for member_key in space.get("members", []):
            mage = registry.get("mages", {}).get(member_key, {})
            raw = mage.get("discord_id")
            if not raw:
                continue
            try:
                uid = int(raw)
            except (TypeError, ValueError):
                continue
            member = guild.get_member(uid)
            if member is None:
                continue
            ow = overwrites.get(member)
            if ow is None or not ow.view_channel:
                issues.append(f"space member `{member_key}` missing view access")

    return issues


def _overwrite_snapshot(channel: discord.abc.GuildChannel) -> dict[str, tuple]:
    overwrites = getattr(channel, "overwrites", None) or {}
    snap: dict[str, tuple] = {}
    for target, ow in overwrites.items():
        key = str(getattr(target, "id", target))
        snap[key] = ow.pair()
    return snap


def _sync_channel_discord_name(registry: dict[str, Any], channel_id_str: str, name: str) -> bool:
    entry = registry.get("channels", {}).get(channel_id_str)
    if not isinstance(entry, dict):
        return False
    if entry.get("discord_name") == name:
        return False
    entry["discord_name"] = name
    from river_keys import save_registry

    save_registry(registry)
    return True


async def reconcile_channel_create(
    channel: discord.abc.GuildChannel,
    *,
    discord_client,
) -> dict[str, Any]:
    """S3: unregistered channel notice with binding hints (no auto-register)."""
    if _channel_is_category(channel):
        return {"skipped": "category", "channel_id": channel.id}

    if not _channel_is_text_like(channel):
        return {"skipped": "channel_type", "channel_id": channel.id}

    ch_id_str = str(channel.id)
    registry = get_registry()
    if ch_id_str in registry.get("channels", {}):
        return {"skipped": "already_registered", "channel_id": channel.id}

    if channel.id in _pending_registry_channel_ids:
        _pending_registry_channel_ids.discard(channel.id)
        return {"skipped": "blessed_path_pending", "channel_id": channel.id}

    from helpers import log_activity

    cat_name = getattr(getattr(channel, "category", None), "name", None) or "no category"
    hint = _channel_binding_hint(channel)
    label = f"#{channel.name}"
    msg = (
        f"New Discord channel {label} (`{ch_id_str}`) in **{cat_name}** — not in registry. "
        f"{hint}"
    )
    try:
        await log_activity(msg, "\U0001f4c1")
    except Exception as exc:
        print(f"log_activity for channel create failed: {exc}")

    print(f"Unregistered channel notice: {label} ({ch_id_str})")
    return {"notice_posted": True, "channel_id": channel.id, "channel_name": channel.name}


async def reconcile_channel_update(
    before: discord.abc.GuildChannel,
    after: discord.abc.GuildChannel,
    *,
    discord_client,
) -> dict[str, Any]:
    """S3: sync registered metadata; flag permission drift on native edits."""
    if _channel_is_category(after):
        return {"skipped": "category", "channel_id": after.id}

    if not _channel_is_text_like(after):
        return {"skipped": "channel_type", "channel_id": after.id}

    ch_id_str = str(after.id)
    registry = get_registry()
    entry = registry.get("channels", {}).get(ch_id_str)
    if not isinstance(entry, dict):
        return {"skipped": "unregistered", "channel_id": after.id}

    if entry.get("orphaned"):
        return {"skipped": "orphaned", "channel_id": after.id}

    changes: list[str] = []
    renamed = False

    before_name = getattr(before, "name", None)
    after_name = getattr(after, "name", None)
    if before_name and after_name and before_name != after_name:
        changes.append(f"renamed `{before_name}` → `#{after_name}`")
        renamed = _sync_channel_discord_name(registry, ch_id_str, after_name)

    before_cat = getattr(before, "category_id", None)
    after_cat = getattr(after, "category_id", None)
    if before_cat != after_cat:
        changes.append("moved category")

    if _overwrite_snapshot(before) != _overwrite_snapshot(after):
        drift = _permission_drift_issues(after, entry, registry)
        for issue in drift:
            changes.append(f"permission drift: {issue}")

    if not changes:
        return {"skipped": "no_changes", "channel_id": after.id}

    from helpers import log_activity

    mage_key = entry.get("mage", "?")
    ch_type = entry.get("type", "unknown")
    detail = "; ".join(changes)
    msg = (
        f"Registry channel `#{after.name}` (`{ch_id_str}`) type `{ch_type}` mage `{mage_key}` — "
        f"{detail}. Run `!admin space sync` or `!admin audit` to repair."
    )
    try:
        await log_activity(msg, "\u26a0\ufe0f")
    except Exception as exc:
        print(f"log_activity for channel update failed: {exc}")

    print(f"Channel update reconciled: #{after.name} ({ch_id_str}) — {detail}")
    return {
        "channel_updated": True,
        "channel_id": after.id,
        "renamed": renamed,
        "changes": changes,
    }


async def reconcile_channel_delete(channel: discord.abc.GuildChannel, *, discord_client) -> dict[str, Any]:
    """S2: native channel/category delete → orphan registry entry + ops notice."""
    from mage import reload_mage_registry
    from space_provisioning import mark_channel_orphaned

    ch_id_str = str(channel.id)
    registry = get_registry()
    entry = registry.get("channels", {}).get(ch_id_str)
    if not isinstance(entry, dict):
        return {"skipped": "unregistered_channel", "channel_id": channel.id}

    ch_type = entry.get("type", "unknown")
    mage_key = entry.get("mage", "?")
    ch_name = getattr(channel, "name", ch_id_str)

    if entry.get("orphaned"):
        return {"skipped": "already_orphaned", "channel_id": channel.id}

    mark_channel_orphaned(registry, ch_id_str, reason="discord_deleted")
    reload_mage_registry()

    from helpers import log_activity

    label = f"#{ch_name}" if hasattr(channel, "name") else ch_name
    msg = (
        f"Discord deleted registered channel {label} (`{ch_id_str}`) "
        f"type `{ch_type}` mage `{mage_key}` — registry marked orphaned; workshop kept"
    )
    try:
        await log_activity(msg, "\u26a0\ufe0f")
    except Exception as exc:
        print(f"log_activity for channel delete failed: {exc}")

    print(f"Channel delete reconciled: {label} ({ch_id_str})")
    return {
        "channel_orphaned": True,
        "channel_id": channel.id,
        "channel_type": ch_type,
        "mage": mage_key,
    }
