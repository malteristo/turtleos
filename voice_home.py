"""A spoken sentence becomes one turn in the owner's day eddy, and the reply comes back.

The phone can read the sentence. The speaker is given the full reply and keeps
only the talk. Personal voice, the house speaker and a later headphone button,
lands in that day's eddy. A triple press does not open another. He opens a
separate eddy himself when he wants one. At the next local day the eddy is
archived and a new one opens. Another member's home is not a candidate, even
when the owner has no home channel of their own.

A sentence typed with the Google keyboard, and a voice message sent in the
Discord app, do not come through this door.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from boom_takeup import home_channel_id

VOICE_EDDY_NAME = "voice"
WEBHOOK_NAME = "House speaker"

# What the voice assistant is told. Home Assistant renders this as a Jinja
# template before the sentence ever reaches the door. A brace that fails
# becomes the spoken line "Sorry, I had a problem with my template", and
# Turtle never hears the sentence. Plain text cannot fail that way. The
# triple press is reserved and is not read from here.
HA_INSTRUCTION = (
    "The words the person just said are the whole request. "
    "Reply with only the words that should be spoken."
)

def reset_presses() -> None:
    """Test seam. A press no longer carries state."""
    return None


def title_from(sentence: str) -> str:
    """A conversation name taken from what was said. Never empty."""
    text = " ".join((sentence or "").split())
    if not text:
        return VOICE_EDDY_NAME
    for match in re.finditer(r"[.?!](?:\s|$)", text):
        at = match.start()
        if 0 < at <= 80:
            text = text[:at]
            break
    text = text.strip()
    if len(text) > 80:
        cut = text[:80].rsplit(" ", 1)[0].strip()
        text = cut or text[:80].strip()
    return text or VOICE_EDDY_NAME


def name_for(*, current: str, opening: str, sentence: str, fresh: bool) -> str | None:
    """The name to set, or None when the conversation already has one.

    A new conversation is named from the sentence. The placeholder left by
    the first setup is named from the sentence that opened it.
    """
    if fresh:
        title = title_from(sentence)
        return title if title != current else None
    if (current or "") == VOICE_EDDY_NAME:
        title = title_from((opening or "").strip() or sentence)
        if title != VOICE_EDDY_NAME:
            return title
    return None


def note_press(body: dict) -> bool:
    """A triple press is accepted and does not open a conversation.

    One press and the wake word never arrive here. They start the microphone
    and the sentence continues the day eddy. The triple is reserved.
    """
    if not isinstance(body, dict):
        return False
    return str(body.get("event_type") or "") == "triple_press"


def note_messages(messages, now: float | None = None) -> None:
    """A triple mark in the request is ignored.

    The speaker still sends it. It does not choose which eddy the sentence joins.
    """
    del messages, now


def take_new_eddy(now: float | None = None) -> bool:
    """A press never opens a second voice eddy."""
    del now
    return False


def _tz() -> ZoneInfo:
    from state import PRACTICE_TIMEZONE

    return ZoneInfo(PRACTICE_TIMEZONE)


def local_now(now: datetime | None = None) -> datetime:
    """The practice clock. A naive value is read in that zone, not as UTC."""
    zone = _tz()
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def day_key(now: datetime | None = None) -> str:
    return local_now(now).strftime("%Y-%m-%d")


def day_title(now: datetime | None = None) -> str:
    when = local_now(now)
    return f"{when.strftime('%A')} {when.day} {when.strftime('%b')}"


def day_action(stored_day: str | None, today: str) -> str:
    """'stay' on today's eddy. 'open' when the stored day is missing or older."""
    if stored_day == today:
        return "stay"
    return "open"


def seconds_until_next_day(now: datetime | None = None) -> float:
    """Seconds until the next local midnight. At least one, so a watch can sleep."""
    current = local_now(now)
    nxt = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, (nxt - current).total_seconds())


def stamp_sentence(sentence: str, now: datetime | None = None) -> str:
    """The sentence as posted. The small line is when it was said."""
    when = local_now(now)
    clock = when.strftime("%A %H:%M")
    body = (sentence or "").strip()
    return f"{body}\n-# {clock}. Day eddy. This sentence may be hours after the last."


