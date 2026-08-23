"""Native practice freshness for health canary and operator readiness.

All practice roots use ``state/current.yaml`` and ``sessions/`` — no legacy
portable capture files (boom/compass/bright).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from practice_io import file_age_hours, format_age, read_safe

CANARY_MAX_AGE_HOURS = 168  # 7 days — INT-027 health canary
READINESS_MAX_AGE_HOURS = 48  # operator !readiness state freshness

PracticeTopology = Literal["native", "empty"]


@dataclass(frozen=True)
class FreshnessResult:
    passed: bool
    topology: PracticeTopology
    detail: str
    signals: dict[str, float]


def _latest_session_age_hours(pd: str) -> float:
    sessions_dir = os.path.join(pd, "sessions")
    if not os.path.isdir(sessions_dir):
        return float("inf")
    try:
        md_files = [f for f in os.listdir(sessions_dir) if f.endswith(".md")]
    except OSError:
        return float("inf")
    if not md_files:
        return float("inf")
    latest = max(md_files, key=lambda f: os.path.getmtime(os.path.join(sessions_dir, f)))
    return file_age_hours(os.path.join(sessions_dir, latest))


def detect_topology(pd: str) -> PracticeTopology:
    """Infer whether ``pd`` has native continuity signals."""
    if os.path.isfile(os.path.join(pd, "state", "current.yaml")):
        return "native"
    if os.path.isdir(os.path.join(pd, "state")):
        return "native"
    if _latest_session_age_hours(pd) != float("inf"):
        return "native"
    return "empty"


def _format_signal_pairs(signals: dict[str, float]) -> str:
    parts = [f"{name}: {format_age(age)}" for name, age in signals.items()]
    return ", ".join(parts) if parts else "no signals"


def evaluate_freshness(pd: str, *, max_age_hours: float = CANARY_MAX_AGE_HOURS) -> FreshnessResult:
    """Return whether practice state is fresh enough for infra health checks."""
    topology = detect_topology(pd)

    if topology == "empty":
        return FreshnessResult(
            passed=True,
            topology="empty",
            detail="practice space fresh (no surfaces yet)",
            signals={},
        )

    current_path = os.path.join(pd, "state", "current.yaml")
    current_age = file_age_hours(current_path)
    signals: dict[str, float] = {}
    if current_age != float("inf"):
        signals["current"] = current_age
        age = current_age
    else:
        session_age = _latest_session_age_hours(pd)
        signals["last_session"] = session_age
        age = session_age
    passed = age < max_age_hours
    label = "native state fresh" if passed else "native practice stale"
    return FreshnessResult(
        passed=passed,
        topology="native",
        detail=f"{label} ({_format_signal_pairs(signals)})",
        signals=signals,
    )


def canary_detail(result: FreshnessResult) -> str:
    """Human-readable INT-027 detail line for ``practice_freshness`` failures."""
    if result.topology == "native":
        return result.detail.replace("native practice stale", "Practice state stale").replace(
            "native state fresh", "Practice state fresh"
        )
    return result.detail


def readiness_freshness_issues(pd: str, *, max_age_hours: float = READINESS_MAX_AGE_HOURS) -> list[str]:
    """Issue strings for operator readiness State Freshness dimension."""
    result = evaluate_freshness(pd, max_age_hours=max_age_hours)
    if result.passed:
        return []
    issues = []
    for name, age in result.signals.items():
        if age == float("inf"):
            issues.append(f"{name} missing")
        elif age >= max_age_hours:
            issues.append(f"{name} {format_age(age)}")
    if not issues:
        issues.append(result.detail)
    return issues


def readiness_context_detail(pd: str) -> tuple[str, str]:
    """Return (status, detail) for Context Coherence — ready/degraded/impaired."""
    topology = detect_topology(pd)
    if topology == "empty":
        return "ready", "empty — new practice"

    current = read_safe(os.path.join(pd, "state", "current.yaml"))
    session_age = _latest_session_age_hours(pd)
    if current.strip():
        age = file_age_hours(os.path.join(pd, "state", "current.yaml"))
        return "ready", f"state/current {format_age(age)}"
    if session_age != float("inf"):
        return "ready", f"last session {format_age(session_age)} ago"
    return "impaired", "no state/current.yaml or sessions"


def readiness_workshop_visibility(pd: str) -> tuple[str, str]:
    """Return (status, detail) for Workshop Visibility dimension."""
    topology = detect_topology(pd)
    if topology == "empty":
        return "impaired", "no practice files reachable"

    age = file_age_hours(os.path.join(pd, "state", "current.yaml"))
    if age == float("inf"):
        session_age = _latest_session_age_hours(pd)
        if session_age == float("inf"):
            return "impaired", "no native continuity signals"
        age = session_age
        label = "last session"
    else:
        label = "state/current"
    if age < 24:
        return "ready", f"practice active ({label} {format_age(age)} ago)"
    if age < 72:
        return "degraded", f"practice {format_age(age)} old ({label})"
    return "impaired", f"practice stale ({label} {format_age(age)})"
