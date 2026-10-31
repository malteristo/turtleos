#!/usr/bin/env python3
"""Shakedown for practice artifact viewer (TURTLE_SPEC §11.5).

Offline: allowlist, command registration, shelf formatting.
Live (--live): Spirit types a retired browse command and reads the pointer reply (spirit_ops).
"""
from __future__ import annotations

# Declared for scripts/shake_report.py: this script mutates nothing a
# practitioner can see, so the nightly gate may run it unattended.
OFFLINE_SAFE = True

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import discord  # noqa: F401
except ModuleNotFoundError:
    from unittest.mock import MagicMock

    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ui", MagicMock())

VENV_PY = REPO / "venv" / "bin" / "python3"
SPIRIT_OPS = REPO / "spirit_ops.py"
TEST_RUNS = REPO / "test-runs"
RIVER_CHANNEL = "1479428854513664030"


def check_registration() -> list[str]:
    """The typed door is shut and the button's room stays: handler + button gate, no member command."""
    errors: list[str] = []
    from commands import DIRECT_COMMANDS
    from cmd_dispatch import COMMAND_ACT_FALLBACK, CONTEXTUAL_ACTION_COMMANDS, _PRACTITIONER_COMMANDS

    for name in ("artifacts", "read", "export"):
        if name not in DIRECT_COMMANDS:
            errors.append(f"DIRECT_COMMANDS missing {name} (the Open and Browse buttons run it)")
        if name not in CONTEXTUAL_ACTION_COMMANDS:
            errors.append(f"CONTEXTUAL_ACTION_COMMANDS missing {name} (the button gate)")
        if name in _PRACTITIONER_COMMANDS:
            errors.append(f"_PRACTITIONER_COMMANDS still lists {name}: the typed door should be shut")
    if "artifacts" not in COMMAND_ACT_FALLBACK:
        errors.append("COMMAND_ACT_FALLBACK missing artifacts")
    return errors


def check_allowlist() -> list[str]:
    errors: list[str] = []
    import artifact_viewer as av

    with patch("artifact_viewer.get_pd", return_value=str(REPO)), patch(
        "artifact_viewer.get_runtime_dir", return_value=str(REPO / "test-runs")
    ):
        if not av.is_artifact_readable("sessions/x.md", mage_type="practitioner"):
            errors.append("sessions should be readable")
        if av.is_artifact_readable("proposals/x.md", mage_type="practitioner"):
            errors.append("proposals must be denied for practitioner")
        if not av.is_artifact_readable("proposals/x.md", mage_type="mage"):
            errors.append("proposals should be readable for operator")
        if av.is_artifact_readable("thread-state/x.md", mage_type="mage"):
            errors.append("thread-state must be denied")
    return errors


def check_practice_io() -> list[str]:
    errors: list[str] = []
    from practice_io import is_readable

    with patch("artifact_viewer.get_pd", return_value=str(REPO)), patch(
        "artifact_viewer.get_runtime_dir", return_value=str(REPO / "test-runs")
    ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
        if is_readable("proposals/secret.md"):
            errors.append("practice_io.is_readable must deny proposals for practitioner")
    return errors


def check_shelf_menu() -> list[str]:
    errors: list[str] = []
    import artifact_viewer as av

    text = av.format_shelf_menu(mage_type="mage")
    if "Practice artifacts" not in text:
        errors.append("shelf menu missing title")
    if "Sessions" not in text:
        errors.append("shelf menu missing the sessions shelf")
    for gone in ("`!artifacts", "`!read", "`!export", "`!search", "`!ls"):
        if gone in text:
            errors.append(f"shelf menu still tells a person to type {gone[1:]}`")
    return errors


def check_discoverability() -> list[str]:
    errors: list[str] = []
    import artifact_viewer as av

    with patch("artifact_viewer._load_discoverability", return_value={}), patch(
        "artifact_viewer.tier1_artifact_count", return_value=0
    ):
        if av.artifacts_ui_eligible():
            errors.append("should be ineligible with empty corpus and no unlock")
    with patch("artifact_viewer._load_discoverability", return_value={"ui_unlocked": True}):
        if not av.artifacts_ui_eligible():
            errors.append("should be eligible when unlocked")
    return errors


def _run(cmd: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO))


def check_live(wait_seconds: int) -> list[str]:
    """The typed doors answer once with where they went (2026-10-14); the shelves are buttons."""
    errors: list[str] = []
    if not VENV_PY.is_file() or not SPIRIT_OPS.is_file():
        return ["run live shake on Mac Mini (venv + spirit_ops required)"]

    for typed in ("!artifacts", "!read thread-state/registry.yaml", "!ls"):
        proc = _run([str(VENV_PY), str(SPIRIT_OPS), "send", RIVER_CHANNEL, typed], timeout=60)
        if proc.returncode != 0:
            errors.append(f"spirit {typed} send failed: {proc.stderr or proc.stdout}")
            continue
        time.sleep(wait_seconds)
        read_proc = _run([str(VENV_PY), str(SPIRIT_OPS), "read", RIVER_CHANNEL, "6"], timeout=60)
        transcript = read_proc.stdout + read_proc.stderr
        name = typed.split()[0]
        if f"`{name}` is gone" not in transcript:
            errors.append(f"{name} did not answer with where it went: {transcript[:300]}")
    return errors


def main() -> int:
    live = "--live" in sys.argv
    wait = 25
    for i, arg in enumerate(sys.argv):
        if arg == "--wait" and i + 1 < len(sys.argv):
            wait = int(sys.argv[i + 1])

    all_errors: dict[str, list[str]] = {
        "registration": check_registration(),
        "allowlist": check_allowlist(),
        "practice_io": check_practice_io(),
        "shelf_menu": check_shelf_menu(),
        "discoverability": check_discoverability(),
    }
    if live:
        all_errors["live_river"] = check_live(wait)

    status = "pass" if not any(all_errors.values()) else "fail"
    report = {
        "capability": "artifacts/viewer",
        "status": status,
        "live": live,
        "checks": {k: "ok" if not v else v for k, v in all_errors.items()},
    }
    print(json.dumps(report, indent=2))

    TEST_RUNS.mkdir(exist_ok=True)
    (TEST_RUNS / "shake-artifacts-latest.json").write_text(json.dumps(report, indent=2) + "\n")

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
