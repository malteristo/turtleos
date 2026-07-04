"""turtleOS mage registry — channel→mage resolution, practice directory context.

Loads mage_registry.yaml and provides context variable management
for multi-mage practice directory routing.
"""

import contextvars
import os

import discord

from state import client, get_channel, CHANNELS


# ─── Context Variables ───────────────────────────────────────────

RUNTIME_DIR_DEFAULT = os.path.expanduser("~/workshops/default")
_practice_dir_ctx = contextvars.ContextVar("practice_dir", default=None)
_runtime_dir_ctx = contextvars.ContextVar("runtime_dir", default=None)
_mage_name_ctx = contextvars.ContextVar("mage_name", default="Practitioner")
_mage_key_ctx = contextvars.ContextVar("mage_key", default="default")
_workshop_root_ctx = contextvars.ContextVar("workshop_root", default=None)


# ─── Registry Loading ────────────────────────────────────────────

REGISTRY_PATH = os.path.expanduser("~/turtleos/mage_registry.yaml")
_registry_mtime: float | None = None


def _registry_file_mtime() -> float | None:
    try:
        return os.path.getmtime(REGISTRY_PATH)
    except OSError:
        return None


def _load_mage_registry():
    """Load the mage registry from YAML config."""
    if not os.path.exists(REGISTRY_PATH):
        return {"channels": {}, "mages": {}, "spaces": {}}
    try:
        import yaml
        with open(REGISTRY_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load mage registry: {e}")
        return {"channels": {}, "mages": {}, "spaces": {}}


_MAGE_REGISTRY = _load_mage_registry()
_registry_mtime = _registry_file_mtime()


def reload_mage_registry():
    """Reload the mage registry from disk."""
    global _MAGE_REGISTRY, _registry_mtime
    _MAGE_REGISTRY = _load_mage_registry()
    _registry_mtime = _registry_file_mtime()


def maybe_reload_mage_registry() -> bool:
    """Reload registry when mage_registry.yaml changed on disk (split-bot safe).

    River bot reloads on claim; Turtle bot must observe the same file without restart.
    Returns True when a reload occurred.
    """
    current = _registry_file_mtime()
    if current is None:
        if _registry_mtime is not None:
            reload_mage_registry()
            return True
        return False
    if _registry_mtime is None or current != _registry_mtime:
        reload_mage_registry()
        return True
    return False


def get_registry():
    """Get the current mage registry dict."""
    return _MAGE_REGISTRY


def get_attunement_profile() -> str:
    """Return global attunement profile: native (vanilla platform law) or magic (legacy)."""
    profile = (_MAGE_REGISTRY.get("attunement") or "magic").strip().lower()
    if profile not in ("native", "magic"):
        return "magic"
    return profile


def get_channel_attunement(channel_id) -> str | None:
    """Per-channel attunement override from mage_registry (native, magic, craft)."""
    entry = _MAGE_REGISTRY.get("channels", {}).get(str(channel_id))
    if isinstance(entry, dict):
        att = entry.get("attunement")
        if att:
            normalized = att.strip().lower()
            if normalized in ("native", "magic", "craft"):
                return normalized
    return None


def resolve_dialogue_channel_id(message_or_channel_id) -> int:
    """Parent channel id for threads; channel id for parent channels."""
    if hasattr(message_or_channel_id, "channel"):
        channel = message_or_channel_id.channel
    else:
        channel = message_or_channel_id
    if hasattr(channel, "parent_id") and channel.parent_id:
        return channel.parent_id
    return channel.id


def get_effective_attunement(channel_id) -> str:
    """Effective attunement for a channel: per-channel override, craft type, or global."""
    ch_att = get_channel_attunement(channel_id)
    if ch_att:
        return ch_att
    if _get_channel_type(channel_id) == "craft":
        return "craft"
    return get_attunement_profile()


def uses_craft_surface(channel_id) -> bool:
    """True when channel should use Craft Turtle vocation (semi-attuned builder mode)."""
    return get_effective_attunement(channel_id) == "craft"


def uses_native_eddy(channel_id) -> bool:
    """True when eddies in this channel use vanilla native Turtle prompts."""
    return get_effective_attunement(channel_id) == "native"


def _channel_is_river(ch_id: int) -> bool:
    """True when channel id is a parent river, hosted-river, or shared-river surface."""
    if is_channel_archived(ch_id):
        return False
    if str(ch_id) not in _MAGE_REGISTRY.get("channels", {}):
        dialogue = get_channel("dialogue")
        if not dialogue or ch_id != dialogue.id:
            return False
    ch_type = _get_channel_type(ch_id)
    if ch_type in ("river", "hosted-river", "shared-river"):
        return True
    if ch_type is None and get_attunement_profile() == "native":
        return True
    return False


def is_river_channel(channel) -> bool:
    """True for parent river / hosted-river channels (not eddy threads)."""
    if isinstance(channel, discord.Thread):
        return False
    return _channel_is_river(channel.id)


def is_river_message(message) -> bool:
    """True when message is in the main river channel (not an eddy/thread)."""
    if isinstance(message.channel, discord.Thread):
        return False
    return _channel_is_river(message.channel.id)


def uses_native_river(message) -> bool:
    """True when this message should use the River act harness (not Turtle dialogue)."""
    if not is_river_message(message):
        return False
    if _get_channel_type(message.channel.id) == "shared-river":
        return True
    return get_attunement_profile() == "native"


def river_bot_enabled() -> bool:
    """True when a separate River bot token is configured (two-bot native mode)."""
    from river_state import river_bot_configured

    return river_bot_configured()


def turtle_handles_native_river(message) -> bool:
    """True when Turtle (single-bot fallback) should run the River harness."""
    return uses_native_river(message) and not river_bot_enabled()


def suppress_turtle_river_voice() -> bool:
    """True when Turtle must not post proactive voice in the parent river channel."""
    return get_attunement_profile() == "native"


def _get_channel_mage(channel_id):
    """Extract mage key from channel entry (supports both string and dict formats)."""
    entry = _MAGE_REGISTRY.get("channels", {}).get(str(channel_id))
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry.get("mage")
    return entry


def _get_channel_entry(channel_id) -> dict | None:
    entry = _MAGE_REGISTRY.get("channels", {}).get(str(channel_id))
    return entry if isinstance(entry, dict) else None


def is_channel_archived(channel_id) -> bool:
    entry = _get_channel_entry(channel_id)
    return bool(entry and entry.get("archived"))


def _get_channel_type(channel_id):
    """Get channel type (river, hosted-river, shared-river, shared). Returns None for legacy format."""
    entry = _get_channel_entry(channel_id)
    if entry:
        return entry.get("type")
    return None


def get_channel_default_context(channel_id):
    """Get the default practice context for a channel. Returns None if no default."""
    entry = _MAGE_REGISTRY.get("channels", {}).get(str(channel_id))
    if isinstance(entry, dict):
        return entry.get("default_context")
    return None


# ─── Resolution Functions ────────────────────────────────────────

def _primary_mage_key():
    """Return the mage key used for context-free/background tasks."""
    configured = _MAGE_REGISTRY.get("default_mage")
    if configured:
        return configured
    for key, mage in _MAGE_REGISTRY.get("mages", {}).items():
        if mage.get("primary"):
            return key
    mages = _MAGE_REGISTRY.get("mages", {})
    return next(iter(mages), None)


def _default_runtime_dir_for_key(key):
    return os.path.expanduser(f"~/workshops/{key}") if key else RUNTIME_DIR_DEFAULT


def _resolve_primary_practice_dir():
    key = _primary_mage_key()
    mage = _MAGE_REGISTRY.get("mages", {}).get(key, {}) if key else {}
    return os.path.expanduser(mage.get("practice_dir") or _default_runtime_dir_for_key(key))


def _resolve_primary_runtime_dir():
    key = _primary_mage_key()
    mage = _MAGE_REGISTRY.get("mages", {}).get(key, {}) if key else {}
    return os.path.expanduser(mage.get("runtime_dir") or _default_runtime_dir_for_key(key))


def _resolve_primary_workshop_root():
    key = _primary_mage_key()
    mage = _MAGE_REGISTRY.get("mages", {}).get(key, {}) if key else {}
    root = mage.get("workshop_root")
    return os.path.expanduser(root) if root else None


def _resolve_practice_dir_for_channel(channel_id):
    """Resolve canonical writable practice directory from channel ID via registry."""
    mage_name = _get_channel_mage(channel_id)
    if not mage_name:
        return _resolve_primary_practice_dir()
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_name, {})
    if mage:
        return os.path.expanduser(mage.get("practice_dir") or _default_runtime_dir_for_key(mage_name))
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_name, {})
    if space:
        return os.path.expanduser(space.get("practice_dir") or _default_runtime_dir_for_key(mage_name))
    return _resolve_primary_practice_dir()


