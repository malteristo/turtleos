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

def _load_mage_registry():
    """Load the mage registry from YAML config."""
    registry_path = os.path.expanduser("~/turtleos/mage_registry.yaml")
    if not os.path.exists(registry_path):
        return {"channels": {}, "mages": {}, "spaces": {}}
    try:
        import yaml
        with open(registry_path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load mage registry: {e}")
        return {"channels": {}, "mages": {}, "spaces": {}}


_MAGE_REGISTRY = _load_mage_registry()


def reload_mage_registry():
    """Reload the mage registry from disk."""
    global _MAGE_REGISTRY
    _MAGE_REGISTRY = _load_mage_registry()


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
    """True when channel id is a parent river or hosted-river surface."""
    if str(ch_id) not in _MAGE_REGISTRY.get("channels", {}):
        dialogue = get_channel("dialogue")
        if not dialogue or ch_id != dialogue.id:
            return False
    ch_type = _get_channel_type(ch_id)
    if ch_type in ("river", "hosted-river"):
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
    return get_attunement_profile() == "native" and is_river_message(message)


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


def _get_channel_type(channel_id):
    """Get channel type (river, hosted-river, shared). Returns None for legacy format."""
    entry = _MAGE_REGISTRY.get("channels", {}).get(str(channel_id))
    if isinstance(entry, dict):
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


def set_practice_context(message):
    """Set the practice directory context for the current async task."""
    channel = message.channel
    ch_id = channel.parent_id if hasattr(channel, "parent_id") and channel.parent_id else channel.id
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
    pd = _resolve_practice_dir_for_channel(channel_id)
    _practice_dir_ctx.set(pd)
    _runtime_dir_ctx.set(_resolve_runtime_dir_for_channel(channel_id))
    mage_name, mage_key = _resolve_mage_info_for_channel(channel_id)
    _mage_name_ctx.set(mage_name)
    _mage_key_ctx.set(mage_key)
    wr = _resolve_workshop_root_for_channel(channel_id)
    _workshop_root_ctx.set(wr)
    return pd


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
