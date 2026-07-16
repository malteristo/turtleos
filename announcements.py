"""Versioned update announcements for practitioner rivers (River-owned).

Manual fanout after ship — posts locale-aware embeds into every ``river`` and
``hosted-river`` channel. Subsumes return-visit into a dated announcement series.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent
ANNOUNCEMENTS_DIR = REPO_ROOT / "template" / "announcements"
RETURN_VISIT_ANNOUNCEMENT_ID = "2026-07-16-nesrine-ready"
_ANNOUNCEMENT_CHANNEL_TYPES = frozenset({"river", "hosted-river"})
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$|^[a-z0-9]$")


@dataclass
class AnnouncementSpec:
    announcement_id: str
    title: str
    body: str
    locale: str
    path: Path


def _state_path(channel_id: int) -> Path:
    from mage import _resolve_runtime_dir_for_channel, set_practice_context_for_channel

    set_practice_context_for_channel(channel_id)
    runtime = _resolve_runtime_dir_for_channel(channel_id)
    river_dir = Path(runtime) / "thread-state" / "river"
    river_dir.mkdir(parents=True, exist_ok=True)
    return river_dir / "announcements.json"


def _load_state(channel_id: int) -> dict[str, Any]:
    path = _state_path(channel_id)
    if not path.is_file():
        return {"posted": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"posted": {}}
    if not isinstance(data, dict):
        return {"posted": {}}
    posted = data.get("posted")
    if not isinstance(posted, dict):
        data["posted"] = {}
    return data


def is_posted(channel_id: int, announcement_id: str) -> bool:
    posted = _load_state(channel_id).get("posted") or {}
    return str(announcement_id) in posted


def mark_posted(
    channel_id: int,
    announcement_id: str,
    message_id: int | None = None,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    data = _load_state(channel_id)
    posted = data.setdefault("posted", {})
    entry: dict[str, Any] = {"at": now.isoformat(timespec="seconds")}
    if message_id is not None:
        entry["message_id"] = int(message_id)
    posted[str(announcement_id)] = entry
    path = _state_path(channel_id)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def list_announcement_ids(*, announcements_dir: Path | None = None) -> list[str]:
    base = announcements_dir or ANNOUNCEMENTS_DIR
    if not base.is_dir():
        return []
    ids: set[str] = set()
    for path in base.glob("*.md"):
        if path.name.startswith("_"):
            continue
        # id.locale.md or id.md
        name = path.name[:-3]
        if "." in name:
            ann_id, locale = name.rsplit(".", 1)
            if locale in ("en", "de") and _ID_RE.match(ann_id):
                ids.add(ann_id)
        elif _ID_RE.match(name):
            ids.add(name)
    return sorted(ids)


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.strip().startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, parts[2].strip()


def _resolve_announcement_path(
    announcement_id: str, locale: str, *, announcements_dir: Path | None = None
) -> Path | None:
    base = announcements_dir or ANNOUNCEMENTS_DIR
    for candidate in (
        base / f"{announcement_id}.{locale}.md",
        base / f"{announcement_id}.en.md",
        base / f"{announcement_id}.md",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_announcement(
    announcement_id: str,
    locale: str = "en",
    *,
    announcements_dir: Path | None = None,
) -> AnnouncementSpec | None:
    locale = (locale or "en").strip().lower()
    if locale not in ("de", "en"):
        locale = "en"
    path = _resolve_announcement_path(
        announcement_id, locale, announcements_dir=announcements_dir
    )
    if path is None:
        return None
    raw = path.read_text(encoding="utf-8")
    meta, body = _split_front_matter(raw)
    title = str(meta.get("title") or "").strip()
    if not title:
        # First markdown H1 becomes embed title via onboarding helper.
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
    if not title:
        title = "What's new" if locale == "en" else "Was neu ist"
    file_id = str(meta.get("id") or announcement_id).strip() or announcement_id
    # Prefer locale of the file we actually loaded.
    loaded_locale = locale
    if path.name.endswith(".en.md"):
        loaded_locale = "en"
    elif path.name.endswith(".de.md"):
        loaded_locale = "de"
    return AnnouncementSpec(
        announcement_id=file_id,
        title=title,
        body=body,
        locale=loaded_locale,
        path=path,
    )


def list_announcement_channel_ids() -> list[int]:
    """Registry channel ids for river + hosted-river (not archived, not shared)."""
    from mage import get_registry, reload_mage_registry

    reload_mage_registry()
    ids: list[int] = []
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("archived"):
            continue
        if entry.get("type") not in _ANNOUNCEMENT_CHANNEL_TYPES:
            continue
        try:
            ids.append(int(ch_id_str))
        except (ValueError, TypeError):
            continue
    return sorted(set(ids))


def locale_for_channel(channel_id: int) -> str:
    from hosted_river_onboarding import _practitioner_locale
    from mage import set_practice_context_for_channel

    set_practice_context_for_channel(channel_id)
    return _practitioner_locale(channel_id)


async def post_announcement(
    channel_id: int,
    announcement_id: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    client=None,
) -> tuple[str, int | None]:
    """Post one announcement to one channel.

    Returns ``(status, message_id)`` where status is ok | skip | fail | dry-run.
    When ``client`` is provided, reuse it; otherwise open a short-lived River client.
    """
    from hosted_river_onboarding import _markdown_to_embed
    from mage import set_practice_context_for_channel

    set_practice_context_for_channel(channel_id)
    if not force and is_posted(channel_id, announcement_id):
        return "skip", None

    locale = locale_for_channel(channel_id)
    spec = load_announcement(announcement_id, locale)
    if spec is None:
        print(f"Announcement {announcement_id!r} not found (locale={locale})")
        return "fail", None

    # Embed title from H1 in body; ensure body has H1 if front matter title differs.
    body_for_embed = spec.body
    if not any(line.startswith("# ") for line in body_for_embed.splitlines()):
        body_for_embed = f"# {spec.title}\n\n{body_for_embed}"

    if dry_run:
        print(
            f"dry-run: would post {announcement_id} → channel {channel_id} "
            f"(locale={spec.locale}, title={spec.title!r})"
        )
        return "dry-run", None

    import discord
    from river_handler import reconcile_river_bar_floor

    embed = _markdown_to_embed(body_for_embed, locale=spec.locale)
    owns_client = client is None
    if owns_client:
        token = os.environ.get("RIVER_BOT_TOKEN", "").strip()
        if not token:
            print("Error: RIVER_BOT_TOKEN not set")
            return "fail", None
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        await client.login(token)

    try:
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        msg = await channel.send(embed=embed, silent=True)
        mark_posted(channel_id, announcement_id, msg.id)
        try:
            await reconcile_river_bar_floor(channel, client)
        except Exception as exc:
            print(f"Bar reconcile after announcement failed: {type(exc).__name__}: {exc}")
        print(
            f"Posted {announcement_id} in "
            f"#{getattr(channel, 'name', channel_id)} ({msg.id})"
        )
        return "ok", msg.id
    except Exception as exc:
        print(f"Post failed for channel {channel_id}: {type(exc).__name__}: {exc}")
        return "fail", None
    finally:
        if owns_client and client is not None:
            await client.close()


async def fanout_announcement(
    announcement_id: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    channel_ids: list[int] | None = None,
) -> dict[str, list[int]]:
    """Post to many channels with one River client. Returns status → channel ids."""
    import discord

    targets = channel_ids if channel_ids is not None else list_announcement_channel_ids()
    results: dict[str, list[int]] = {"ok": [], "skip": [], "fail": [], "dry-run": []}

    if not targets:
        print("No river / hosted-river channels in registry")
        return results

    if dry_run:
        for ch_id in targets:
            status, _ = await post_announcement(
                ch_id, announcement_id, force=force, dry_run=True
            )
            results.setdefault(status, []).append(ch_id)
        return results

    token = os.environ.get("RIVER_BOT_TOKEN", "").strip()
    if not token:
        print("Error: RIVER_BOT_TOKEN not set")
        for ch_id in targets:
            results["fail"].append(ch_id)
        return results

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    await client.login(token)
    try:
        for ch_id in targets:
            status, _ = await post_announcement(
                ch_id,
                announcement_id,
                force=force,
                dry_run=False,
                client=client,
            )
            results.setdefault(status, []).append(ch_id)
    finally:
        await client.close()
    return results