def _resolve_runtime_dir_for_channel(channel_id):
    """Resolve Turtle-local operational state directory from channel ID via registry."""
    mage_name = _get_channel_mage(channel_id)
    if not mage_name:
        return _resolve_primary_runtime_dir()
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_name, {})
    if mage:
        return os.path.expanduser(mage.get("runtime_dir") or _default_runtime_dir_for_key(mage_name))
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_name, {})
    if space:
        return os.path.expanduser(space.get("runtime_dir") or _default_runtime_dir_for_key(mage_name))
    return _resolve_primary_runtime_dir()


def _resolve_mage_info_for_channel(channel_id):
    """Resolve mage name and key from channel ID via registry."""
    ch_str = str(channel_id)
    mage_key = _get_channel_mage(channel_id)
    if mage_key:
        mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key, {})
        if mage:
            return mage.get("address", mage_key.capitalize()), mage_key
        space = _MAGE_REGISTRY.get("spaces", {}).get(mage_key, {})
        if space:
            return mage_key.capitalize(), mage_key
    key = _primary_mage_key() or "default"
    mage = _MAGE_REGISTRY.get("mages", {}).get(key, {})
    return mage.get("address", key.capitalize()), key


def _resolve_workshop_root_for_channel(channel_id):
    """Resolve workshop root from channel ID via registry."""
    ch_str = str(channel_id)
    mage_name = _get_channel_mage(channel_id)
    if not mage_name:
        return None
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_name, {})
    if mage and mage.get("workshop_root"):
        return os.path.expanduser(mage["workshop_root"])
    return None


