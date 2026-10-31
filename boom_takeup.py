"""The button on a Boom eddy that passes the claim into the owner's home.

A sentence in that eddy is the thought. "I should do this" is often the
thought itself, so the pass is a button. Pressing it opens one session in
the owner's home, carrying his words, Boom Turtle's reply, and the note
if one has been written. When that owner has a workshop checkout, the
session may work on the platform and the workshop keeps it. The eddy gets
one line with the link. While that session is open, the button points at
it. After it is released or archived, the button opens another.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import discord

BUTTON_ID = "boom:takeup"
LABEL = "Take this up"
OPENED_FROM = (
    "This session opened from a Boom eddy. "
    "Check it against the workshop, then carry it out if it is ready."
)
TAKEN_UP = "Taken up."
ALREADY = "Already open."
COULD_NOT = "Could not open the session."
_WORDS = 600
_REPLY = 500
_NOTE = 400
_MESSAGE = 1900


def still_open(*, found: bool, archived: bool, released: bool) -> bool:
    """A session the button should point at, not replace."""
    return bool(found) and not archived and not released


def carry_text(*, words: str, reply: str, note: str) -> str:
    """What the magic session opens on. The first line is the one Spirit is told to hear."""
    parts = [OPENED_FROM, "", "His words:", _clip(words, _WORDS) or "(none)"]
    reply = _clip(reply, _REPLY)
    note = _clip(note, _NOTE)
    if reply:
        parts += ["", "Boom Turtle:", reply]
    if note:
        parts += ["", "Note:", note]
    return "\n".join(parts)[:_MESSAGE]


def eddy_line(url: str, *, already: bool) -> str:
    lead = ALREADY if already else TAKEN_UP
    url = (url or "").strip()
    return f"{lead} {url}".strip()


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _record_path(runtime_dir: str, eddy_id: int) -> Path:
    return Path(runtime_dir) / "thread-state" / "boom-takeup" / f"{int(eddy_id)}.json"


def load_session(runtime_dir: str, eddy_id: int) -> int | None:
    path = _record_path(runtime_dir, eddy_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return int(data["session_id"])
    except (KeyError, TypeError, ValueError):
        return None


def save_session(runtime_dir: str, eddy_id: int, session_id: int) -> None:
    path = _record_path(runtime_dir, eddy_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"session_id": int(session_id)}, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def read_note(practice_dir: Path, eddy_id: int) -> str:
    """The eddy's note, if the idle checkpoint has written one. Empty otherwise."""
    from story_entries import EDDIES_SUBDIR

    folder = Path(practice_dir) / EDDIES_SUBDIR
    if not folder.is_dir():
        return ""
    matches = sorted(path for path in folder.glob(f"{int(eddy_id)}-*.md") if path.is_file())
    if not matches:
        return ""
    try:
        return matches[0].read_text(encoding="utf-8")
    except OSError:
        return ""


def _status_line(content: str) -> bool:
    text = (content or "").strip()
    return text.startswith((TAKEN_UP, ALREADY, COULD_NOT))


def _is_button_message(message) -> bool:
    for row in getattr(message, "components", None) or []:
        children = getattr(row, "children", None) or getattr(row, "components", None) or []
        for child in children:
            if getattr(child, "custom_id", None) == BUTTON_ID:
                return True
    return False


class TakeUpView(discord.ui.View):
    """One button, one id, every Boom eddy. The eddy is the channel of the press."""

    def __init__(self):
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label=LABEL,
            custom_id=BUTTON_ID,
            style=discord.ButtonStyle.primary,
        )
        button.callback = self._on_press
        self.add_item(button)

    async def _on_press(self, interaction: discord.Interaction) -> None:
        await on_takeup(interaction)


def arm_takeup(client) -> None:
    """Re-arm the button after a restart. One view covers every eddy that has it."""
    client.add_view(TakeUpView())


async def post_takeup_button(thread) -> None:
    await thread.send("\u200b", view=TakeUpView())


async def _fetch(client, channel_id: int):
    found = client.get_channel(int(channel_id))
    if found is not None:
        return found
    try:
        return await client.fetch_channel(int(channel_id))
    except Exception:
        return None


def _url(channel) -> str:
    jump = getattr(channel, "jump_url", None)
    if jump:
        return str(jump)
    guild = getattr(channel, "guild", None)
    guild_id = getattr(guild, "id", None)
    if guild_id and getattr(channel, "id", None):
        return f"https://discord.com/channels/{guild_id}/{channel.id}"
    return ""


async def gather_packet(thread, *, river_id: int | None, practice_dir: Path | None) -> tuple[str, str, str]:
    """His words, Boom Turtle's reply, and the note. Status lines and the button are not part of it."""
    words = ""
    parent = getattr(thread, "parent", None)
    if parent is not None:
        try:
            starter = await parent.fetch_message(thread.id)
            words = (getattr(starter, "content", None) or "").strip()
        except Exception:
            words = ""
    preface: list[str] = []
    reply: list[str] = []
    async for message in thread.history(limit=50, oldest_first=True):
        content = (getattr(message, "content", None) or "").strip()
        if _is_button_message(message) or _status_line(content) or not content:
            continue
        author = getattr(message, "author", None)
        if river_id is not None and getattr(author, "id", None) == river_id:
            preface.append(content)
            continue
        if getattr(author, "bot", False):
            reply.append(content)
    if preface:
        words = "\n\n".join(part for part in (words, "\n\n".join(preface)) if part)
    note = read_note(practice_dir, thread.id) if practice_dir is not None else ""
    return words, "\n\n".join(reply), note


def home_channel_id(registry: dict, owner: str) -> str | None:
    """The owner's one home channel. None when there is not exactly one."""
    found = []
    for cid, row in (registry.get("channels") or {}).items():
        if not isinstance(row, dict) or row.get("mage") != owner:
            continue
        if row.get("archived") or row.get("orphaned"):
            continue
        kind = str(row.get("primitive") or row.get("type") or "").strip().lower()
        if kind in {"private", "river", "hosted-river"}:
            found.append(str(cid))
    if len(found) != 1:
        return None
    return found[0]


def _platform_path(runtime_dir: str, thread_id: int) -> Path:
    return Path(runtime_dir) / "thread-state" / "platform-sessions" / str(int(thread_id))


def mark_platform_session(runtime_dir: str, thread_id: int) -> None:
    """This thread may work on the platform. The workshop keeps the session."""
    path = _platform_path(runtime_dir, thread_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("1", encoding="utf-8")


def is_platform_session(runtime_dir: str, thread_id: int) -> bool:
    try:
        return _platform_path(runtime_dir, thread_id).is_file()
    except (OSError, TypeError, ValueError):
        return False


def begin_platform_turn(is_thread: bool, runtime_dir: str, thread_id: int):
    """Mark this turn as a platform session, or return None when it is not one.

    The home room has no workshop capability. The file written at open is what
    lets this thread work on the platform. The caller still has to be the owner
    who holds the checkout; this only opens that door for the turn.
    """
    if not is_thread or not is_platform_session(runtime_dir, thread_id):
        return None
    from workshop_tools import set_platform_turn

    return set_platform_turn(True)


_house = None


def bind_house(fn) -> None:
    """The room that already opens eddies handles the press.

    This module does not import that room. Importing it back would put the
    button inside the same mutual-dependency cycle the layering ratchet forbids.
    """
    global _house
    _house = fn


async def on_takeup(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    if _house is None:
        channel = interaction.channel
        if channel is not None:
            await channel.send(COULD_NOT)
        return
    await _house(interaction)
