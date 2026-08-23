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


def practice_root() -> Path:
    """Active turtleOS practice root from registry (via get_pd when importable)."""
    try:
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from mage import get_pd

        return Path(get_pd()).expanduser()
    except Exception:
        return Path.home() / "workshops" / "kermit"


def workshop_root() -> Path:
    """Deprecated alias — native topology uses practice_root() only."""
    return practice_root()


def resolve_automation_reports_dir() -> Path:
    """Mini path for Spirit ops reports (Forge harvests desk/craft/automation-reports)."""
    pd = practice_root()
    for candidate in (
        pd / "state" / "notes" / "automation-reports",
        pd / "craft" / "automation-reports",
    ):
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    fallback = Path.home() / "workshops" / "kermit" / "state" / "notes" / "automation-reports"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
