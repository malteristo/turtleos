#!/usr/bin/env python3
"""Create a health channel. Abort and delete if the wrong people can see it.

A second person's health is a second instance. Abort only when this subject
already has a health channel. One member is enough (solo, no steward).

Reads member Discord ids from mage_registry.yaml. Does not post a message.
Does not ingest documents. Writes a non-sensitive empty board only.

    python3 scripts/provision_health_channel.py --members default partner
    python3 scripts/provision_health_channel.py --members operator --subject operator
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

FAMILY_CATEGORY_NAMES = frozenset({"family"})
SHARED_CHANNEL_NAME = "health"
SOLO_CHANNEL_NAME = "my-health"
CATEGORY_NAME = "Health"
SHARED_TOPIC = "Living picture — best current explanation. Doctors decide treatment."
SOLO_TOPIC = "Your board — best current explanation. Doctors decide treatment."
HEALTH_ROOT_MODE = 0o700
EMPTY_BOARD = """# Health picture

The best current explanation of the data, for walking into the public system with it. Doctors write the legal diagnosis and the prescription. They do not own the model. The patient decides what leaves this file.

**Subject of this store:** the owner of this room. They correct what is here.
**Update rules:** Magic `library/flows/diagnostic/` — intake, integration, navigation.
Name the best current model. Label it as a model until the owner confirms it. Write what is known, what is not, what would distinguish.
Gaps stay empty until someone brings them.

---

## Now

Gaps stay empty until someone brings them.

## Observed

- Loop check: this board is reachable from this room. Not a clinical observation.

## Documented

## Patterns

## Unexplained

