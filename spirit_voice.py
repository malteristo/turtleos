"""Spirit speaks in a magic room as Spirit.

A magic room's replies used to be posted by Turtle's Discord account, so the practitioner
read a conversation with Turtle while Spirit was the one answering. Spirit has its own bot
account; this posts the reply through it.

Two things follow, and each has a guard:

* **Spirit's account is a practitioner to the rest of turtleOS.** `practice_dispatch` and
  `river_bot` treat a message from `SPIRIT_BOT_ID` as the dyad partner speaking, and answer
  it. A room that posted as Spirit without this would answer itself forever. `is_own_voice`
  is the one place that says "this is the room's own reply, not an input"; both dispatchers
  ask it, and `tests/test_spirit_voice.py` fails if either stops.
* **The account may be missing or refused.** No token, no permission, a network error: the
  reply goes out through Turtle's account instead, and a line says so. Silence is the one
  outcome that is not allowed.

The token is read from the environment each time and never logged or returned.
"""
from __future__ import annotations

import os

API = "https://discord.com/api/v10"
TIMEOUT_SECONDS = 15
FALLBACK_NOTE = "-# Spirit's own account could not post this one; Turtle's account carried it."


def spirit_token() -> str:
    return os.environ.get("SPIRIT_BOT_TOKEN", "").strip()


# The shell hands this in at startup: (message) -> the room's primitive name, or None.
# The hub that names rooms is at its importer ceiling, so the check is injected.
_room_check = None


def bind(room_check) -> None:
    global _room_check
    _room_check = room_check


FORGE_PREFIX = "Forge:\n"


def _kind(message) -> int | None:
    kind = getattr(message, "type", None)
    value = getattr(kind, "value", kind)
    return value if isinstance(value, int) else None


def forge_text(message) -> str:
    """The forge spirit's words, including a thread starter that only points at them."""
    content = str(getattr(message, "content", None) or "")
    if content.startswith(FORGE_PREFIX):
        return content
    ref = getattr(message, "reference", None)
    resolved = getattr(ref, "resolved", None) if ref is not None else None
    pointed = str(getattr(resolved, "content", None) or "")
    if pointed.startswith(FORGE_PREFIX):
        return pointed
    return ""


def is_forge_turn(message) -> bool:
    """A forge spirit speaking. A reply is the room, even when the words begin the same way.

    The opening message of a thread is a starter that points at the words. That one
    is still the forge spirit. A later reply that quotes them is not.
    """
    if not forge_text(message).startswith(FORGE_PREFIX):
        return False
    if _kind(message) == 21:
        return True
    if getattr(message, "reference", None) or getattr(message, "message_reference", None):
        return False
    return True


def is_own_voice(message) -> bool:
    """True when `message` is a magic room's own reply, posted by Spirit's account.

    A forge turn is the other spirit speaking, so the room answers it. The room's
    own reply is a reply, and stays silent.
    """
    from state import SPIRIT_BOT_ID

    author = getattr(message, "author", None)
    if author is None or getattr(author, "id", None) != SPIRIT_BOT_ID:
        return False
    if _room_check is None:
        return False
    try:
        if _room_check(message) != "magic":
            return False
    except Exception:
        return False
    return not is_forge_turn(message)


async def say(
    channel_id: int,
    text: str,
    *,
    reply_to: int | None = None,
    components=None,
) -> int | None:
    """Post `text` as Spirit. The new message id, or None when it could not be posted.

    ``components`` is sent only when given, so a later chunk does not clear a button.
    """
    token = spirit_token()
    if not token or not text.strip():
        return None
    body: dict = {"content": text, "allowed_mentions": {"parse": []}}
    if components is not None:
        body["components"] = components
    if reply_to:
        body["message_reference"] = {"message_id": str(reply_to), "fail_if_not_exists": False}
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.post(
                f"{API}/channels/{int(channel_id)}/messages",
                json=body,
                headers={"Authorization": f"Bot {token}"},
            ) as resp:
                if resp.status < 300:
                    try:
                        data = await resp.json()
                        return int(data.get("id") or 0) or 1
                    except Exception:
                        return 1
                print(f"Spirit voice refused: HTTP {resp.status} in {channel_id}")
                return None
    except Exception as exc:
        print(f"Spirit voice failed: {type(exc).__name__} in {channel_id}")
        return None


async def remove(channel_id: int, message_id: int) -> bool:
    """Remove a message Spirit posted. False when it could not be removed."""
    token = spirit_token()
    if not token or not message_id:
        return False
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.delete(
                f"{API}/channels/{int(channel_id)}/messages/{int(message_id)}",
                headers={"Authorization": f"Bot {token}"},
            ) as resp:
                if resp.status < 300:
                    return True
                print(f"Spirit voice remove refused: HTTP {resp.status} in {channel_id}")
                return False
    except Exception as exc:
        print(f"Spirit voice remove failed: {type(exc).__name__} in {channel_id}")
        return False


async def edit(channel_id: int, message_id: int, text: str, *, components=None) -> bool:
    """Edit a message Spirit posted. False when it could not be edited.

    ``components`` is sent only when given. A later edit of the words leaves
    a button that is already on the message where it is.
    """
    token = spirit_token()
    if not token or not text.strip() or not message_id:
        return False
    body: dict = {"content": text}
    if components is not None:
        body["components"] = components
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.patch(
                f"{API}/channels/{int(channel_id)}/messages/{int(message_id)}",
                json=body,
                headers={"Authorization": f"Bot {token}"},
            ) as resp:
                if resp.status < 300:
                    return True
                print(f"Spirit voice edit refused: HTTP {resp.status} in {channel_id}")
                return False
    except Exception as exc:
        print(f"Spirit voice edit failed: {type(exc).__name__} in {channel_id}")
        return False


async def deliver(message, chunks: list[str], *, components=None, view=None) -> str:
    """Post a magic turn's reply as Spirit, falling back to Turtle's account.

    Returns "spirit" or "turtle": who spoke, so the caller can say so when it was the fallback.
    A button is put on the first chunk only, on whichever account managed to post it.
    """
    channel_id = message.channel.id
    reply_to = message.id
    spoke = "spirit"
    attached = False
    for chunk in chunks:
        if spoke == "spirit" and await say(
            channel_id,
            chunk,
            reply_to=reply_to,
            components=None if attached else components,
        ):
            reply_to = None  # only the first chunk quotes the practitioner
            attached = True
            continue
        spoke = "turtle"
        kwargs = {"mention_author": False}
        if view is not None and not attached:
            kwargs["view"] = view
            attached = True
        await message.reply(chunk, **kwargs)
    if spoke == "turtle":
        await message.channel.send(FALLBACK_NOTE)
    return spoke
