#!/usr/bin/env python3
"""Shakedown for hosted rivers — onboarding, river keys, routing (offline).

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

# Declared for scripts/shake_report.py: this script mutates nothing a
# practitioner can see, so the nightly gate may run it unattended.
OFFLINE_SAFE = True

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
    hosted_river_channel_name,
    is_unclaimed_river,
    load_claim_room_markdown,
    parse_invite_args,
)
from admin_experience import admin_help_default
from readiness import assess_practitioner_substrate


def _private_names() -> list[str]:
    """The operator's private-name list, lowercased.

    Resolved the same way the pre-commit guard resolves it, so one list serves
    every repository. Returns empty when no list is configured — and says so on
    stderr rather than passing quietly, because a name check that silently
    checks nothing reports clean on exactly the file it was meant to catch.
    """
    import os
    import subprocess

    candidates = [os.environ.get("MAGIC_PRIVATE_NAMES", "")]
    try:
        candidates.append(
            subprocess.run(
                ["git", "config", "--get", "magic.privateNames"],
                capture_output=True, text=True, cwd=REPO, check=False,
            ).stdout.strip()
        )
    except OSError:
        pass

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            lines = Path(candidate).read_text(encoding="utf-8").splitlines()
            return [
                line.strip().lower()
                for line in lines
                if line.strip() and not line.lstrip().startswith("#")
            ]

    print(
        "note: no private-name list configured — template name check is OFF "
        "(git config magic.privateNames /path/to/private_names.txt)",
        file=sys.stderr,
    )
    return []


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
        #
        # This check used to hardcode one practitioner's first name — a leak
        # detector that leaked, and one that only ever protected the single
        # person it named. Names come from the operator's gitignored list, the
        # same one the pre-commit guard reads.
        for private_name in _private_names():
            if private_name in low:
                errors.append(
                    f"{name}: still specific to one practitioner — keep template generic"
                )
                break
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
    if hosted_river_channel_name("anna_marie") != "river-anna-marie":
        errors.append("hosted river channel name law failed")
    try:
        name, key, locale, member = parse_invite_args(
            ["guest", "👽", "--member", "guest.handle"]
        )
        if (name, key, locale, member) != ("guest", "👽", "en", "guest.handle"):
            errors.append("parse_invite_args unexpected result")
    except Exception as exc:
        errors.append(f"parse_invite_args: {exc}")
    if "Claim your river" not in load_claim_room_markdown("en"):
        errors.append("claim room en template empty")
    return errors


def check_admin_help() -> list[str]:
    errors: list[str] = []
    help_text = admin_help_default()
    if "!admin invite" not in help_text:
        errors.append("admin help missing invite")
    if "!admin onboard" in help_text:
        errors.append("admin help still teaches onboard")
    src = (REPO / "river_keys.py").read_text(encoding="utf-8")
    if "hosted_river_channel_name" not in src:
        errors.append("river_keys missing hosted_river_channel_name")
    claim_fn = src.split("async def complete_river_claim", 1)
    if len(claim_fn) < 2 or "-dialogue" in claim_fn[1].split("async def ", 1)[0]:
        errors.append("complete_river_claim still references *-dialogue rename")
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
        "admin_help": check_admin_help(),
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
