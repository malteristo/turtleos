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

    async def test_a_magic_room_records_the_spirit_join_and_a_present_spirit_is_quiet(self) -> None:
        import tempfile
        from pathlib import Path

        from eddy_spawn import river_add_spirit_to_eddy

        practice = Path(tempfile.mkdtemp())
        primitive = MagicMock()
        primitive.name = "magic"

        fresh = MagicMock()
        fresh.id = 123
        fresh.parent_id = 1
        fresh.name = "5"
        fresh.fetch_member = AsyncMock(side_effect=discord.HTTPException())
        fresh.add_user = AsyncMock()

        present = MagicMock()
        present.id = 124
        present.parent_id = 1
        present.fetch_member = AsyncMock(return_value=MagicMock())
        present.add_user = AsyncMock()

        with patch("mage.get_channel_primitive", return_value=primitive), patch(
            "mage.get_pd", return_value=str(practice)
        ):
            self.assertTrue(await river_add_spirit_to_eddy(fresh))
            self.assertTrue(await river_add_spirit_to_eddy(present))

        recorded = (practice / "state/sessions/123.jsonl").read_text(encoding="utf-8")
        self.assertIn("River added Spirit", recorded)
        self.assertFalse((practice / "state/sessions/124.jsonl").exists())
        present.add_user.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
