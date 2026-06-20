"""River-side eddy seneschal helpers.

Post-Turtle ``Save to library`` offers (harness split Slice 2): after Turtle replies,
River may offer ``!fetch`` when a practitioner URL is not yet in ``link-resonance/``.
Runs in the **River bot process** only. River receives practitioner messages, not Turtle
bot events reliably — poll thread history after practitioner URL posts.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict

import discord

from content_fetch import _URL_PATTERN
from link_read import external_urls

_save_offer_seen: dict[int, set[str]] = defaultdict(set)
_save_poll_tasks: dict[int, asyncio.Task] = {}


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


def _dialogue_history_snapshot(channel_id: int) -> list[dict]:
    """Best-effort thread history for save-offer eligibility (Turtle process may own this)."""
    try:
        from state import dialogue_histories

        return list(dialogue_histories.get(channel_id, []))
    except Exception:
        return []


def save_offer_skip_reason(
    practitioner_text: str,
    history: list[dict],
    channel_id: int,
    *,
    is_cached,
) -> str | None:
    """Human-readable skip reason when no Save offer should post."""
    urls = practitioner_external_urls(practitioner_text)
    if not urls:
        return "no_external_url"
    recent_fetched = _recent_fetch_urls(history)
    offered = _save_offer_seen.get(channel_id, set())
    for url in urls:
        key = _normalize_url(url).lower()
        if key in offered:
            continue
        if key in recent_fetched:
            continue
        if is_cached(url):
            continue
        return None
    for url in urls:
        key = _normalize_url(url).lower()
        if key in offered:
            return f"already_offered:{url[:120]}"
        if key in recent_fetched:
            return f"recent_fetch_act:{url[:120]}"
        if is_cached(url):
            return f"cached_in_link_resonance:{url[:120]}"
    return "no_eligible_url"


def pick_save_offer_url(
    practitioner_text: str,
    history: list[dict],
    channel_id: int,
    *,
    is_cached,
) -> str | None:
    """First uncached practitioner URL eligible for a post-Turtle save offer."""
    if save_offer_skip_reason(
        practitioner_text, history, channel_id, is_cached=is_cached
    ):
        return None
    for url in practitioner_external_urls(practitioner_text):
        key = _normalize_url(url).lower()
        if key in _recent_fetch_urls(history):
            continue
        if key in _save_offer_seen.get(channel_id, set()):
            continue
        if is_cached(url):
            continue
        return url
    return None


def _log_save_offer_skip(channel, reason: str) -> None:
    ch_name = getattr(channel, "name", getattr(channel, "id", "?"))
    print(f"Save offer skip ({reason}) in #{ch_name}")


def mark_save_offer_posted(channel_id: int, url: str) -> None:
    _save_offer_seen[channel_id].add(_normalize_url(url).lower())


def clear_save_offer_state(channel_id: int | None = None) -> None:
    """Test helper — reset in-memory offer dedupe."""
    if channel_id is None:
        _save_offer_seen.clear()
        for task in _save_poll_tasks.values():
            if not task.done():
                task.cancel()
        _save_poll_tasks.clear()
    else:
        _save_offer_seen.pop(channel_id, None)
        task = _save_poll_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()


def _cancel_save_poll(channel_id: int) -> None:
    task = _save_poll_tasks.pop(channel_id, None)
    if task and not task.done():
        task.cancel()


async def maybe_offer_eddy_save_after_turn(
    channel,
    *,
    practitioner_text: str,
) -> None:
    """River harness: post Save act row once Turtle has replied."""
    from cmd_link_resonance import get_cached_resonance
    from eddy_lifecycle_bar import post_act_suggestion_row
    from eddy_spawn import is_awaiting_flow_intake, is_awaiting_title
    from mage import river_bot_enabled
    from prompts import uses_native_turtle_prompt
    from river_state import river_client

    if not river_bot_enabled():
        return
    parent_id = getattr(channel, "parent_id", None)
    if not parent_id or not uses_native_turtle_prompt(parent_id):
        return
    if is_awaiting_flow_intake(channel.id, parent_id) or is_awaiting_title(channel.id, parent_id):
        return
    if not practitioner_external_urls(practitioner_text):
        return

    history = _dialogue_history_snapshot(channel.id)
    is_cached = lambda u: bool(get_cached_resonance(u))
    skip = save_offer_skip_reason(
        practitioner_text, history, channel.id, is_cached=is_cached
    )
    if skip:
        _log_save_offer_skip(channel, skip)
        return

    url = pick_save_offer_url(
        practitioner_text,
        history,
        channel.id,
        is_cached=is_cached,
    )
    if not url:
        _log_save_offer_skip(channel, "no_eligible_url")
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
    print(f"Save offer posted in #{getattr(channel, 'name', channel.id)} ({channel.id})")
    from bar_anchor import ensure_channel_bars

    await ensure_channel_bars(channel, river_client)


async def _wait_for_turtle_reply_after(
    channel: discord.Thread,
    practitioner_message: discord.Message,
    *,
    timeout_s: float = 240,
    poll_s: float = 2.0,
) -> bool:
    """Return True when a Turtle prose message appears after the practitioner turn."""
    from eddy_spawn import resolve_turtle_bot_user_id

    turtle_id = resolve_turtle_bot_user_id(getattr(channel, "guild", None))
    if not turtle_id:
        print("Save offer poll: turtle bot id unknown")
        return False

    practitioner_id = practitioner_message.id
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            async for msg in channel.history(limit=30, after=practitioner_message):
                if msg.id <= practitioner_id:
                    continue
                if getattr(msg.author, "id", None) != turtle_id:
                    continue
                if not (msg.content or "").strip():
                    continue
                print(
                    f"Save offer poll: Turtle reply seen in "
                    f"#{getattr(channel, 'name', channel.id)} (msg {msg.id})"
                )
                return True
        except discord.HTTPException as exc:
            print(f"Save offer poll failed for {channel.id}: {exc}")
            return False
        await asyncio.sleep(poll_s)
    print(f"Save offer poll timed out in #{getattr(channel, 'name', channel.id)}")
    return False


async def _run_save_offer_poll(practitioner_message: discord.Message) -> None:
    channel = practitioner_message.channel
    if not getattr(channel, "parent_id", None):
        return
    practitioner_text = practitioner_message.content or ""
    if not practitioner_external_urls(practitioner_text):
        return

    from cmd_link_resonance import get_cached_resonance
    from mage import set_practice_context, set_practice_context_for_channel

    set_practice_context(practitioner_message)
    if channel.parent_id:
        set_practice_context_for_channel(channel.parent_id)

    is_cached = lambda u: bool(get_cached_resonance(u))
    pre_history = _dialogue_history_snapshot(channel.id)
    pre_skip = save_offer_skip_reason(
        practitioner_text, pre_history, channel.id, is_cached=is_cached
    )
    if pre_skip:
        _log_save_offer_skip(channel, pre_skip)
        return

    ch_name = getattr(channel, "name", channel.id)
    print(f"Save offer polling in #{ch_name} ({channel.id})")
    if not await _wait_for_turtle_reply_after(channel, practitioner_message):
        return
    await maybe_offer_eddy_save_after_turn(channel, practitioner_text=practitioner_text)


def schedule_save_offer_after_practitioner_url(practitioner_message: discord.Message) -> None:
    """Schedule Save offer after practitioner URL post (River receives this message)."""
    channel = practitioner_message.channel
    if not getattr(channel, "parent_id", None):
        return
    if not practitioner_external_urls(practitioner_message.content or ""):
        return

    channel_id = channel.id
    _cancel_save_poll(channel_id)
    ch_name = getattr(channel, "name", channel_id)
    print(f"Save offer scheduled in #{ch_name} ({channel_id})")

    async def _wrapped() -> None:
        try:
            await _run_save_offer_poll(practitioner_message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Save offer schedule error #{channel_id}: {type(exc).__name__}: {exc}")

    _save_poll_tasks[channel_id] = asyncio.create_task(_wrapped())


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
