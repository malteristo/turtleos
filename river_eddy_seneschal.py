"""River-side eddy seneschal — act rows from practitioner input, not Turtle prose.

Split-bot law: Turtle converses; River posts structured acts. This module is the
Option 1 seam — URL detection on practitioner messages → fetch button, without
parsing Turtle output or orchestrating from the dialogue path.
"""

from __future__ import annotations

import re

import discord

from content_fetch import extract_urls
from helpers import get_history
from link_read import external_urls


def _recent_fetch_act(history: list[dict]) -> bool:
    recent = "\n".join(m.get("content", "") for m in history[-12:])
    return "[Act: !fetch]" in recent


async def maybe_offer_eddy_fetch(message: discord.Message, client) -> None:
    """Post a single Fetch act row when an eddy message contains an external URL."""
    if message.content.strip().startswith("!"):
        return
    text = message.content or ""
    urls = external_urls(await extract_urls(text))
    if not urls:
        return

    channel_id = message.channel.id
    history = get_history(channel_id)
    if _recent_fetch_act(history):
        return

    url = urls[0]
    from eddy_lifecycle_bar import post_act_suggestion_row

    await post_act_suggestion_row(
        message.channel,
        "-# Suggested action",
        [("Fetch link", f"!fetch {url}")],
        client,
    )


def dedupe_fetch_actions(actions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """One Fetch button per row — backtick + plain-tail extraction can duplicate."""
    seen_fetch: set[str] = set()
    out: list[tuple[str, str]] = []
    for label, command in actions:
        cmd = command.lstrip("!").split(None, 1)[0].lower()
        if cmd == "fetch":
            key = re.sub(r"\s+", " ", command.strip().lower())
            if key in seen_fetch:
                continue
            seen_fetch.add(key)
        out.append((label, command))
    return out
