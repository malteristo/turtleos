#!/usr/bin/env python3
"""Name the established craft and partnership channel presets in the registry."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from channel_primitives import resolve_primitive


def migrated(
    registry: dict,
    *,
    craft_key: str = "kermit",
    partnership_key: str = "family",
) -> tuple[dict, dict[str, str]]:
    result = deepcopy(registry)
    found: dict[str, str] = {}
    for channel_id, entry in (result.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived") or entry.get("orphaned"):
            continue
        key = str(entry.get("mage") or "")
        if key == craft_key and entry.get("type") == "craft":
            entry["primitive"] = "craft"
            entry["attunement"] = "craft"
            found["craft"] = str(channel_id)
        elif key == partnership_key and entry.get("type") in {"shared", "shared-river"}:
            entry["primitive"] = "partnership"
            entry["attunement"] = "native"
            entry["default_context"] = "partnership-room"
            found["partnership"] = str(channel_id)

    missing = {"craft", "partnership"} - found.keys()
    if missing:
        raise RuntimeError(f"missing active channel(s): {', '.join(sorted(missing))}")
    for name, channel_id in found.items():
        primitive = resolve_primitive(result, channel_id)
        if primitive is None or primitive.name != name:
            raise RuntimeError(f"{name} channel does not validate after migration")
    return result, found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--craft-key", default="kermit")
    parser.add_argument("--partnership-key", default="family")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    import mage

    result, found = migrated(
        mage._load_mage_registry(),
        craft_key=args.craft_key,
        partnership_key=args.partnership_key,
    )
    if args.apply:
        from river_keys import save_registry

        save_registry(result)
    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "channels": {
                    name: {
                        "channel_id": channel_id,
                        "primitive": resolve_primitive(result, channel_id).name,
                    }
                    for name, channel_id in found.items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
