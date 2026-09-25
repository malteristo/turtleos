#!/usr/bin/env python3
"""Offline functional gate for shared team work and asynchronous activities."""

from __future__ import annotations

OFFLINE_SAFE = True

import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PYTHON = REPO / "venv" / "bin" / "python3"
TEST_RUNS = REPO / "test-runs"
sys.path.insert(0, str(REPO))


def main() -> int:
    checks: dict[str, dict] = {}
    proc = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "unittest",
            "tests.test_team_state",
            "tests.test_team_lanes",
            "tests.test_team_federation",
            "tests.test_campaign_state",
            "tests.test_quest_migration",
            "tests.test_channel_conformance",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    checks["team_acceptance"] = {
        "ok": proc.returncode == 0,
        "detail": (proc.stderr or proc.stdout)[-1800:],
    }

    from tests.test_team_state import team_primitive
    from team_lanes import gate_lane_turn

    planted = gate_lane_turn(999999, actor="member-a", primitive=team_primitive())
    checks["ordinary_eddy_control"] = {
        "ok": planted.allowed,
        "detail": "an eddy without lane metadata remains ordinary shared dialogue",
    }

    flow = (REPO / "template" / "flows" / "dnd_dm.md").read_text(
        encoding="utf-8"
    )
    checks["campaign_persistence_control"] = {
        "ok": (
            "events.jsonl" in flow
            and "write_practice_file" not in flow
            and "Every completed" in flow
        ),
        "detail": "campaign flow names the automatic event path, not model-willed writes",
    }

    status = "pass" if all(row["ok"] for row in checks.values()) else "fail"
    report = {
        "capability": "team-work",
        "status": status,
        "live": False,
        "checks": checks,
    }
    TEST_RUNS.mkdir(exist_ok=True)
    (TEST_RUNS / "shake-team-work-latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
