#!/usr/bin/env python3
"""Shakedown for split-bot lifecycle capture (R4/R5 acceptance scenarios).

Offline: dialogue_store + reload_history wiring.
Live: spawn eddy → Spirit dialogue → shared runtime file → !checkpoint → !release.

Exit 0 = pass, 1 = fail. Verdict: test-runs/shake-lifecycle-latest.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

VENV_PY = Path.home() / "turtleos" / "venv" / "bin" / "python3"
SPIRIT_OPS = Path.home() / "turtleos" / "spirit_ops.py"
DISCORD_OPS = Path.home() / "turtleos" / "discord_ops.py"
SHAKE_SPAWN = REPO / "scripts" / "shake_spawn_eddy.py"
VERDICT_PATH = REPO / "test-runs" / "shake-lifecycle-latest.json"

SHAKE_MSGS = [
    "shake lifecycle R4/R5: first turn — what is one sentence about Mars meteorites?",
    "shake lifecycle: second turn — summarize what we discussed in one line.",
    "shake lifecycle: third turn — ready for checkpoint test.",
]


def check_offline() -> list[str]:
    errors: list[str] = []
    if "discord" not in sys.modules:
        try:
            import discord  # noqa: F401
        except ModuleNotFoundError:
            from unittest.mock import MagicMock

            sys.modules.setdefault("discord", MagicMock())
            sys.modules.setdefault("discord.ui", MagicMock())
            sys.modules.setdefault("discord.ext", MagicMock())
            sys.modules.setdefault("discord.ext.tasks", MagicMock())

    from dialogue_store import read_shared, shared_dialogue_enabled, write_shared

    if not hasattr(write_shared, "__call__"):
        errors.append("dialogue_store.write_shared missing")

    with tempfile.TemporaryDirectory() as tmp:
        try:
            with patch("mage.get_runtime_dir", return_value=tmp):
                write_shared(12345, [{"role": "user", "content": "offline"}])
                loaded = read_shared(12345)
                if not loaded or loaded[0]["content"] != "offline":
                    errors.append("dialogue_store roundtrip failed")
        except Exception as exc:
            errors.append(f"dialogue_store offline check: {type(exc).__name__}: {exc}")

    try:
        from helpers import dialogue_histories, reload_history

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dialogue"
            path.mkdir()
            (path / "99.json").write_text(
                json.dumps([{"role": "user", "content": "x"}]), encoding="utf-8"
            )
            dialogue_histories.clear()
            with patch("dialogue_store.shared_dialogue_enabled", return_value=True), patch(
                "mage.get_runtime_dir", return_value=tmp
            ):
                h = reload_history(99)
                if len(h) != 1 or h[0]["content"] != "x":
                    errors.append("reload_history did not load shared file")
    except Exception as exc:
        errors.append(f"reload_history wiring: {type(exc).__name__}: {exc}")

    errors.extend(_check_preview_surface_offline())

    return errors


def _check_preview_surface_offline() -> list[str]:
    """Issue 036 / TURTLE_SPEC §8.4 checkpoint visibility: the manual
    checkpoint reply surfaces the eddy-note preview + open action, consumed
    from CheckpointResult.eddy_note (no re-read from disk)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    errors: list[str] = []
    try:
        import cmd_sessions
        import story_notes
        from sessions import CheckpointResult

        practice_root = "/tmp/shake-036-practice"
        note = story_notes.EddyNoteResult(
            note_path=Path(practice_root) / "story" / "eddies" / "2-shake-eddy.md",
            entry_text="---\nthread: '2'\n---\n\nshake entry\n",
            preview_text="Shake preview: the eddy held a checkpoint rehearsal.",
        )
        result = CheckpointResult(
            trigger="manual", session_note="2026-07-15.md", eddy_note=note
        )
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()

        async def run() -> object:
            with patch(
                "cmd_sessions.reload_history",
                return_value=[{"role": "user", "content": "a"}] * 4,
            ), patch(
                "sessions.checkpoint_session",
                new_callable=AsyncMock,
                return_value=result,
            ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
                "cmd_sessions.get_pd", return_value=practice_root
            ), patch(
                "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
            ) as reply:
                await cmd_sessions.cmd_checkpoint(message)
            return reply.await_args.args[1]

        surface = asyncio.run(run())
        if not surface.content or note.preview_text not in surface.content:
            errors.append("036 fail: manual checkpoint reply missing eddy-note preview")
        if "```md" not in (surface.content or ""):
            errors.append("036 fail: preview not rendered as expandable code block")
        if ("Open note", "!read story/eddies/2-shake-eddy.md") not in surface.open_actions:
            errors.append("036 fail: manual checkpoint reply missing note open action")
    except Exception as exc:
        errors.append(f"preview surface offline check: {type(exc).__name__}: {exc}")
    return errors


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO))