def _resolve_mage_from_author(author):
    """Resolve a Discord message author to their mage key and personal practice dir.
    Returns (mage_key, personal_practice_dir) or (None, None) if not a registered mage."""
    author_id = str(author.id)
    for mk, minfo in _MAGE_REGISTRY.get("mages", {}).items():
        if minfo.get("discord_id") == author_id:
            pd = os.path.expanduser(minfo.get("practice_dir", ""))
            return mk, pd
    return None, None


# ─── Context Management ─────────────────────────────────────────

def get_mage_name():
    return _mage_name_ctx.get()


def get_mage_key():
    return _mage_key_ctx.get()


def get_mage_type():
    """Return the type ('mage' or 'practitioner') for the current channel's mage."""
    mage_key = _mage_key_ctx.get()
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key, {})
    return mage.get("type", "mage")


def get_mage_address():
    """Return the display name (address) for the current channel's mage."""
    mage_key = _mage_key_ctx.get()
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key, {})
    return mage.get("address", mage_key.capitalize() if mage_key else "Mage")


def get_pd():
    """Get the canonical practice directory for the current context."""
    return _practice_dir_ctx.get() or _resolve_primary_practice_dir()


def get_runtime_dir():
    """Get Turtle-local operational state directory for the current context."""
    return _runtime_dir_ctx.get() or _resolve_primary_runtime_dir()


