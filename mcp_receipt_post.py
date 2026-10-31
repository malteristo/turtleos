"""River posts MCP receipts. The access point only writes them.

A receipt in a conversation or in the health channel is silent, so an old
thread does not ping. The private-channel line is not silent: that is where
she actually hears it. Nothing in the receipt is written back into a note.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.atomic_io import file_lock
from mcp_access.receipts import RECEIPTS_REL, _load, _path, _save, pending_posts
from mcp_access.registry import private_root, river_channel_id


def health_channel_id(registry: dict, owner: str) -> int | None:
    from channel_primitives import resolve_primitive

    for cid, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived"):
            continue
        primitive = resolve_primitive(registry, cid)
        if primitive is not None and primitive.name == "health" and primitive.subject == owner:
            try:
                return int(cid)
            except (TypeError, ValueError):
                continue
    return None


def _destination(post: dict, *, owner: str, registry: dict) -> tuple[int | None, bool]:
    """(channel id, silent). None means this post cannot be placed."""
    kind = post.get("to")
    if kind == "private":
        return river_channel_id(owner, registry), False
    if kind == "health":
        return health_channel_id(registry, owner), True
    if kind == "thread":
        raw = post.get("thread_id")
        try:
            return int(raw), True
        except (TypeError, ValueError):
            return None, True
    return None, True


async def _send(client, channel_id: int, text: str, *, silent: bool) -> str:
    channel = client.get_channel(channel_id)
    if channel is None:
        channel = await client.fetch_channel(channel_id)
    join = getattr(channel, "join", None)
    if join is not None:
        await join()
    message = await channel.send(text, silent=silent)
    return str(message.id)


async def post_pending(client, registry_loader) -> int:
    """Post every unsent receipt. Returns how many messages left. Texts stay out of the log."""
    registry = registry_loader()
    sent = 0
    now = datetime.now(timezone.utc)
    for owner in list(registry.get("mages") or {}):
        root = private_root(str(owner), registry)
        if root is None or not (root / RECEIPTS_REL).is_file():
            continue
        path = _path(root)
        with file_lock(path):
            rows = _load(path)
            due = pending_posts(rows, now)
            jobs = []
            for row, index in due:
                post = row["posts"][index]
                channel_id, silent = _destination(post, owner=str(owner), registry=registry)
                if channel_id is None:
                    post["sent"] = "skipped:no-channel"
                    continue
                jobs.append((row["id"], index, channel_id, silent, post.get("text") or ""))
            _save(path, rows)
        for receipt_id, index, channel_id, silent, text in jobs:
            try:
                message_id = await _send(client, channel_id, text, silent=silent)
            except Exception as exc:
                print(f"MCP receipt post failed: {type(exc).__name__}")
                continue
            with file_lock(path):
                rows = _load(path)
                for current in rows:
                    if current.get("id") != receipt_id:
                        continue
                    posts = current.get("posts") or []
                    if index < len(posts) and posts[index].get("sent") is None:
                        posts[index]["sent"] = message_id
                        sent += 1
                _save(path, rows)
    return sent
