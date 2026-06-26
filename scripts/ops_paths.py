"""Shared paths for Mini-hosted ops automation (Layer 1 + 2)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEST_RUNS = REPO / "test-runs"


def venv_python() -> Path:
    candidate = REPO / "venv" / "bin" / "python3"
    if candidate.is_file():
        return candidate
    return Path(sys.executable)


def workshop_root() -> Path:
    return Path.home() / "workshop"


def resolve_automation_reports_dir() -> Path:
    """Practice desk path for Spirit Ops Reports (Forge harvests at . craft)."""
    try:
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from mage import get_pd

        return Path(get_pd()) / "desk" / "craft" / "automation-reports"
    except Exception:
        root = workshop_root()
        if (root / "desk").is_dir():
            return root / "desk" / "craft" / "automation-reports"
        return Path.home() / "workshops" / "default" / "desk" / "craft" / "automation-reports"
