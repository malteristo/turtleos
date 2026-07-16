"""Shared-river / hosted-river eddy rejoin after restart (Galactic Adventure class)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
discord = sys.modules["discord"]
discord.HTTPException = type("HTTPException", (Exception,), {})
discord.NotFound = type("NotFound", (discord.HTTPException,), {})
discord.Thread = type("Thread", (), {})

import mage


class PracticeParentChannelIdsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved)

    def test_includes_shared_and_hosted_skips_orphaned(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "channels": {
                    "111": {"type": "river", "mage": "kermit"},
                    "222": {"type": "shared-river", "mage": "lukas_sandbox"},
                    "333": {"type": "hosted-river", "mage": "lukas"},
                    "444": {
                        "type": "shared-river",
                        "mage": "lukas_play",
                        "orphaned": True,
                    },
                    "555": {
                        "type": "shared-river",
                        "mage": "old",
                        "archived": True,
                    },
                    "666": {"type": "craft", "mage": "kermit"},
                }
            }
        )
        with patch("mage._resolve_dialogue_channel_id", return_value=111):
            ids = mage.practice_parent_channel_ids()
        self.assertEqual(ids, [111, 222, 333])

    def test_adds_dialogue_fallback_when_unlisted(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update({"channels": {}})
        with patch("mage._resolve_dialogue_channel_id", return_value=999):
            ids = mage.practice_parent_channel_ids()
        self.assertEqual(ids, [999])


class RiverRejoinPracticeThreadsTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejoins_threads_via_guild_active_threads(self) -> None:
        from river_bot import _rejoin_practice_threads

        thread = MagicMock()
        thread.name = "Galactic Adventure"
        thread.id = 1522648705360990469
        thread.parent_id = 1522210357622341766
        thread.join = AsyncMock()

        other = MagicMock()
        other.name = "unrelated"
        other.id = 1
        other.parent_id = 999
        other.join = AsyncMock()

        parent = MagicMock()
        parent.name = "lukas-sandbox"
        parent.id = 1522210357622341766
        parent.guild = MagicMock()
        parent.guild.active_threads = AsyncMock(return_value=[thread, other])

        client = MagicMock()
        client.get_channel.return_value = parent

        with patch(
            "mage.practice_parent_channel_ids",
            return_value=[1522210357622341766],
        ), patch(
            "river_handler._resolve_client_channel",
            new=AsyncMock(return_value=parent),
        ), patch("river_bot.asyncio.sleep", new=AsyncMock()):
            await _rejoin_practice_threads(client)

        thread.join.assert_awaited_once()
        other.join.assert_not_awaited()


class RiverEnsureTurtleOnTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_turtle_delegates_to_river_add(self) -> None:
        from river_bot import _ensure_turtle_in_eddy

        thread = MagicMock()
        with patch(
            "eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()
        ) as add:
            await _ensure_turtle_in_eddy(thread)
        add.assert_awaited_once_with(thread)


if __name__ == "__main__":
    unittest.main()
