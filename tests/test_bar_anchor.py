"""Tests for unified bar bottom-anchor helper."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import bar_anchor


class TestEnsureChannelBars(unittest.IsolatedAsyncioTestCase):
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

    async def test_river_channel_calls_river_bar(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.parent_id = None
        client = MagicMock()

        with patch("mage.is_river_channel", return_value=True):
            with patch("river_handler._river_client_for_channel", return_value=client):
                with patch(
                    "river_handler.ensure_bar_at_bottom",
                    new_callable=AsyncMock,
                ) as ensure_river:
                    await bar_anchor.ensure_channel_bars(channel)
                    ensure_river.assert_awaited_once_with(channel, client)

    async def test_non_river_parent_is_noop(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.parent_id = None

        with patch("mage.is_river_channel", return_value=False):
            with patch(
                "river_handler.ensure_bar_at_bottom",
                new_callable=AsyncMock,
            ) as ensure_river:
                await bar_anchor.ensure_channel_bars(channel)
                ensure_river.assert_not_called()


if __name__ == "__main__":
    unittest.main()