def _parse_spawn(stdout: str) -> dict | None:
    start = stdout.find("{")
    if start == -1:
        return None
    try:
        data = json.loads(stdout[start:])
        return data if data.get("status") == "ok" else None
    except json.JSONDecodeError:
        return None


def _spirit_send(channel_id: str, text: str) -> None:
    proc = _run([str(VENV_PY), str(SPIRIT_OPS), "send", channel_id, text], timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "spirit_ops send failed")


def _read_thread(thread_id: str, limit: int = 25) -> str:
    proc = _run([str(VENV_PY), str(DISCORD_OPS), "read", thread_id, str(limit)], timeout=60)
    return proc.stdout + proc.stderr


def _wait_for_transcript(
    thread_id: str,
    predicate,
    *,
    timeout: int = 120,
    interval: int = 10,
) -> str:
    deadline = time.time() + timeout
    transcript = ""
    while time.time() < deadline:
        transcript = _read_thread(thread_id, 40)
        if predicate(transcript):
            return transcript
        time.sleep(interval)
    return transcript


def _shared_dialogue_path(thread_id: str) -> Path:
    from mage import get_runtime_dir, set_practice_context_for_channel

    set_practice_context_for_channel(int(thread_id))
    return Path(get_runtime_dir()) / "dialogue" / f"{thread_id}.json"


