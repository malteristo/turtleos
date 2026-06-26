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


def _resolve_desk_root(practice_dir: Path) -> Path:
    """practice_dir may be the desk root (~/workshop/desk) or parent (~/workshops/default)."""
    if (practice_dir / "boom.md").is_file() or (practice_dir / "boom" / "bright.md").is_file():
        return practice_dir
    if (practice_dir / "desk" / "boom.md").is_file():
        return practice_dir / "desk"
    if practice_dir.name == "desk":
        return practice_dir
    return practice_dir / "desk"


def resolve_automation_reports_dir() -> Path:
    """Practice desk path for Spirit Ops Reports (Forge harvests at . craft)."""
    try:
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from mage import get_pd

        desk = _resolve_desk_root(Path(get_pd()))
        return desk / "craft" / "automation-reports"
    except Exception:
        root = workshop_root()
        if (root / "desk" / "boom.md").is_file():
            return root / "desk" / "craft" / "automation-reports"
        return Path.home() / "workshops" / "default" / "desk" / "craft" / "automation-reports"
