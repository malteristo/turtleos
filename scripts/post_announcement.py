#!/usr/bin/env python3
"""Post a versioned update announcement to practitioner rivers (River bot).

Fanout to every river + hosted-river channel, or a single --channel.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _load_env() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def _cmd_list() -> int:
    from announcements import (
        is_posted,
        list_announcement_channel_ids,
        list_announcement_ids,
        load_announcement,
        locale_for_channel,
    )
    from mage import reload_mage_registry

    reload_mage_registry()
    ids = list_announcement_ids()
    if not ids:
        print("No announcements in template/announcements/")
        return 1
    channels = list_announcement_channel_ids()
    print(f"Announcements ({len(ids)}):")
    for ann_id in ids:
        en = load_announcement(ann_id, "en")
        title = en.title if en else "?"
        print(f"  {ann_id} — {title}")
        for ch_id in channels:
            locale = locale_for_channel(ch_id)
            status = "posted" if is_posted(ch_id, ann_id) else "pending"
            print(f"    channel {ch_id} locale={locale} {status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post versioned update announcements to practitioner rivers"
    )
    parser.add_argument(
        "--id",
        dest="announcement_id",
        help="Announcement id (filename stem without locale)",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Post to one channel id only (default: fanout all river + hosted-river)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Post even if this announcement was already marked for the channel",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print targets without posting",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List announcement ids and per-channel posted state",
    )
    args = parser.parse_args()
    _load_env()

    if args.list:
        return _cmd_list()

    if not args.announcement_id:
        parser.error("--id is required (or use --list)")

    from announcements import fanout_announcement, list_announcement_ids, load_announcement

    if args.announcement_id not in list_announcement_ids():
        # Still allow if file exists for a locale
        if load_announcement(args.announcement_id, "en") is None:
            print(f"Unknown announcement id: {args.announcement_id}", file=sys.stderr)
            return 1

    channel_ids = [args.channel] if args.channel is not None else None
    results = asyncio.run(
        fanout_announcement(
            args.announcement_id,
            force=args.force,
            dry_run=args.dry_run,
            channel_ids=channel_ids,
        )
    )
    for status in ("ok", "dry-run", "skip", "fail"):
        chans = results.get(status) or []
        if chans:
            print(f"{status}: {len(chans)} — {chans}")
    if results.get("fail"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
