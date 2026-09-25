"""Compact house picture for River — first role-need slice.

Instruments already exist for Spirit. This gatherer lets River see a
short form of them at classify time. River uses the picture to withhold,
never to narrate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.deploy_guard import DEFAULT_QUIET_MINUTES, WORKSHOPS, _describe, _signals

CANARY_HISTORY = Path("/tmp/canary-history.jsonl")

_WITHHOLD = frozenset({"red", "in flight"})
OFFER_ACTS = frozenset({"offer_flow", "offer_flow_menu", "offer_eddy", "revise_offer"})


def render_house_facts(facts: dict[str, str]) -> dict[str, str]:
    """Drop blank and unknown. Preserve a stable key order."""
    out: dict[str, str] = {}
    for key in ("canary", "last_turn"):
        value = (facts.get(key) or "").strip()
        if value and value != "unknown":
            out[key] = value
    return out


def house_prompt_block(facts: dict[str, str]) -> str:
    cleaned = render_house_facts(facts)
    if not cleaned:
        return ""
    lines = ["## House"]
    for key, value in cleaned.items():
        lines.append(f"{key}: {value}")
    lines.append(
        "Use this only to withhold offers when canary is red or a turn is in flight. "
        "Never put these facts in an act."
    )
    return "\n".join(lines)


def should_withhold(facts: dict[str, str]) -> bool:
    cleaned = render_house_facts(facts)
    return any(value in _WITHHOLD for value in cleaned.values())


def withhold_offers(acts: list[dict[str, Any]], facts: dict[str, str]) -> list[dict[str, Any]]:
    if not should_withhold(facts):
        return acts
    return [a for a in acts if a.get("type") not in OFFER_ACTS]


def _canary_overall(path: Path = CANARY_HISTORY) -> str:
    if not path.is_file():
        return "unknown"
    try:
        last = ""
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if not last:
            return "unknown"
        data = json.loads(last)
    except (OSError, json.JSONDecodeError):
        return "unknown"
    overall = str(data.get("overall") or "").strip().lower()
    return overall if overall in {"green", "yellow", "red"} else "unknown"


def _last_turn_label(workshops: Path = WORKSHOPS, *, now: float | None = None) -> str:
    import time

    signals = _signals(workshops)
    if not signals:
        return "unknown"
    latest, _root, what = max(signals, key=lambda row: row[0])
    if "write in flight" in what:
        return "in flight"
    age = (time.time() if now is None else now) - latest
    if age < DEFAULT_QUIET_MINUTES * 60:
        return "in flight"
    return _describe(age)


def gather_house_facts(
    *,
    workshops: Path = WORKSHOPS,
    canary_history: Path = CANARY_HISTORY,
    now: float | None = None,
) -> dict[str, str]:
    """Fail-soft. Missing files become omitted keys, not a crash."""
    try:
        return render_house_facts(
            {
                "canary": _canary_overall(canary_history),
                "last_turn": _last_turn_label(workshops, now=now),
            }
        )
    except Exception:
        return {}


def attach_house_to_prompt(prompt: str, facts: dict[str, str] | None = None) -> str:
    block = house_prompt_block(facts if facts is not None else gather_house_facts())
    if not block:
        return prompt
    return f"{prompt.rstrip()}\n\n{block}\n"
