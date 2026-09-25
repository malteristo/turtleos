#!/usr/bin/env python3
"""Migrate an established shared channel into a team instance in place.

Instance identifiers and member names belong in a private JSON manifest, never
in this public repository. Dry-run is the default; ``--apply`` performs the
Discord and shared-root migration through River.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from campaign_state import seed_from_prologue
from channel_primitives import resolve_primitive
from core.atomic_io import atomic_write_json


@dataclass(frozen=True)
class Lane:
    member: str
    title: str
    character: str
    initial_state: str


@dataclass(frozen=True)
class MigrationConfig:
    channel_id: str
    prologue_thread_id: str
    space_key: str
    activity_id: str
    channel_name: str
    coordinator: str
    topic: str
    world: str
    current_scene: str
    lanes: tuple[Lane, ...]

    @property
    def member_states(self) -> dict[str, str]:
        return {lane.member: lane.initial_state for lane in self.lanes}


def load_manifest(path: str | Path) -> MigrationConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    lanes = tuple(Lane(**row) for row in payload.get("lanes") or [])
    config = MigrationConfig(
        channel_id=str(payload["channel_id"]),
        prologue_thread_id=str(payload["prologue_thread_id"]),
        space_key=str(payload["space_key"]),
        activity_id=str(payload["activity_id"]),
        channel_name=str(payload.get("channel_name") or "quest"),
        coordinator=str(payload["coordinator"]),
        topic=str(payload["topic"]),
        world=str(payload["world"]),
        current_scene=str(payload["current_scene"]),
        lanes=lanes,
    )
    if len(config.lanes) < 2:
        raise ValueError("team migration manifest needs at least two member lanes")
    return config


def migrated_registry(registry: dict, config: MigrationConfig) -> dict:
    """Return the team declaration while preserving channel, root and audience."""
    result = deepcopy(registry)
    entry = (result.get("channels") or {}).get(config.channel_id)
    if not isinstance(entry, dict) or entry.get("mage") != config.space_key:
        raise RuntimeError("team source channel is not the expected shared space")
    space = (result.get("spaces") or {}).get(config.space_key)
    if not isinstance(space, dict):
        raise RuntimeError("team source space is missing")
    members = [str(value) for value in (space.get("members") or [])]
    lane_members = [lane.member for lane in config.lanes]
    if (
        len(members) < 2
        or config.coordinator not in members
        or set(lane_members) != set(members)
    ):
        raise RuntimeError(
            "manifest lanes must match all members and coordinator must be a member"
        )
    space["coordinator"] = config.coordinator
    space["memory"] = "own_root"
    entry.update(
        {
            "primitive": "team",
            "type": "shared-river",
            "attunement": "native",
            "default_context": "team",
            "discord_category": config.channel_name.replace("-", " ").title(),
            "name": config.channel_name,
            "discord_name": config.channel_name,
            "description": config.topic,
        }
    )
    primitive = resolve_primitive(result, config.channel_id)
    if primitive is None or primitive.name != "team":
        raise RuntimeError("migrated team contract does not validate")
    return result


def backup_live_inputs(registry_path: Path, practice_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = Path.home() / f"pre-team-migration-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(registry_path, backup / "mage_registry.yaml")
    campaign = practice_dir / "campaign"
    if campaign.is_dir():
        shutil.copytree(campaign, backup / "campaign")
    return backup


def seed_live_campaign(
    practice_dir: Path,
    primitive,
    config: MigrationConfig,
) -> dict:
    checkpoint = practice_dir / "campaign" / "checkpoints" / "latest.md"
    prologue = (
        practice_dir
        / "campaign"
        / "prologue"
        / f"{config.prologue_thread_id}.md"
    )
    source = prologue if prologue.is_file() else checkpoint
    if not source.is_file():
        raise RuntimeError("activity checkpoint is missing")
    return seed_from_prologue(
        practice_dir,
        primitive=primitive,
        activity_id=config.activity_id,
        source_thread_id=config.prologue_thread_id,
        checkpoint_text=source.read_text(encoding="utf-8"),
        world=config.world,
        current_scene=config.current_scene,
        member_states=config.member_states,
    )


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


async def apply_live(
    registry: dict,
    migrated: dict,
    config: MigrationConfig,
) -> dict:
    import discord
    import mage
    from river_keys import save_registry
    from team_lanes import register_lane
    from thread_registry import (
        mark_cooled,
        register_thread,
        update_thread_context_type,
        update_thread_locked,
    )

    token = load_env().get("RIVER_BOT_TOKEN")
    if not token:
        raise RuntimeError("RIVER_BOT_TOKEN not found")
    practice_dir = Path(
        os.path.expanduser(migrated["spaces"][config.space_key]["practice_dir"])
    )
    marker = (
        practice_dir
        / "team"
        / "migrations"
        / f"{config.activity_id}-team-v1.json"
    )
    if marker.is_file():
        return json.loads(marker.read_text(encoding="utf-8"))
    backup = backup_live_inputs(Path(mage.REGISTRY_PATH), practice_dir)
    primitive = resolve_primitive(migrated, config.channel_id)
    seeded = seed_live_campaign(practice_dir, primitive, config)

    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    await client.login(token)
    created = []
    try:
        channel = await client.fetch_channel(int(config.channel_id))
        prologue = await client.fetch_channel(int(config.prologue_thread_id))
        old_name = channel.name
        old_topic = getattr(channel, "topic", None)
        desired_category = migrated["channels"][config.channel_id][
            "discord_category"
        ]
        categories = [
            item
            for item in await channel.guild.fetch_channels()
            if isinstance(item, discord.CategoryChannel)
        ]
        category = next(
            (
                item
                for item in categories
                if item.name.casefold() == desired_category.casefold()
            ),
            None,
        )
        if category is None:
            category = await channel.guild.create_category(
                desired_category,
                overwrites=channel.overwrites,
                reason="team practice navigation",
            )
        await channel.edit(
            name=config.channel_name,
            topic=config.topic,
            category=category,
            sync_permissions=False,
            reason="team practice migration",
        )
        save_registry(migrated)
        mage.reload_mage_registry()

        if getattr(prologue, "archived", False):
            await prologue.edit(
                archived=False,
                reason="briefly reopen for team migration metadata",
            )
        await prologue.edit(
            name=f"{config.activity_id.replace('-', ' ').title()} — Prologue (shared table)",
            locked=True,
            archived=True,
            reason="superseded by asynchronous member lanes",
        )
        update_thread_locked(int(config.prologue_thread_id), True)
        mark_cooled(int(config.prologue_thread_id))

        threads: dict[str, object] = {}
        for lane in config.lanes:
            thread = await channel.create_thread(
                name=lane.title,
                auto_archive_duration=10080,
                type=discord.ChannelType.public_thread,
                reason="asynchronous team member lane",
            )
            created.append(thread)
            register_thread(
                thread.id,
                lane.title,
                parent_channel=config.channel_name,
                parent_channel_id=channel.id,
                model="local",
                attunement="native",
                context_type="dnd_dm",
                eddy_type="standard",
            )
            update_thread_context_type(thread.id, "dnd_dm")
            register_lane(
                thread.id,
                activity_id=config.activity_id,
                owner=lane.member,
                role="player",
                character=lane.character,
            )
            threads[lane.member] = thread

        sibling_ids = tuple(thread.id for thread in created)
        for lane in config.lanes:
            thread = threads[lane.member]
            register_lane(
                thread.id,
                activity_id=config.activity_id,
                owner=lane.member,
                role="player",
                character=lane.character,
                siblings=tuple(
                    value for value in sibling_ids if value != thread.id
                ),
            )
            await thread.send(
                "This is the member-owned lane for **"
                f"{lane.character}**. The story advances here without waiting "
                "for another lane; every team member may read it.\n\n"
                f"**From the preserved prologue:** {config.current_scene}"
            )

        note = await channel.send(
            "**This team space is ready.** The shared activity now advances "
            "asynchronously: each member writes in their own eddy, may peek at "
            "the others, and does not have to wait. Turtle carries meaningful "
            "effects between lanes inside the activity. The former shared table "
            "remains as the prologue."
        )
        payload = {
            "schema": 1,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "channel_id": config.channel_id,
            "old_channel_name": old_name,
            "old_channel_topic": old_topic,
            "prologue_thread_id": config.prologue_thread_id,
            "lanes": {
                member: str(thread.id) for member, thread in threads.items()
            },
            "announcement_message_id": str(note.id),
            "campaign_event_id": seeded["event"]["event_id"],
            "backup": str(backup),
        }
        atomic_write_json(marker, payload, indent=2)
        return payload
    except Exception:
        for thread in reversed(created):
            try:
                await thread.delete(reason="team migration rollback")
            except discord.HTTPException:
                pass
        raise
    finally:
        await client.close()


def dry_run(migrated: dict, config: MigrationConfig) -> dict:
    primitive = resolve_primitive(migrated, config.channel_id)
    return {
        "mode": "dry-run",
        "channel_id": config.channel_id,
        "channel_name": config.channel_name,
        "space_key": config.space_key,
        "practice_dir": migrated["spaces"][config.space_key]["practice_dir"],
        "primitive": primitive.name,
        "coordinator": primitive.coordinator,
        "members": list(primitive.members),
        "prologue_thread_id": config.prologue_thread_id,
        "lanes": {
            lane.member: lane.title for lane in config.lanes
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    import mage

    config = load_manifest(args.manifest)
    registry = mage._load_mage_registry()
    migrated = migrated_registry(registry, config)
    result = (
        asyncio.run(apply_live(registry, migrated, config))
        if args.apply
        else dry_run(migrated, config)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
