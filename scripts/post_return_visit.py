#!/usr/bin/env python3
"""Deprecated: forwards to versioned update announcements.

Prefer::

    scripts/post_announcement.py --id 2026-07-16-nesrine-ready [--channel ID]

This wrapper keeps old runbooks working. Idempotency uses
``thread-state/river/announcements.json`` (not the legacy return_visit_v1.json).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from announcements import RETURN_VISIT_ANNOUNCEMENT_ID, post_announcement


def _load_env() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deprecated wrapper — posts announcement "
            f"{RETURN_VISIT_ANNOUNCEMENT_ID} via announcements.py"
        )
    )
    parser.add_argument("channel_id", type=int, help="Discord channel ID")
    parser.add_argument("--force", action="store_true", help="Post even if already marked")
    args = parser.parse_args()
    _load_env()

    print(
        f"post_return_visit.py is deprecated; forwarding to announcement "
        f"{RETURN_VISIT_ANNOUNCEMENT_ID}",
        file=sys.stderr,
    )
    status, msg_id = asyncio.run(
        post_announcement(
            args.channel_id,
            RETURN_VISIT_ANNOUNCEMENT_ID,
            force=args.force,
        )
    )
    if status == "ok":
        return 0
    if status == "skip":
        print(f"Already posted for channel {args.channel_id} (use --force to re-post)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
