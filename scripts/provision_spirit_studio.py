#!/usr/bin/env python3
"""Create Spirit's coach studio. Not a household seat.

A private river on its own root. Operator and house bots can see it.
Community is not seated. ``roster: false`` keeps doctor clean.

    python3 scripts/provision_spirit_studio.py
    python3 scripts/provision_spirit_studio.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAGE_KEY = "spirit"
CHANNEL_NAME = "spirit"
CATEGORY_NAME = "Rivers"
TOPIC = "Spirit live-test only. Collaborate with Craft Turtle in #craft-turtle."
DESCRIPTION = "Live-test river — not a roster member; not the Forge collaboration room"
FAMILY_CATEGORY_NAMES = frozenset({"family"})


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


def existing_studio_channel(registry: dict) -> str | None:
    mage = (registry.get("mages") or {}).get(MAGE_KEY)
    if isinstance(mage, dict) and mage.get("roster") is False:
        for cid, entry in (registry.get("channels") or {}).items():
            if not isinstance(entry, dict) or entry.get("archived"):
                continue
            if entry.get("mage") == MAGE_KEY and entry.get("type") == "river":
                return str(cid)
    return None


def operator_discord_ids(registry: dict) -> list[int]:
    from mage import admin_discord_ids

    return sorted(admin_discord_ids(registry))


def first_guild_channel_id(registry: dict) -> int:
    for cid, entry in (registry.get("channels") or {}).items():
        if not str(cid).isdigit():
            continue
        if isinstance(entry, dict) and entry.get("archived"):
            continue
        return int(cid)
    raise RuntimeError("No registered channel to resolve the guild from.")


def bind_spirit_studio_registry(
    registry: dict,
    *,
    channel_id: int,
    discord_id: str | int,
) -> None:
    registry.setdefault("mages", {})[MAGE_KEY] = {
        "discord_id": str(discord_id),
        "address": "Spirit",
        "practice_dir": f"~/workshops/{MAGE_KEY}",
        "runtime_dir": f"~/workshops/{MAGE_KEY}",
        "type": "practitioner",
        "relation": "guest",
        "roster": False,
    }
    registry.setdefault("channels", {})[str(channel_id)] = {
        "mage": MAGE_KEY,
        "type": "river",
        "primitive": "private",
        "attunement": "native",
        "default_context": None,
        "discord_category": CATEGORY_NAME,
        "name": CHANNEL_NAME,
        "discord_name": CHANNEL_NAME,
        "description": DESCRIPTION,
    }


def write_spirit_studio_registry(
    registry: dict,
    *,
    channel_id: int,
    discord_id: str | int,
) -> None:
    from river_keys import save_registry

    bind_spirit_studio_registry(
        registry, channel_id=channel_id, discord_id=discord_id
    )
    save_registry(registry)


def revert_registry_row(registry: dict, *, channel_id: int) -> None:
    from river_keys import save_registry

    (registry.get("channels") or {}).pop(str(channel_id), None)
    (registry.get("mages") or {}).pop(MAGE_KEY, None)
    save_registry(registry)


async def provision(*, dry_run: bool = False) -> int:
    import discord
    from health_room import health_permission_overwrites, raw_everyone_denied
    from hosted_river_onboarding import seed_practitioner_workshop
    from river_keys import _river_bot_member
    from roster_sync import live_mages
    from state import SPIRIT_BOT_ID

    env = load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found")

    registry = load_registry()
    existing = existing_studio_channel(registry)
    if existing:
        print(f"already bound: #{CHANNEL_NAME} {existing}")
        return 0

    operator_ids = operator_discord_ids(registry)
    if not operator_ids:
        print("ABORT: no administrator discord_id to grant the studio", file=sys.stderr)
        return 2
    lookup_id = first_guild_channel_id(registry)

    if dry_run:
        print(
            f"dry-run: would open #{CHANNEL_NAME} for {MAGE_KEY} "
            f"(roster: false; operators {operator_ids})"
        )
        return 0

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    channel = None
    try:
        seed_practitioner_workshop(MAGE_KEY)

        seed = await client.fetch_channel(lookup_id)
        guild = seed.guild
        if guild is None:
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
            print(f"ABORT: #{CHANNEL_NAME} already exists", file=sys.stderr)
            return 2

        if client.user is None:
            raise RuntimeError("Discord login did not yield a user.")
        bot_ids = {client.user.id, int(SPIRIT_BOT_ID)}
        river = _river_bot_member(guild)
        if river:
            bot_ids.add(river.id)
        raw_river = env.get("RIVER_BOT_USER_ID", "").strip()
        if raw_river.isdigit():
            bot_ids.add(int(raw_river))

        everyone_id = guild.id
        payload = health_permission_overwrites(
            everyone_id=everyone_id,
            member_ids=operator_ids,
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
            print(f"ABORT: category {CATEGORY_NAME!r} not found", file=sys.stderr)
            return 2
        if (category.name or "").strip().lower() in FAMILY_CATEGORY_NAMES:
            print("ABORT: refusing to place the studio under Family", file=sys.stderr)
            return 2

        data = await client.http.create_channel(
            guild.id,
            0,
            name=CHANNEL_NAME,
            topic=TOPIC,
            parent_id=category.id,
            permission_overwrites=payload,
        )
        channel = await client.fetch_channel(int(data["id"]))

        async def abort_channel(reason: str, message: str) -> int:
            if channel is not None:
                await channel.delete(reason=reason)
            revert_registry_row(registry, channel_id=channel.id)
            print(message, file=sys.stderr)
            return 1

        if not raw_everyone_denied(data.get("permission_overwrites") or [], everyone_id):
            return await abort_channel(
                "spirit studio @everyone deny missing",
                "ABORT: @everyone deny did not land — deleted",
            )
        if channel.category and (channel.category.name or "").strip().lower() in FAMILY_CATEGORY_NAMES:
            return await abort_channel(
                "spirit studio landed under Family",
                "ABORT: channel landed under Family — deleted",
            )

        write_spirit_studio_registry(
            registry, channel_id=channel.id, discord_id=SPIRIT_BOT_ID
        )
        if MAGE_KEY in live_mages(registry):
            return await abort_channel(
                "spirit studio became a member",
                "ABORT: studio row counted as a roster member — deleted",
            )
        print(f"#{CHANNEL_NAME} {channel.id} — coach studio (roster: false)")
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
