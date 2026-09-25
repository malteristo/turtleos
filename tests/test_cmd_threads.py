"""Tests for thread/eddy command handlers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import cmd_threads as ct


class _FakeThread:
    pass


class TestBuildConfigLine(unittest.TestCase):
    def test_includes_eddy_type(self) -> None:
        from state import thread_configs

        thread_configs[42] = {
            "model_label": "local",
            "model": "gemma",
            "use_api": False,
            "attunement": "native",
            "eddy_type": "standard",
        }
        line = ct.build_config_line(42)
        self.assertIn("standard", line.lower() or "Standard" in line)
        self.assertIn("gemma", line)


class TestCmdEddyCheck(unittest.IsolatedAsyncioTestCase):
    async def test_retired_message(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        await ct.cmd_eddy_check(message, [])
        self.assertIn("retired", message.reply.await_args[0][0].lower())


class TestCmdRename(unittest.IsolatedAsyncioTestCase):
    async def test_requires_thread(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.reply = AsyncMock()
        with patch.object(ct.discord, "Thread", _FakeThread):
            await ct.cmd_rename(message, [])
        self.assertIn("inside an eddy thread", message.reply.await_args[0][0])


class TestCollectFiveStateItems(unittest.TestCase):
    def test_discord_live_and_registry_resting(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        live = MagicMock()
        live.id = 11
        live.name = "talking"
        live.created_at = now
        live.archived = False
        live.locked = False
        items = ct.collect_five_state_thread_items(
            [live],
            {
                "11": {"harvest_status": "pending", "name": "talking"},
                "22": {
                    "harvest_status": "cooled",
                    "name": "asleep",
                    "parent_channel": "craft-turtle",
                },
                "33": {
                    "harvest_status": "dissolved",
                    "name": "closed",
                    "parent_channel": "craft-turtle",
                },
            },
            parent_name="craft-turtle",
            parent_id=1,
            show_all=False,
            now=now,
        )
        states = {state for state, _ in items}
        self.assertIn("live", states)
        self.assertIn("resting", states)
        self.assertNotIn("gone", states)
        blob = "\n".join(line for _, line in items)
        self.assertIn("**talking**", blob)
        self.assertIn("**asleep**", blob)
        self.assertNotIn("unconfigured", blob)
        self.assertNotIn("id:", blob)
        self.assertNotIn("local", blob)

    def test_discord_last_message_order_matches_sidebar(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        older = MagicMock()
        older.id = 10
        older.name = "older talk"
        older.created_at = now
        older.last_message_id = 100
        older.archived = False
        older.locked = False
        newer = MagicMock()
        newer.id = 20
        newer.name = "newer talk"
        newer.created_at = now
        newer.last_message_id = 200
        newer.archived = False
        newer.locked = False
        items = ct.collect_five_state_thread_items(
            [older, newer],
            {},
            parent_name="craft-turtle",
            parent_id=1,
            show_all=False,
            now=now,
        )
        names = [line for _, line in items]
        self.assertIn("newer talk", names[0])
        self.assertIn("older talk", names[1])

    def test_registry_row_without_parent_is_not_this_channel(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        items = ct.collect_five_state_thread_items(
            [],
            {
                "99": {"harvest_status": "cooled", "name": "other-room"},
                "22": {
                    "harvest_status": "cooled",
                    "name": "asleep",
                    "parent_channel": "craft-turtle",
                },
            },
            parent_name="craft-turtle",
            parent_id=1,
            show_all=False,
            now=now,
        )
        names = [line for _, line in items]
        self.assertTrue(any("asleep" in line for line in names))
        self.assertFalse(any("other-room" in line for line in names))

    def test_show_all_includes_gone(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        items = ct.collect_five_state_thread_items(
            [],
            {
                "33": {
                    "harvest_status": "dissolved",
                    "name": "closed",
                    "parent_channel": "craft-turtle",
                },
            },
            parent_name="craft-turtle",
            parent_id=1,
            show_all=True,
            now=now,
        )
        self.assertEqual(items[0][0], "gone")


class TestCmdNew(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_in_thread(self) -> None:
        message = MagicMock()
        message.channel = _FakeThread()
        message.reply = AsyncMock()
        with patch.object(ct.discord, "Thread", _FakeThread):
            await ct.cmd_new(message, [])
        self.assertIn("main channel", message.reply.await_args[0][0])


if __name__ == "__main__":
    unittest.main()