def list_registered_runtime_dirs() -> list[str]:
    """Unique runtime roots from registry — for cross-space background polling."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(path: str | None) -> None:
        if not path:
            return
        expanded = os.path.expanduser(path)
        if expanded in seen:
            return
        seen.add(expanded)
        out.append(expanded)

    _add(_resolve_primary_runtime_dir())
    for entry in (_MAGE_REGISTRY.get("mages") or {}).values():
        if isinstance(entry, dict):
            _add(entry.get("runtime_dir"))
    for entry in (_MAGE_REGISTRY.get("spaces") or {}).values():
        if isinstance(entry, dict):
            _add(entry.get("runtime_dir"))
    return out


def get_topology():
    """Return current topology paths for diagnostics and drift checks."""
    return {
        "mage_key": get_mage_key(),
        "practice_dir": get_pd(),
        "workshop_root": get_workshop_root(),
        "runtime_dir": get_runtime_dir(),
    }


def get_workshop_root():
    """Get the workshop root for the current context (read-only wider access).
    Returns None if no workshop_root is configured."""
    return _workshop_root_ctx.get() or _resolve_primary_workshop_root()


def _parent_id_from_thread_state(thread_id: int) -> int | None:
    """Resolve parent river channel from eddy thread state on disk."""
    import json
    from pathlib import Path

    tid = str(thread_id)
    for runtime_dir in list_registered_runtime_dirs():
        base = Path(runtime_dir) / "thread-state"
        for subdir, key in (
            ("flow-bootstrap", "parent_id"),
            ("awaiting-title", "parent_channel_id"),
        ):
            path = base / subdir / f"{tid}.json"
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                parent = data.get(key)
                if parent:
                    return int(parent)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    for ch_id_str in _MAGE_REGISTRY.get("channels", {}):
        try:
            parent_id = int(ch_id_str)
        except ValueError:
            continue
        runtime_dir = _resolve_runtime_dir_for_channel(parent_id)
        for subdir in ("awaiting-title", "pending"):
            path = Path(runtime_dir) / "thread-state" / subdir / f"{tid}.json"
            if not path.is_file():
                continue
            if subdir == "awaiting-title":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    parent = data.get("parent_channel_id")
                    if parent:
                        return int(parent)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            return parent_id

    return None


def resolve_registry_channel_id(channel_id) -> int:
    """Parent channel for eddy threads; same id for registered parent channels."""
    ch_id = int(channel_id)
    if is_registered_parent_channel(ch_id):
        return ch_id
    parent = _parent_id_from_thread_state(ch_id)
    if parent and is_registered_parent_channel(parent):
        return parent
    return ch_id


def set_practice_context(message):
    """Set the practice directory context for the current async task."""
    channel = message.channel
    ch_id = resolve_registry_channel_id(
        channel.parent_id if hasattr(channel, "parent_id") and channel.parent_id else channel.id
    )
    pd = _resolve_practice_dir_for_channel(ch_id)
    _practice_dir_ctx.set(pd)
    _runtime_dir_ctx.set(_resolve_runtime_dir_for_channel(ch_id))
    mage_name, mage_key = _resolve_mage_info_for_channel(ch_id)
    _mage_name_ctx.set(mage_name)
    _mage_key_ctx.set(mage_key)
    wr = _resolve_workshop_root_for_channel(ch_id)
    _workshop_root_ctx.set(wr)
    return pd


def set_practice_context_for_channel(channel_id):
    """Set full practice context from a raw channel ID (for thread creation, session close, etc.)."""
    registry_id = resolve_registry_channel_id(channel_id)
    pd = _resolve_practice_dir_for_channel(registry_id)
    _practice_dir_ctx.set(pd)
    _runtime_dir_ctx.set(_resolve_runtime_dir_for_channel(registry_id))
    mage_name, mage_key = _resolve_mage_info_for_channel(registry_id)
    _mage_name_ctx.set(mage_name)
    _mage_key_ctx.set(mage_key)
    wr = _resolve_workshop_root_for_channel(registry_id)
    _workshop_root_ctx.set(wr)
    return pd


def set_practice_context_for_mage_key(mage_key: str) -> bool:
    """Set practice context from a registry mage/space key (no Discord channel).

    Used by allowlisted HTTP artifact reads where the URL carries the mage key.
    """
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key)
    if mage:
        pd = os.path.expanduser(mage.get("practice_dir") or _default_runtime_dir_for_key(mage_key))
        rd = os.path.expanduser(mage.get("runtime_dir") or _default_runtime_dir_for_key(mage_key))
        wr = mage.get("workshop_root")
        _practice_dir_ctx.set(pd)
        _runtime_dir_ctx.set(rd)
        _mage_name_ctx.set(mage.get("address", mage_key.capitalize()))
        _mage_key_ctx.set(mage_key)
        _workshop_root_ctx.set(os.path.expanduser(wr) if wr else None)
        return True
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_key)
    if space:
        pd = os.path.expanduser(space.get("practice_dir") or _default_runtime_dir_for_key(mage_key))
        rd = os.path.expanduser(space.get("runtime_dir") or _default_runtime_dir_for_key(mage_key))
        _practice_dir_ctx.set(pd)
        _runtime_dir_ctx.set(rd)
        _mage_name_ctx.set(mage_key.capitalize())
        _mage_key_ctx.set(mage_key)
        _workshop_root_ctx.set(None)
        return True
    return False


# ─── Channel Checks ─────────────────────────────────────────────

def is_practice_channel(message):
    """Check if message is from a registered practice channel (direct or thread)."""
    channel = message.channel
    ch_id = channel.id
    parent_id = channel.parent_id if isinstance(channel, discord.Thread) else None

    registry_channels = set(_MAGE_REGISTRY.get("channels", {}).keys())
    if str(ch_id) in registry_channels:
        return True
    if parent_id and str(parent_id) in registry_channels:
        return True

    dialogue = get_channel("dialogue")
    if dialogue:
        if ch_id == dialogue.id:
            return True
        if parent_id and parent_id == dialogue.id:
            return True
    return False


def is_registered_parent_channel(channel_id):
    """Check if a channel ID is registered in the mage registry."""
    registry_channels = set(_MAGE_REGISTRY.get("channels", {}).keys())
    if str(channel_id) in registry_channels:
        return True
    dialogue = get_channel("dialogue")
    return dialogue and channel_id == dialogue.id


def get_thread_member_ids(channel_id):
    """Return list of discord_id strings for practitioners who should be auto-added to threads in this channel.
    For mage/practitioner channels: returns that user's discord_id.
    For space channels (e.g. family): returns discord_ids of all space members."""
    ch_str = str(channel_id)
    mage_key = _get_channel_mage(channel_id)
    if not mage_key:
        return []

    # Check if it maps to a space (e.g. family)
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_key, {})
    if space:
        member_ids = []
        for member_key in space.get("members", []):
            mage = _MAGE_REGISTRY.get("mages", {}).get(member_key, {})
            if mage.get("discord_id"):
                member_ids.append(mage["discord_id"])
        return member_ids

    # Direct mage channel
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key, {})
    if mage.get("discord_id"):
        return [mage["discord_id"]]
    return []


def _shared_river_member_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        create_public_threads=True,
        send_messages_in_threads=True,
    )


async def ensure_space_channel_access(channel, guild=None) -> bool:
    """Grant registry space members access to a shared-river parent channel."""
    ch_type = _get_channel_type(channel.id)
    if ch_type != "shared-river":
        return False

    mage_key = _get_channel_mage(channel.id)
    if not mage_key:
        return False
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_key, {})
    if not space:
        return False

    guild = guild or getattr(channel, "guild", None)
    if guild is None:
        return False

    overwrites = dict(channel.overwrites)
    changed = False
    perms = _shared_river_member_overwrite()

    for member_key in space.get("members", []):
        mage = _MAGE_REGISTRY.get("mages", {}).get(member_key, {})
        raw_id = mage.get("discord_id")
        if not raw_id:
            continue
        try:
            uid = int(raw_id)
        except (TypeError, ValueError):
            continue

        member = guild.get_member(uid)
        if member is None:
            try:
                member = await guild.fetch_member(uid)
            except discord.HTTPException:
                print(
                    f"ensure_space_channel_access: member {member_key} ({uid}) not in guild"
                )
                continue

        existing = overwrites.get(member)
        if existing is not None and existing.view_channel is not False:
            continue

        overwrites[member] = perms
        changed = True

    if not changed:
        return False

    try:
        await channel.edit(overwrites=overwrites)
        print(f"ensure_space_channel_access: granted access on channel {channel.id}")
        return True
    except discord.HTTPException as exc:
        print(f"ensure_space_channel_access failed: {exc}")
        return False


async def sync_shared_river_channel_access(client) -> None:
    """On startup: align Discord overwrites with registry space members."""
    for ch_id_str, entry in _MAGE_REGISTRY.get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "shared-river":
            continue
        if entry.get("archived"):
            continue
        try:
            ch_id = int(ch_id_str)
        except (TypeError, ValueError):
            continue
        channel = client.get_channel(ch_id)
        if channel is None:
            continue
        await ensure_space_channel_access(channel)
