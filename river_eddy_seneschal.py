"""River-side eddy seneschal helpers.

Post-Turtle ``Save to library`` offers (harness split Slice 2): after Turtle replies,
River may offer ``!fetch`` when a practitioner URL is not yet in ``link-resonance/``.
Must run in the **River bot process** — Turtle's discord_bot cannot post via ``river_client``.
"""

from __future__ import annotations

import re
from collections import defaultdict

import discord

from content_fetch import _URL_PATTERN
from link_read import external_urls

_save_offer_seen: dict[int, set[str]] = defaultdict(set)


def _normalize_url(url: str) -> str:
    return re.sub(r"\s+", " ", url.strip().rstrip(".,;:)"))


def practitioner_external_urls(text: str) -> list[str]:
    """External URLs from practitioner-visible message text."""
    found = external_urls(_URL_PATTERN.findall(text or ""))
    out: list[str] = []
    seen: set[str] = set()
    for url in found:
        key = _normalize_url(url).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def _recent_fetch_urls(history: list[dict], *, window: int = 12) -> set[str]:
    urls: set[str] = set()
    recent = "\n".join(m.get("content", "") for m in history[-window:])
    for line in recent.splitlines():
        if not line.startswith("[Act: !fetch]"):
            continue
        for url in external_urls(_URL_PATTERN.findall(line)):
            urls.add(_normalize_url(url).lower())
    return urls


def pick_save_offer_url(
    practitioner_text: str,
    history: list[dict],
    channel_id: int,
    *,
    is_cached,
) -> str | None:
    """First uncached practitioner URL eligible for a post-Turtle save offer."""
    recent_fetched = _recent_fetch_urls(history)
    offered = _save_offer_seen.get(channel_id, set())
    for url in practitioner_external_urls(practitioner_text):
        key = _normalize_url(url).lower()
        if key in recent_fetched or key in offered:
            continue
        if is_cached(url):
            continue
        return url
    return None


def mark_save_offer_posted(channel_id: int, url: str) -> None:
    _save_offer_seen[channel_id].add(_normalize_url(url).lower())


def clear_save_offer_state(channel_id: int | None = None) -> None:
    """Test helper — reset in-memory offer dedupe."""
    if channel_id is None:
        _save_offer_seen.clear()
    else:
        _save_offer_seen.pop(channel_id, None)


async def practitioner_text_from_turtle_reply(turtle_message: discord.Message) -> str:
    """Practitioner-visible text that triggered this Turtle reply."""
    ref = turtle_message.reference
    if ref and ref.message_id:
        try:
            src = ref.resolved
            if src is None:
                src = await turtle_message.channel.fetch_message(ref.message_id)
            if src and not getattr(src.author, "bot", False):
                return src.content or ""
        except discord.HTTPException as exc:
            print(f"Save offer: could not resolve reply reference: {exc}")
    try:
        async for msg in turtle_message.channel.history(
            limit=20,
            before=turtle_message.created_at,
        ):
            if not getattr(msg.author, "bot", False) and (msg.content or "").strip():
                return msg.content or ""
    except discord.HTTPException as exc:
        print(f"Save offer: history scan failed: {exc}")
    return ""


async def maybe_offer_eddy_save_on_turtle_reply(turtle_message: discord.Message) -> None:
    """River harness: post Save act row after Turtle prose in a native eddy."""
    from commands import _get_cached_resonance
    from eddy_lifecycle_bar import post_act_suggestion_row
    from eddy_spawn import is_awaiting_flow_intake, is_awaiting_title
    from mage import river_bot_enabled
    from prompts import uses_native_turtle_prompt
    from river_state import river_client

    if not river_bot_enabled():
        return
    channel = turtle_message.channel
    parent_id = getattr(channel, "parent_id", None)
    if not parent_id or not uses_native_turtle_prompt(parent_id):
        return
    if is_awaiting_flow_intake(channel.id, parent_id) or is_awaiting_title(channel.id, parent_id):
        return

    practitioner_text = await practitioner_text_from_turtle_reply(turtle_message)
    if not practitioner_external_urls(practitioner_text):
        return

    url = pick_save_offer_url(
        practitioner_text,
        [],
        channel.id,
        is_cached=lambda u: bool(_get_cached_resonance(u)),
    )
    if not url:
        return

    try:
        msg = await post_act_suggestion_row(
            channel,
            "-# Save to library",
            [("Save to library", f"!fetch {url}")],
            river_client,
        )
    except Exception as exc:
        print(f"Save offer failed for {channel.id}: {type(exc).__name__}: {exc}")
        return
    if not msg:
        print(f"Save offer skipped for #{getattr(channel, 'name', channel.id)} — no act buttons")
        return

    mark_save_offer_posted(channel.id, url)
    from bar_anchor import ensure_channel_bars

    await ensure_channel_bars(channel, river_client)


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
