from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from runtime.handoff import submit_practice_handoff
from runtime.tasks import Task


ArtifactKind = Literal["boom", "session", "proposal"]


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
