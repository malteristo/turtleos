#!/usr/bin/env python3
"""Shakedown for eddy link reading (link_read slice).

Offline checks always run. With --live, drops a URL in a fresh eddy on Discord
via shake_spawn_eddy + spirit_ops (run on Mac Mini).

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import argparse
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

# Stable public page — example.com is predictable; use a known-good article in live if needed.
OFFLINE_URL = "https://example.com"
LIVE_URL = "https://example.com"
LIVE_MESSAGE = f"shake link read {LIVE_URL}"


def check_offline() -> list[str]:
    errors: list[str] = []

    if "discord" not in sys.modules:
        try:
            import discord  # noqa: F401
        except ModuleNotFoundError:
            from unittest.mock import MagicMock

            sys.modules.setdefault("discord", MagicMock())
            sys.modules.setdefault("discord.ui", MagicMock())

    suite = unittest.defaultTestLoader.loadTestsFromNames(
        ["tests.test_link_read", "tests.test_url_validate"]
    )
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful():
        errors.append(f"tests.test_link_read failed ({len(result.failures)} fail, {len(result.errors)} err)")

    from link_read import (
        DIALOGUE_INJECT_MAX,
        FetchResult,
        _partial_read_status_lines,
        should_auto_fetch_urls,
        should_rename_thread_from_fetch,
    )

    if not should_auto_fetch_urls(OFFLINE_URL, [OFFLINE_URL]):
        errors.append("URL-only message should auto-fetch")
    if should_rename_thread_from_fetch("navigator", OFFLINE_URL, river_enabled=True):
        errors.append("River mode must not allow link-read rename")
    if not should_rename_thread_from_fetch("new eddy", OFFLINE_URL, river_enabled=False):
        errors.append("blank eddy should allow rename in single-bot mode")
    if DIALOGUE_INJECT_MAX < 8000:
        errors.append(f"DIALOGUE_INJECT_MAX too low: {DIALOGUE_INJECT_MAX}")

    lines = _partial_read_status_lines(
        FetchResult(
            url=LIVE_URL,
            ok=True,
            content="x" * 10000,
            source="article",
            char_count=10000,
            artifact_path="box/intake/test.md",
            prompt_excerpt_chars=8000,
        )
    )
    joined = "\n".join(lines)
    if "8,000 / 10,000" not in joined:
        errors.append("partial read status missing N/M ratio")

    link_ux = REPO / "docs" / "ux" / "link-reading.md"
    if link_ux.is_file():
        ux_text = link_ux.read_text(encoding="utf-8")
        for needle in (
            "Two jobs, two modes",
            "Timeline owns the trace",
            "URL-primary auto",
            "River names threads",
        ):
            if needle not in ux_text:
                errors.append(f"docs/ux/link-reading.md missing: {needle}")
    else:
        errors.append("docs/ux/link-reading.md not found")

    spec_path = REPO / "TURTLE_SPEC.md"
    if spec_path.is_file():
        spec_text = spec_path.read_text(encoding="utf-8")
        for needle in ("### 9.5 Link Reading", "Law of Visible Link Read", "Read for dialogue"):
            if needle not in spec_text:
                errors.append(f"TURTLE_SPEC missing: {needle}")
    else:
        errors.append("TURTLE_SPEC.md not found")

    return errors


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _parse_thread_id(stdout: str) -> str | None:
    match = re.search(r"thread[_\s]?id[=:\s]+(\d+)", stdout, re.I)
    return match.group(1) if match else None


def _spirit_send(thread_id: str, text: str) -> None:
    proc = _run(
        [str(VENV_PY), str(SPIRIT_OPS), "send", "--thread", thread_id, text],
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "spirit_ops send failed")


def _read_thread(thread_id: str) -> str:
    proc = _run(
        [str(VENV_PY), str(DISCORD_OPS), "read-thread", thread_id, "--limit", "40"],
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "discord_ops read failed")
    return proc.stdout


def check_live(wait_seconds: int) -> list[str]:
    errors: list[str] = []
    if not VENV_PY.is_file():
        return ["venv python not found — run on Mac Mini"]

    spawn = _run([str(VENV_PY), str(SHAKE_SPAWN), "--flow", "navigator", "--topic", "shake-link-read"], timeout=90)
    if spawn.returncode != 0:
        errors.append(f"shake_spawn_eddy failed: {spawn.stderr or spawn.stdout}")
        return errors

    thread_id: str | None = None
    try:
        data = json.loads(spawn.stdout)
        thread_id = str(data.get("thread_id") or "")
    except json.JSONDecodeError:
        thread_id = _parse_thread_id(spawn.stdout)
    if not thread_id:
        errors.append(f"could not parse thread id: {spawn.stdout[:300]}")
        return errors

    time.sleep(3)
    try:
        _spirit_send(thread_id, LIVE_MESSAGE)
    except Exception as exc:
        errors.append(f"spirit URL message failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript = _read_thread(thread_id)
    lower = transcript.lower()
    if "reading" not in lower and "read " not in lower and "🔗" not in transcript:
        errors.append("no link-read status embed (Reading/Read) in thread transcript")
    if "turtle" not in lower:
        errors.append("no Turtle reply after URL message")

    try:
        _spirit_send(thread_id, "!release")
    except Exception as exc:
        errors.append(f"spirit !release failed: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Link reading shakedown")
    parser.add_argument("--live", action="store_true", help="Run live Discord exercise on Mini")
    parser.add_argument("--wait", type=int, default=30, help="Seconds to wait for fetch + reply")
    args = parser.parse_args()

    all_errors: dict[str, list[str]] = {"offline": check_offline()}
    if args.live:
        all_errors["live"] = check_live(args.wait)

    status = "pass" if all(not v for v in all_errors.values()) else "fail"
    artifact = {
        "capability": "link_read/eddy-dialogue",
        "status": status,
        "live": args.live,
        "checks": {k: ("ok" if not v else v) for k, v in all_errors.items()},
    }
    out_path = REPO / "test-runs" / "shake-link-read-latest.json"
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
