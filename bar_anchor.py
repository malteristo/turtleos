"""Bottom-anchor bars — keep river and lifecycle bars last after timeline activity."""

from __future__ import annotations


def _is_eddy_thread(channel) -> bool:
    """True for Discord thread channels (eddies), not parent river surfaces."""
    return getattr(channel, "parent_id", None) is not None


async def channel_for_client(channel, client):
    """Return a channel object bound to `client` so sends use the correct bot identity."""
    if client is None:
        return channel
    resolved = client.get_channel(channel.id)
    if resolved is None:
        try:
            resolved = await client.fetch_channel(channel.id)
        except Exception:
            return channel
    return resolved


async def ensure_channel_bars(channel, client=None) -> None:
    """Repost standing bars after any message that extends the channel timeline.

    River parent channels: standing eddy bar (new eddy · flow menu).
    Live eddy threads: lifecycle bar (checkpoint · release · dissolve) when active.

    Idempotent when the bar is already last. Split-bot safe: uses River client for
    bar post/edit even when Turtle posted the preceding command or ops embed.
    """
    if _is_eddy_thread(channel):
        from eddy_lifecycle_bar import (
            ensure_eddy_lifecycle_bar_at_bottom,
            get_lifecycle_bar_client,
            is_lifecycle_bar_active,
        )

        if not is_lifecycle_bar_active(channel.id):
            return
        bar_client = client or get_lifecycle_bar_client(channel)
        if bar_client:
            await ensure_eddy_lifecycle_bar_at_bottom(channel, bar_client)
        return

    from mage import is_river_channel

    if not is_river_channel(channel):
        return

    from river_handler import _river_client_for_channel, ensure_bar_at_bottom

    bar_client = client or _river_client_for_channel(channel)
    if bar_client:
        await ensure_bar_at_bottom(channel, bar_client)
