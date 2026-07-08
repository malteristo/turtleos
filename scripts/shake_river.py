#!/usr/bin/env python3
"""Shakedown for native River act harness (slice 1).

Runs offline checks always; optional live Ollama classify when available.
Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Allow shake on machines without discord.py (parse/prompt checks only).
if "--import-only" not in sys.argv:
    try:
        import discord  # noqa: F401
    except ModuleNotFoundError:
        from unittest.mock import MagicMock

        sys.modules.setdefault("discord", MagicMock())
        sys.modules.setdefault("discord.ui", MagicMock())

from river_handler import (
    finalize_parent_river_acts,
    load_river_prompt,
    list_installed_flows,
    parse_river_output,
)


def check_parse() -> list[str]:
    errors: list[str] = []
    acts, reason = parse_river_output('{"acts": [{"type": "acknowledge", "emoji": "👋"}]}')
    if reason or not acts:
        errors.append(f"valid JSON failed: {reason}")
    acts, reason = parse_river_output("Hello, I can help you with that today!")
    if not reason or "prose" not in reason:
        errors.append("prose should be rejected")
    out = finalize_parent_river_acts([{"type": "acknowledge", "emoji": "👋"}])
    if out != []:
        errors.append("finalize_parent_river_acts should drop acknowledge-only acts")
    stripped = finalize_parent_river_acts([
        {"type": "acknowledge", "emoji": "👋"},
        {"type": "offer_eddy", "title": "x", "button_label": "Go"},
    ])
    if any(a.get("type") == "offer_eddy" for a in stripped):
        errors.append("finalize_parent_river_acts did not strip offer_eddy")
    return errors


def check_prompt() -> list[str]:
    errors: list[str] = []
    prompt = load_river_prompt()
    if len(prompt) < 100:
        errors.append(f"river prompt too short ({len(prompt)} chars)")
    if "acts" not in prompt.lower() and "json" not in prompt.lower():
        errors.append("river prompt missing acts/json guidance")
    if "eddy bar" not in prompt.lower() and "eddy door" not in prompt.lower():
        errors.append("river prompt missing standing eddy bar guidance")
    return errors


def check_mage_routing() -> list[str]:
    errors: list[str] = []
    try:
        from mage import get_attunement_profile, uses_native_river

        profile = get_attunement_profile()
        if profile != "native":
            errors.append(f"unexpected attunement profile: {profile}")
    except Exception as exc:
        errors.append(f"mage routing import failed: {exc}")
    return errors


async def check_classify_live() -> list[str]:
    errors: list[str] = []
    try:
        from river_handler import classify_river_acts

        acts = await classify_river_acts("quick check-in about turtleOS shell migration")
        if not acts:
            errors.append("classify returned empty acts")
            return errors
        types = [a.get("type") for a in acts]
        if "offer_eddy" in types:
            errors.append(f"parent river should not include offer_eddy (standing bar): {types}")
        prose_types = [t for t in types if t not in (
            "acknowledge", "revise_offer", "offer_flow_menu",
            "offer_flow", "error", "chronicle",
        )]
        if prose_types:
            errors.append(f"unknown act types: {prose_types}")
    except Exception as exc:
        errors.append(f"live classify failed: {type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    live = "--live" in sys.argv
    all_errors: dict[str, list[str]] = {}

    all_errors["parse"] = check_parse()
    all_errors["prompt"] = check_prompt()
    all_errors["routing"] = check_mage_routing()

    if live:
        all_errors["classify_live"] = asyncio.run(check_classify_live())

    flows = list_installed_flows()
    try:
        from river_state import river_bot_configured
        split_bot = river_bot_configured()
    except Exception:
        split_bot = False
    report = {
        "capability": "river/offline",
        "status": "pass" if not any(all_errors.values()) else "fail",
        "live": live,
        "attunement": _safe_profile(),
        "river_bot_configured": split_bot,
        "flows_sample": flows[:4],
        "checks": {k: "ok" if not v else v for k, v in all_errors.items()},
    }
    print(json.dumps(report, indent=2))
    out_dir = REPO / "test-runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "shake-river-latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


def _safe_profile() -> str:
    try:
        from mage import get_attunement_profile
        return get_attunement_profile()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
