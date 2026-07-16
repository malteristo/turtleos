"""Bottom-anchor bars — reconciled river floor + eddy standing chrome.

River parent channels use a **reconciled floor**: activity schedules a debounced
reconcile (scan orphans → one bar last). Multi-step acts can **hold** reconcile
until the sequence ends. See docs/chapters/design-river-bar-floor.md.

Eddy threads: contextual act rows stay timeline-anchored; standing lifecycle bar
(when active) still uses ensure-at-bottom.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

RIVER_OFFER_EMBED_COLOR = 0x5865F2

# Quiet window before reconcile after timeline activity.
_RIVER_BAR_DEBOUNCE_S = 1.5
# Hold expires so a abandoned browse cannot pin the floor forever.
_RIVER_BAR_HOLD_TTL_S = 300.0

_bar_holds: dict[int, float] = {}
_pending_reconcile: dict[int, asyncio.Task] = {}
_pending_clients: dict[int, Any] = {}


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


def hold_river_bar(channel_id: int) -> None:
    """Pause river-floor reconcile for a multi-step act (e.g. artifacts browse)."""
    _bar_holds[int(channel_id)] = time.monotonic()


def release_river_bar(channel_id: int) -> None:
    """Clear hold so the next reconcile / schedule can settle the floor."""
    _bar_holds.pop(int(channel_id), None)


def is_river_bar_held(channel_id: int) -> bool:
    """True when reconcile should no-op for this channel."""
    started = _bar_holds.get(int(channel_id))
    if started is None:
        return False
    if time.monotonic() - started > _RIVER_BAR_HOLD_TTL_S:
        _bar_holds.pop(int(channel_id), None)
        return False
    return True


def clear_river_bar_scheduler_state() -> None:
    """Test helper — cancel pending debounces and clear holds."""
    for task in list(_pending_reconcile.values()):
        task.cancel()
    _pending_reconcile.clear()
    _pending_clients.clear()
    _bar_holds.clear()


async def ensure_channel_bars(channel, client=None) -> None:
    """After timeline activity: schedule river reconcile or ensure eddy bars."""
    from state import get_channel_lock

    lock = get_channel_lock(channel.id)
    async with lock:
        await _ensure_channel_bars_unlocked(channel, client)


async def _ensure_channel_bars_unlocked(channel, client=None) -> None:
    """River: schedule debounced reconcile. Eddy: lifecycle bar ensure when active."""
    if _is_eddy_thread(channel):
        from eddy_lifecycle_bar import (
            _ensure_eddy_lifecycle_bar_at_bottom_unlocked,
            get_lifecycle_bar_client,
            is_lifecycle_bar_active,
            standing_lifecycle_bar_enabled,
        )

        if not standing_lifecycle_bar_enabled() or not is_lifecycle_bar_active(channel.id):
            return
        from mage import river_bot_enabled

        if river_bot_enabled():
            bar_client = get_lifecycle_bar_client(channel)
            if not bar_client:
                return
            await _ensure_eddy_lifecycle_bar_at_bottom_unlocked(channel, bar_client)
            return
        bar_client = client or get_lifecycle_bar_client(channel)
        if bar_client:
            await _ensure_eddy_lifecycle_bar_at_bottom_unlocked(channel, bar_client)
        return

    from mage import is_river_channel

    if not is_river_channel(channel):
        return

    from river_handler import _river_client_for_channel

    bar_client = client or _river_client_for_channel(channel)
    if bar_client:
        schedule_river_bar_reconcile(channel, bar_client)


def schedule_river_bar_reconcile(channel, client) -> None:
    """Coalesce activity into one reconcile after a quiet window."""
    channel_id = int(channel.id)
    _pending_clients[channel_id] = (channel, client)
    existing = _pending_reconcile.get(channel_id)
    if existing and not existing.done():
        existing.cancel()

    async def _run() -> None:
        try:
            await asyncio.sleep(_RIVER_BAR_DEBOUNCE_S)
        except asyncio.CancelledError:
            return
        pair = _pending_clients.pop(channel_id, None)
        _pending_reconcile.pop(channel_id, None)
        if not pair:
            return
        ch, cl = pair
        from river_handler import reconcile_river_bar_floor

        await reconcile_river_bar_floor(ch, cl)

    _pending_reconcile[channel_id] = asyncio.create_task(_run())


async def reconcile_river_bar_now(channel, client) -> None:
    """Immediate floor reconcile (ready, safety sweep, hold release)."""
    from river_handler import reconcile_river_bar_floor

    await reconcile_river_bar_floor(channel, client)


async def release_river_bar_and_settle(channel, client=None) -> None:
    """End multi-step hold and schedule a floor settle."""
    release_river_bar(channel.id)
    from mage import is_river_channel
    from river_handler import _river_client_for_channel

    if not is_river_channel(channel) and getattr(channel, "parent_id", None) is None:
        return
    # Artifacts browse runs in the parent river channel.
    bar_client = client or _river_client_for_channel(channel)
    if bar_client:
        schedule_river_bar_reconcile(channel, bar_client)
