"""Discord → runtime translation. Named for Discord, importing none of it.

Everything here reads its input with `getattr`, which is why this module can sit
inside `runtime/` without breaking the boundary `tests/test_transport_boundary.py`
enforces. The practical benefit is that the whole inbound path can be tested with
plain objects, and the runtime never learns a snowflake from a Matrix MXID.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from runtime.handoff import submit_practice_handoff
from runtime.messages import Attachment, IncomingMessage
from runtime.tasks import Task


ArtifactKind = Literal["note", "session", "proposal"]

# What a Discord surface can do. Stated once, here, so no runtime code has to ask
# "is this Discord" to find out — it reads the declaration on the message.
DISCORD_AFFORDANCES = frozenset({"buttons", "attachments", "threads", "edit"})


def _id_str(obj: Any, attr: str = "id") -> str:
    value = getattr(obj, attr, None)
    return "" if value is None else str(value)


def incoming_from_discord(
    message: Any,
    *,
    urls: tuple[str, ...] | list[str] = (),
    affordances: frozenset[str] | None = None,
) -> IncomingMessage:
    """Normalize one Discord message into the transport-agnostic turn object.

    `urls` is passed in rather than re-extracted here: the caller has already run
    the URL scan and applied its own filtering, and a second extraction is a second
    thing that can disagree with the first.

    A Discord `Thread` is recognised by having a `parent_id`, not by an `isinstance`
    check, because the whole point of this module is that it holds no Discord types.
    Attachments are described, not fetched — fetching is the caller's decision and
    can be expensive.
    """
    channel = getattr(message, "channel", None)
    author = getattr(message, "author", None)

    channel_id = _id_str(channel)
    thread_id = channel_id if getattr(channel, "parent_id", None) is not None else None
    parent_id = _id_str(channel, "parent_id")

    reference = getattr(message, "reference", None)
    reply_to = getattr(reference, "message_id", None) if reference is not None else None

    attachments = tuple(
        Attachment(
            filename=str(getattr(att, "filename", "") or ""),
            content_type=str(getattr(att, "content_type", "") or ""),
            url=str(getattr(att, "url", "") or ""),
            size_bytes=int(getattr(att, "size", 0) or 0),
        )
        for att in (getattr(message, "attachments", None) or ())
    )

    return IncomingMessage(
        text=str(getattr(message, "content", "") or ""),
        practitioner_id=_id_str(author) or "unknown-author",
        # `channel_id` is the conversation's *root* where there is one, so that
        # `conversation_id` resolves to the thread and `channel_id` still names the
        # channel that owns it — which is what the offer ledger records against.
        channel_id=parent_id or channel_id or "unknown-channel",
        transport="discord",
        thread_id=thread_id,
        message_id=_id_str(message) or None,
        attachments=attachments,
        reply_to_id=str(reply_to) if reply_to is not None else None,
        urls=tuple(u for u in urls if u),
        is_from_bot=bool(getattr(author, "bot", False)),
        affordances=affordances if affordances is not None else DISCORD_AFFORDANCES,
        raw=message,
    )


def submit_discord_practice_handoff(
    *,
    message: Any,
    principal: str,
    artifact: ArtifactKind,
    title: str,
    body: str,
    registry_path: Path | str = Path("mage_registry.yaml"),
) -> Task:
    """Translate a Discord message-like object into a native runtime handoff.

    The runtime receives primitive source metadata only. Discord objects do not
    cross into task, audit, or capability code.
    """
    channel_id = getattr(getattr(message, "channel", None), "id", "unknown-channel")
    message_id = getattr(message, "id", "unknown-message")
    author_id = getattr(getattr(message, "author", None), "id", "unknown-author")
    source = f"discord:{channel_id}:{message_id}:author:{author_id}"
    return submit_practice_handoff(
        principal=principal,
        artifact=artifact,
        title=title,
        body=body,
        source=source,
        interface="discord",
        registry_path=registry_path,
        scope="practice",
        trust_level="operator",
    )
