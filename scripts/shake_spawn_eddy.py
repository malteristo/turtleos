#!/usr/bin/env python3
"""Spawn a native flow eddy for Spirit shakedown (no Eddy Door button click).

Uses the Turtle bot token. With split-bot mode, writes pending native eddy
state for the running discord_bot to finalize on thread join.

Exit 0 on success (prints JSON with thread_id). Exit 1 on failure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ENV_PATH = Path.home() / "turtleos" / ".env"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def resolve_river_channel_id(env: dict[str, str]) -> int:
    raw = env.get("DISCORD_CHANNEL_DIALOGUE") or env.get("DISCORD_CHANNEL_RIVER")
    if raw and raw.isdigit():
        return int(raw)
    registry_path = Path.home() / "turtleos" / "mage_registry.yaml"
    if registry_path.is_file():
        import yaml

        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        for ch_id, entry in (registry.get("channels") or {}).items():
            if not str(ch_id).isdigit():
                continue
            if isinstance(entry, dict) and entry.get("type") in ("river", "hosted-river"):
                return int(ch_id)
            if isinstance(entry, str):
                return int(ch_id)
    raise RuntimeError("Could not resolve river channel id from .env or mage_registry.yaml")


async def main_async(args: argparse.Namespace) -> dict:
    import discord
    from eddy_spawn import spawn_blank_river_eddy

    env = load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found in ~/turtleos/.env")

    channel_id = resolve_river_channel_id(env)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    topic = args.topic or f"shake-{args.flow}-{stamp}"

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        channel = await client.fetch_channel(channel_id)
        thread = await spawn_blank_river_eddy(
            channel,
            flow_id=args.flow,
            eddy_type=args.eddy_type,
            topic=topic,
        )
        if thread is None:
            raise RuntimeError("spawn_blank_river_eddy returned None")
        return {
            "status": "ok",
            "flow_id": args.flow,
            "topic": topic,
            "thread_id": str(thread.id),
            "parent_channel_id": str(channel_id),
            "jump_url": getattr(thread, "jump_url", None),
        }
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Spawn a shake eddy with flow context")
    parser.add_argument("--flow", default="shelter", help="Flow id (default: shelter)")
    parser.add_argument("--topic", default=None, help="Thread name (default: shake-<flow>-<stamp>)")
    parser.add_argument("--eddy-type", default="standard", dest="eddy_type")
    args = parser.parse_args()
    try:
        report = asyncio.run(main_async(args))
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
