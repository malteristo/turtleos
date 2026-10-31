#!/usr/bin/env python3
"""Create the owner's private #magic room and bind it to their workshop checkout.

One room, one person: @everyone cannot see it, only the owner and the bots can.
The registry row names the `magic` primitive and the owner's `workshop.checkout`;
nothing else about the house changes. Aborts and deletes what it made if the
@everyone deny did not land or the row does not resolve to the magic primitive.

    python3 scripts/provision_magic_channel.py --owner kermit --dry-run
    python3 scripts/provision_magic_channel.py --owner kermit
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHANNEL_NAME = "magic"
CATEGORY_NAME = "Magic"
TOPIC = "Practise magic here. Summon opens a session."
DESCRIPTION = "The magic practice, in its own room"
DEFAULT_CHECKOUT = "~/workshop"


class Abort(Exception):
    pass


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

    data = yaml.safe_load(Path(REGISTRY_PATH).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise Abort("The registry is not a mapping.")
    return data


def check_ready(registry: dict, owner: str, checkout: str) -> int:
    """Abort unless the owner is a real member with a Discord id, the workshop is a git checkout, and no magic room exists."""
    entry = (registry.get("mages") or {}).get(owner)
    if not isinstance(entry, dict) or not entry.get("discord_id"):
        raise Abort(f"`{owner}` is not a member with a Discord id.")
    if not (Path(os.path.expanduser(checkout)) / ".git").exists():
        raise Abort(f"{checkout} is not a git checkout.")
    for cid, row in (registry.get("channels") or {}).items():
        if isinstance(row, dict) and not row.get("archived") and row.get("mage") == owner and (
            row.get("primitive") == "magic" or row.get("type") == "magic"
        ):
            raise Abort(f"{owner} already has a magic room ({cid}).")
    return int(entry["discord_id"])


def write_registry(registry: dict, *, channel_id: int, owner: str, checkout: str) -> None:
    """Add the room's row and the owner's checkout; nothing else is touched."""
    registry.setdefault("channels", {})[str(channel_id)] = {
        "mage": owner,
        "type": "magic",
        "primitive": "magic",
        "name": CHANNEL_NAME,
        "discord_name": CHANNEL_NAME,
        "discord_category": CATEGORY_NAME,
        "description": DESCRIPTION,
    }
    shop = registry["mages"][owner].setdefault("workshop", {})
    shop.setdefault("checkout", checkout)


def resolves_to_magic(registry: dict, channel_id: int) -> bool:
    from channel_primitives import resolve_primitive

    primitive = resolve_primitive(registry, channel_id)
    return bool(primitive and primitive.name == "magic" and primitive.has("workshop"))


async def ensure_category(client, guild, channels, payload) -> int:
    """The id of the room's category, made as private as the room when it is missing.

    A room without a category used to be created silently when the named category was
    absent. Every room belongs to one, so absence is made good here or the script stops.
    """
    import discord

    for item in channels:
        if isinstance(item, discord.CategoryChannel) and item.name.casefold() == CATEGORY_NAME.casefold():
            return int(item.id)
    data = await client.http.create_channel(guild.id, 4, name=CATEGORY_NAME, permission_overwrites=payload)
    return int(data["id"])


async def provision(owner: str, *, dry_run: bool = False) -> int:
    import discord
    from health_room import health_permission_overwrites, raw_everyone_denied
    from river_keys import _river_bot_member, save_registry
    from state import SPIRIT_BOT_ID

    env = load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise Abort("DISCORD_BOT_TOKEN not found")
    registry = load_registry()
    owner_id = check_ready(registry, owner, DEFAULT_CHECKOUT)
    lookup_id = next(
        (int(cid) for cid, row in (registry.get("channels") or {}).items() if str(cid).isdigit() and isinstance(row, dict) and not row.get("archived")),
        None,
    )
    if lookup_id is None:
        raise Abort("No registered channel to resolve the guild from.")
    if dry_run:
        print(f"dry-run: would create private #{CHANNEL_NAME} for {owner} on {DEFAULT_CHECKOUT}")
        return 0

    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    await client.login(token)
    channel = None
    try:
        guild = (await client.fetch_channel(lookup_id)).guild
        channels = await guild.fetch_channels()
        if any(getattr(ch, "name", None) == CHANNEL_NAME for ch in channels):
            raise Abort(f"#{CHANNEL_NAME} already exists")
        bot_ids = {client.user.id, int(SPIRIT_BOT_ID)}
        river = _river_bot_member(guild)
        if river:
            bot_ids.add(river.id)
        raw_river = env.get("RIVER_BOT_USER_ID", "").strip()
        if raw_river.isdigit():
            bot_ids.add(int(raw_river))
        payload = health_permission_overwrites(everyone_id=guild.id, member_ids=[owner_id], bot_ids=sorted(bot_ids))
        category_id = await ensure_category(client, guild, channels, payload)
        kwargs = {"name": CHANNEL_NAME, "topic": TOPIC, "permission_overwrites": payload, "parent_id": category_id}
        data = await client.http.create_channel(guild.id, 0, **kwargs)
        channel = await client.fetch_channel(int(data["id"]))
        if int(data.get("parent_id") or 0) != category_id:
            raise Abort(f"#{CHANNEL_NAME} did not land in the {CATEGORY_NAME} category")
        if not raw_everyone_denied(data.get("permission_overwrites") or [], guild.id):
            raise Abort("@everyone deny did not land")
        write_registry(registry, channel_id=channel.id, owner=owner, checkout=DEFAULT_CHECKOUT)
        if not resolves_to_magic(registry, channel.id):
            raise Abort("the row does not resolve to the magic primitive")
        save_registry(registry)
        print(f"#{CHANNEL_NAME} {channel.id} for {owner}")
        return 0
    except Abort:
        if channel is not None:
            await channel.delete(reason="magic room did not verify")
        raise
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(provision(args.owner, dry_run=args.dry_run))
    except Abort as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
