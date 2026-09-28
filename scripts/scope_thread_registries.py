#!/usr/bin/env python3
"""Give each practice root back only its own threads (issues/050).

One cache served every root, so every ``thread-state/registry.yaml`` holds the
whole house's threads. This gathers every copy, keeps the most recent of each
thread, assigns it to the root of the room it was made in, and rewrites each
root's file with exactly those. A thread whose room cannot be told goes to
``house/thread_registry_unowned.yaml`` — outside every member's root, kept.

    python3 scripts/scope_thread_registries.py            # counts only
    python3 scripts/scope_thread_registries.py --apply    # rewrite; restart the bots right after

The bots cache these files; restart right after ``--apply`` or a cache writes the
old contents back.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml


def _root_of(registry: dict, key: str) -> Path | None:
    for section in ("mages", "spaces"):
        entry = (registry.get(section) or {}).get(key)
        if isinstance(entry, dict):
            path = entry.get("runtime_dir") or entry.get("practice_dir")
            if path:
                return Path(os.path.expanduser(path))
    return None


def room_index(registry: dict) -> tuple[dict[str, Path], dict[str, Path]]:
    """Channel id → root, and every name a channel has carried → root."""
    by_id: dict[str, Path] = {}
    by_name: dict[str, Path] = {}
    for cid, e in (registry.get("channels") or {}).items():
        if not isinstance(e, dict) or not e.get("mage"):
            continue
        root = _root_of(registry, str(e["mage"]))
        if root is None:
            continue
        by_id[str(cid)] = root
        slug = str(e["mage"]).replace("_", "-")
        names = {e.get("name"), e.get("discord_name")}
        if e.get("type") in ("hosted-river", "unclaimed-river"):
            names |= {f"{slug}-dialogue", f"river-{slug}", f"home-{slug}"}
        if e.get("type") == "river":
            names |= {"river", f"home-{slug}"}
        for n in names - {None, ""}:
            by_name.setdefault(str(n), root)
    return by_id, by_name


def plan(registry: dict, roots: list[Path]) -> tuple[dict[Path, dict], dict, dict[Path, int]]:
    by_id, by_name = room_index(registry)
    newest: dict[str, dict] = {}
    for root in roots:
        path = root / "thread-state" / "registry.yaml"
        if not path.is_file():
            continue
        for tid, info in ((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("threads") or {}).items():
            if not isinstance(info, dict):
                continue
            old = newest.get(str(tid))
            if old is None or str(info.get("last_activity") or "") > str(old.get("last_activity") or ""):
                newest[str(tid)] = info
    owned: dict[Path, dict] = {r: {} for r in roots}
    unowned: dict = {}
    for tid, info in newest.items():
        root = by_id.get(str(info.get("parent_channel_id") or "")) or by_name.get(str(info.get("parent_channel") or ""))
        if root in owned:
            owned[root][tid] = info
        else:
            unowned[tid] = info
    before = {}
    for root in roots:
        path = root / "thread-state" / "registry.yaml"
        before[root] = len(((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("threads") or {})) if path.is_file() else 0
    return owned, unowned, before


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from river_keys import registry_file
    from cloud_fallback import house_dir

    registry = yaml.safe_load(registry_file().read_text(encoding="utf-8")) or {}
    roots = sorted({r for r in (_root_of(registry, k) for s in ("mages", "spaces")
                                for k in (registry.get(s) or {})) if r and r.is_dir()})
    owned, unowned, before = plan(registry, roots)
    for root in roots:
        print(f"{root}: {before[root]} → {len(owned[root])}")
    print(f"unowned (to house/): {len(unowned)}")
    if not args.apply:
        print("Counts only. --apply to rewrite, then restart the bots.")
        return 0
    for root in roots:
        path = root / "thread-state" / "registry.yaml"
        data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}
        if not data and not owned[root]:
            continue
        data["threads"] = owned[root]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
        tmp.replace(path)
    out = house_dir(create=True) / "thread_registry_unowned.yaml"
    out.write_text(yaml.dump({"threads": unowned}, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.chmod(out, 0o600)
    print(f"Rewritten. Unowned kept in {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
