"""Founder key entry handling for MAGIC e.V. founding room.

A founder key is a self-chosen emoji that is bound to a Discord handle
only after the primary operator confirms the association. The key is
ceremonial and operational, not security authentication.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - turtleOS runtime has yaml via mage registry
    yaml = None

from mage import get_registry, get_pd


def _registry_path() -> Path:
    explicit = os.environ.get("FOUNDER_KEY_REGISTRY")
    if explicit:
        return Path(explicit).expanduser()
    return Path(get_pd()) / "state" / "magic_ev" / "founding_key_registry.yaml"

_PENDING: dict[int, dict] = {}
_CONFIRM_RE = re.compile(
    r"^(?:yes[, ]+)?(?:bind(?:\s+it|\s+\S+)?\s+to|this\s+is)\s+(?P<name>.+?)[.!]?$",
    re.IGNORECASE,
)


def _load_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        return {"founders": {}, "bindings": []}
    try:
        text = path.read_text()
        if yaml:
            return yaml.safe_load(text) or {"founders": {}, "bindings": []}
    except Exception as e:
        print(f"Founder key registry load failed: {e}")
    return {"founders": {}, "bindings": []}


def _save_registry(data: dict) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml:
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    else:
        import json
        text = json.dumps(data, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _channel_entry(channel_id: int) -> dict | str | None:
    return get_registry().get("channels", {}).get(str(channel_id))


def _is_founding_channel(message) -> bool:
    channel = message.channel
    ids = os.environ.get("MAGIC_EV_FOUNDING_CHANNEL_ID") or os.environ.get("FOUNDER_KEY_CHANNEL_IDS", "")
    configured_ids = {x.strip() for x in ids.split(",") if x.strip()}
    if str(channel.id) in configured_ids:
        return True
    parent_id = getattr(channel, "parent_id", None)
    if parent_id and str(parent_id) in configured_ids:
        return True

    entry = _channel_entry(channel.id) or (parent_id and _channel_entry(parent_id))
    if isinstance(entry, dict):
        context = str(entry.get("default_context") or "").lower()
        ch_type = str(entry.get("type") or "").lower()
        if context in {"magic_ev_founding", "founding", "founders"}:
            return True
        if ch_type in {"founding", "founders", "magic_ev_founding"}:
            return True

    name = getattr(channel, "name", "") or ""
    parent = getattr(channel, "parent", None)
    parent_name = getattr(parent, "name", "") if parent else ""
    combined = f"{name} {parent_name}".lower().replace("_", "-")
    return "found" in combined and ("magic" in combined or "ev" in combined)


def _primary_mage_ids() -> set[int]:
    ids: set[int] = set()
    registry = get_registry()
    default_mage = registry.get("default_mage")
    for key, mage in registry.get("mages", {}).items():
        if key == default_mage or mage.get("primary"):
            raw = mage.get("discord_id")
            if raw:
                try:
                    ids.add(int(raw))
                except ValueError:
                    pass
    return ids


def _is_primary_operator(message) -> bool:
    ids = _primary_mage_ids()
    return bool(ids) and message.author.id in ids


def _looks_like_single_key(text: str) -> bool:
    text = text.strip()
    if not text or text.startswith("!") or " " in text or "\n" in text:
        return False
    if text.startswith("<@") or text.startswith("http"):
        return False
    # Emoji can be multi-codepoint. Keep this intentionally permissive but short.
    return len(text) <= 16 and any(ord(ch) > 127 for ch in text)


def _find_binding_for_user(data: dict, user_id: int) -> tuple[str, dict] | tuple[None, None]:
    for name, record in (data.get("founders") or {}).items():
        if str(record.get("discord_id") or "") == str(user_id):
            return name, record
    return None, None


def _find_binding_for_key(data: dict, key: str) -> tuple[str, dict] | tuple[None, None]:
    for name, record in (data.get("founders") or {}).items():
        if (record.get("key") or "") == key:
            return name, record
    return None, None


def _normalize_founder_key(name: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", name.strip().lower())
    clean = re.sub(r"[\s-]+", "_", clean).strip("_")
    return clean or "founder"


def _display_author(message) -> str:
    return getattr(message.author, "global_name", None) or getattr(message.author, "display_name", None) or str(message.author)


async def try_founder_key_entry(message) -> bool:
    """Handle founder key claims/confirmations. Returns True when consumed."""
    if not _is_founding_channel(message):
        return False

    text = (message.content or "").strip()
    channel_id = message.channel.id

    if _is_primary_operator(message):
        pending = _PENDING.get(channel_id)
        match = _CONFIRM_RE.match(text)
        if pending and match:
            display_name = match.group("name").strip().strip("`*_ ")
            founder_key = _normalize_founder_key(display_name)
            data = _load_registry()
            data.setdefault("founders", {})
            data.setdefault("bindings", [])
            now = datetime.now(timezone.utc).isoformat()
            record = data["founders"].get(founder_key, {})
            record.update({
                "display_name": display_name,
                "key": pending["key"],
                "discord_id": str(pending["discord_id"]),
                "discord_handle": pending["discord_handle"],
                "binding_status": "confirmed",
                "confirmed_by": "primary_operator",
                "confirmed_at": now,
            })
            data["founders"][founder_key] = record
            data["bindings"].append({
                "founder": founder_key,
                "display_name": display_name,
                "key": pending["key"],
                "discord_id": str(pending["discord_id"]),
                "discord_handle": pending["discord_handle"],
                "confirmed_by": "primary_operator",
                "confirmed_at": now,
                "channel_id": str(channel_id),
            })
            _save_registry(data)
            _PENDING.pop(channel_id, None)
            await message.channel.send(
                f"Bound. Welcome, {display_name}. {pending['key']} is now your key in this founding room.\n\n"
                "This room is for the founding circle around MAGIC e.V. Questions are useful here, "
                "including skeptical ones. I can explain the practice, turtleOS, and the current founding "
                "process as I understand them. If something needs the primary operator's own perspective or legal confirmation, "
                "I will say so rather than guessing."
            )
            return True
        return False

    if not _looks_like_single_key(text):
        return False

    data = _load_registry()
    existing_name, existing_record = _find_binding_for_user(data, message.author.id)
    if existing_record:
        current_key = existing_record.get("key") or "your current key"
        await message.channel.send(
            f"I already have {current_key} as your key here.\n\n"
            "If you want to change it, the primary operator can confirm the change."
        )
        return True

    key_name, key_record = _find_binding_for_key(data, text)
    if key_record:
        await message.channel.send(
            "That key is already bound in this room.\n\n"
            "Primary operator, please confirm whether this is a key change, a mistake, or a different person."
        )
        return True

    _PENDING[channel_id] = {
        "key": text,
        "discord_id": message.author.id,
        "discord_handle": str(message.author),
        "display_name": _display_author(message),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    await message.channel.send(
        f"I see your key: {text}.\n\n"
        "Primary operator, who should I bind this Discord handle to?"
    )
    return True
