"""
!load <context> command implementation for turtleOS.

Searches the workshop for matching resonance (circles, library/resonance)
and loads it into the current conversation.
"""

import os
from datetime import datetime, timezone

import discord

from state import absorbed_contexts, EMBED_COLORS, get_channel
from mage import get_workshop_root
from practice_io import read_safe, truncate
from helpers import get_history, log_activity


# ─── Search Index ────────────────────────────────────────────────

def _build_resonance_index(wr: str) -> list[dict]:
    """Build a searchable index of loadable resonance in the workshop.

    Returns list of dicts: {name, aliases, type, path, description}
    """
    index = []

    # 1. Circles
    circles_dir = os.path.join(wr, "circles")
    if os.path.isdir(circles_dir):
        for name in os.listdir(circles_dir):
            circle_path = os.path.join(circles_dir, name)
            if not os.path.isdir(circle_path) or name.startswith("."):
                continue
            # Generate aliases: full name + parts
            aliases = [name] + name.split("-")
            readme = read_safe(os.path.join(circle_path, "README.md"))
            desc = readme.split("\n")[0] if readme.strip() else name
            index.append({
                "name": name,
                "aliases": aliases,
                "type": "circle",
                "path": circle_path,
                "description": desc,
            })

    # 2. Library resonance bundles
    res_dir = os.path.join(wr, "library", "resonance")
    if os.path.isdir(res_dir):
        for name in os.listdir(res_dir):
            bundle_path = os.path.join(res_dir, name)
            if not os.path.isdir(bundle_path) or name.startswith("."):
                continue
            aliases = [name] + name.split("-")
            manifest = read_safe(os.path.join(bundle_path, "manifest.md"))
            readme = read_safe(os.path.join(bundle_path, "README.md"))
            desc_source = manifest or readme
            desc = desc_source.split("\n")[0] if desc_source.strip() else name
            index.append({
                "name": name,
                "aliases": aliases,
                "type": "resonance",
                "path": bundle_path,
                "description": desc,
            })

    return index


def _search_resonance(query: str, wr: str) -> list[dict]:
    """Search for resonance matching query. Returns matches sorted by relevance."""
    index = _build_resonance_index(wr)
    query_lower = query.lower().strip()
    scored = []

    for entry in index:
        score = 0
        # Exact name match
        if query_lower == entry["name"].lower():
            score = 100
        # Exact alias match
        elif query_lower in [a.lower() for a in entry["aliases"]]:
            score = 80
        # Substring of name
        elif query_lower in entry["name"].lower():
            score = 60
        # Any alias contains query
        elif any(query_lower in a.lower() for a in entry["aliases"]):
            score = 40
        # Query word appears in description
        elif query_lower in entry["description"].lower():
            score = 20

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [entry for _, entry in scored]


# ─── Loading Strategy ────────────────────────────────────────────

MAX_LOAD_CHARS = 12000


