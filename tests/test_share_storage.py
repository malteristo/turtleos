"""Tests for share_storage — filesystem persistence (share_eddy decomposition Slice 3)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])


class InboxBundleTests(unittest.TestCase):
    def test_inbox_roundtrip(self) -> None:
        from share_storage import load_inbox_bundle, write_inbox_bundle
        from share_transcript import build_export_bundle

        with tempfile.TemporaryDirectory() as tmp:
            bundle = build_export_bundle(
                title="test",
                history=[{"role": "user", "content": "hi"}],
                sharer_id="1",
                sharer_key="a",
                sharer_address="A",
                source_thread_id=1,
            )
            write_inbox_bundle(tmp, bundle)
            loaded = load_inbox_bundle(tmp, bundle["share_id"])
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["title"], "test")
            self.assertEqual(loaded["sharer_key"], "a")

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import load_inbox_bundle, write_inbox_bundle
        from share_transcript import build_export_bundle

        with tempfile.TemporaryDirectory() as tmp:
            bundle = build_export_bundle(
                title="t",
                history=[{"role": "user", "content": "x"}],
                sharer_id="1",
                sharer_key="a",
                sharer_address="A",
                source_thread_id=1,
            )
            write_inbox_bundle(tmp, bundle)
            self.assertIsNotNone(load_inbox_bundle(tmp, bundle["share_id"]))


class ActiveShareActsTests(unittest.IsolatedAsyncioTestCase):
    async def test_supersede_keeps_older_different_shares(self) -> None:
        from share_storage import _load_active_share_acts, _save_active_share_acts, supersede_stale_share_acts

        with tempfile.TemporaryDirectory() as tmp:
            _save_active_share_acts(
                tmp,
                [
                    {"share_id": "share_a", "message_id": "100"},
                    {"share_id": "share_b", "message_id": "200"},
                ],
            )
            channel = AsyncMock()
            old_msg = AsyncMock()
            channel.fetch_message = AsyncMock(return_value=old_msg)

            await supersede_stale_share_acts(
                AsyncMock(),
                channel,
                tmp,
                keep_share_id="share_c",
                keep_message_id=300,
            )

            channel.fetch_message.assert_not_called()
            old_msg.edit.assert_not_called()

            acts = _load_active_share_acts(tmp)
            share_ids = {act["share_id"] for act in acts}
            self.assertEqual(share_ids, {"share_a", "share_b", "share_c"})

    async def test_supersede_strips_duplicate_share_only(self) -> None:
        from share_storage import _load_active_share_acts, _save_active_share_acts, supersede_stale_share_acts

        with tempfile.TemporaryDirectory() as tmp:
            _save_active_share_acts(
                tmp,
                [
                    {"share_id": "share_a", "message_id": "100"},
                    {"share_id": "dup", "message_id": "200"},
                ],
            )
            channel = AsyncMock()
            stale_msg = AsyncMock()
            channel.fetch_message = AsyncMock(return_value=stale_msg)

            await supersede_stale_share_acts(
                AsyncMock(),
                channel,
                tmp,
                keep_share_id="dup",
                keep_message_id=999,
            )

            channel.fetch_message.assert_called_once_with(200)
            stale_msg.edit.assert_called_once_with(view=None)

            acts = _load_active_share_acts(tmp)
            self.assertEqual(
                acts,
                [
                    {"share_id": "share_a", "message_id": "100"},
                    {"share_id": "dup", "message_id": "999"},
                ],
            )


class ReceivedThreadConfigTests(unittest.TestCase):
    def test_received_thread_config_roundtrip(self) -> None:
        from share_storage import (
            load_received_thread_config,
            mark_received_thread_notified,
            save_received_thread_config,
        )

        cfg = {
            "origin": "received",
            "share_id": "abc",
            "share_creator": "111",
            "sharer_key": "kermit",
            "share_recipient_id": "222",
            "share_notify_pending": True,
            "topic": "testing eddy sharing",
            "from_sharer": "Kermit",
        }
        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(tmp, 555, cfg)
            loaded = load_received_thread_config(tmp, 555)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded["share_notify_pending"])
            mark_received_thread_notified(tmp, 555)
            loaded = load_received_thread_config(tmp, 555)
            assert loaded is not None
            self.assertFalse(loaded["share_notify_pending"])


class ShareRuntimeDirTests(unittest.TestCase):
    def test_pending_draft_roundtrip_uses_parent_runtime(self) -> None:
        from share_storage import (
            load_pending_draft,
            resolve_share_runtime_dir,
            write_pending_draft,
        )

        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.set_practice_context_for_channel") as set_ctx, patch(
                "mage.get_runtime_dir", return_value=tmp
            ):
                runtime = resolve_share_runtime_dir(parent_channel_id=999001)
                self.assertEqual(runtime, tmp)
                set_ctx.assert_called_once_with(999001)
                write_pending_draft(runtime, 222, 333, {"share_id": "abc"})
                draft = load_pending_draft(runtime, 222, 333)
                self.assertEqual(draft["share_id"], "abc")

    def test_find_received_thread_for_share(self) -> None:
        from share_storage import find_received_thread_for_share, save_received_thread_config

        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(
                tmp,
                777,
                {"share_id": "abc123", "origin": "received"},
            )
            self.assertEqual(find_received_thread_for_share(tmp, "abc123"), 777)
            self.assertIsNone(find_received_thread_for_share(tmp, "missing"))
