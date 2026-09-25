#!/usr/bin/env python3
"""Offline functional gate for the resolved channel architecture."""

from __future__ import annotations

OFFLINE_SAFE = True

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

REPO = Path(__file__).resolve().parents[1]
PYTHON = REPO / "venv" / "bin" / "python3"
TEST_RUNS = REPO / "test-runs"
sys.path.insert(0, str(REPO))

CONTRACT_MODULES = [
    "tests.test_channel_conformance",
    "tests.test_channel_primitives",
    "tests.test_primitive_runtime",
    "tests.test_primitive_architecture",
    "tests.test_mage_channel_resolution",
    "tests.test_shared_prompt_boundary",
    "tests.test_roster_sync",
    "tests.test_discord_reconcile",
    "tests.test_admin_space",
]

# C5 is not earned by mapping it onto an older pass. These modules hold the
# audit + `!admin space sync` repair; dropping either makes the catalogue a lie.
C5_MODULES = (
    "tests.test_discord_reconcile",
    "tests.test_admin_space",
)


def category_navigation_control() -> dict:
    """C5 can fail here even if unittest discovery is later trimmed."""
    from runtime.adapters.structural import (
        collect_registry_audit_issues,
        ensure_channel_category,
    )

    guild = MagicMock()
    channel = MagicMock()
    channel.id = 301
    channel.name = "health"
    channel.category = None
    channel.guild = guild
    channel.overwrites = {}
    channel.edit = AsyncMock()
    guild.get_channel.return_value = channel
    guild.text_channels = [channel]
    category = MagicMock()
    category.name = "Health"
    guild.categories = [category]
    registry = {
        "channels": {
            "301": {
                "mage": "health",
                "type": "unknown",
                "discord_category": "Health",
            }
        }
    }
    issues = collect_registry_audit_issues(registry, guild)
    audited = (
        len(issues) == 1
        and "category drift" in issues[0]
        and "Health" in issues[0]
    )
    changed = asyncio.run(
        ensure_channel_category(channel, {"discord_category": "Health"})
    )
    kwargs = channel.edit.await_args.kwargs if channel.edit.await_args else {}
    repaired = bool(changed) and kwargs.get("sync_permissions") is False
    return {
        "ok": audited and repaired,
        "detail": (
            "declared category is audited and repaired without permission sync"
            if audited and repaired
            else f"audited={audited} repaired={repaired} issues={issues!r}"
        ),
    }


def main() -> int:
    checks: dict[str, dict] = {}
    proc = subprocess.run(
        [str(PYTHON), "-m", "unittest", *CONTRACT_MODULES],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    checks["contract_acceptance"] = {
        "ok": proc.returncode == 0,
        "detail": (proc.stderr or proc.stdout)[-1600:],
    }

    from tests.test_primitive_architecture import conditional_offenders

    planted = {"dialogue_turn.py": "if uses_team_surface(parent): pass"}
    checks["anti_special_case_control"] = {
        "ok": conditional_offenders(planted)
        == ["dialogue_turn.py: uses_team_surface"],
        "detail": "planted team helper is detected",
    }

    from channel_primitives import resolve_primitive

    invalid = {
        "spaces": {"team": {"members": ["one", "two"], "memory": "own_root"}},
        "channels": {"7": {"primitive": "team", "mage": "team"}},
    }
    checks["authority_control"] = {
        "ok": resolve_primitive(invalid, 7) is None,
        "detail": "team without an explicit member coordinator fails closed",
    }
    checks["category_navigation_control"] = category_navigation_control()

    status = "pass" if all(row["ok"] for row in checks.values()) else "fail"
    report = {
        "capability": "channel-architecture",
        "status": status,
        "live": False,
        "checks": checks,
    }
    TEST_RUNS.mkdir(exist_ok=True)
    (TEST_RUNS / "shake-channel-architecture-latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