def _latest_session_note(mtime_after: float, thread_id: str) -> Path | None:
    from mage import get_pd, set_practice_context_for_channel

    set_practice_context_for_channel(int(thread_id))
    sessions = Path(get_pd()) / "sessions"
    if not sessions.is_dir():
        return None
    candidates = [
        p for p in sessions.glob("*.md") if p.stat().st_mtime >= mtime_after - 5
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def check_live(wait_seconds: int) -> tuple[list[str], dict]:
    errors: list[str] = []
    evidence: dict = {}
    started = time.time()

    if not VENV_PY.is_file():
        return ["venv python not found — run on Mac Mini"], evidence

    spawn = _run([str(VENV_PY), str(SHAKE_SPAWN), "--topic", f"shake-lifecycle-{int(started)}"], timeout=120)
    if spawn.returncode != 0:
        return [f"shake_spawn_eddy failed: {spawn.stderr or spawn.stdout}"], evidence

    spawn_data = _parse_spawn(spawn.stdout)
    if not spawn_data:
        return [f"spawn parse failed: {spawn.stdout[:400]}"], evidence
    thread_id = str(spawn_data["thread_id"])
    evidence["thread_id"] = thread_id
    evidence["jump_url"] = spawn_data.get("jump_url")

    time.sleep(5)
    for i, msg in enumerate(SHAKE_MSGS):
        try:
            _spirit_send(thread_id, msg)
        except Exception as exc:
            errors.append(f"spirit message {i + 1} failed: {exc}")
            return errors, evidence
        time.sleep(wait_seconds)

    transcript = _read_thread(thread_id)
    evidence["transcript_after_dialogue"] = transcript[-2000:]
    turtle_replies = len(re.findall(r"\bturtle\b", transcript, re.I))
    if turtle_replies < 2:
        errors.append(f"expected >=2 Turtle replies, saw {turtle_replies}")

    shared_path = _shared_dialogue_path(thread_id)
    evidence["shared_dialogue_path"] = str(shared_path)
    if not shared_path.is_file():
        errors.append(f"shared dialogue file missing: {shared_path}")
    else:
        try:
            entries = json.loads(shared_path.read_text(encoding="utf-8"))
            evidence["shared_dialogue_entries"] = len(entries)
            if len(entries) < 4:
                errors.append(f"shared dialogue has {len(entries)} entries, need >=4 for reflection")
        except json.JSONDecodeError:
            errors.append("shared dialogue file is invalid JSON")

    bar_count = transcript.lower().count("checkpoint")
    evidence["checkpoint_mentions_in_transcript"] = bar_count

    try:
        _spirit_send(thread_id, "!checkpoint")
    except Exception as exc:
        errors.append(f"!checkpoint failed: {exc}")
        return errors, evidence

    def _checkpoint_done(t: str) -> bool:
        lower = t.lower()
        if "not enough conversation to checkpoint" in lower:
            return True
        return (
            "checkpoint saved" in lower
            or "nothing new met the save threshold" in lower
        )

    checkpoint_transcript = _wait_for_transcript(
        thread_id, _checkpoint_done, timeout=360, interval=15
    )
    evidence["transcript_after_checkpoint"] = checkpoint_transcript[-2000:]
    lower_cp = checkpoint_transcript.lower()
    if "not enough conversation to checkpoint" in lower_cp:
        errors.append("R4 fail: checkpoint still says not enough conversation")

    session_after_cp = _latest_session_note(started, thread_id)
    if session_after_cp:
        evidence["session_note_after_checkpoint"] = str(session_after_cp)

    if not _checkpoint_done(checkpoint_transcript) and session_after_cp is None:
        errors.append("R4 fail: no checkpoint confirmation within timeout")
        return errors, evidence

    try:
        _spirit_send(thread_id, "!release")
    except Exception as exc:
        errors.append(f"!release failed: {exc}")
        return errors, evidence

    def _release_done(t: str) -> bool:
        lower = t.lower()
        return "session released" in lower

    release_transcript = _wait_for_transcript(
        thread_id, _release_done, timeout=180, interval=12
    )
    evidence["transcript_after_release"] = release_transcript[-2000:]
    lower_rel = release_transcript.lower()
    if "**session note:**" in lower_rel and session_after_cp is None:
        errors.append("R5 fail: release embed claims session note but none on disk")
    if not _release_done(release_transcript):
        errors.append("R5 fail: no Session Released embed within timeout")
    if (
        session_after_cp
        and "no new resonance captured" not in lower_rel
        and "session note" not in lower_rel
        and "sessions/" not in lower_rel
    ):
        errors.append("R5 fail: release embed neither cites session note nor honest empty copy")

    if shared_path.is_file():
        errors.append("shared dialogue file should be cleared after release")

    return errors, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Lifecycle split-bot shakedown (R4/R5)")
    parser.add_argument("--live", action="store_true", help="Exercise Discord on Mac Mini")
    parser.add_argument("--wait", type=int, default=55, help="Seconds between Spirit messages")
    args = parser.parse_args()

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "capability": "split-bot-lifecycle-capture",
        "scenarios": ["R4-checkpoint", "R5-release"],
        "offline_errors": check_offline(),
        "live_errors": [],
        "evidence": {},
        "pass": False,
    }

    if args.live:
        live_errors, evidence = check_live(args.wait)
        report["live_errors"] = live_errors
        report["evidence"] = evidence

    report["pass"] = not report["offline_errors"] and (not args.live or not report["live_errors"])

    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
