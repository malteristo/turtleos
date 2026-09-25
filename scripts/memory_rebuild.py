#!/usr/bin/env python3
"""Rebuild or inspect a room's topic memory (memory_agent) from its notes.

    python3 scripts/memory_rebuild.py ~/workshops/<room> --rebuild            # model formation
    python3 scripts/memory_rebuild.py ~/workshops/<room> --rebuild --keyword  # deterministic only
    python3 scripts/memory_rebuild.py ~/workshops/<room> --show "a message"   # render the passive block
    python3 scripts/memory_rebuild.py ~/workshops/<room>                      # list topics

Memory is a derived view: deleting ``memory/`` and running ``--rebuild`` must
give the same answer. The roots read follow ``mage.memory_roots`` — a personal
root also carries the shared rooms its practitioner belongs to.
"""
from __future__ import annotations

# Rebuild is minutes of local inference and writes under a real root.
OFFLINE_SAFE = False

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", default=os.environ.get("PRACTICE_DIR", "."))
    parser.add_argument("--rebuild", action="store_true", help="rebuild memory/ from the notes")
    parser.add_argument("--keyword", action="store_true", help="deterministic formation only")
    parser.add_argument("--show", metavar="MESSAGE", help="render the passive block for a message")
    args = parser.parse_args()

    import memory_agent
    from mage import memory_roots

    root = os.path.expanduser(args.root)
    roots = memory_roots(root)

    if args.rebuild:
        if args.keyword:
            topics = memory_agent.build_room_memory(root, roots)
        else:
            from background import reflection_chat

            topics = asyncio.run(memory_agent.rebuild_room_memory(root, roots, chat=reflection_chat))
        print(f"# {len(topics)} topics → {memory_agent.memory_dir(root)} (reads: {', '.join(r for r, _ in roots)})")
        for t in topics:
            print(f"  {t.heat:5.1f}  {t.conversations:3d} conv  {t.since}→{t.last_seen}  {t.label}")
    if args.show is not None:
        print(memory_agent.render_topic_memory_block(root, args.show))
    if not args.rebuild and args.show is None:
        for t in memory_agent.read_topics(root):
            print(f"  {float(t.get('heat') or 0):5.1f}  {t.get('conversations'):3d} conv  {t.get('label')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
