"""River-side eddy seneschal — post-Turtle contextual act rows (D3).

After Turtle replies in a native eddy, River may post **one** situational act row:
Save to library (uncached URL) or Checkpoint (explicit practitioner intent).
Runs in the **River bot process** only — polls thread history for Turtle prose.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass

import discord

from content_fetch import _URL_PATTERN
from link_read import external_urls

_save_offer_seen: dict[int, set[str]] = defaultdict(set)
_contextual_poll_tasks: dict[int, asyncio.Task] = {}

_CHECKPOINT_INTENT_RE = re.compile(
    r"\b(?:"
    r"checkpoint|check\s*point|"
    r"wrap\s*(?:this|up|it|here)|"
    r"save\s+(?:this|our|the)\s+(?:session|progress|conversation|thread)|"
    r"capture\s+(?:this|that|our|the)"
    r")\b",
    re.IGNORECASE,
)

TURTLE_REPLY_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class ContextualOffer:
    kind: str
    label: str
    actions: list[tuple[str, str]]


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


def _recent_act(history: list[dict], cmd: str, *, window: int = 8) -> bool:
    needle = f"[Act: !{cmd}]"
    recent = "\n".join(m.get("content", "") for m in history[-window:])
    return needle in recent


def _dialogue_history_snapshot(channel_id: int) -> list[dict]:
    """Thread history for offer eligibility — shared store in split-bot mode."""
    try:
        from dialogue_store import read_shared, shared_dialogue_enabled
        from state import dialogue_histories

        if shared_dialogue_enabled():
            disk = read_shared(channel_id)
            if disk:
                return list(disk)
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


def checkpoint_offer_skip_reason(
    practitioner_text: str,
    history: list[dict],
    *,
    min_exchanges: int,
) -> str | None:
    """Skip reason when no Checkpoint offer should post."""
    if not _CHECKPOINT_INTENT_RE.search(practitioner_text or ""):
        return "no_checkpoint_intent"
    if len(history) < min_exchanges:
        return f"thin_history:{len(history)}"
    if _recent_act(history, "checkpoint"):
        return "recent_checkpoint_act"
    return None


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


def pick_contextual_offer(
    practitioner_text: str,
    history: list[dict],
    channel_id: int,
    *,
    is_cached,
    min_exchanges: int,
) -> ContextualOffer | None:
    """Return at most one contextual offer for this practitioner turn."""
    url = pick_save_offer_url(
        practitioner_text, history, channel_id, is_cached=is_cached
    )
    if url:
        return ContextualOffer(
            kind="save",
            label="-# Save to library",
            actions=[("Save to library", f"!fetch {url}")],
        )
    if not checkpoint_offer_skip_reason(
        practitioner_text, history, min_exchanges=min_exchanges
    ):
        return ContextualOffer(
            kind="checkpoint",
            label="-# Checkpoint this thread",
            actions=[("Checkpoint", "!checkpoint")],
        )
    return None


def _log_contextual_skip(channel, kind: str, reason: str) -> None:
    ch_name = getattr(channel, "name", getattr(channel, "id", "?"))
    print(f"Contextual offer skip ({kind}:{reason}) in #{ch_name}")


def _log_contextual_posted(channel, kind: str) -> None:
    ch_name = getattr(channel, "name", getattr(channel, "id", "?"))
    print(f"Contextual offer posted ({kind}) in #{getattr(channel, 'name', channel.id)} ({channel.id})")


def mark_save_offer_posted(channel_id: int, url: str) -> None:
    _save_offer_seen[channel_id].add(_normalize_url(url).lower())


def clear_save_offer_state(channel_id: int | None = None) -> None:
    """Test helper — reset in-memory offer dedupe and poll tasks."""
    if channel_id is None:
        _save_offer_seen.clear()
        for task in _contextual_poll_tasks.values():
            if not task.done():
                task.cancel()
        _contextual_poll_tasks.clear()
    else:
        _save_offer_seen.pop(channel_id, None)
        task = _contextual_poll_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()


def _cancel_contextual_poll(channel_id: int) -> None:
    task = _contextual_poll_tasks.pop(channel_id, None)
    if task and not task.done():
        task.cancel()


async def maybe_offer_contextual_act_after_turn(
    channel,
    *,
    practitioner_text: str,
) -> None:
    """River harness: post one contextual act row once Turtle has replied."""
    from cmd_link_resonance import get_cached_resonance
    from eddy_lifecycle_bar import post_act_suggestion_row
    from eddy_spawn import is_awaiting_flow_intake, is_awaiting_title
    from mage import river_bot_enabled
    from prompts import uses_native_turtle_prompt
    from river_state import river_client
    from state import MIN_EXCHANGES_FOR_CHECKPOINT

    if not river_bot_enabled():
        return
    parent_id = getattr(channel, "parent_id", None)
    if not parent_id or not uses_native_turtle_prompt(parent_id):
        return
    if is_awaiting_flow_intake(channel.id, parent_id) or is_awaiting_title(channel.id, parent_id):
        return

    history = _dialogue_history_snapshot(channel.id)
    is_cached = lambda u: bool(get_cached_resonance(u))
    offer = pick_contextual_offer(
        practitioner_text,
        history,
        channel.id,
        is_cached=is_cached,
        min_exchanges=MIN_EXCHANGES_FOR_CHECKPOINT,
    )
    if not offer:
        save_skip = save_offer_skip_reason(
            practitioner_text, history, channel.id, is_cached=is_cached
        )
        ckpt_skip = checkpoint_offer_skip_reason(
            practitioner_text, history, min_exchanges=MIN_EXCHANGES_FOR_CHECKPOINT
        )
        _log_contextual_skip(
            channel,
            "any",
            f"save={save_skip or 'eligible'};checkpoint={ckpt_skip or 'eligible'}",
        )
        return

    try:
        msg = await post_act_suggestion_row(
            channel,
            offer.label,
            offer.actions,
            river_client,
        )
    except Exception as exc:
        print(f"Contextual offer failed for {channel.id}: {type(exc).__name__}: {exc}")
        return
    if not msg:
        print(f"Contextual offer skipped for #{getattr(channel, 'name', channel.id)} — no act buttons")
        return

    if offer.kind == "save":
        url = pick_save_offer_url(
            practitioner_text, history, channel.id, is_cached=is_cached
        )
        if url:
            mark_save_offer_posted(channel.id, url)

    _log_contextual_posted(channel, offer.kind)
    from bar_anchor import ensure_channel_bars

    await ensure_channel_bars(channel, river_client)


async def maybe_offer_eddy_save_after_turn(
    channel,
    *,
    practitioner_text: str,
) -> None:
    """Backward-compatible alias — delegates to unified contextual offers."""
    await maybe_offer_contextual_act_after_turn(channel, practitioner_text=practitioner_text)


def _assistant_replied_for_practitioner_turn(
    history: list[dict],
    practitioner_text: str,
) -> bool:
    """True when shared dialogue history has assistant prose after this user turn."""
    needle = (practitioner_text or "").strip()
    if not needle:
        return False
    last_user_idx: int | None = None
    for i, entry in enumerate(history):
        if entry.get("role") != "user":
            continue
        content = (entry.get("content") or "").strip()
        if needle[:240] in content or content[:240] in needle:
            last_user_idx = i
    if last_user_idx is None:
        return False
    for entry in history[last_user_idx + 1 :]:
        if entry.get("role") != "assistant":
            continue
        if (entry.get("content") or "").strip():
            return True
    return False


def _turtle_discord_message_ready(msg: discord.Message) -> bool:
    if (msg.content or "").strip():
        return True
    embeds = getattr(msg, "embeds", None) or []
    return any((getattr(e, "description", None) or "").strip() for e in embeds)


async def _wait_for_turtle_reply_after(
    channel: discord.Thread,
    practitioner_message: discord.Message,
    *,
    timeout_s: float = TURTLE_REPLY_TIMEOUT_S,
    poll_s: float = 2.0,
) -> bool:
    """Return True when Turtle finishes the practitioner turn (split-bot safe)."""
    from eddy_spawn import resolve_turtle_bot_user_id
    from river_turn_signal import consume_turtle_turn_complete

    turtle_id = resolve_turtle_bot_user_id(getattr(channel, "guild", None))
    if not turtle_id:
        print("Contextual offer poll: turtle bot id unknown")
        return False

    practitioner_id = practitioner_message.id
    practitioner_text = practitioner_message.content or ""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if consume_turtle_turn_complete(channel.id, practitioner_id):
            print(
                f"Contextual offer poll: Turtle turn signal in "
                f"#{getattr(channel, 'name', channel.id)} (msg {practitioner_id})"
            )
            return True

        history = _dialogue_history_snapshot(channel.id)
        if _assistant_replied_for_practitioner_turn(history, practitioner_text):
            print(
                f"Contextual offer poll: shared history assistant in "
                f"#{getattr(channel, 'name', channel.id)}"
            )
            return True

        try:
            async for msg in channel.history(limit=30, after=practitioner_message):
                if msg.id <= practitioner_id:
                    continue
                if getattr(msg.author, "id", None) != turtle_id:
                    continue
                if not _turtle_discord_message_ready(msg):
                    continue
                print(
                    f"Contextual offer poll: Turtle reply seen in "
                    f"#{getattr(channel, 'name', channel.id)} (msg {msg.id})"
                )
                return True
        except discord.HTTPException as exc:
            print(f"Contextual offer poll failed for {channel.id}: {exc}")
            return False
        await asyncio.sleep(poll_s)
    print(f"Contextual offer poll timed out in #{getattr(channel, 'name', channel.id)}")
    return False


async def _run_contextual_offer_poll(practitioner_message: discord.Message) -> None:
    channel = practitioner_message.channel
    if not getattr(channel, "parent_id", None):
        return
    practitioner_text = practitioner_message.content or ""

    from cmd_link_resonance import get_cached_resonance
    from mage import set_practice_context, set_practice_context_for_channel
    from state import MIN_EXCHANGES_FOR_CHECKPOINT

    set_practice_context(practitioner_message)
    if channel.parent_id:
        set_practice_context_for_channel(channel.parent_id)

    is_cached = lambda u: bool(get_cached_resonance(u))
    pre_history = _dialogue_history_snapshot(channel.id)
    pre_offer = pick_contextual_offer(
        practitioner_text,
        pre_history,
        channel.id,
        is_cached=is_cached,
        min_exchanges=MIN_EXCHANGES_FOR_CHECKPOINT,
    )
    if not pre_offer:
        save_skip = save_offer_skip_reason(
            practitioner_text, pre_history, channel.id, is_cached=is_cached
        )
        ckpt_skip = checkpoint_offer_skip_reason(
            practitioner_text, pre_history, min_exchanges=MIN_EXCHANGES_FOR_CHECKPOINT
        )
        _log_contextual_skip(
            channel,
            "pre_poll",
            f"save={save_skip};checkpoint={ckpt_skip}",
        )
        return

    ch_name = getattr(channel, "name", channel.id)
    print(f"Contextual offer polling ({pre_offer.kind}) in #{ch_name} ({channel.id})")
    if not await _wait_for_turtle_reply_after(channel, practitioner_message):
        return
    await maybe_offer_contextual_act_after_turn(channel, practitioner_text=practitioner_text)


def schedule_contextual_offer_after_practitioner_turn(
    practitioner_message: discord.Message,
) -> None:
    """Schedule contextual offer after practitioner message (River process)."""
    channel = practitioner_message.channel
    if not getattr(channel, "parent_id", None):
        return

    channel_id = channel.id
    _cancel_contextual_poll(channel_id)
    ch_name = getattr(channel, "name", channel_id)
    print(f"Contextual offer scheduled in #{ch_name} ({channel_id})")

    async def _wrapped() -> None:
        try:
            await _run_contextual_offer_poll(practitioner_message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Contextual offer schedule error #{channel_id}: {type(exc).__name__}: {exc}")

    _contextual_poll_tasks[channel_id] = asyncio.create_task(_wrapped())


def schedule_save_offer_after_practitioner_url(practitioner_message: discord.Message) -> None:
    """Backward-compatible alias."""
    schedule_contextual_offer_after_practitioner_turn(practitioner_message)


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


# Legacy names for tests / imports
_save_poll_tasks = _contextual_poll_tasks
_cancel_save_poll = _cancel_contextual_poll
_run_save_offer_poll = _run_contextual_offer_poll
