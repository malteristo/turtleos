#!/usr/bin/env python3
"""Shakedown for Discord permalink read-for-dialogue (D2 / D2b).

Offline checks always run. With --live, seeds a source eddy, pastes permalinks
into a target eddy on Discord via shake_spawn_eddy + spirit_ops (run on Mini).

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

VENV_PY = Path.home() / "turtleos" / "venv" / "bin" / "python3"
SPIRIT_OPS = Path.home() / "turtleos" / "spirit_ops.py"
DISCORD_OPS = Path.home() / "turtleos" / "discord_ops.py"
SHAKE_SPAWN = REPO / "scripts" / "shake_spawn_eddy.py"
ENV_PATH = Path.home() / "turtleos" / ".env"

MARKER_ALPHA = "SHAKE_D2_ALPHA: turquoise widgets win"
MARKER_BETA = "SHAKE_D2_BETA: ship by Friday"


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
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

    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_discord_ref_read")
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful():
        errors.append(
            f"tests.test_discord_ref_read failed ({len(result.failures)} fail, {len(result.errors)} err)"
        )

    from discord_ref_read import (
        DISCORD_REF_INJECT_LABEL,
        DISCORD_THREAD_REF_LABEL,
        THREAD_HISTORY_MAX_MESSAGES,
        THREAD_INLINE_MAX,
        extract_all_discord_refs,
        permalink_for,
    )

    sample = f"remind me {permalink_for(1, 2, 3)}"
    if extract_all_discord_refs(sample) != [(1, 2, 3)]:
        errors.append("extract_all_discord_refs broken for message permalink")
    thread_sample = f"what happened {permalink_for(1, 99)}"
    if extract_all_discord_refs(thread_sample) != [(1, 99, None)]:
        errors.append("extract_all_discord_refs broken for thread permalink")
    if THREAD_HISTORY_MAX_MESSAGES < 10:
        errors.append(f"THREAD_HISTORY_MAX_MESSAGES too low: {THREAD_HISTORY_MAX_MESSAGES}")
    if THREAD_INLINE_MAX < 8000:
        errors.append(f"THREAD_INLINE_MAX too low: {THREAD_INLINE_MAX}")
    if DISCORD_REF_INJECT_LABEL != "Read Discord message":
        errors.append("unexpected DISCORD_REF_INJECT_LABEL")
    if DISCORD_THREAD_REF_LABEL != "Read Discord thread":
        errors.append("unexpected DISCORD_THREAD_REF_LABEL")

    link_ux = REPO / "docs" / "ux" / "link-reading.md"
    if link_ux.is_file():
        ux_text = link_ux.read_text(encoding="utf-8")
        for needle in (
            "Discord permalinks",
            "Reading Discord message",
            "summarized",
            "shake_discord_ref.py",
        ):
            if needle not in ux_text:
                errors.append(f"docs/ux/link-reading.md missing: {needle}")
    else:
        errors.append("docs/ux/link-reading.md not found")

    spec_path = REPO / "TURTLE_SPEC.md"
    if spec_path.is_file():
        spec_text = spec_path.read_text(encoding="utf-8")
        for needle in (
            "Discord permalinks (read-for-dialogue)",
            "discord_ref_read.py",
            "Discord permalinks are never distilled",
        ):
            if needle not in spec_text:
                errors.append(f"TURTLE_SPEC missing: {needle}")
    else:
        errors.append("TURTLE_SPEC.md not found")

    return errors


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _spirit_send(thread_id: str, text: str) -> None:
    proc = _run([str(VENV_PY), str(SPIRIT_OPS), "send", thread_id, text], timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "spirit_ops send failed")


def _read_thread(thread_id: str, limit: int = 40) -> str:
    proc = _run(
        [str(VENV_PY), str(DISCORD_OPS), "read", thread_id, str(limit)],
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "discord_ops read failed")
    return proc.stdout


def _parse_json_stdout(stdout: str) -> dict:
    start = stdout.find("{")
    if start == -1:
        raise ValueError(f"no JSON in stdout: {stdout[:300]}")
    return json.loads(stdout[start:])


def _spawn_eddy(topic: str) -> dict:
    proc = _run(
        [str(VENV_PY), str(SHAKE_SPAWN), "--flow", "navigator", "--topic", topic],
        timeout=90,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "shake_spawn_eddy failed")
    return _parse_json_stdout(proc.stdout)


async def _send_message_and_permalink(thread_id: str, text: str) -> str:
    env = _load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found")

    import discord
    from discord_ref_read import permalink_for

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        channel = await client.fetch_channel(int(thread_id))
        message = await channel.send(text)
        guild_id = channel.guild.id
        return permalink_for(guild_id, channel.id, message.id)
    finally:
        await client.close()


def check_live(wait_seconds: int) -> list[str]:
    errors: list[str] = []
    if not VENV_PY.is_file():
        return ["venv python not found — run on Mac Mini"]

    stamp = int(time.time())
    try:
        source = _spawn_eddy(f"shake-d2-src-{stamp}")
        source_thread = str(source["thread_id"])
    except Exception as exc:
        return [f"source eddy spawn failed: {exc}"]

    time.sleep(4)
    try:
        asyncio.run(_send_message_and_permalink(source_thread, MARKER_ALPHA))
        _spirit_send(source_thread, MARKER_BETA)
        time.sleep(2)
        msg_link = asyncio.run(_send_message_and_permalink(source_thread, "SHAKE_D2 anchor message"))
    except Exception as exc:
        errors.append(f"source eddy seed failed: {exc}")
        return errors

    from discord_ref_read import permalink_for

    thread_link = permalink_for(
        int(msg_link.split("/")[5]),
        int(msg_link.split("/")[6]),
    )

    try:
        target = _spawn_eddy(f"shake-d2-tgt-{stamp}")
        target_thread = str(target["thread_id"])
    except Exception as exc:
        errors.append(f"target eddy spawn failed: {exc}")
        return errors

    time.sleep(4)
    try:
        _spirit_send(target_thread, f"what did we decide about widgets? {msg_link}")
    except Exception as exc:
        errors.append(f"D2 message permalink send failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript = _read_thread(target_thread)
    lower = transcript.lower()
    if "reading discord" not in lower and "read discord message" not in lower:
        errors.append("D2: no Read Discord message trace in target thread")
    if "turquoise" not in lower and "widgets" not in lower:
        errors.append("D2: Turtle reply did not reference linked content")

    time.sleep(3)
    try:
        _spirit_send(
            target_thread,
            f"summarize the whole eddy — {thread_link}",
        )
    except Exception as exc:
        errors.append(f"D2b thread permalink send failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript_b = _read_thread(target_thread, limit=60)
    lower_b = transcript_b.lower()
    if "read discord thread" not in lower_b and "reading discord thread" not in lower_b:
        errors.append("D2b: no Read Discord thread trace in target thread")
    if not re.search(r"\b\d+\s*messages?\b", lower_b):
        errors.append("D2b: embed missing message count hint")

    try:
        _spirit_send(target_thread, "!release")
    except Exception as exc:
        errors.append(f"spirit !release failed: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Discord permalink read shakedown")
    parser.add_argument("--live", action="store_true", help="Run live Discord exercise on Mini")
    parser.add_argument("--wait", type=int, default=35, help="Seconds to wait for read + reply")
    args = parser.parse_args()

    all_errors: dict[str, list[str]] = {"offline": check_offline()}
    if args.live:
        all_errors["live"] = check_live(args.wait)

    status = "pass" if all(not v for v in all_errors.values()) else "fail"
    artifact = {
        "capability": "discord_ref_read/D2-D2b",
        "status": status,
        "live": args.live,
        "checks": {k: ("ok" if not v else v) for k, v in all_errors.items()},
    }
    out_path = REPO / "test-runs" / "shake-discord-ref-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))

    if status != "pass":
        for section, errs in all_errors.items():
            for err in errs:
                print(f"FAIL [{section}]: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
