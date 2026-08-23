"""Tests for river bar reconcile floor + launch-pad chrome."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import bar_anchor
import mage
import river_handler
from river_handler import (
    RiverEddyBarView,
    message_looks_like_river_bar,
    reconcile_river_bar_floor,
)

OPERATOR_RIVER = 1479428854513664030
HOSTED_RIVER = 201
FAMILY_CHANNEL = 202


def _bar_registry(tmp: str) -> dict:
    return {
        "mages": {
            "kermit": {
                "practice_dir": f"{tmp}/kermit",
                "runtime_dir": f"{tmp}/kermit",
                "primary": True,
            },
            "partner": {
                "practice_dir": f"{tmp}/partner",
                "runtime_dir": f"{tmp}/partner",
            },
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "runtime_dir": f"{tmp}/family",
                "members": ["kermit", "partner"],
            },
        },
        "channels": {
            str(OPERATOR_RIVER): {"mage": "kermit", "type": "river"},
            str(HOSTED_RIVER): {"mage": "partner", "type": "hosted-river"},
            str(FAMILY_CHANNEL): {"mage": "family", "type": "shared-river"},
        },
    }


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


class EddyBarOwnershipTests(unittest.TestCase):
    """INT-050: each river's bar anchor lives in its own runtime root."""

    def test_hosted_save_does_not_touch_operator_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            kermit_bar = (
                Path(tmp) / "kermit" / "thread-state" / "river" / "eddy_bar.json"
            )
            kermit_bar.parent.mkdir(parents=True)
            kermit_bar.write_text(
                json.dumps(
                    {
                        str(OPERATOR_RIVER): 111,
                        str(HOSTED_RIVER): 222,
                        str(FAMILY_CHANNEL): 333,
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(mage, "_MAGE_REGISTRY", _bar_registry(tmp)):
                river_handler._save_eddy_bar_message(HOSTED_RIVER, 999)

            partner_bar = (
                Path(tmp) / "partner" / "thread-state" / "river" / "eddy_bar.json"
            )
            self.assertTrue(partner_bar.is_file())
            hosted = json.loads(partner_bar.read_text(encoding="utf-8"))
            self.assertEqual(hosted, {str(HOSTED_RIVER): 999})

            # Operator file untouched by the hosted save.
            operator = json.loads(kermit_bar.read_text(encoding="utf-8"))
            self.assertEqual(operator[str(HOSTED_RIVER)], 222)

    def test_operator_save_drops_foreign_channel_keys(self) -> None:
        """Rewriting the operator file cleans 2026-07-10 merge contamination."""
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            kermit_bar = (
                Path(tmp) / "kermit" / "thread-state" / "river" / "eddy_bar.json"
            )
            kermit_bar.parent.mkdir(parents=True)
            kermit_bar.write_text(
                json.dumps(
                    {
                        str(OPERATOR_RIVER): 111,
                        str(HOSTED_RIVER): 222,
                        str(FAMILY_CHANNEL): 333,
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(mage, "_MAGE_REGISTRY", _bar_registry(tmp)):
                river_handler._save_eddy_bar_message(OPERATOR_RIVER, 444)

            operator = json.loads(kermit_bar.read_text(encoding="utf-8"))
            self.assertEqual(operator, {str(OPERATOR_RIVER): 444})
            self.assertNotIn(str(HOSTED_RIVER), operator)
            self.assertNotIn(str(FAMILY_CHANNEL), operator)


if __name__ == "__main__":
    unittest.main()
