"""Share eddy filesystem persistence — inbox, pending, received (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import discord


def find_received_thread_for_share(runtime_dir: str, share_id: str) -> int | None:
    """Return thread id if this share was already continued (idempotent re-click)."""
    received = Path(runtime_dir) / "share" / "received"
    if not received.is_dir():
        return None
    for path in received.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("share_id") == share_id:
            try:
                return int(path.stem)
            except ValueError:
                continue
    return None


def _share_dir(runtime_dir: str, sub: str) -> Path:
    path = Path(runtime_dir) / "share" / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


def inbox_path(runtime_dir: str, share_id: str) -> Path:
    return _share_dir(runtime_dir, "inbox") / f"{share_id}.json"


def pending_path(runtime_dir: str, author_id: int, thread_id: int) -> Path:
    return _share_dir(runtime_dir, "pending") / f"{author_id}_{thread_id}.json"


def resolve_share_runtime_dir(*, parent_channel_id: int | None) -> str:
    """Practice runtime for share drafts — must match the sharer's hosted river parent."""
    from mage import get_runtime_dir, set_practice_context_for_channel

    if parent_channel_id:
        set_practice_context_for_channel(parent_channel_id)
    return get_runtime_dir()


def resolve_share_runtime_dir_from_interaction(interaction: discord.Interaction) -> str:
    channel = interaction.channel
    parent_id = channel.parent_id if isinstance(channel, discord.Thread) else None
    return resolve_share_runtime_dir(parent_channel_id=parent_id)


def received_thread_path(runtime_dir: str, thread_id: int) -> Path:
    return _share_dir(runtime_dir, "received") / f"{thread_id}.json"


def save_received_thread_config(runtime_dir: str, thread_id: int, cfg: dict[str, Any]) -> None:
    """Persist share-eddy notify metadata for cross-process reads (River vs Turtle bots)."""
    payload = {
        "origin": cfg.get("origin"),
        "share_id": cfg.get("share_id"),
        "share_creator": cfg.get("share_creator"),
        "sharer_key": cfg.get("sharer_key"),
        "share_recipient_id": cfg.get("share_recipient_id"),
        "share_notify_pending": cfg.get("share_notify_pending", False),
        "topic": cfg.get("topic"),
        "from_sharer": cfg.get("from_sharer"),
        "space_key": cfg.get("space_key"),
    }
    received_thread_path(runtime_dir, thread_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_received_thread_config(runtime_dir: str, thread_id: int) -> dict[str, Any] | None:
    path = received_thread_path(runtime_dir, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def mark_received_thread_notified(runtime_dir: str, thread_id: int) -> None:
    path = received_thread_path(runtime_dir, thread_id)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        path.unlink(missing_ok=True)
        return
    if not isinstance(data, dict):
        path.unlink(missing_ok=True)
        return
    data["share_notify_pending"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_inbox_bundle(runtime_dir: str, bundle: dict[str, Any]) -> Path:
    path = inbox_path(runtime_dir, bundle["share_id"])
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_inbox_bundle(runtime_dir: str, share_id: str) -> dict[str, Any] | None:
    path = inbox_path(runtime_dir, share_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write_pending_draft(runtime_dir: str, author_id: int, thread_id: int, draft: dict) -> None:
    pending_path(runtime_dir, author_id, thread_id).write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )


def load_pending_draft(runtime_dir: str, author_id: int, thread_id: int) -> dict | None:
    path = pending_path(runtime_dir, author_id, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def clear_pending_draft(runtime_dir: str, author_id: int, thread_id: int) -> None:
    pending_path(runtime_dir, author_id, thread_id).unlink(missing_ok=True)


def _active_acts_path(runtime_dir: str) -> Path:
    return _share_dir(runtime_dir, ".") / "active_river_acts.json"


def _load_active_share_acts(runtime_dir: str) -> list[dict[str, Any]]:
    path = _active_acts_path(runtime_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    acts = data.get("acts") if isinstance(data, dict) else data
    return acts if isinstance(acts, list) else []


def _save_active_share_acts(runtime_dir: str, acts: list[dict[str, Any]]) -> None:
    path = _active_acts_path(runtime_dir)
    path.write_text(json.dumps({"acts": acts}, ensure_ascii=False, indent=2), encoding="utf-8")


async def supersede_stale_share_acts(
    client: discord.Client,
    channel: discord.abc.Messageable,
    runtime_dir: str,
    *,
    keep_share_id: str,
    keep_message_id: int,
) -> None:
    """Track active share acts; only strip Continue when re-delivering the same share."""
    prior = _load_active_share_acts(runtime_dir)
    kept: list[dict[str, Any]] = []
    for act in prior:
        sid = act.get("share_id")
        mid = act.get("message_id")
        if sid == keep_share_id and mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(view=None)
            except discord.HTTPException:
                pass
            continue
        if sid and sid != keep_share_id:
            kept.append(act)
    kept.append({"share_id": keep_share_id, "message_id": str(keep_message_id)})
    _save_active_share_acts(runtime_dir, kept)
