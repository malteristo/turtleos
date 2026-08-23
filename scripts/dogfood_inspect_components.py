#!/usr/bin/env python3
"""One-off: print Discord message components for dogfood verification."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ENV_PATH = REPO / ".env"


def _load_env() -> None:
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


async def inspect_channel(channel_id: int, *, limit: int = 10) -> None:
    import discord

    token = os.environ.get("RIVER_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("RIVER_BOT_TOKEN not set")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        ch = await client.fetch_channel(channel_id)
        msgs = [m async for m in ch.history(limit=limit)]
        print(f"=== #{getattr(ch, 'name', channel_id)} — last {limit} messages (oldest first) ===")
        for m in reversed(msgs):
            labels: list[str] = []
            for row in m.components or []:
                for c in getattr(row, "children", []):
                    lbl = getattr(c, "label", None) or getattr(c, "placeholder", None)
                    if lbl:
                        labels.append(str(lbl))
                    elif getattr(c, "url", None):
                        labels.append(f"link:{c.url[:40]}...")
            comp = f" [{', '.join(labels)}]" if labels else ""
            if m.embeds:
                emb = m.embeds[0]
                preview = emb.title or (emb.description[:40] + "…" if emb.description else "embed")
            else:
                preview = (m.content or "∅")[:50]
            author = m.author.name if m.author else "?"
            print(f"{author}: {preview}{comp}")
    finally:
        await client.close()


def main() -> int:
    _load_env()
    if len(sys.argv) < 2:
        print("Usage: dogfood_inspect_components.py <channel_id> [limit]", file=sys.stderr)
        return 1
    channel_id = int(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    asyncio.run(inspect_channel(channel_id, limit=limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