def _load_circle(path: str, budget: int = MAX_LOAD_CHARS) -> tuple[str, list[str]]:
    """Load a circle's shared context. Returns (content, list of files loaded).

    Strategy: load shared/ files sorted by size (smaller first, so more files fit).
    This naturally prioritizes charters and focused docs over large models,
    but still loads the big files if budget allows.
    """
    shared_dir = os.path.join(path, "shared")
    parts = []
    files_loaded = []
    total = 0

    # Collect all .md files with sizes, sort smallest first
    candidates = []
    if os.path.isdir(shared_dir):
        for fname in os.listdir(shared_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(shared_dir, fname)
            content = read_safe(fpath)
            if content.strip():
                candidates.append((len(content), fname, content))
    candidates.sort()  # smallest first

    for _size, fname, content in candidates:
        remaining = budget - total
        if remaining <= 200:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[... truncated ...]"
        parts.append(f"### {fname}\n\n{content}")
        files_loaded.append(fname)
        total += len(content) + 50

    return "\n\n---\n\n".join(parts), files_loaded


def _load_resonance_bundle(path: str, budget: int = MAX_LOAD_CHARS) -> tuple[str, list[str]]:
    """Load a resonance bundle. Returns (content, list of files loaded)."""
    parts = []
    files_loaded = []
    total = 0

    # Manifest first (designed entry point)
    manifest = read_safe(os.path.join(path, "manifest.md"))
    if manifest.strip():
        if len(manifest) > budget // 2:
            manifest = manifest[:budget // 2] + "\n\n[... truncated ...]"
        parts.append(f"### manifest.md\n\n{manifest}")
        files_loaded.append("manifest.md")
        total += len(manifest) + 50

    # Then lore files
    lore_dir = os.path.join(path, "lore")
    if os.path.isdir(lore_dir):
        for fname in sorted(os.listdir(lore_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(lore_dir, fname)
            content = read_safe(fpath)
            if not content.strip():
                continue
            remaining = budget - total
            if remaining <= 500:
                break
            if len(content) > remaining:
                content = content[:remaining] + "\n\n[... truncated ...]"
            parts.append(f"### lore/{fname}\n\n{content}")
            files_loaded.append(f"lore/{fname}")
            total += len(content) + 50

    # Fallback: README if no manifest
    if not manifest.strip():
        readme = read_safe(os.path.join(path, "README.md"))
        if readme.strip():
            remaining = budget - total
            if len(readme) > remaining:
                readme = readme[:remaining] + "\n\n[... truncated ...]"
            parts.append(f"### README.md\n\n{readme}")
            files_loaded.append("README.md")

    return "\n\n---\n\n".join(parts), files_loaded


def load_resonance(entry: dict, budget: int = MAX_LOAD_CHARS) -> tuple[str, list[str]]:
    """Load resonance content from a search result entry."""
    if entry["type"] == "circle":
        return _load_circle(entry["path"], budget)
    elif entry["type"] == "resonance":
        return _load_resonance_bundle(entry["path"], budget)
    return "", []


# ─── Command Handler ─────────────────────────────────────────────

async def cmd_load(message, args):
    """!load <context> — search workshop for resonance and load into conversation."""
    if not args:
        await message.reply(
            "**Usage:** `!load <context>`\n"
            "Searches circles and resonance bundles.\n"
            "Examples: `!load practitioner-context`, `!load romantic-partnership`, `!load travel`, `!load neurodiversity`",
            mention_author=False,
        )
        return

    query = " ".join(args)
    wr = get_workshop_root() or os.path.expanduser("~/workshop")

    matches = _search_resonance(query, wr)

    if not matches:
        # List what's available
        index = _build_resonance_index(wr)
        available = ", ".join(f"`{e['name']}`" for e in index)
        await message.reply(
            f"No resonance found for **{query}**.\n\n"
            f"**Available:** {available}",
            mention_author=False,
        )
        return

    # Load the best match
    best = matches[0]
    content, files_loaded = load_resonance(best)

    if not content.strip():
        await message.reply(
            f"Found **{best['name']}** ({best['type']}) but no loadable content.",
            mention_author=False,
        )
        return

    # Inject into absorbed_contexts for this channel
    channel_id = message.channel.id

    # Build the context entry
    context_entry = {
        "name": f"{best['name']} ({best['type']})",
        "digest": content,
        "absorbed_at": datetime.now(timezone.utc),
        "model_info": f"loaded from {best['type']}",
    }

    if channel_id not in absorbed_contexts:
        absorbed_contexts[channel_id] = []

    # Replace if same name already loaded
    existing = [a for a in absorbed_contexts[channel_id] if a["name"] != context_entry["name"]]
    existing.append(context_entry)
    absorbed_contexts[channel_id] = existing

    # Confirmation embed
    files_list = "\n".join(f"- `{f}`" for f in files_loaded[:10])
    if len(files_loaded) > 10:
        files_list += f"\n- ... and {len(files_loaded) - 10} more"

    type_emoji = "⭕" if best["type"] == "circle" else "📚"
    embed = discord.Embed(
        title=f"{type_emoji} Loaded: {best['name']}",
        description=(
            f"**Type:** {best['type']}\n"
            f"**Files loaded:**\n{files_list}\n\n"
            f"**Size:** {len(content):,} chars\n\n"
            f"This context is now active in this conversation."
        ),
        color=EMBED_COLORS.get("sync", 0x1ABC9C),
    )

    if len(matches) > 1:
        others = ", ".join(f"`{m['name']}`" for m in matches[1:4])
        embed.set_footer(text=f"Also matched: {others}")

    await message.reply(embed=embed, mention_author=False)
    await log_activity(
        f"Loaded **{best['name']}** ({best['type']}) resonance — {len(files_loaded)} files, {len(content):,} chars",
        type_emoji,
        channel=message.channel,
    )
