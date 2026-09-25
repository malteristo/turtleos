#!/usr/bin/env python3
"""Migrate one legacy health registry row to the declarative primitive."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from channel_primitives import resolve_primitive


def migrated(registry: dict, *, subject: str, steward: str) -> tuple[dict, str]:
    result = deepcopy(registry)
    matches = [
        (channel_id, entry)
        for channel_id, entry in (result.get("channels") or {}).items()
        if isinstance(entry, dict)
        and (entry.get("primitive") == "health" or entry.get("type") == "health")
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one health channel, found {len(matches)}")
    channel_id, entry = matches[0]
    space_key = str(entry.get("mage") or "")
    space = (result.get("spaces") or {}).get(space_key)
    if not isinstance(space, dict):
        raise RuntimeError("health channel has no shared-space registry entry")
    members = [str(item) for item in (space.get("members") or [])]
    if subject not in members or steward not in members:
        raise RuntimeError("subject and steward must already be health members")
    space["subject"] = subject
    space["steward"] = steward
    space["memory"] = "isolated"
    entry["primitive"] = "health"
    entry["type"] = "health"
    entry["attunement"] = "health"
    if resolve_primitive(result, channel_id) is None:
        raise RuntimeError("migrated health primitive does not validate")
    return result, str(channel_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--steward", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    import mage

    registry = mage._load_mage_registry()
    result, channel_id = migrated(
        registry, subject=args.subject, steward=args.steward
    )
    if args.apply:
        from river_keys import save_registry

        save_registry(result)
    primitive = resolve_primitive(result, channel_id)
    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "channel_id": channel_id,
                "primitive": primitive.name,
                "base": primitive.base,
                "parent_owner": primitive.parent_owner,
                "subject": primitive.subject,
                "steward": primitive.steward,
                "capabilities": sorted(primitive.capabilities),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
