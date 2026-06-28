"""Tests for runtime/adapters/lifecycle.py (S4)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLifecycleAdapters(unittest.IsolatedAsyncioTestCase):
    async def test_close_eddy_command_delegates_to_dissolve_eddy(self) -> None:
        from runtime.adapters.lifecycle import close_eddy

        with patch(
            "runtime.adapters.lifecycle.is_eddy_already_dissolved",
            return_value=False,
        ), patch(
            "sessions.dissolve_eddy",
            new_callable=AsyncMock,
            return_value=MagicMock(thread_name="test"),
        ) as dissolve:
            await close_eddy(
                9001,
                [{"role": "user", "content": "hi"}],
                source="command",
                discord_client=MagicMock(),
            )
        dissolve.assert_awaited_once()
        self.assertFalse(dissolve.await_args.kwargs.get("native_close"))

    async def test_close_eddy_skips_when_already_dissolved(self) -> None:
        from runtime.adapters.lifecycle import close_eddy

        dc = MagicMock()
        dc.get_channel.return_value = None
        dc.fetch_channel = AsyncMock(side_effect=Exception("missing"))
        with patch(
            "runtime.adapters.lifecycle.is_eddy_already_dissolved",
            return_value=True,
        ), patch("sessions.dissolve_eddy", new_callable=AsyncMock) as dissolve:
            result = await close_eddy(9001, [], source="admin", discord_client=dc)
        dissolve.assert_not_called()
        self.assertTrue(result.already_archived)


if __name__ == "__main__":
    unittest.main()
