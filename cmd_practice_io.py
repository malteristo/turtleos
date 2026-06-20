"""Practice-root browse commands — read, ls, search (TURTLE_SPEC §5.5)."""

from __future__ import annotations

import os
from datetime import datetime

from helpers import split_message
from mage import get_pd
from practice_io import is_readable, obsidian_link, read_safe
from tos_tools import execute_tos_tool


async def cmd_read(message, args):
    if not args:
        await message.reply(
            "Usage: `!read <file>`\n"
            "Examples: `!read bright.md`, `!read intentions/turtle.md`, `!read sessions/2026-03-16.md`\n"
            "Use `!ls` to browse available files.",
            mention_author=False,
        )
        return

    filename = args[0]
    if not filename.endswith(".md"):
        filename += ".md"

    if not is_readable(filename):
        await message.reply(f"Cannot read `{filename}`. Use `!ls` to see available files.", mention_author=False)
        return

    path = os.path.join(get_pd(), filename)
    content = read_safe(path)
    if not content.strip():
        await message.reply(f"`{filename}` is empty.", mention_author=False)
        return

    link = obsidian_link(filename)
    if len(content) <= 1800:
        await message.reply(f"{link}\n```md\n{content}\n```", mention_author=False)
    elif len(content) <= 6000:
        await message.reply(link, mention_author=False)
        for chunk in split_message(f"```md\n{content}\n```", limit=1900):
            await message.reply(chunk, mention_author=False)
    else:
        preview = content[:1500]
        lines = content.count("\n") + 1
        await message.reply(
            f"{link} ({lines} lines, {len(content)} chars) — showing first ~50 lines:\n"
            f"```md\n{preview}\n```\n"
            f"*File too long for Discord. Use `!search <term>` or ask Spirit to summarize.*",
            mention_author=False,
        )


async def cmd_ls(message, args):
    directory = args[0] if args else ""
    target = os.path.join(get_pd(), directory) if directory else get_pd()

    if not os.path.isdir(target):
        await message.reply(f"Directory `{directory}` not found.", mention_author=False)
        return

    lines = []
    for item in sorted(os.listdir(target)):
        full = os.path.join(target, item)
        if item.startswith("."):
            continue
        if os.path.isdir(full):
            count = len([f for f in os.listdir(full) if f.endswith(".md")])
            lines.append(f"  `{item}/` — {count} files")
        elif item.endswith(".md"):
            size = os.path.getsize(full)
            age = datetime.now().timestamp() - os.path.getmtime(full)
            if age < 3600:
                age_str = f"{int(age / 60)}m ago"
            elif age < 86400:
                age_str = f"{int(age / 3600)}h ago"
            else:
                age_str = f"{int(age / 86400)}d ago"
            filepath = f"{directory}/{item}" if directory else item
            link = obsidian_link(filepath)
            lines.append(f"  {link} — {size}b, {age_str}")

    if not lines:
        await message.reply(f"`{directory or 'practice/'}` is empty.", mention_author=False)
        return

    header = f"**{directory + '/' if directory else 'practice/'}**"
    await message.reply(f"{header}\n" + "\n".join(lines), mention_author=False)


async def cmd_search(message, args):
    if not args:
        await message.reply(
            "Usage: `!search <query>`\nSearches across all practice files for matching text.",
            mention_author=False,
        )
        return
    query = " ".join(args)
    result = execute_tos_tool("search_practice_files", {"query": query})
    if len(result) <= 1900:
        await message.reply(result, mention_author=False)
    else:
        for chunk in split_message(result, limit=1900):
            await message.reply(chunk, mention_author=False)
