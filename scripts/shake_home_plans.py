#!/usr/bin/env python3
"""Shakedown for pinned home eddies (TURTLE_SPEC §5 / §8 / §11.5).

Offline: YAML bind 1:1, sticky skip flag, pin-card button labels, cmd registration.
Live (--live): optional — deferred to operator dogfood after both-bot restart.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

TEST_RUNS = REPO / "test-runs"


def check_registry() -> list[str]:
    errors: list[str] = []
    import home_plans as hp

    with tempfile.TemporaryDirectory() as tmp:
        plan = hp.bind_home(
            tmp,
            title="Shake plan",
            home_eddy_id=101,
            river_channel_id=202,
            body="# Shake\n\n- item\n",
        )
        if not hp.is_sticky_eddy(tmp, 101):
            errors.append("bound plan should be sticky")
        if hp.get_by_artifact(tmp, plan["artifact_path"]) is None:
            errors.append("get_by_artifact miss")
        try:
            hp.bind_home(
                tmp, title="Dup", home_eddy_id=101, river_channel_id=202
            )
            errors.append("duplicate eddy bind should raise")
        except hp.HomePlanError:
            pass
        labels_ok = True
        try:
            import home_plan_ui as ui

            if ui.PIN_CARD_BUTTON_LABELS != ("Continue", "Open", "Stop pinning"):
                labels_ok = False
                errors.append(f"pin labels wrong: {ui.PIN_CARD_BUTTON_LABELS}")
        except Exception as exc:
            errors.append(f"home_plan_ui import: {exc}")
            labels_ok = False
        if not labels_ok:
            pass
        cleared = hp.clear_plan(tmp, plan["id"])
        if cleared is None or hp.get_by_eddy(tmp, 101) is not None:
            errors.append("clear_plan failed")
        art = Path(tmp) / plan["artifact_path"]
        if not art.exists():
            errors.append("clear must keep artifact file")
    return errors


def check_registration() -> list[str]:
    errors: list[str] = []
    from commands import DIRECT_COMMANDS

    if "pin" not in DIRECT_COMMANDS:
        errors.append("DIRECT_COMMANDS missing pin")
    return errors


def check_honesty_copy() -> list[str]:
    errors: list[str] = []
    import home_plans as hp

    with tempfile.TemporaryDirectory() as tmp:
        hp.bind_home(
            tmp, title="Honest", home_eddy_id=1, river_channel_id=2, body="body"
        )
        packet = hp.render_home_attunement_packet(tmp, 1).lower()
        if "river pin" not in packet:
            errors.append("attunement missing river pin framing")
        if "side-panel" in packet and "do not describe side-panels" not in packet:
            errors.append("attunement must not promote side-panel fiction")
    return errors


def check_plan_offer_heuristic() -> list[str]:
    """Crystallization L3 — River offers Keep after plan-shaped Turtle replies."""
    errors: list[str] = []
    import home_plans as hp
    import river_eddy_seneschal as res

    plan = (
        "Here is a break-time plan you can rotate through between development sessions.\n\n"
        "### 1. Strength\n"
        "* pull-ups or chin-ups on the bar you already have at home\n"
        "* push-ups — standard or diamond when you want more challenge\n"
        "* squats or split squats to wake the legs after sitting\n"
        "* hangs from the bar for grip and shoulder decompression\n"
        "### 2. Mobility\n"
        "* thoracic opener hang for thirty seconds with soft knees\n"
        "* world's greatest stretch — lunge plus torso twist\n"
        "### Rotation\n"
        "* quick refresh between turtleOS commits with pull-ups and push-ups\n"
        "* deep reset after long sits at the desk when shoulders lock up\n"
    )
    if not hp.looks_like_working_plan(plan):
        errors.append("workout-shaped body should match looks_like_working_plan")
    if hp.looks_like_working_plan("Sure — try a few pull-ups."):
        errors.append("short scratch must not match looks_like_working_plan")
    if not hasattr(res, "maybe_offer_home_plan_after_turtle_reply"):
        errors.append("seneschal missing maybe_offer_home_plan_after_turtle_reply")
    return errors


def main() -> int:
    live = "--live" in sys.argv
    report = {
        "shake": "home_plans",
        "offline": {},
        "live": {"skipped": True, "reason": "operator dogfood after both-bot restart"},
    }
    errs: list[str] = []
    for name, fn in (
        ("registry", check_registry),
        ("registration", check_registration),
        ("honesty", check_honesty_copy),
        ("plan_offer", check_plan_offer_heuristic),
    ):
        e = fn()
        report["offline"][name] = {"ok": not e, "errors": e}
        errs.extend(e)

    if live:
        report["live"] = {
            "skipped": True,
            "reason": "use recognition tests after deploy — Continuet→home eddy",
        }

    TEST_RUNS.mkdir(parents=True, exist_ok=True)
    out = TEST_RUNS / "shake-home-plans-latest.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errs:
        print(f"FAIL: {len(errs)} error(s)", file=sys.stderr)
        return 1
    print("OK: home_plans offline shake")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
