"""River-side eddy seneschal helpers.

Post-Turtle ``Save to library`` offers (harness split Slice 2): after Turtle replies,
River may offer ``!fetch`` when a practitioner URL is not yet in ``link-resonance/``.
Turtle link-read informs dialogue; River persistence is opt-in.
"""

from __future__ import annotations

import re
from collections import defaultdict

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


async def maybe_offer_eddy_save_after_turn(
    channel,
    *,
    practitioner_text: str,
    history: list[dict],
) -> None:
    """Post one River Save act row after Turtle replies in a native eddy."""
    from commands import _get_cached_resonance, send_with_actions
    from mage import river_bot_enabled

    if not river_bot_enabled():
        return
    channel_id = getattr(channel, "id", None)
    if not channel_id:
        return

    url = pick_save_offer_url(
        practitioner_text,
        history,
        channel.id,
        is_cached=lambda u: bool(_get_cached_resonance(u)),
    )
    if not url:
        return

    mark_save_offer_posted(channel.id, url)
    try:
        await send_with_actions(
            channel,
            "-# Save to library",
            [("Save to library", f"!fetch {url}")],
        )
    except Exception as exc:
        print(f"Save offer failed for {channel.id}: {type(exc).__name__}: {exc}")


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
