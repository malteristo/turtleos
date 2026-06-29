"""Practice-root browse commands — read, ls, search, artifacts, export (TURTLE_SPEC §5.5, §11.5)."""

from __future__ import annotations

import io
import os
from datetime import datetime

import discord

from artifact_viewer import (
    SHELF_DEFS,
    format_shelf_listing,
    format_shelf_menu,
    is_artifact_directory,
    is_artifact_readable,
    mark_artifacts_ui_unlocked,
    resolve_artifact_path,
)
from helpers import split_message
from mage import get_mage_type, get_pd
from practice_io import artifact_display_name, is_readable, obsidian_link, read_safe
from state import PRACTICE_WEB_BASE
from tos_tools import execute_tos_tool


def _read_embed(filename: str, content: str, url: str) -> discord.Embed:
    title = artifact_display_name(filename)
    lines = content.count("\n") + 1
    embed = discord.Embed(
        title=title,
        url=url,
        description="Tap the title to open in Discord's browser.",
        color=0x5865F2,
    )
    embed.add_field(name="Artifact", value=f"`{filename}`", inline=False)
    embed.set_footer(text=f"{lines} lines · {len(content)} chars")
    return embed


async def cmd_read(message, args):
    if not args:
        await message.reply(
            "Usage: `!read <artifact>`\n"
            "Examples: `!read bright.md`, `!read sessions/2026-03-16.md`\n"
            "Browse shelves: `!artifacts`",
            mention_author=False,
        )
        return

    filename = args[0]
    if not filename.endswith(".md"):
        filename += ".md"

    if not is_readable(filename):
        await message.reply(
            f"Cannot read `{filename}`. Use `!artifacts` to browse your practice corpus.",
            mention_author=False,
        )
        return

    path = resolve_artifact_path(filename)
    if not path:
        await message.reply(
            f"Cannot read `{filename}`. Use `!artifacts` to browse your practice corpus.",
            mention_author=False,
        )
        return

    content = read_safe(path)
    if not content.strip():
        await message.reply(f"`{filename}` is empty.", mention_author=False)
        return

    link = obsidian_link(filename)
    if PRACTICE_WEB_BASE:
        await message.reply(embed=_read_embed(filename, content, link), mention_author=False)
        return

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
            f"*Artifact too long for Discord. Use `!search <term>` or ask Turtle to summarize.*",
            mention_author=False,
        )


def _rel_path(directory: str, item: str) -> str:
    return f"{directory}/{item}" if directory else item


def _ls_visible_subdir(directory: str, name: str, *, mage_type: str) -> bool:
    rel = _rel_path(directory, name)
    if rel in ("state", "state/notes"):
        return True
    if rel in ("box", "box/intake"):
        return True
    if rel == "chronicle":
        return True
    if rel == "proposals" and mage_type != "practitioner":
        return True
    return is_artifact_directory(rel, mage_type=mage_type)


async def cmd_ls(message, args):
    directory = args[0] if args else ""
    rel_dir = directory.rstrip("/")
    mage_type = get_mage_type()

    if rel_dir and not is_artifact_directory(rel_dir, mage_type=mage_type):
        await message.reply(
            f"Cannot browse `{directory}`. Use `!artifacts` for curated shelves.",
            mention_author=False,
        )
        return

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
            if not _ls_visible_subdir(directory, item, mage_type=mage_type):
                continue
            subdir = _rel_path(directory, item)
            count = len(
                [
                    f
                    for f in os.listdir(full)
                    if f.endswith(".md")
                    and is_artifact_readable(f"{subdir}/{f}", mage_type=mage_type)
                ]
            )
            lines.append(f"  `{item}/` — {count} artifacts")
        elif item.endswith(".md"):
            filepath = _rel_path(directory, item)
            if not is_artifact_readable(filepath, mage_type=mage_type):
                continue
            size = os.path.getsize(full)
            age = datetime.now().timestamp() - os.path.getmtime(full)
            if age < 3600:
                age_str = f"{int(age / 60)}m ago"
            elif age < 86400:
                age_str = f"{int(age / 3600)}h ago"
            else:
                age_str = f"{int(age / 86400)}d ago"
            link = obsidian_link(filepath)
            lines.append(f"  {link} — {size}b, {age_str}")

    if not lines:
        await message.reply(
            f"`{directory or 'practice/'}` has no browsable artifacts. Try `!artifacts`.",
            mention_author=False,
        )
        return

    header = f"**{directory + '/' if directory else 'practice/'}** (allowlisted)"
    await message.reply(f"{header}\n" + "\n".join(lines), mention_author=False)


async def cmd_search(message, args):
    if not args:
        await message.reply(
            "Usage: `!search <query>`\nSearches your allowlisted practice artifacts.",
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


async def cmd_artifacts(message, args):
    mark_artifacts_ui_unlocked("typed")
    mage_type = get_mage_type()
    if not args:
        await message.reply(format_shelf_menu(mage_type=mage_type), mention_author=False)
        return

    shelf_key = args[0].lower()
    known = {s.key for s in SHELF_DEFS}
    if shelf_key not in known or (
        shelf_key == "proposals" and mage_type == "practitioner"
    ):
        await message.reply(
            f"Unknown shelf `{args[0]}`. Try `!artifacts` for the menu.",
            mention_author=False,
        )
        return

    text = format_shelf_listing(shelf_key, mage_type=mage_type)
    if len(text) <= 1900:
        await message.reply(text, mention_author=False)
    else:
        for chunk in split_message(text, limit=1900):
            await message.reply(chunk, mention_author=False)


async def cmd_export(message, args):
    if not args:
        await message.reply(
            "Usage: `!export <artifact>`\n"
            "Example: `!export sessions/2026-06-29.md`",
            mention_author=False,
        )
        return

    filename = args[0]
    if not filename.endswith(".md"):
        filename += ".md"

    if not is_readable(filename):
        await message.reply(
            f"Cannot export `{filename}`. Use `!artifacts` to browse your practice corpus.",
            mention_author=False,
        )
        return

    path = resolve_artifact_path(filename)
    if not path or not os.path.isfile(path):
        await message.reply(f"Cannot export `{filename}`.", mention_author=False)
        return

    content = read_safe(path)
    if not content.strip():
        await message.reply(f"`{filename}` is empty.", mention_author=False)
        return

    attachment_name = os.path.basename(filename)
    file_obj = discord.File(fp=io.BytesIO(content.encode("utf-8")), filename=attachment_name)
    await message.reply(
        f"Exported `{attachment_name}` ({len(content)} chars).",
        file=file_obj,
        mention_author=False,
    )
