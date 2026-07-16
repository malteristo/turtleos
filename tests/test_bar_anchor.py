"""Tests for unified bar bottom-anchor helper + river floor debounce/hold."""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import bar_anchor


class TestEnsureChannelBars(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        bar_anchor.clear_river_bar_scheduler_state()

    async def test_thread_with_active_lifecycle_bar(self) -> None:
        thread = MagicMock()
        thread.id = 42
        thread.parent_id = 123
        client = MagicMock()

        with patch("eddy_lifecycle_bar.standing_lifecycle_bar_enabled", return_value=True):
            with patch("eddy_lifecycle_bar.is_lifecycle_bar_active", return_value=True):
                with patch("mage.river_bot_enabled", return_value=False):
                    with patch("eddy_lifecycle_bar.get_lifecycle_bar_client", return_value=client):
                        with patch(
                            "eddy_lifecycle_bar._ensure_eddy_lifecycle_bar_at_bottom_unlocked",
                            new_callable=AsyncMock,
                        ) as ensure_lifecycle:
                            await bar_anchor.ensure_channel_bars(thread)
                            ensure_lifecycle.assert_awaited_once_with(thread, client)

    async def test_thread_without_lifecycle_bar_is_noop(self) -> None:
        thread = MagicMock()
        thread.id = 42
        thread.parent_id = 123

        with patch("eddy_lifecycle_bar.is_lifecycle_bar_active", return_value=False):
            with patch(
                "eddy_lifecycle_bar._ensure_eddy_lifecycle_bar_at_bottom_unlocked",
                new_callable=AsyncMock,
            ) as ensure_lifecycle:
                await bar_anchor.ensure_channel_bars(thread)
                ensure_lifecycle.assert_not_called()

    async def test_river_channel_schedules_reconcile(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.parent_id = None
        client = MagicMock()

        with patch("mage.is_river_channel", return_value=True):
            with patch("river_handler._river_client_for_channel", return_value=client):
                with patch("bar_anchor.schedule_river_bar_reconcile") as schedule:
                    await bar_anchor.ensure_channel_bars(channel)
                    schedule.assert_called_once_with(channel, client)

    async def test_non_river_parent_is_noop(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.parent_id = None

        with patch("mage.is_river_channel", return_value=False):
            with patch("bar_anchor.schedule_river_bar_reconcile") as schedule:
                await bar_anchor.ensure_channel_bars(channel)
                schedule.assert_not_called()


class TestRiverBarHold(unittest.TestCase):
    def tearDown(self) -> None:
        bar_anchor.clear_river_bar_scheduler_state()

    def test_hold_and_release(self) -> None:
        bar_anchor.hold_river_bar(7)
        self.assertTrue(bar_anchor.is_river_bar_held(7))
        bar_anchor.release_river_bar(7)
        self.assertFalse(bar_anchor.is_river_bar_held(7))

    def test_hold_expires(self) -> None:
        bar_anchor.hold_river_bar(8)
        bar_anchor._bar_holds[8] = time.monotonic() - (bar_anchor._RIVER_BAR_HOLD_TTL_S + 1)
        self.assertFalse(bar_anchor.is_river_bar_held(8))


class TestScheduleReconcile(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        bar_anchor.clear_river_bar_scheduler_state()

    async def test_debounce_coalesces_to_one_reconcile(self) -> None:
        channel = MagicMock()
        channel.id = 55
        client = MagicMock()

        with patch("bar_anchor._RIVER_BAR_DEBOUNCE_S", 0.05), patch(
            "river_handler.reconcile_river_bar_floor", new_callable=AsyncMock
        ) as reconcile:
            bar_anchor.schedule_river_bar_reconcile(channel, client)
            bar_anchor.schedule_river_bar_reconcile(channel, client)
            await asyncio.sleep(0.12)
            reconcile.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
