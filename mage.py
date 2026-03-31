"""turtleOS mage registry — channel→mage resolution, practice directory context.

Loads mage_registry.yaml and provides context variable management
for multi-mage practice directory routing.
"""

import contextvars
import os

import discord

from state import client, get_channel, CHANNELS


# ─── Context Variables ───────────────────────────────────────────

_TOS_DIR_DEFAULT = os.path.expanduser("~/workshops/kermit")
_practice_dir_ctx = contextvars.ContextVar("practice_dir", default=_TOS_DIR_DEFAULT)
_mage_name_ctx = contextvars.ContextVar("mage_name", default="Kermit")
_mage_key_ctx = contextvars.ContextVar("mage_key", default="kermit")
_workshop_root_ctx = contextvars.ContextVar("workshop_root", default=None)


# ─── Registry Loading ────────────────────────────────────────────

def _load_mage_registry():
    """Load the mage registry from YAML config."""
    registry_path = os.path.expanduser("~/turtle-shell/mage_registry.yaml")
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


# ─── Resolution Functions ────────────────────────────────────────

def _resolve_practice_dir_for_channel(channel_id):
    """Resolve practice directory from channel ID via registry."""
    ch_str = str(channel_id)
    mage_name = _MAGE_REGISTRY.get("channels", {}).get(ch_str)
    if not mage_name:
        return _TOS_DIR_DEFAULT
    mage = _MAGE_REGISTRY.get("mages", {}).get(mage_name, {})
    if mage:
        return os.path.expanduser(mage.get("practice_dir", _TOS_DIR_DEFAULT))
    space = _MAGE_REGISTRY.get("spaces", {}).get(mage_name, {})
    if space:
        return os.path.expanduser(space.get("practice_dir", _TOS_DIR_DEFAULT))
    return _TOS_DIR_DEFAULT


def _resolve_mage_info_for_channel(channel_id):
    """Resolve mage name and key from channel ID via registry."""
    ch_str = str(channel_id)
    mage_key = _MAGE_REGISTRY.get("channels", {}).get(ch_str)
    if mage_key:
        mage = _MAGE_REGISTRY.get("mages", {}).get(mage_key, {})
        if mage:
            return mage.get("address", mage_key.capitalize()), mage_key
        space = _MAGE_REGISTRY.get("spaces", {}).get(mage_key, {})
        if space:
            return mage_key.capitalize(), mage_key
    return "Kermit", "kermit"


def _resolve_workshop_root_for_channel(channel_id):
    """Resolve workshop root from channel ID via registry."""
    ch_str = str(channel_id)
    mage_name = _MAGE_REGISTRY.get("channels", {}).get(ch_str)
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
    """Get the practice directory for the current context."""
    return _practice_dir_ctx.get()


def get_workshop_root():
    """Get the workshop root for the current context (read-only wider access).
    Returns None if no workshop_root is configured (falls back to practice_dir)."""
    return _workshop_root_ctx.get()


def set_practice_context(message):
    """Set the practice directory context for the current async task."""
    channel = message.channel
    ch_id = channel.parent_id if hasattr(channel, "parent_id") and channel.parent_id else channel.id
    pd = _resolve_practice_dir_for_channel(ch_id)
    _practice_dir_ctx.set(pd)
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
