#!/usr/bin/env python3
"""Create the house-wide #community room. Not a practice.

Join seats every new member here. Partnership, health, and quest stay
their own rooms. Abort and delete if @everyone can see it, or if the
channel lands under Family.

    python3 scripts/provision_community_channel.py
    python3 scripts/provision_community_channel.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPACE_KEY = "community"
CHANNEL_NAME = "community"
CATEGORY_NAME = "Community"
FAMILY_CATEGORY_NAMES = frozenset({"family"})
TOPIC = "Everyone's room."
DESCRIPTION = "House-wide shared river — not a practice"


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    path = Path.home() / "turtleos" / ".env"
    if not path.is_file():
        path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env.setdefault(key.strip(), value.strip())
    return env


def load_registry() -> dict:
    import yaml
    from mage import REGISTRY_PATH

    path = Path(REGISTRY_PATH)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Registry is not a mapping: {path}")
    return data


def live_member_keys(registry: dict) -> list[str]:
    """Seat people who already have a live private river.

    A mage row can stay live after its river is archived (a retired
    guest, a departed-but-not-flagged row). They are not house members
    for this room.
    """
    from roster_sync import has_private_river, live_mages

    return sorted(
        key for key in live_mages(registry) if has_private_river(registry, key)
    )


def member_discord_ids(registry: dict, keys: list[str]) -> list[int]:
    mages = registry.get("mages") or {}
    ids: list[int] = []
    for key in keys:
        entry = mages.get(key) or {}
        raw = entry.get("discord_id")
        if not raw:
            raise RuntimeError(f"Practitioner `{key}` has no discord_id in the registry.")
        ids.append(int(raw))
    return ids


def first_guild_channel_id(registry: dict) -> int:
    for cid, entry in (registry.get("channels") or {}).items():
        if not str(cid).isdigit():
            continue
        if isinstance(entry, dict) and entry.get("archived"):
            continue
        return int(cid)
    raise RuntimeError("No registered channel to resolve the guild from.")


def existing_community_channel(registry: dict) -> str | None:
    from roster_sync import find_community_space
    from space_provisioning import find_shared_river_channel

    if find_community_space(registry):
        binding = find_shared_river_channel(registry, SPACE_KEY)
        if binding:
            return binding[0]
    for cid, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived"):
            continue
        if entry.get("mage") == SPACE_KEY and entry.get("type") == "shared-river":
            return str(cid)
    return None


def write_community_registry(
    registry: dict,
    *,
    channel_id: int,
    member_keys: list[str],
) -> None:
    from river_keys import save_registry

    if not member_keys:
        raise ValueError("Community needs at least one live member.")
    registry.setdefault("spaces", {})[SPACE_KEY] = {
        "practice_dir": f"~/workshops/{SPACE_KEY}",
        "runtime_dir": f"~/workshops/{SPACE_KEY}",
        "members": list(member_keys),
        "share_policy": "members_only",
        "memory": "own_root",
    }
    registry.setdefault("channels", {})[str(channel_id)] = {
        "mage": SPACE_KEY,
        "type": "shared-river",
        "primitive": "shared",
        "attunement": "native",
        "default_context": "shared",
        "discord_category": CATEGORY_NAME,
        "name": CHANNEL_NAME,
        "discord_name": CHANNEL_NAME,
        "description": DESCRIPTION,
    }
    save_registry(registry)


def revert_registry_row(registry: dict, *, channel_id: int) -> None:
    from river_keys import save_registry

    (registry.get("channels") or {}).pop(str(channel_id), None)
    (registry.get("spaces") or {}).pop(SPACE_KEY, None)
    save_registry(registry)


def rollback_workshop(practice_dir: Path, *, created: bool) -> None:
    if created and practice_dir.is_dir():
        shutil.rmtree(practice_dir)


async def provision(*, dry_run: bool = False) -> int:
    import discord
    from health_room import health_permission_overwrites, raw_everyone_denied
    from river_keys import _river_bot_member
    from space_provisioning import seed_space_workshop
    from state import SPIRIT_BOT_ID

    env = load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found")

    registry = load_registry()
    existing = existing_community_channel(registry)
    if existing:
        print(f"ABORT: community channel already bound ({existing})", file=sys.stderr)
        return 2

    member_keys = live_member_keys(registry)
    if not member_keys:
        print("ABORT: no live members to seat in community", file=sys.stderr)
        return 2
    member_ids = member_discord_ids(registry, member_keys)
    lookup_id = first_guild_channel_id(registry)
    practice_dir = Path(f"~/workshops/{SPACE_KEY}").expanduser()

    if dry_run:
        print(f"dry-run: would seat {', '.join(member_keys)} in #{CHANNEL_NAME}")
        return 0

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    created_root = False
    channel = None
    try:
        created_root = not practice_dir.is_dir()
        seed_space_workshop(SPACE_KEY)

        seed = await client.fetch_channel(lookup_id)
        guild = seed.guild
        if guild is None:
            rollback_workshop(practice_dir, created=created_root)
            raise RuntimeError("Could not resolve the guild from a registered channel.")
        try:
            await guild.chunk()
        except discord.HTTPException:
            pass

        guild_channels = await guild.fetch_channels()
        existing_named = [
            ch for ch in guild_channels if getattr(ch, "name", None) == CHANNEL_NAME
        ]
        if existing_named:
            rollback_workshop(practice_dir, created=created_root)
            print(f"ABORT: #{CHANNEL_NAME} already exists", file=sys.stderr)
            return 2

        if client.user is None:
            rollback_workshop(practice_dir, created=created_root)
            raise RuntimeError("Discord login did not yield a user.")
        bot_ids = {client.user.id}
        river = _river_bot_member(guild)
        if river:
            bot_ids.add(river.id)
        raw_river = env.get("RIVER_BOT_USER_ID", "").strip()
        if raw_river.isdigit():
            bot_ids.add(int(raw_river))
        bot_ids.add(int(SPIRIT_BOT_ID))
        everyone_id = guild.id
        payload = health_permission_overwrites(
            everyone_id=everyone_id,
            member_ids=member_ids,
            bot_ids=sorted(bot_ids),
        )
        category = next(
            (
                item
                for item in guild_channels
                if isinstance(item, discord.CategoryChannel)
                and item.name.casefold() == CATEGORY_NAME.casefold()
            ),
            None,
        )
        if category is None:
            category_data = await client.http.create_channel(
                guild.id,
                4,
                name=CATEGORY_NAME,
                permission_overwrites=payload,
            )
            category_id = int(category_data["id"])
        else:
            category_id = category.id
        data = await client.http.create_channel(
            guild.id,
            0,
            name=CHANNEL_NAME,
            topic=TOPIC,
            parent_id=category_id,
            permission_overwrites=payload,
        )
        channel = await client.fetch_channel(int(data["id"]))

        async def abort_channel(reason: str, message: str) -> int:
            if channel is not None:
                await channel.delete(reason=reason)
            remaining = [
                ch
                for ch in (await guild.fetch_channels())
                if getattr(ch, "category_id", None) == category_id
            ]
            if not remaining:
                await client.http.delete_channel(category_id)
            rollback_workshop(practice_dir, created=created_root)
            print(message, file=sys.stderr)
            return 1

        if not raw_everyone_denied(data.get("permission_overwrites") or [], everyone_id):
            return await abort_channel(
                "community @everyone deny missing",
                "ABORT: @everyone deny did not land — deleted",
            )
        if channel.category and (channel.category.name or "").strip().lower() in FAMILY_CATEGORY_NAMES:
            return await abort_channel(
                "community landed under Family",
                "ABORT: channel landed under Family — deleted",
            )

        write_community_registry(
            registry, channel_id=channel.id, member_keys=member_keys
        )
        from channel_primitives import resolve_primitive
        from roster_sync import find_community_space

        primitive = resolve_primitive(registry, channel.id)
        if find_community_space(registry) != SPACE_KEY or (
            primitive is None or primitive.name != "shared"
        ):
            revert_registry_row(registry, channel_id=channel.id)
            return await abort_channel(
                "community contract invalid",
                "ABORT: community contract did not resolve — deleted",
            )
        print(
            f"#{CHANNEL_NAME} {channel.id} — seated {', '.join(member_keys)}"
        )
        return 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(provision(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
