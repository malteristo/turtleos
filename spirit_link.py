"""A forge spirit speaks to a house spirit.

The connection is the only door. ``speak`` opens one magic session, or
continues one this path already opened, and the house keeps the turn in the
channel and in the session file. It does not change files. It has no terminal
and no browser. The house spirit answers in the room, and ``hear`` brings
that reply back on this connection. A forge turn can look
at the workshop. A change still waits on him.

A grant does not gain this by a profile edit. The operation is on the house
profile for grants made after it, and an older grant gets it only when
``GrantStore.add_operation`` is asked.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from mcp_access.registry import load_registry
from session_record import append_event, read_turns

API = "https://discord.com/api/v10"
TIMEOUT_SECONDS = 15
TEXT_MAX = 1900
OPENED = "A forge spirit opened this session."


def channel_text(text: str) -> str:
    return f"Forge:\n{text.strip()}"


def thread_name(when: datetime) -> str:
    return when.astimezone().strftime("Forge · %d.%m")


def magic_channel_id(registry: dict, owner: str) -> str | None:
    """The owner's one magic channel. None when there is not exactly one."""
    found = []
    for cid, row in (registry.get("channels") or {}).items():
        if not isinstance(row, dict):
            continue
        kind = row.get("primitive") or row.get("type")
        if kind == "magic" and row.get("mage") == owner:
            found.append(str(cid))
    if len(found) != 1:
        return None
    return found[0]


def practice_dir_for(registry: dict, owner: str) -> Path | None:
    row = (registry.get("mages") or {}).get(owner) or {}
    raw = row.get("practice_dir")
    if not raw:
        return None
    path = Path(os.path.expanduser(str(raw)))
    return path if path.is_dir() else None


def known_session(practice_dir: Path, eddy: str) -> bool:
    """True when this path opened the session. Another sitting is not ours to enter."""
    return any(
        turn.get("actor") == "forge" and turn.get("kind") in ("greeting", "forge")
        for turn in read_turns(practice_dir, eddy)
    )


def _token() -> str:
    env = os.environ.get("SPIRIT_BOT_TOKEN", "").strip()
    if env:
        return env
    path = Path(os.environ.get("TURTLE_ENV_FILE", str(Path.home() / "turtleos" / ".env")))
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SPIRIT_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _http_send(method: str, url: str, body: dict) -> tuple[int, dict]:
    token = _token()
    if not token:
        return 0, {}
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        method=method,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "turtleos-spirit-link",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = resp.read().decode("utf-8")
            data = json.loads(payload) if payload else {}
            return resp.status, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        print(f"Spirit link refused: HTTP {exc.code}")
        return exc.code, {}
    except Exception as exc:
        print(f"Spirit link failed: {type(exc).__name__}")
        return 0, {}


def _record(practice_dir: Path, eddy: str, text: str, *, opened: bool) -> None:
    if opened:
        append_event(practice_dir, eddy, kind="greeting", actor="forge", text=OPENED)
    append_event(practice_dir, eddy, kind="forge", actor="forge", text=text)


def speak(
    *,
    owner: str,
    text: str,
    session: str | None,
    registry: dict,
    send,
    when: datetime | None = None,
) -> dict:
    """Open or continue one magic session. ``send(method, url, body) -> (status, data)``."""
    body = (text or "").strip()
    if not body:
        return {"ok": False, "error": "a turn needs words"}
    if len(body) > TEXT_MAX:
        return {"ok": False, "error": "that turn is too long for the channel"}
    root = practice_dir_for(registry, owner)
    if root is None:
        return {"ok": False, "error": "the practice root is not on this host"}
    channel = magic_channel_id(registry, owner)
    if channel is None:
        return {"ok": False, "error": "this house has no single magic channel for that owner"}
    posted = channel_text(body)
    if not session:
        status, thread = send(
            "POST",
            f"{API}/channels/{channel}/threads",
            {
                "name": thread_name(when or datetime.now().astimezone()),
                "type": 11,
                "auto_archive_duration": 1440,
            },
        )
        thread_id = str((thread or {}).get("id") or "")
        if status >= 300 or status == 0 or not thread_id:
            return {"ok": False, "error": "the house could not open the session"}
        discord_id = str(((registry.get("mages") or {}).get(owner) or {}).get("discord_id") or "")
        if discord_id.isdigit():
            send("PUT", f"{API}/channels/{thread_id}/thread-members/{discord_id}", {})
        # The words are a normal message in the thread. A thread starter only
        # points at its opening message, and the room would not see the words.
        status, _ = send(
            "POST",
            f"{API}/channels/{thread_id}/messages",
            {"content": posted, "allowed_mentions": {"parse": []}},
        )
        if status >= 300 or status == 0:
            return {"ok": False, "error": "the house could not open the session"}
        _record(root, thread_id, body, opened=True)
        return {
            "ok": True,
            "session": thread_id,
            "opened": True,
            "kept": "The turn is in the magic channel. hear brings the house spirit's reply back.",
        }
    if not session.isdigit() or not known_session(root, session):
        return {"ok": False, "error": "that session was not opened from this connection"}
    status, _ = send(
        "POST",
        f"{API}/channels/{session}/messages",
        {"content": posted, "allowed_mentions": {"parse": []}},
    )
    if status >= 300 or status == 0:
        return {"ok": False, "error": "the house could not keep that turn"}
    _record(root, session, body, opened=False)
    return {
        "ok": True,
        "session": session,
        "opened": False,
        "kept": "The turn is in the magic channel. hear brings the house spirit's reply back.",
    }


