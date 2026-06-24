"""Tests for River → Turtle eddy handoff without remove/re-add noise."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
discord = sys.modules["discord"]
discord.Object = lambda id: {"id": id}
discord.HTTPException = type("HTTPException", (Exception,), {})


class RiverAddTurtleTests(unittest.IsolatedAsyncioTestCase):
    async def test_skips_remove_when_turtle_already_member(self) -> None:
        from eddy_spawn import river_add_turtle_to_eddy

        thread = MagicMock()
        thread.id = 123
        thread.name = "test-eddy"
        thread.fetch_member = AsyncMock(return_value=MagicMock())
        thread.remove_user = AsyncMock()
        thread.add_user = AsyncMock()

        with patch("mage.river_bot_enabled", return_value=True), patch(
            "eddy_spawn._resolve_turtle_bot_user_id", return_value=999
        ), patch("river_state.river_client", MagicMock()):
            ok = await river_add_turtle_to_eddy(thread)

        self.assertTrue(ok)
        thread.remove_user.assert_not_awaited()
        thread.add_user.assert_not_awaited()

    async def test_adds_turtle_when_not_member(self) -> None:
        from eddy_spawn import river_add_turtle_to_eddy

        thread = MagicMock()
        thread.id = 123
        thread.name = "test-eddy"
        thread.fetch_member = AsyncMock(side_effect=discord.HTTPException())
        thread.add_user = AsyncMock()

        with patch("mage.river_bot_enabled", return_value=True), patch(
            "eddy_spawn._resolve_turtle_bot_user_id", return_value=999
        ), patch("river_state.river_client", MagicMock()):
            ok = await river_add_turtle_to_eddy(thread)

        self.assertTrue(ok)
        thread.add_user.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
