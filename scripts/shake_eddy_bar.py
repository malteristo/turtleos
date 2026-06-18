#!/usr/bin/env python3
"""Shakedown for standing eddy bar → flow menu materialize path.

Exercises the same spawn path as [flow menu] → Shelter on the river bar:
`_spawn_eddy_from_anchor(channel, flow_id=...)` → `spawn_river_eddy` →
`prepare_flow_eddy_entry`.

Offline checks always run. With --live, uses River bot token on Mac Mini.

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

VENV_PY = Path.home() / "turtleos" / "venv" / "bin" / "python3"
SPIRIT_OPS = Path.home() / "turtleos" / "spirit_ops.py"
DISCORD_OPS = Path.home() / "turtleos" / "discord_ops.py"
ENV_PATH = Path.home() / "turtleos" / ".env"

FLOW_ID = "shelter"


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    for key, val in values.items():
        os.environ.setdefault(key, val)
    return values


def check_offline() -> list[str]:
    errors: list[str] = []
    if "discord" not in sys.modules:
        try:
            import discord  # noqa: F401
        except ModuleNotFoundError:
            from unittest.mock import MagicMock

            sys.modules.setdefault("discord", MagicMock())
            sys.modules.setdefault("discord.ui", MagicMock())

    from flow_runner import (
        flow_entry_blurb,
        list_resolvable_flow_ids,
        load_flow_spec,
    )

    flows = list_resolvable_flow_ids()
    if FLOW_ID not in flows:
        errors.append(f"{FLOW_ID} not in list_resolvable_flow_ids: {flows}")

    spec = load_flow_spec(FLOW_ID)
    if spec is None:
        errors.append(f"load_flow_spec({FLOW_ID}) returned None")
    elif spec.title != "Shelter":
        errors.append(f"unexpected flow title: {spec.title!r}")
    else:
        blurb = flow_entry_blurb(spec)
        if "checkpoint" not in blurb.lower() and "fresh start" not in blurb.lower():
            errors.append("flow_entry_blurb missing checkpoint hint")

    try:
        from river_handler import _spawn_eddy_from_anchor  # noqa: F401 — import path
    except ImportError as exc:
        errors.append(f"river_handler spawn import failed: {exc}")

    return errors


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO))


def _read_thread(thread_id: str, limit: int = 20) -> str:
    proc = _run([str(VENV_PY), str(DISCORD_OPS), "read", thread_id, str(limit)], timeout=60)
    return proc.stdout + proc.stderr


def _spirit_send(channel_id: str, text: str) -> None:
    proc = _run([str(VENV_PY), str(SPIRIT_OPS), "send", channel_id, text], timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "spirit_ops send failed")


async def _spawn_bar_flow_eddy() -> dict:
    import discord
    from river_handler import _spawn_eddy_from_anchor

    env = _load_env()
    token = env.get("RIVER_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIVER_BOT_TOKEN not set — bar path requires split-bot River")

    channel_id = env.get("DISCORD_CHANNEL_DIALOGUE") or env.get("DISCORD_CHANNEL_RIVER")
    if not channel_id or not str(channel_id).isdigit():
        registry_path = Path.home() / "turtleos" / "mage_registry.yaml"
        if registry_path.is_file():
            import yaml

            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            for cid, entry in (registry.get("channels") or {}).items():
                if str(cid).isdigit():
                    channel_id = str(cid)
                    break
    if not channel_id:
        raise RuntimeError("Could not resolve river channel id")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        channel = await client.fetch_channel(int(channel_id))
        thread = await _spawn_eddy_from_anchor(channel, flow_id=FLOW_ID)
        if thread is None:
            raise RuntimeError("_spawn_eddy_from_anchor returned None")
        return {
            "status": "ok",
            "thread_id": str(thread.id),
            "thread_name": thread.name,
            "jump_url": getattr(thread, "jump_url", None),
            "parent_channel_id": str(channel_id),
        }
    finally:
        await client.close()


def check_live(wait_seconds: int) -> list[str]:
    errors: list[str] = []
    if not VENV_PY.is_file():
        return ["venv python not found — run on Mac Mini"]

    env = _load_env()
    if not env.get("RIVER_BOT_TOKEN", "").strip():
        return ["RIVER_BOT_TOKEN not set — bar flow menu path needs split-bot"]

    import asyncio

    try:
        spawn = asyncio.run(_spawn_bar_flow_eddy())
    except Exception as exc:
        return [f"bar flow spawn failed: {type(exc).__name__}: {exc}"]

    thread_id = spawn.get("thread_id")
    thread_name = (spawn.get("thread_name") or "").strip()
    if not thread_id:
        errors.append(f"spawn missing thread_id: {spawn}")
        return errors

    if thread_name.lower() != "shelter":
        errors.append(f"expected thread titled Shelter, got {thread_name!r}")

    time.sleep(2)
    transcript = _read_thread(thread_id)
    if "shelter eddy" not in transcript.lower() and "speak when ready" not in transcript.lower():
        errors.append("orientation embed not visible in thread (missing Shelter eddy / footer)")

    try:
        _spirit_send(thread_id, "shake: bar flow menu path — holding space")
    except Exception as exc:
        errors.append(f"spirit first message failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript = _read_thread(thread_id)
    if "turtle" not in transcript.lower():
        errors.append("no Turtle reply after first message in bar-flow eddy")

    try:
        _spirit_send(thread_id, "!checkpoint")
    except Exception as exc:
        errors.append(f"spirit !checkpoint failed: {exc}")
        return errors

    time.sleep(15)
    transcript = _read_thread(thread_id)
    if "checkpoint saved" not in transcript.lower() and "flow:" not in transcript.lower():
        errors.append("!checkpoint did not produce expected confirmation embed")

    checkpoint = Path.home() / "workshop" / "desk" / "state" / "notes" / "shelter-last.md"
    if not checkpoint.is_file():
        errors.append(f"flow checkpoint file missing: {checkpoint}")
    elif "bar flow menu" not in checkpoint.read_text(encoding="utf-8").lower():
        if "holding space" not in checkpoint.read_text(encoding="utf-8").lower():
            errors.append("shelter-last.md missing shake bar-path content")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Eddy bar flow-menu shakedown")
    parser.add_argument("--live", action="store_true", help="Live Discord on Mini (River token)")
    parser.add_argument("--wait", type=int, default=50, help="Seconds to wait for Turtle reply")
    args = parser.parse_args()

    all_errors: dict[str, list[str]] = {"offline": check_offline()}
    if args.live:
        all_errors["live"] = check_live(args.wait)

    report = {
        "capability": "river/eddy_bar_flow_menu",
        "status": "pass" if not any(all_errors.values()) else "fail",
        "live": args.live,
        "checks": {k: "ok" if not v else v for k, v in all_errors.items()},
    }
    print(json.dumps(report, indent=2))

    out_dir = REPO / "test-runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "shake-eddy-bar-latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