def voice_owner(registry: dict) -> str | None:
    """The primary person, when that person has exactly one home channel."""
    mages = registry.get("mages") or {}
    default = registry.get("default_mage")
    primary = None
    for key, row in mages.items():
        if not isinstance(row, dict):
            continue
        if row.get("primary") or key == default:
            primary = key
            break
    if not primary:
        return None
    if home_channel_id(registry, primary):
        return primary
    return None


def eddy_path(runtime_dir: str) -> Path:
    return Path(runtime_dir) / "voice-eddy.json"


def _load_record(runtime_dir: str) -> dict:
    try:
        data = json.loads(eddy_path(runtime_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_eddy_id(runtime_dir: str) -> int | None:
    try:
        return int(_load_record(runtime_dir)["thread_id"])
    except (KeyError, TypeError, ValueError):
        return None


def load_voice_day(runtime_dir: str) -> str | None:
    day = _load_record(runtime_dir).get("day")
    return day if isinstance(day, str) and day else None


def save_eddy_id(runtime_dir: str, thread_id: int, day: str | None = None) -> None:
    path = eddy_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if day is None:
        day = load_voice_day(runtime_dir)
    payload: dict = {"thread_id": int(thread_id)}
    if day:
        payload["day"] = day
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class SpokenTurn:
    """The turn dialogue replies to. The reply is kept even if posting it fails."""

    def __init__(self, channel, content: str, author_name: str, author_id: int):
        self.channel = channel
        self.content = content
        self.id = time.time_ns()
        self.author = type(
            "Author",
            (),
            {"display_name": author_name, "id": author_id, "bot": False},
        )()
        self.attachments = []
        self.reference = None
        self.message_snapshots = None
        self.mentions = []
        self.parts: list[str] = []

    async def reply(self, text, *, mention_author=False, view=None):
        self.parts.append(text)
        kwargs = {}
        if view is not None:
            kwargs["view"] = view
        try:
            await self.channel.send(text, **kwargs)
        except Exception as exc:
            print(f"Voice reply post failed: {type(exc).__name__}: {exc}")


async def deliver(sentence: str, *, thread, author_name: str, author_id: int, mirror, dialogue) -> str:
    """Post the sentence where it can be read, run the turn, return the full reply."""
    text = (sentence or "").strip()
    if not text:
        raise ValueError("empty sentence")
    try:
        await mirror(thread, text)
    except Exception as exc:
        print(f"Voice mirror failed: {type(exc).__name__}: {exc}")
    turn = SpokenTurn(thread, text, author_name, author_id)
    await dialogue(turn)
    return "\n".join(turn.parts)


def _discord_id(registry: dict, owner: str) -> int:
    raw = (registry.get("mages") or {}).get(owner, {}).get("discord_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def _mirror(parent, thread, text: str, username: str) -> None:
    import discord

    hook = None
    try:
        for existing in await parent.webhooks():
            if getattr(existing, "name", "") == WEBHOOK_NAME:
                hook = existing
                break
        if hook is None:
            hook = await parent.create_webhook(name=WEBHOOK_NAME)
        await hook.send(text, thread=thread, username=(username or "You")[:80])
    except Exception:
        await thread.send(text)


async def _apply_name(thread, title: str | None) -> None:
    if not title or title == getattr(thread, "name", ""):
        return
    try:
        await thread.edit(name=title[:100])
    except Exception as exc:
        print(f"Voice eddy rename failed: {type(exc).__name__}: {exc}")


async def _opening_sentence(thread) -> str:
    try:
        async for message in thread.history(limit=20, oldest_first=True):
            content = (getattr(message, "content", None) or "").strip()
            if content:
                return content
    except Exception as exc:
        print(f"Voice eddy opening unreadable: {type(exc).__name__}: {exc}")
    return ""


async def name_placeholder(thread) -> None:
    """A conversation still named voice takes the sentence that opened it."""
    if (getattr(thread, "name", "") or "") != VOICE_EDDY_NAME:
        return
    opening = await _opening_sentence(thread)
    await _apply_name(
        thread,
        name_for(
            current=VOICE_EDDY_NAME,
            opening=opening,
            sentence="",
            fresh=False,
        ),
    )


async def name_stored_placeholder(client) -> None:
    """Rename the open setup conversation once the door is up."""
    from mage import get_runtime_dir

    thread_id = load_eddy_id(get_runtime_dir())
    if not thread_id:
        return
    try:
        thread = await client.fetch_channel(thread_id)
    except Exception as exc:
        print(f"Voice eddy rename failed: {type(exc).__name__}: {exc}")
        return
    await name_placeholder(thread)


async def _ensure_thread(client, home_id: int, runtime_dir: str, *, fresh: bool, title: str, day: str):
    import discord
    from commands import thread_configs
    from datetime import datetime, timezone
    from state import TURTLE_MODEL

    existing = None if fresh else load_eddy_id(runtime_dir)
    thread = None
    if existing:
        try:
            thread = await client.fetch_channel(existing)
        except Exception:
            thread = None
        if thread is not None and getattr(thread, "archived", False):
            try:
                await thread.edit(archived=False)
            except Exception:
                thread = None
    if thread is None:
        channel = await client.fetch_channel(int(home_id))
        thread = await channel.create_thread(
            name=(title or VOICE_EDDY_NAME)[:100],
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread,
        )
        save_eddy_id(runtime_dir, thread.id, day)
    else:
        opening = await _opening_sentence(thread) if not fresh else ""
        await _apply_name(
            thread,
            name_for(
                current=getattr(thread, "name", "") or "",
                opening=opening,
                sentence=title,
                fresh=False,
            ),
        )
        save_eddy_id(runtime_dir, thread.id, day)
    thread_configs.setdefault(
        thread.id,
        {
            "model": TURTLE_MODEL,
            "use_api": False,
            "attunement": "semi",
            "model_label": "local",
            "eddy_type": "standard",
            "context_type": None,
            "created": datetime.now(timezone.utc),
            "native_vanilla": True,
            "blank_eddy": False,
            "awaiting_title": False,
            "presence_posted": True,
        },
    )
    return thread


async def _archive_thread(client, thread_id: int) -> None:
    try:
        thread = await client.fetch_channel(int(thread_id))
    except Exception as exc:
        print(f"Voice day close failed: {type(exc).__name__}: {exc}")
        return
    try:
        if not getattr(thread, "archived", False):
            await thread.edit(archived=True)
    except Exception as exc:
        print(f"Voice day close failed: {type(exc).__name__}: {exc}")


async def ensure_day_eddy(client, now: datetime | None = None):
    """Today's voice eddy. An older one is archived first. None without a home."""
    from mage import get_registry, get_runtime_dir, note_actor, set_practice_context_for_channel

    registry = get_registry()
    owner = voice_owner(registry)
    home = home_channel_id(registry, owner) if owner else None
    if not owner or not home:
        return None
    home_id = int(home)
    set_practice_context_for_channel(home_id)
    note_actor(owner)
    runtime_dir = get_runtime_dir()
    today = day_key(now)
    opened = day_action(load_voice_day(runtime_dir), today) == "open"
    if opened:
        previous = load_eddy_id(runtime_dir)
        if previous:
            await _archive_thread(client, previous)
    thread = await _ensure_thread(
        client,
        home_id,
        runtime_dir,
        fresh=opened,
        title=day_title(now) if opened else VOICE_EDDY_NAME,
        day=today,
    )
    return thread


async def answer_in_home(client, sentence: str) -> str:
    """One sentence in today's eddy. The full reply, page included."""
    from dialogue_turn import handle_dialogue
    from mage import address_for_mage_key, get_registry
    from state import get_channel_lock

    registry = get_registry()
    owner = voice_owner(registry)
    if not owner or not home_channel_id(registry, owner):
        raise RuntimeError("no home channel for the voice door")
    thread = await ensure_day_eddy(client)
    if thread is None:
        raise RuntimeError("no home channel for the voice door")
    home_id = int(home_channel_id(registry, owner))
    parent = getattr(thread, "parent", None)
    if parent is None:
        parent = await client.fetch_channel(home_id)
    name = address_for_mage_key(owner)
    author_id = _discord_id(registry, owner)
    if author_id:
        try:
            import discord

            await thread.add_user(discord.Object(id=author_id))
        except Exception as exc:
            print(f"Voice eddy add failed: {type(exc).__name__}: {exc}")

    async def mirror(found, text: str) -> None:
        await _mirror(parent, found, text, name)

    async def dialogue(turn) -> None:
        async with get_channel_lock(thread.id):
            await handle_dialogue(turn)

    return await deliver(
        stamp_sentence(sentence),
        thread=thread,
        author_name=name,
        author_id=author_id,
        mirror=mirror,
        dialogue=dialogue,
    )
