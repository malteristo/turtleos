"""Tests for river bar reconcile floor + launch-pad chrome."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import bar_anchor
from river_handler import (
    RiverEddyBarView,
    message_looks_like_river_bar,
    reconcile_river_bar_floor,
)


class _Child:
    def __init__(self, custom_id: str):
        self.custom_id = custom_id


class _Row:
    def __init__(self, *ids: str):
        self.children = [_Child(cid) for cid in ids]


class _Msg:
    def __init__(self, msg_id: int, *custom_ids: str, content: str = "\u200b"):
        self.id = msg_id
        self.content = content
        self.components = [_Row(*custom_ids)] if custom_ids else []
        self.delete = AsyncMock()


class MessageLooksLikeRiverBarTests(unittest.TestCase):
    def test_new_and_more_ids(self) -> None:
        msg = _Msg(1, "river:bar:new:99", "river:bar:more:99")
        self.assertTrue(message_looks_like_river_bar(msg, 99))

    def test_legacy_act_buttons_on_zwsp(self) -> None:
        msg = _Msg(2, "river:act:99:artifacts")
        self.assertTrue(message_looks_like_river_bar(msg, 99))

    def test_rejects_prose(self) -> None:
        msg = _Msg(3, "river:bar:new:99", content="hello")
        self.assertFalse(message_looks_like_river_bar(msg, 99))

    def test_rejects_unrelated_components(self) -> None:
        msg = _Msg(4, "share:target:1")
        self.assertFalse(message_looks_like_river_bar(msg, 99))


class ReconcileFloorTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        bar_anchor.clear_river_bar_scheduler_state()

    async def test_hold_blocks_reconcile(self) -> None:
        channel = MagicMock()
        channel.id = 11
        client = MagicMock()
        bar_anchor.hold_river_bar(11)
        with patch(
            "bar_anchor.channel_for_client", new_callable=AsyncMock, return_value=channel
        ), patch("river_handler.post_river_eddy_bar", new_callable=AsyncMock) as post, patch(
            "river_handler._delete_river_bar_orphans", new_callable=AsyncMock
        ) as delete:
            await reconcile_river_bar_floor(channel, client)
            delete.assert_not_awaited()
            post.assert_not_awaited()

    async def test_reconcile_sweeps_then_posts(self) -> None:
        channel = MagicMock()
        channel.id = 12
        client = MagicMock()
        orphan = _Msg(100, "river:bar:new:12")
        other = _Msg(101, content="hi")
        other.components = []

        async def _history(limit=40):
            for m in (orphan, other):
                yield m

        channel.history = lambda limit=40: _history(limit)

        with patch("bar_anchor.channel_for_client", new_callable=AsyncMock, return_value=channel), patch(
            "river_handler.post_river_eddy_bar", new_callable=AsyncMock
        ) as post:
            await reconcile_river_bar_floor(channel, client)
            orphan.delete.assert_awaited_once()
            post.assert_awaited_once_with(channel, client)


class RiverEddyBarViewChromeTests(unittest.TestCase):
    def test_custom_id_helpers(self) -> None:
        from river_handler import _river_bar_custom_ids

        new_id, more_id = _river_bar_custom_ids(42)
        self.assertEqual(new_id, "river:bar:new:42")
        self.assertEqual(more_id, "river:bar:more:42")
        # View constructs under MagicMock discord.ui; assert construction does not raise.
        RiverEddyBarView(42)


class HandleRiverMessageScheduleTests(unittest.IsolatedAsyncioTestCase):
    async def test_dot_schedules_reconcile(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "."
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel = MagicMock()

        with patch("river_handler.classify_river_acts", new_callable=AsyncMock) as classify, patch(
            "river_handler._river_client_for_channel", return_value=MagicMock()
        ), patch("bar_anchor.schedule_river_bar_reconcile") as schedule:
            await handle_river_message(message)
            classify.assert_not_awaited()
            schedule.assert_called_once()


if __name__ == "__main__":
    unittest.main()
