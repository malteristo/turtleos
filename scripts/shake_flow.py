#!/usr/bin/env python3
"""Shakedown for Turtle Practice flows (flow_runner slice).

Offline checks always run. With --live, exercises Shelter on Discord via
shake_spawn_eddy + spirit_ops + discord_ops (run on Mac Mini).

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

VENV_PY = Path.home() / "turtleos" / "venv" / "bin" / "python3"
SPIRIT_OPS = Path.home() / "turtleos" / "spirit_ops.py"
DISCORD_OPS = Path.home() / "turtleos" / "discord_ops.py"
SHAKE_SPAWN = REPO / "scripts" / "shake_spawn_eddy.py"

FLOW_SPECS: dict[str, dict] = {
    "shelter": {
        "flow_id": "shelter",
        "checkpoint_rel": "state/notes/shelter-last.md",
        "prompt_markers": ["-# flow: Shelter", "Shelter"],
        "shake_message": "shake: heavy day, need shelter — just hold space with me",
        "followup_message": "thanks — that helped a little",
    },
}


def check_offline(flow_id: str) -> list[str]:
    errors: list[str] = []
    spec_cfg = FLOW_SPECS.get(flow_id)
    if not spec_cfg:
        return [f"unknown flow capability: {flow_id}"]

    if "discord" not in sys.modules:
        try:
            import discord  # noqa: F401
        except ModuleNotFoundError:
            from unittest.mock import MagicMock

            sys.modules.setdefault("discord", MagicMock())
            sys.modules.setdefault("discord.ui", MagicMock())

    from flow_runner import (
        build_flow_prompt_sections,
        load_flow_spec,
        write_flow_checkpoint,
    )

    spec = load_flow_spec(flow_id)
    if spec is None:
        errors.append(f"load_flow_spec({flow_id}) returned None")
        return errors

    if spec_cfg["checkpoint_rel"] not in spec.writes:
        errors.append(f"expected write path missing: {spec_cfg['checkpoint_rel']}")

    sections, _ = build_flow_prompt_sections(flow_id)
    joined = "\n".join(sections)
    for marker in spec_cfg["prompt_markers"]:
        if marker not in joined:
            errors.append(f"prompt missing marker: {marker}")

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        history = [
            {"role": "user", "content": "shake offline"},
            {"role": "assistant", "content": "I'm here."},
        ]
        written = write_flow_checkpoint(spec, history, "Spirit", tmp)
        if not written:
            errors.append("write_flow_checkpoint wrote nothing")
        else:
            path = Path(tmp) / spec_cfg["checkpoint_rel"]
            if not path.is_file():
                errors.append(f"checkpoint file missing: {spec_cfg['checkpoint_rel']}")

    return errors


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO),
    )


def _parse_thread_id(spawn_stdout: str) -> str | None:
    text = spawn_stdout.strip()
    start = text.find("{")
    if start == -1:
        return None
    try:
        data = json.loads(text[start:])
        return str(data.get("thread_id")) if data.get("status") == "ok" else None
    except json.JSONDecodeError:
        return None


def _read_thread(thread_id: str, limit: int = 15) -> str:
    proc = _run([str(VENV_PY), str(DISCORD_OPS), "read", thread_id, str(limit)], timeout=60)
    return proc.stdout + proc.stderr


def _spirit_send(channel_id: str, text: str) -> None:
    proc = _run([str(VENV_PY), str(SPIRIT_OPS), "send", channel_id, text], timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "spirit_ops send failed")


def check_live(flow_id: str, wait_seconds: int) -> list[str]:
    errors: list[str] = []
    spec_cfg = FLOW_SPECS.get(flow_id)
    if not spec_cfg:
        return [f"unknown flow capability: {flow_id}"]

    if not VENV_PY.is_file():
        return ["venv python not found — run on Mac Mini"]

    spawn = _run([str(VENV_PY), str(SHAKE_SPAWN), "--flow", flow_id], timeout=90)
    if spawn.returncode != 0:
        errors.append(f"shake_spawn_eddy failed: {spawn.stderr or spawn.stdout}")
        return errors

    thread_id = _parse_thread_id(spawn.stdout)
    if not thread_id:
        errors.append(f"could not parse thread id from spawn output: {spawn.stdout[:300]}")
        return errors

    time.sleep(3)
    try:
        _spirit_send(thread_id, spec_cfg["shake_message"])
    except Exception as exc:
        errors.append(f"spirit first message failed: {exc}")
        return errors

    time.sleep(wait_seconds)
    transcript = _read_thread(thread_id)
    if "Turtle" not in transcript and "turtle" not in transcript.lower():
        errors.append("no Turtle reply detected in thread after first message")

    try:
        _spirit_send(thread_id, spec_cfg["followup_message"])
    except Exception as exc:
        errors.append(f"spirit followup failed: {exc}")

    time.sleep(wait_seconds)
    transcript = _read_thread(thread_id)
    turtle_lines = [ln for ln in transcript.splitlines() if "Turtle" in ln or "turtle" in ln.lower()]
    if len(turtle_lines) < 1:
        errors.append("no Turtle lines in transcript after followup")

    try:
        _spirit_send(thread_id, "!release")
    except Exception as exc:
        errors.append(f"spirit !release failed: {exc}")

    time.sleep(20)
    from mage import get_pd

    checkpoint = Path(get_pd()) / spec_cfg["checkpoint_rel"]
    if not checkpoint.is_file():
        errors.append(f"checkpoint not written: {checkpoint}")
    else:
        text = checkpoint.read_text(encoding="utf-8")
        if "shake" not in text.lower() and "heavy" not in text.lower():
            errors.append("checkpoint file exists but missing expected shake content")

    if re.search(r"shake-" + re.escape(flow_id), transcript, re.I) is None:
        # thread name may only appear in threads list — non-fatal
        pass

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Flow shakedown harness")
    parser.add_argument("flow", nargs="?", default="shelter", help="Flow id (default: shelter)")
    parser.add_argument("--live", action="store_true", help="Run live Discord exercise on Mini")
    parser.add_argument("--wait", type=int, default=45, help="Seconds to wait for Turtle replies")
    args = parser.parse_args()

    all_errors: dict[str, list[str]] = {"offline": check_offline(args.flow)}
    if args.live:
        all_errors["live"] = check_live(args.flow, args.wait)

    report = {
        "capability": f"flow_runner/{args.flow}",
        "status": "pass" if not any(all_errors.values()) else "fail",
        "live": args.live,
        "checks": {k: "ok" if not v else v for k, v in all_errors.items()},
    }
    print(json.dumps(report, indent=2))

    out_dir = REPO / "test-runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "shake-flow-latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
