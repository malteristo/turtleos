"""Operator provisioning for shared-river spaces (!admin space)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import discord

from river_keys import (
    REGISTRY_PATH,
    _bot_channel_perms,
    _primary_operator_ids,
    _river_bot_member,
    save_registry,
)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SPACE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VALID_POLICIES = frozenset({"members_only", "all_practitioners"})
VALID_CONTEXTS = frozenset({"family", "shared"})
MENTION_RE = re.compile(r"^<@!?(\d+)>$")


@dataclass
class SpaceCreateOptions:
    space_key: str
    member_tokens: list[str]
    share_policy: str = "members_only"
    default_context: str | None = "shared"
    channel_name: str | None = None
    open_to_everyone: bool = False


@dataclass
class SpaceCloseOptions:
    space_key: str
    confirm: bool = False
    dissolve_eddies: bool = False
    keep_workshop: bool = True


def normalize_space_key(raw: str) -> str:
    key = (raw or "").strip().lower().replace("-", "_")
    if not SPACE_KEY_RE.match(key):
        raise ValueError(
            "Space key must be snake_case (lowercase letters, digits, underscores; start with a letter)."
        )
    return key


def default_channel_name(space_key: str) -> str:
    return space_key.replace("_", "-")[:100]


def parse_space_create_args(args: list[str]) -> SpaceCreateOptions:
    """Parse tokens after ``!admin space create``."""
    if len(args) < 2:
        raise ValueError("Usage: `!admin space create <space-key> [--members @user ...] [--open] [--policy all_practitioners|members_only] [--context family|shared] [--channel name]`")

    space_key = normalize_space_key(args[1])
    share_policy = "members_only"
    default_context: str | None = "shared"
    channel_name: str | None = None
    open_to_everyone = False
    member_tokens: list[str] = []

    idx = 2
    while idx < len(args):
        token = args[idx]
        if token == "--members":
            idx += 1
            while idx < len(args) and not args[idx].startswith("--"):
                member_tokens.append(args[idx])
                idx += 1
            continue
        if token == "--open":
            open_to_everyone = True
            idx += 1
            continue
        if token == "--policy":
            idx += 1
            if idx >= len(args):
                raise ValueError("`--policy` requires `members_only` or `all_practitioners`.")
            share_policy = args[idx].lower()
            if share_policy not in VALID_POLICIES:
                raise ValueError(f"Unknown share policy `{share_policy}`.")
            idx += 1
            continue
        if token == "--context":
            idx += 1
            if idx >= len(args):
                raise ValueError("`--context` requires `family` or `shared`.")
            ctx = args[idx].lower()
            if ctx not in VALID_CONTEXTS:
                raise ValueError(f"Unknown context `{ctx}`.")
            default_context = ctx
            idx += 1
            continue
        if token == "--channel":
            idx += 1
            if idx >= len(args):
                raise ValueError("`--channel` requires a Discord channel name slug.")
            channel_name = args[idx].strip().lower().replace("_", "-")[:100]
            idx += 1
            continue
        raise ValueError(f"Unknown flag or argument: `{token}`.")
    return SpaceCreateOptions(
        space_key=space_key,
        member_tokens=member_tokens,
        share_policy=share_policy,
        default_context=default_context,
        channel_name=channel_name,
        open_to_everyone=open_to_everyone,
    )


def parse_space_close_args(args: list[str]) -> SpaceCloseOptions:
    if len(args) < 2:
        raise ValueError("Usage: `!admin space close <space-key> [--confirm] [--dissolve-eddies] [--keep-workshop]`")
    space_key = normalize_space_key(args[1])
    confirm = False
    dissolve_eddies = False
    keep_workshop = True
    idx = 2
    while idx < len(args):
        token = args[idx]
        if token == "--confirm":
            confirm = True
        elif token == "--dissolve-eddies":
            dissolve_eddies = True
        elif token == "--keep-workshop":
            keep_workshop = True
        else:
            raise ValueError(f"Unknown flag: `{token}`.")
        idx += 1
    return SpaceCloseOptions(
        space_key=space_key,
        confirm=confirm,
        dissolve_eddies=dissolve_eddies,
        keep_workshop=keep_workshop,
    )


def mage_key_for_discord_id(registry: dict[str, Any], discord_id: str | int) -> str | None:
    target = str(discord_id)
    for key, mage in registry.get("mages", {}).items():
        if str(mage.get("discord_id")) == target:
            return key
    return None


def resolve_member_keys(
    guild: discord.Guild,
    registry: dict[str, Any],
    *,
    member_tokens: list[str],
    message_mentions: list[discord.Member],
    operator_id: int,
) -> list[str]:
    """Resolve --members tokens and mentions to registered mage keys."""
    resolved: list[str] = []
    seen: set[str] = set()

    mention_by_id = {str(m.id): m for m in message_mentions}

    def add_key(key: str) -> None:
        if key not in seen:
            seen.add(key)
            resolved.append(key)

    for token in member_tokens:
        match = MENTION_RE.match(token)
        if match:
            uid = match.group(1)
            member = mention_by_id.get(uid) or guild.get_member(int(uid))
            if not member:
                raise ValueError(f"Mention `{token}` is not a server member.")
            key = mage_key_for_discord_id(registry, member.id)
            if not key:
                raise ValueError(
                    f"**{member.display_name}** is not a registered practitioner. "
                    f"Run `!admin onboard` or `!admin river-key` first."
                )
            add_key(key)
            continue

        mage_key_candidate = token.lower().lstrip("@")
        if mage_key_candidate in registry.get("mages", {}):
            mage = registry["mages"][mage_key_candidate]
            if mage.get("discord_id"):
                add_key(mage_key_candidate)
                continue

        # Discord @-autocomplete mentions arrive in message.mentions, not always as <@id> tokens.
        if token.startswith("@"):
            continue

        target_member = None
        lowered = token.lower()
        for m in guild.members:
            if m.name.lower() == lowered or m.display_name.lower() == lowered:
                target_member = m
                break
        if not target_member:
            raise ValueError(f"Member `{token}` not found on server.")
        key = mage_key_for_discord_id(registry, target_member.id)
        if not key:
            raise ValueError(
                f"**{target_member.display_name}** is not a registered practitioner. "
                f"Run `!admin onboard` or `!admin river-key` first."
            )
        add_key(key)

    for member in message_mentions:
        key = mage_key_for_discord_id(registry, member.id)
        if not key:
            raise ValueError(
                f"**{member.display_name}** is not a registered practitioner. "
                f"Run `!admin onboard` or `!admin river-key` first."
            )
        add_key(key)

    if not resolved:
        op_key = mage_key_for_discord_id(registry, operator_id)
        if not op_key:
            raise ValueError(
                "Could not resolve operator mage key. Pass `--members` explicitly."
            )
        add_key(op_key)

    return resolved


def validate_space_available(registry: dict[str, Any], space_key: str) -> None:
    if space_key in registry.get("spaces", {}):
        raise ValueError(f"Space `{space_key}` already exists in registry.")
    for entry in registry.get("channels", {}).values():
        if isinstance(entry, dict) and entry.get("mage") == space_key and entry.get("type") == "shared-river":
            if not entry.get("archived"):
                raise ValueError(f"A shared-river channel is already bound to `{space_key}`.")


def shared_member_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        create_public_threads=True,
        send_messages_in_threads=True,
    )


def build_shared_space_overwrites(
    guild: discord.Guild,
    *,
    member_discord_ids: list[int],
    open_to_everyone: bool,
) -> dict:
    everyone = guild.default_role
    overwrites: dict = {}
    if open_to_everyone:
        overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
        )
    else:
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)

    member_perms = shared_member_overwrite()
    for uid in member_discord_ids:
        member = guild.get_member(uid)
        if member:
            overwrites[member] = member_perms

    for op_id in _primary_operator_ids():
        if op_id in member_discord_ids:
            continue
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


def seed_space_workshop(space_key: str) -> str:
    """Minimal practice root for a shared space (not full practitioner onboarding)."""
    import shutil

    workshop = os.path.expanduser(f"~/workshops/{space_key}")
    for sub in ("state", "state/notes", "flows", "sessions", "proposals"):
        os.makedirs(os.path.join(workshop, sub), exist_ok=True)

    flow_src = os.path.join(REPO_ROOT, "template", "flows", "shared-river-orientation.md")
    flow_dest = os.path.join(workshop, "flows", "shared-river-orientation.md")
    if os.path.isfile(flow_src) and not os.path.exists(flow_dest):
        shutil.copy2(flow_src, flow_dest)

    canon_src = os.path.join(
        REPO_ROOT, "template", "flows", "shared-river-orientation-canonical.stub.md"
    )
    canon_dest = os.path.join(workshop, "state", "notes", "shared-river-orientation-canonical.md")
    if os.path.isfile(canon_src) and not os.path.exists(canon_dest):
        shutil.copy2(canon_src, canon_dest)

    return workshop


def find_shared_river_channel(registry: dict[str, Any], space_key: str) -> tuple[str, dict] | None:
    for ch_id_str, entry in registry.get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "shared-river":
            continue
        if entry.get("mage") != space_key:
            continue
        if entry.get("archived"):
            continue
        return ch_id_str, entry
    return None


def list_active_spaces(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spaces = registry.get("spaces", {})
    for ch_id_str, entry in registry.get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "shared-river":
            continue
        if entry.get("archived"):
            continue
        space_key = entry.get("mage")
        if not space_key:
            continue
        space = spaces.get(space_key, {}) if isinstance(spaces.get(space_key), dict) else {}
        rows.append(
            {
                "space_key": space_key,
                "channel_id": ch_id_str,
                "members": list(space.get("members") or []),
                "share_policy": space.get("share_policy", "members_only"),
                "default_context": entry.get("default_context"),
            }
        )
    return sorted(rows, key=lambda r: r["space_key"])


def write_space_registry(
    registry: dict[str, Any],
    *,
    space_key: str,
    channel_id: int,
    member_keys: list[str],
    share_policy: str,
    default_context: str | None,
) -> None:
    registry.setdefault("spaces", {})[space_key] = {
        "practice_dir": f"~/workshops/{space_key}",
        "runtime_dir": f"~/workshops/{space_key}",
        "members": list(member_keys),
        "share_policy": share_policy,
    }
    registry.setdefault("channels", {})[str(channel_id)] = {
        "mage": space_key,
        "type": "shared-river",
        "default_context": default_context,
        "description": f"Shared practice space ({space_key})",
    }
    save_registry(registry)


def mark_space_archived(registry: dict[str, Any], channel_id_str: str) -> None:
    entry = registry.get("channels", {}).get(channel_id_str)
    if isinstance(entry, dict):
        entry["archived"] = True
        entry["archived_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)


def mark_channel_orphaned(
    registry: dict[str, Any],
    channel_id_str: str,
    *,
    reason: str = "discord_deleted",
) -> bool:
    """Registry-bound channel removed in Discord — keep workshop, flag orphan."""
    entry = registry.get("channels", {}).get(channel_id_str)
    if not isinstance(entry, dict):
        return False
    entry["archived"] = True
    entry["orphaned"] = True
    entry["orphan_reason"] = reason
    entry["orphaned_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return True


async def create_shared_space(
    guild: discord.Guild,
    options: SpaceCreateOptions,
    *,
    member_keys: list[str],
) -> tuple[discord.TextChannel, str]:
    from mage import get_registry, reload_mage_registry

    registry = get_registry()
    validate_space_available(registry, options.space_key)

    channel_slug = options.channel_name or default_channel_name(options.space_key)
    existing = discord.utils.get(guild.text_channels, name=channel_slug)
    if existing:
        raise ValueError(f"Channel `#{channel_slug}` already exists.")

    member_ids: list[int] = []
    for key in member_keys:
        mage = registry.get("mages", {}).get(key, {})
        raw = mage.get("discord_id")
        if not raw:
            raise ValueError(f"Practitioner `{key}` has no discord_id in registry.")
        member_ids.append(int(raw))

    category = discord.utils.get(guild.categories, name="Practice")
    overwrites = build_shared_space_overwrites(
        guild,
        member_discord_ids=member_ids,
        open_to_everyone=options.open_to_everyone,
    )

    create_kwargs = {
        "name": channel_slug,
        "overwrites": overwrites,
        "topic": f"Shared practice space — {options.space_key.replace('_', ' ')}",
    }
    if category:
        create_kwargs["category"] = category

    channel = await guild.create_text_channel(**create_kwargs)
    try:
        workshop = seed_space_workshop(options.space_key)
        write_space_registry(
            registry,
            space_key=options.space_key,
            channel_id=channel.id,
            member_keys=member_keys,
            share_policy=options.share_policy,
            default_context=options.default_context,
        )
        reload_mage_registry()

        from mage import ensure_space_channel_access

        await ensure_space_channel_access(channel, guild=guild)
        return channel, workshop
    except Exception:
        try:
            await channel.delete(reason="space provisioning rollback")
        except discord.HTTPException:
            pass
        raise


async def close_shared_space(
    guild: discord.Guild,
    options: SpaceCloseOptions,
    *,
    discord_client,
) -> dict[str, Any]:
    from mage import get_registry, reload_mage_registry

    registry = get_registry()
    binding = find_shared_river_channel(registry, options.space_key)
    if not binding:
        raise ValueError(f"No active shared-river space `{options.space_key}` found.")

    ch_id_str, entry = binding
    channel = guild.get_channel(int(ch_id_str))
    if channel is None:
        try:
            channel = await guild.fetch_channel(int(ch_id_str))
        except discord.HTTPException as exc:
            raise ValueError(f"Registry channel `{ch_id_str}` not reachable: {exc}") from exc

    space = registry.get("spaces", {}).get(options.space_key, {})
    members = list(space.get("members") or []) if isinstance(space, dict) else []
    open_threads = 0
    if isinstance(channel, discord.TextChannel):
        open_threads = len(getattr(channel, "threads", []) or [])

    summary = {
        "space_key": options.space_key,
        "channel_name": getattr(channel, "name", ch_id_str),
        "channel_id": ch_id_str,
        "members": members,
        "share_policy": space.get("share_policy", "members_only") if isinstance(space, dict) else "members_only",
        "open_threads": open_threads,
    }

    if not options.confirm:
        return summary

    if isinstance(channel, discord.TextChannel):
        archived_category = discord.utils.get(guild.categories, name="Archived")
        lock_overwrites = dict(channel.overwrites)
        everyone = guild.default_role
        lock_overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
        )
        for target, ow in list(lock_overwrites.items()):
            if hasattr(target, "bot") and target.bot:
                continue
            lock_overwrites[target] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                create_public_threads=False,
                send_messages_in_threads=False,
            )
        edit_kwargs: dict[str, Any] = {"overwrites": lock_overwrites}
        if archived_category:
            edit_kwargs["category"] = archived_category
        try:
            await channel.edit(**edit_kwargs)
        except discord.HTTPException as exc:
            raise ValueError(f"Could not archive channel: {exc}") from exc

        if options.dissolve_eddies:
            from sessions import dissolve_eddy

            threads = list(channel.threads)
            for thread in threads:
                if not thread.archived:
                    await dissolve_eddy(thread.id, discord_client=discord_client)

    mark_space_archived(registry, ch_id_str)
    reload_mage_registry()
    summary["archived"] = True
    return summary
