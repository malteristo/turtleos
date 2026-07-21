#!/usr/bin/env python3
"""Shakedown for hosted rivers — onboarding, river keys, routing (offline).

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import json
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

from hosted_river_onboarding import load_onboarding_markdown
from river_keys import (
    _looks_like_single_key,
    _normalize_mage_key,
    is_unclaimed_river,
    load_claim_room_markdown,
)
from readiness import assess_practitioner_substrate


def check_templates() -> list[str]:
    errors: list[str] = []
    for name in (
        "onboarding_en.md",
        "onboarding_de.md",
        "claim_room_en.md",
        "claim_room_de.md",
        "resonance.md.example",
    ):
        path = REPO / "template" / "practitioner" / name
        if not path.is_file():
            errors.append(f"missing template: {name}")
    for name in ("soul.md", "conduct.md"):
        path = REPO / "template" / "practitioner" / "character" / name
        if not path.is_file():
            errors.append(f"missing character template: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        # Hosted seed must stay generic (not one person's invite-era overlay).
        if "nesrine" in low:
            errors.append(f"{name}: still Nesrine-specific — keep template generic")
        # Care-only overlays recreate sycophancy (docs/ux/principles.md).
        if "nie drängen" in low or "never push" in low:
            errors.append(
                f"{name}: care-only push language — use offer-agenda / care≠agreement split"
            )
        if name == "soul.md":
            if "care is not agreement" not in low and "challenge" not in low:
                errors.append("soul.md: missing care≠agreement / challenge language")
    return errors


def check_spec() -> list[str]:
    errors: list[str] = []
    spec = (REPO / "TURTLE_SPEC.md").read_text(encoding="utf-8")
    for needle in ("hosted-river", "unclaimed-river", "river key", "15.4"):
        if needle.lower() not in spec.lower():
            errors.append(f"TURTLE_SPEC missing: {needle}")
    return errors


def check_routing() -> list[str]:
    errors: list[str] = []
    from unittest.mock import patch

    from mage import _get_channel_type

    harness_types = {"river", "hosted-river"}
    with patch("mage._MAGE_REGISTRY", {
        "channels": {
            "999001": {"type": "unclaimed-river", "mage": "guest"},
            "999002": {"type": "hosted-river", "mage": "guest"},
        },
        "attunement": "native",
    }):
        unclaimed = _get_channel_type(999001)
        hosted = _get_channel_type(999002)
        if unclaimed in harness_types:
            errors.append("unclaimed-river must not use river act harness before claim")
        if hosted not in harness_types:
            errors.append("hosted-river must use river act harness")
    return errors


def check_practitioner_readiness() -> list[str]:
    errors: list[str] = []
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = assess_practitioner_substrate(tmp)
        if "fresh" not in result["summary"].lower():
            errors.append("empty practitioner substrate should say fresh")
        if result.get("highest_leverage"):
            errors.append("practitioner substrate should not set highest_leverage on empty")
    return errors


def check_keys() -> list[str]:
    errors: list[str] = []
    if not _looks_like_single_key("🌿"):
        errors.append("emoji key not recognized")
    if _normalize_mage_key("Anna Marie") != "anna_marie":
        errors.append("mage key normalize failed")
    if "Claim your river" not in load_claim_room_markdown("en"):
        errors.append("claim room en template empty")
    return errors


def check_registry_live() -> list[str]:
    errors: list[str] = []
    reg_path = Path.home() / "turtleos" / "mage_registry.yaml"
    if not reg_path.is_file():
        return errors
    try:
        import yaml

        reg = yaml.safe_load(reg_path.read_text()) or {}
    except Exception as exc:
        errors.append(f"registry parse: {exc}")
        return errors
    hosted = [
        cid for cid, e in reg.get("channels", {}).items()
        if isinstance(e, dict) and e.get("type") == "hosted-river"
    ]
    if not hosted:
        errors.append("no hosted-river channels in live registry (expected at least one)")
    return errors


def main() -> int:
    live = "--live" in sys.argv
    checks = {
        "templates": check_templates(),
        "spec": check_spec(),
        "routing": check_routing(),
        "practitioner_readiness": check_practitioner_readiness(),
        "river_keys": check_keys(),
    }
    if live:
        checks["registry_live"] = check_registry_live()

    report = {
        "status": "pass" if not any(checks.values()) else "fail",
        "checks": {k: "ok" if not v else v for k, v in checks.items()},
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
