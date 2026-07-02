#!/usr/bin/env python3
"""Shakedown for blank eddy spawn + standing lifecycle bar (flows · checkpoint · share).

Exercises `_spawn_eddy_from_anchor(channel)` → `spawn_river_eddy` (empty room)
→ first practitioner message → bottom lifecycle bar via `touch_eddy_lifecycle_bar`.

Flow library is on-demand via the **flows** button (`!flows`), not a standing bar.

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

    from flow_runner import list_resolvable_flow_ids

    flows = list_resolvable_flow_ids()
    if not flows:
        errors.append("no resolvable flows under practice root")

    try:
        from river_handler import RiverEddyBarView, _spawn_eddy_from_anchor  # noqa: F401
    except ImportError as exc:
        errors.append(f"river_handler import failed: {exc}")
        return errors

    river_src = (REPO / "river_handler.py").read_text(encoding="utf-8")
    bar_block = river_src.split("class RiverEddyBarView")[1].split("class RiverEddyView")[0]
    if "flow menu" in bar_block or "_on_flow_menu" in bar_block:
        errors.append("RiverEddyBarView still references flow menu")

    try:
        from eddy_lifecycle_bar import EddyLifecycleBarView  # noqa: F401
    except ImportError as exc:
        errors.append(f"eddy_lifecycle_bar import failed: {exc}")
        return errors

    lifecycle_src = (REPO / "eddy_lifecycle_bar.py").read_text(encoding="utf-8")
    lifecycle_block = lifecycle_src.split("class EddyLifecycleBarView")[1].split(
        "class EddyDissolveConfirmView", 1
    )[0]
    if "eddy:lifecycle:flowpick:" not in lifecycle_block:
        errors.append("EddyLifecycleBarView missing flow pick select")
    for label in ("checkpoint", "share"):
        if f'label="{label}"' not in lifecycle_block:
            errors.append(f"EddyLifecycleBarView missing {label!r} button (live phase)")
    if "post_eddy_bootstrap_bar" not in lifecycle_src:
        errors.append("eddy_lifecycle_bar missing post_eddy_bootstrap_bar")
    if "upgrade_eddy_bar_to_live" not in lifecycle_src:
        errors.append("eddy_lifecycle_bar missing upgrade_eddy_bar_to_live")

    try:
        from eddy_flow_library import EddyFlowLibraryView, post_eddy_flow_library  # noqa: F401
    except ImportError as exc:
        errors.append(f"eddy_flow_library import failed: {exc}")

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


async def _lifecycle_bar_labels_in_thread(thread_id: str) -> set[str]:
    """Read button labels from recent messages (discord_ops text omits components)."""
    import discord

    env = _load_env()
    token = env.get("RIVER_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIVER_BOT_TOKEN not set")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    found: set[str] = set()
    try:
        ch = await client.fetch_channel(int(thread_id))
        async for message in ch.history(limit=20):
            for row in message.components or []:
                for child in getattr(row, "children", []):
                    label = (getattr(child, "label", None) or "").lower().strip()
                    if label in {"checkpoint", "share"}:
                        found.add(label)
                    cid = getattr(child, "custom_id", None) or ""
                    if "eddy:lifecycle:flowpick:" in cid:
                        found.add("flowpick")
    finally:
        await client.close()
    return found


async def _spawn_blank_eddy() -> dict:
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
        thread = await _spawn_eddy_from_anchor(channel, flow_id=None)
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
        return ["RIVER_BOT_TOKEN not set — blank eddy bar path needs split-bot"]

    import asyncio

    try:
        spawn = asyncio.run(_spawn_blank_eddy())
    except Exception as exc:
        return [f"bar blank spawn failed: {type(exc).__name__}: {exc}"]

    thread_id = spawn.get("thread_id")
    thread_name = (spawn.get("thread_name") or "").strip()
    if not thread_id:
        errors.append(f"spawn missing thread_id: {spawn}")
        return errors

    if thread_name.lower() != "new eddy":
        errors.append(f"expected thread titled 'new eddy', got {thread_name!r}")

    time.sleep(2)
    transcript = _read_thread(thread_id)
    lower = transcript.lower()
    if "guided flow" in lower and "optional" in lower:
        errors.append(
            "flow library embed visible at materialize "
            "(expected bootstrap bar select only)"
        )

    try:
        bar_labels = asyncio.run(_lifecycle_bar_labels_in_thread(thread_id))
    except Exception as exc:
        errors.append(f"lifecycle bar component inspect failed: {exc}")
        return errors

    if "flowpick" not in bar_labels:
        errors.append("bootstrap bar missing flow pick at materialize")
    if "checkpoint" in bar_labels or "share" in bar_labels:
        errors.append("checkpoint/share visible before first practitioner message")

    try:
        _spirit_send(thread_id, "shake: blank eddy bar path — hello turtle")
    except Exception as exc:
        errors.append(f"spirit first message failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript = _read_thread(thread_id)
    lower = transcript.lower()
    if "turtle" not in lower:
        errors.append("no Turtle reply after first message in blank eddy")

    try:
        bar_labels = asyncio.run(_lifecycle_bar_labels_in_thread(thread_id))
    except Exception as exc:
        errors.append(f"lifecycle bar component inspect failed: {exc}")
        return errors

    for label in ("flowpick", "checkpoint", "share"):
        if label not in bar_labels:
            errors.append(
                f"live lifecycle bar missing {label!r} "
                "(expected flow pick · checkpoint · share after first message)"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Blank eddy spawn + standing lifecycle bar shakedown"
    )
    parser.add_argument("--live", action="store_true", help="Live Discord on Mini (River token)")
    parser.add_argument("--wait", type=int, default=50, help="Seconds to wait for Turtle reply")
    args = parser.parse_args()

    all_errors: dict[str, list[str]] = {"offline": check_offline()}
    if args.live:
        all_errors["live"] = check_live(args.wait)

    report = {
        "capability": "river/eddy_lifecycle_bar_blank_eddy",
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
