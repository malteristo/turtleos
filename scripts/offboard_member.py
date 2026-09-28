#!/usr/bin/env python3
"""Offboard a member: what the house holds for them, and — when told — remove it.

    python3 scripts/offboard_member.py <key>            # inventory only
    python3 scripts/offboard_member.py <key> --apply    # registry: member → offboarded marker
    python3 scripts/offboard_member.py <key> --apply --erase
        # also delete their Discord channels, their practice root, and their
        # threads' entries in every other root's thread registry

A departure (someone leaves Discord) hides a home channel and keeps everything
so a return can restore it. Offboarding is the house deciding someone is not a
member: the registry keeps only their Discord id and the date, so no join path
re-admits them. ``--erase`` is irreversible and is run only on the operator's
explicit word. The inventory prints counts and paths, never content.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _registry() -> dict:
    from river_keys import registry_file

    return yaml.safe_load(registry_file().read_text(encoding="utf-8")) or {}


def _roots(registry: dict) -> list[Path]:
    out = []
    for section in ("mages", "spaces"):
        for entry in (registry.get(section) or {}).values():
            if isinstance(entry, dict):
                for field in ("practice_dir", "runtime_dir"):
                    if entry.get(field):
                        out.append(Path(os.path.expanduser(entry[field])))
    return sorted(set(out))


def inventory(registry: dict, key: str) -> dict:
    mage = (registry.get("mages") or {}).get(key)
    if not isinstance(mage, dict):
        raise SystemExit(f"No member `{key}` in the registry.")
    channels = {
        str(cid): e for cid, e in (registry.get("channels") or {}).items()
        if isinstance(e, dict) and e.get("mage") == key
    }
    names = {n for e in channels.values() for n in (e.get("name"), e.get("discord_name")) if n}
    slug = key.replace("_", "-")
    # A home channel has carried three names; threads keep the one current when they were made.
    names |= {f"{slug}-dialogue", f"river-{slug}", f"home-{slug}"}
    own_root = Path(os.path.expanduser(mage["practice_dir"])) if mage.get("practice_dir") else None
    threads: dict[Path, list[str]] = {}
    for root in _roots(registry):
        path = root / "thread-state" / "registry.yaml"
        if not path.is_file() or root == own_root:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        hits = [
            tid for tid, info in (data.get("threads") or {}).items()
            if isinstance(info, dict) and (
                str(info.get("parent_channel_id") or "") in channels
                or info.get("parent_channel") in names
            )
        ]
        if hits:
            threads[path] = hits
    spaces = [k for k, s in (registry.get("spaces") or {}).items()
              if isinstance(s, dict) and key in (s.get("members") or [])]
    return {"mage": mage, "channels": channels, "own_root": own_root, "threads": threads, "spaces": spaces}


def _delete_channel(cid: str) -> str:
    for var in ("RIVER_BOT_TOKEN", "DISCORD_BOT_TOKEN"):
        token = os.environ.get(var, "").strip()
        if not token:
            continue
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{cid}", method="DELETE",
            headers={"Authorization": f"Bot {token}", "User-Agent": "turtleOS offboard"},
        )
        try:
            urllib.request.urlopen(req, timeout=20)
            return "deleted"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return "already gone"
            if exc.code == 403:
                continue
            return f"failed ({exc.code})"
    return "not deleted — no bot token with permission"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--erase", action="store_true")
    args = ap.parse_args()
    if args.erase and not args.apply:
        ap.error("--erase needs --apply")
    _load_env()

    inv = inventory(_registry(), args.key)
    root = inv["own_root"]
    files = sum(1 for p in root.rglob("*") if p.is_file()) if root and root.is_dir() else 0
    print(f"Member `{args.key}`")
    print(f"  practice root: {root} ({files} files)")
    print(f"  channels: {', '.join(inv['channels']) or 'none'}")
    print(f"  seats: {', '.join(inv['spaces']) or 'none'}")
    for path, hits in inv["threads"].items():
        print(f"  thread entries in {path}: {len(hits)}")
    if not args.apply:
        print("Inventory only. --apply to offboard; add --erase to delete.")
        return 0

    from river_keys import update_registry
    from roster_sync import apply_offboard_registry

    update_registry(lambda reg: bool(apply_offboard_registry(reg, args.key) or True))
    print("Registry: offboarded marker written; channel rows and seats removed.")
    if not args.erase:
        return 0

    for cid in inv["channels"]:
        print(f"  Discord channel {cid}: {_delete_channel(cid)}")
    for path, hits in inv["threads"].items():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for tid in hits:
            (data.get("threads") or {}).pop(tid, None)
        tmp = path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
        tmp.replace(path)
        print(f"  {path}: {len(hits)} entries removed")
    if root and root.is_dir():
        shutil.rmtree(root)
        print(f"  {root}: deleted")
    print(json.dumps({"offboarded": args.key, "erased": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
