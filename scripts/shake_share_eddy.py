#!/usr/bin/env python3
"""Offline shakedown for Share eddy Slice 1 (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import discord  # noqa: F401
except ModuleNotFoundError:
    from unittest.mock import MagicMock

    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ui", MagicMock())


def check_module() -> list[str]:
    errors: list[str] = []
    try:
        import share_eddy  # noqa: F401
    except Exception as exc:
        errors.append(f"share_eddy import: {type(exc).__name__}: {exc}")
        return errors

    for name in (
        "list_practitioner_targets",
        "list_space_targets",
        "build_export_bundle",
        "deliver_practitioner_share",
        "deliver_space_share",
        "materialize_space_shared_eddy",
        "cmd_share",
        "ShareContinueView",
    ):
        if not hasattr(share_eddy, name):
            errors.append(f"share_eddy missing: {name}")
    return errors


def check_spec() -> list[str]:
    errors: list[str] = []
    spec = (REPO / "TURTLE_SPEC.md").read_text(encoding="utf-8")
    for needle in ("15.6", "received eddy", "Share eddy"):
        if needle not in spec:
            errors.append(f"TURTLE_SPEC missing: {needle}")
    return errors


def check_commands() -> list[str]:
    errors: list[str] = []
    from commands import DIRECT_COMMANDS

    if "share" not in DIRECT_COMMANDS:
        errors.append("DIRECT_COMMANDS missing share")
    from cmd_dispatch import _PRACTITIONER_COMMANDS

    if "share" not in _PRACTITIONER_COMMANDS:
        errors.append("_PRACTITIONER_COMMANDS missing share")
    return errors


def check_tests() -> list[str]:
    errors: list[str] = []
    pytest = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_share_eddy.py", "-q"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if pytest.returncode == 0:
        return errors
    unittest = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_share_eddy", "-q"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if unittest.returncode != 0:
        errors.append(
            "test_share_eddy failed:\n"
            f"{pytest.stdout}\n{pytest.stderr}\n"
            f"unittest fallback:\n{unittest.stdout}\n{unittest.stderr}"
        )
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_module())
    errors.extend(check_spec())
    errors.extend(check_commands())
    errors.extend(check_tests())

    if errors:
        print("shake_share_eddy: FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("shake_share_eddy: PASS (Slice 1 + 3a — practitioner + space share core)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