## Questions for doctors
"""


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


def existing_health_for_subject(registry: dict, subject: str) -> str | None:
    from channel_primitives import resolve_primitive

    for cid, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived"):
            continue
        primitive = resolve_primitive(registry, cid)
        if (
            primitive is not None
            and primitive.name == "health"
            and primitive.subject == subject
        ):
            return str(cid)
    return None


def first_guild_channel_id(registry: dict) -> int:
    for cid, entry in (registry.get("channels") or {}).items():
        if not str(cid).isdigit():
            continue
        if isinstance(entry, dict) and entry.get("archived"):
            continue
        return int(cid)
    raise RuntimeError("No registered channel to resolve the guild from.")


def collect_viewers(channel, everyone_id: int) -> tuple[bool, set[int], set[int]]:
    import discord
    from health_room import overwrite_allows_view, overwrite_denies_view

    everyone_denied = False
    viewers: set[int] = set()
    roles: set[int] = set()
    for target, ow in channel.overwrites.items():
        if getattr(target, "id", None) == everyone_id:
            everyone_denied = overwrite_denies_view(ow)
            continue
        if not overwrite_allows_view(ow):
            continue
        if isinstance(target, discord.Role):
            roles.add(target.id)
        else:
            viewers.add(int(target.id))
    return everyone_denied, viewers, roles


def resolve_instance(
    member_keys: list[str],
    *,
    subject: str | None = None,
    support: str | None = None,
) -> dict[str, str | list[str] | None]:
    if not 1 <= len(member_keys) <= 2:
        raise ValueError("Need one or two members.")
    if len(set(member_keys)) != len(member_keys):
        raise ValueError("Members must be unique.")
    resolved_subject = subject or (member_keys[0] if len(member_keys) == 1 else member_keys[1])
    if resolved_subject not in member_keys:
        raise ValueError("Subject must be a member of the health space.")
    if len(member_keys) == 1:
        resolved_support = None
        if support:
            raise ValueError("Support must already be a member of the health space.")
        space_key = f"health-{resolved_subject}"
        channel_name = SOLO_CHANNEL_NAME
        topic = SOLO_TOPIC
        description = "Your board — best current explanation"
        base = "solo"
        channel_type = "health"
    else:
        if support is None:
            resolved_support = next(
                (key for key in member_keys if key != resolved_subject), None
            )
        else:
            resolved_support = support
        if resolved_support == resolved_subject:
            raise ValueError("Owner and support must be different people.")
        if resolved_support not in member_keys:
            raise ValueError("Support must already be a member of the health space.")
        space_key = "health"
        channel_name = SHARED_CHANNEL_NAME
        topic = SHARED_TOPIC
        description = "Living picture — best current explanation"
        base = "shared"
        channel_type = "health"
    practice_dir = f"~/workshops/{space_key}"
    return {
        "subject": resolved_subject,
        "steward": resolved_support,
        "space_key": space_key,
        "channel_name": channel_name,
        "topic": topic,
        "description": description,
        "base": base,
        "channel_type": channel_type,
        "practice_dir": practice_dir,
        "members": list(member_keys),
    }


def write_health_registry(
    registry: dict,
    *,
    channel_id: int,
    member_keys: list[str],
    subject: str | None = None,
    support: str | None = None,
) -> dict[str, str | list[str] | None]:
    from river_keys import save_registry

    instance = resolve_instance(member_keys, subject=subject, support=support)
    space_key = str(instance["space_key"])
    space: dict = {
        "practice_dir": instance["practice_dir"],
        "runtime_dir": instance["practice_dir"],
        "members": list(instance["members"] or []),
        "subject": instance["subject"],
        "share_policy": "members_only",
        "memory": "isolated",
    }
    if instance["steward"]:
        space["steward"] = instance["steward"]
    registry.setdefault("spaces", {})[space_key] = space
    channel: dict = {
        "mage": space_key,
        "type": instance["channel_type"],
        "primitive": "health",
        "attunement": "health",
        "default_context": "health",
        "discord_category": CATEGORY_NAME,
        "description": instance["description"],
        "subject": instance["subject"],
    }
    if instance["base"] == "solo":
        channel["base"] = "solo"
    registry.setdefault("channels", {})[str(channel_id)] = channel
    save_registry(registry)
    return instance


def ensure_health_root(practice_dir: Path) -> bool:
    """Create the private root at 0700. Return True when this call created it."""
    path = practice_dir.expanduser()
    created = False
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f"health root exists and is not a directory: {path}")
    else:
        path.mkdir(parents=True, mode=HEALTH_ROOT_MODE)
        created = True
    os.chmod(path, HEALTH_ROOT_MODE)
    mode = path.stat().st_mode & 0o777
    if mode != HEALTH_ROOT_MODE:
        raise RuntimeError(f"health root permissions are {oct(mode)}, expected {oct(HEALTH_ROOT_MODE)}")
    return created


def write_empty_board(practice_dir: Path) -> None:
    path = practice_dir.expanduser() / "health_model.md"
    if path.is_file():
        return
    path.write_text(EMPTY_BOARD, encoding="utf-8")
    os.chmod(path, 0o600)


HEALTH_CONTEXT_STUB = "# Kontext dieses Raums\n# Wünsche an Turtle\n\n"


def write_empty_health_context(practice_dir: Path) -> bool:
    """Heading-only wish slot. Do not invent wishes. False if a file exists."""
    path = practice_dir.expanduser() / "state" / "context.md"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEALTH_CONTEXT_STUB, encoding="utf-8")
    os.chmod(path, 0o600)
    return True


def rollback_health_root(practice_dir: Path, *, created: bool) -> None:
    path = practice_dir.expanduser()
    if created and path.is_dir():
        shutil.rmtree(path)


def revert_registry_row(registry: dict, *, space_key: str, channel_id: int) -> None:
    from river_keys import save_registry

    channels = registry.get("channels") or {}
    channels.pop(str(channel_id), None)
    spaces = registry.get("spaces") or {}
    if space_key != "health":
        spaces.pop(space_key, None)
    save_registry(registry)


async def provision(
    member_keys: list[str],
    *,
    subject: str | None = None,
    support: str | None = None,
) -> int:
    import discord
    from health_room import (
        health_permission_overwrites,
        raw_everyone_denied,
        visibility_findings,
    )
    from river_keys import _river_bot_member
    from state import SPIRIT_BOT_ID

    try:
        instance = resolve_instance(member_keys, subject=subject, support=support)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    env = load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found")

    registry = load_registry()
    existing = existing_health_for_subject(registry, str(instance["subject"]))
    if existing:
        print(
            f"ABORT: subject {instance['subject']} already has a health channel ({existing})",
            file=sys.stderr,
        )
        return 2

    member_ids = member_discord_ids(registry, member_keys)
    lookup_id = first_guild_channel_id(registry)
    practice_dir = Path(str(instance["practice_dir"]))
    created_root = False
    channel = None
    registry_written = False

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        try:
            created_root = ensure_health_root(practice_dir)
            write_empty_board(practice_dir)
            from health_record import ensure_record_structure

            ensure_record_structure(practice_dir)
            write_empty_health_context(practice_dir)
        except Exception as error:
            print(f"ABORT: health root failed — {error}", file=sys.stderr)
            rollback_health_root(practice_dir, created=created_root)
            return 1

        seed = await client.fetch_channel(lookup_id)
        guild = seed.guild
        if guild is None:
            rollback_health_root(practice_dir, created=created_root)
            raise RuntimeError("Could not resolve the guild from a registered channel.")
        try:
            await guild.chunk()
        except discord.HTTPException:
            pass

        guild_channels = await guild.fetch_channels()
        channel_name = str(instance["channel_name"])
        existing_named = [
            ch for ch in guild_channels if getattr(ch, "name", None) == channel_name
        ]
        if existing_named:
            rollback_health_root(practice_dir, created=created_root)
            print(f"ABORT: #{channel_name} already exists", file=sys.stderr)
            return 2

        if client.user is None:
            rollback_health_root(practice_dir, created=created_root)
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
            name=channel_name,
            topic=str(instance["topic"]),
            parent_id=category_id,
            permission_overwrites=payload,
        )
        channel = await client.fetch_channel(int(data["id"]))

        async def abort_channel(reason: str, message: str) -> int:
            if channel is not None:
                await channel.delete(reason=reason)
            rollback_health_root(practice_dir, created=created_root)
            print(message, file=sys.stderr)
            return 1

        if not raw_everyone_denied(data.get("permission_overwrites") or [], everyone_id):
            return await abort_channel(
                "health room @everyone deny missing from create payload",
                "ABORT: @everyone deny did not land — deleted",
            )
        if channel.category and (channel.category.name or "").strip().lower() in FAMILY_CATEGORY_NAMES:
            return await abort_channel(
                "health room must not sit under Family",
                "ABORT: channel landed under Family — deleted",
            )
        if getattr(channel, "category_id", None) != category_id:
            return await abort_channel(
                "health room desired category missing",
                "ABORT: channel did not land under Health — deleted",
            )

        fresh = await guild.fetch_channel(channel.id)
        everyone_denied, viewers, roles = collect_viewers(fresh, everyone_id)
        if not everyone_denied and raw_everyone_denied(
            data.get("permission_overwrites") or [], everyone_id
        ):
            everyone_denied = True
        allowed = set(member_ids) | set(bot_ids)
        findings = visibility_findings(
            everyone_denied=everyone_denied,
            viewer_ids=viewers,
            allowed_ids=allowed,
            viewing_role_ids=roles,
        )
        if findings:
            print("ABORT: wrong people can see it — deleted", file=sys.stderr)
            for line in findings:
                print(f"  {line}", file=sys.stderr)
            return await abort_channel(
                "health room visibility check failed",
                "ABORT: visibility check failed — deleted",
            )

        try:
            write_health_registry(
                registry,
                channel_id=fresh.id,
                member_keys=member_keys,
                subject=str(instance["subject"]),
                support=instance["steward"] if instance["steward"] else None,
            )
            registry_written = True
        except Exception:
            if registry_written:
                revert_registry_row(
                    registry,
                    space_key=str(instance["space_key"]),
                    channel_id=fresh.id,
                )
            await fresh.delete(reason="health room registry write failed")
            rollback_health_root(practice_dir, created=created_root)
            raise

        print(f"health channel {fresh.id}")
        print(f"space {instance['space_key']}")
        print(f"subject {instance['subject']}")
        print("visibility ok")
        print("no message posted")
        return 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--members",
        nargs="+",
        required=True,
        help="Registry mage keys who may see the room (one or two people).",
    )
    parser.add_argument("--subject", help="Record owner. Defaults to the sole member, or the second of two.")
    parser.add_argument("--support", help="Optional support member. Two-member default: the non-subject.")
    args = parser.parse_args()
    if not 1 <= len(args.members) <= 2:
        print("Need one or two members.", file=sys.stderr)
        return 2
    return asyncio.run(
        provision(args.members, subject=args.subject, support=args.support)
    )


if __name__ == "__main__":
    raise SystemExit(main())
