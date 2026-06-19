#!/usr/bin/env python3
"""One-off: re-gather origin thread context for an existing intake from source refs."""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: enrich_craft_intake.py <intake.md> <channel_id> <message_id>")
        sys.exit(1)

    intake_path = Path(sys.argv[1])
    channel_id = int(sys.argv[2])
    message_id = int(sys.argv[3])

    import discord

    with open(Path(__file__).resolve().parents[1] / ".env") as f:
        for line in f:
            if line.startswith("DISCORD_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    from craft_intake import _gather_origin_thread_context

    async def run() -> None:
        await client.login(token)
        origin = await _gather_origin_thread_context(client, channel_id, message_id)
        await client.close()

        body = intake_path.read_text(encoding="utf-8")
        if "## Origin eddy" in body:
            print("Intake already has Origin eddy section — skip")
            return

        block_lines = [
            "",
            "## Origin eddy (enriched post-registration)",
            "",
        ]
        if origin.get("origin_parent_name"):
            block_lines.append(f"- **River:** #{origin['origin_parent_name']}")
        block_lines.append(f"- **Thread:** {origin.get('origin_channel_name')}")
        block_lines.append(f"- **Channel ID:** `{channel_id}`")
        if origin.get("urls_seen"):
            block_lines.extend(["", "### URLs seen in thread", ""])
            block_lines.extend(f"- {u}" for u in origin["urls_seen"])
        if origin.get("trigger_message_block"):
            block_lines.extend(["", "## Trigger message", "", origin["trigger_message_block"]])
        if origin.get("thread_excerpt"):
            block_lines.extend(["", "## Origin thread excerpt", ""])
            block_lines.extend(f"- {line}" for line in origin["thread_excerpt"])

        marker = "## For Spirit"
        if marker in body:
            body = body.replace(marker, "\n".join(block_lines) + "\n\n" + marker)
        else:
            body += "\n".join(block_lines) + "\n"
        intake_path.write_text(body, encoding="utf-8")
        print(f"Enriched {intake_path}")

    await run()


if __name__ == "__main__":
    asyncio.run(main())