def hear(*, owner: str, session: str | None, registry: dict) -> dict:
    """The latest house reply in a session this connection opened.

    Empty, and waiting, until the house spirit has posted one. Another
    sitting's reply is not returned.
    """
    eddy = str(session or "").strip()
    if not eddy.isdigit():
        return {"ok": False, "error": "that session was not opened from this connection"}
    root = practice_dir_for(registry, owner)
    if root is None:
        return {"ok": False, "error": "the practice root is not on this host"}
    if not known_session(root, eddy):
        return {"ok": False, "error": "that session was not opened from this connection"}
    reply = ""
    for turn in read_turns(root, eddy):
        if turn.get("kind") != "turn":
            continue
        text = str(turn.get("reply") or "").strip()
        if text:
            reply = text
    if not reply:
        return {"ok": True, "session": eddy, "reply": "", "waiting": True}
    return {"ok": True, "session": eddy, "reply": reply, "waiting": False}


def needs_answer(turns: list[dict]) -> bool:
    """True when a forge turn is the last thing said and the house has not replied."""
    last_forge = -1
    last_reply = -1
    for i, turn in enumerate(turns):
        if turn.get("kind") == "forge" and turn.get("actor") == "forge":
            last_forge = i
        if turn.get("kind") == "turn" and str(turn.get("reply") or "").strip():
            last_reply = i
    return last_forge >= 0 and last_reply < last_forge


def pending_eddies(practice_dir: Path) -> list[str]:
    folder = Path(practice_dir) / "state" / "sessions"
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob("*.jsonl")):
        turns = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                turns.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        if needs_answer(turns):
            found.append(path.stem)
    return found


_answering: set[str] = set()


async def answer_pending(client, *, registry: dict | None = None, dispatch=None) -> list[str]:
    """Answer a forge turn the room missed because it looked like the room's own voice.

    Returns the session ids it handed to the room. A session already being
    answered is left alone, so a second ready does not start a second reply.
    """
    from spirit_voice import forge_text, is_forge_turn

    if registry is None:
        print("Forge answer skipped: no registry was given")
        return []
    if dispatch is None:
        from practice_dispatch import dispatch_incoming_message

        dispatch = dispatch_incoming_message
    answered: list[str] = []
    owners = list((registry.get("mages") or {}))
    for owner in owners:
        root = practice_dir_for(registry, owner)
        if root is None or magic_channel_id(registry, owner) is None:
            continue
        for eddy in pending_eddies(root):
            if eddy in _answering:
                continue
            _answering.add(eddy)
            try:
                thread = await client.fetch_channel(int(eddy))
                message = None
                async for item in thread.history(limit=30):
                    if is_forge_turn(item):
                        message = item
                        break
                if message is None:
                    continue
                text = forge_text(message)
                if text and not str(getattr(message, "content", None) or "").startswith("Forge:\n"):
                    message.content = text
                print(f"Forge answer: {eddy}")
                await dispatch(message)
                answered.append(eddy)
            except Exception as exc:
                print(f"Forge answer failed for {eddy}: {type(exc).__name__}: {exc}")
            finally:
                _answering.discard(eddy)
    return answered


def deliver_live(owner: str, text: str, session: str | None) -> dict:
    return speak(owner=owner, text=text, session=session, registry=load_registry(), send=_http_send)


def hear_live(owner: str, session: str | None) -> dict:
    return hear(owner=owner, session=session, registry=load_registry())
