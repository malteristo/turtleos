"""Tests for Share eddy Slice 1 (practitioner target)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])


class ShareEddyTargetTests(unittest.TestCase):
    def test_list_practitioner_targets_excludes_self(self) -> None:
        from share_eddy import list_practitioner_targets

        registry = {
            "mages": {
                "kermit": {
                    "discord_id": "111",
                    "address": "Kermit",
                    "type": "mage",
                },
                "nesrine": {
                    "discord_id": "222",
                    "address": "Nesrine",
                    "type": "practitioner",
                },
            },
            "channels": {
                "1001": {"mage": "kermit", "type": "river"},
                "1002": {"mage": "nesrine", "type": "hosted-river"},
            },
        }
        with patch("share_eddy.get_registry", return_value=registry):
            targets = list_practitioner_targets("kermit", "111")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].mage_key, "nesrine")
        self.assertEqual(targets[0].channel_id, 1002)


class ShareEddyBundleTests(unittest.TestCase):
    def test_build_export_bundle_preserves_history(self) -> None:
        from share_eddy import build_export_bundle, build_digest

        history = [
            {"role": "user", "content": "Birthday party heat"},
            {"role": "assistant", "content": "Sprinkler might help."},
        ]
        bundle = build_export_bundle(
            title="birthday party",
            history=history,
            sharer_id="111",
            sharer_key="kermit",
            sharer_address="Kermit",
            source_thread_id=999,
            share_id="abc123",
        )
        self.assertEqual(bundle["share_id"], "abc123")
        self.assertEqual(bundle["title"], "birthday party")
        self.assertEqual(len(bundle["history"]), 2)
        self.assertIn("Birthday party heat", bundle["transcript"])
        self.assertIn("Sprinkler", bundle["digest"])
        self.assertEqual(build_digest("x", history), bundle["digest"])

    def test_inbox_roundtrip(self) -> None:
        from share_eddy import build_export_bundle, load_inbox_bundle, write_inbox_bundle

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


class ShareEddyRiverChannelTests(unittest.TestCase):
    def test_river_channel_for_mage(self) -> None:
        from share_eddy import river_channel_for_mage

        registry = {
            "channels": {
                "42": {"mage": "guest", "type": "hosted-river"},
                "43": {"mage": "guest", "type": "craft"},
            }
        }
        with patch("share_eddy.get_registry", return_value=registry):
            self.assertEqual(river_channel_for_mage("guest"), 42)
            self.assertIsNone(river_channel_for_mage("missing"))


class ShareEddyFilterTests(unittest.TestCase):
    def test_is_placeholder_eddy_title(self) -> None:
        from share_eddy import is_placeholder_eddy_title

        self.assertTrue(is_placeholder_eddy_title("new eddy"))
        self.assertTrue(is_placeholder_eddy_title("hello to turtle please update your status"))
        self.assertFalse(is_placeholder_eddy_title("birthday party heat"))

    def test_filter_share_history_drops_act_digests_and_commands(self) -> None:
        from share_eddy import build_digest, build_export_bundle, filter_share_history

        history = [
            {"role": "user", "content": "!share"},
            {"role": "user", "content": "[Act: !share] Failed: View is not persistent."},
            {"role": "user", "content": "Birthday party heat and sprinkler plan"},
            {"role": "assistant", "content": "Active monitoring makes sense."},
        ]
        filtered = filter_share_history(history)
        self.assertEqual(len(filtered), 2)
        digest = build_digest("party", filtered)
        self.assertNotIn("[Act:", digest)
        self.assertIn("Birthday", digest)

        bundle = build_export_bundle(
            title="party",
            history=history,
            sharer_id="1",
            sharer_key="k",
            sharer_address="K",
            source_thread_id=9,
        )
        self.assertEqual(len(bundle["history"]), 2)


class SharePreviewEmbedTests(unittest.TestCase):
    def test_preview_embed_uses_display_title(self) -> None:
        from share_eddy import ShareTarget, build_preview_embed, share_label

        draft = {
            "title": "hello to turtle please update your status",
            "display_title": "birthday party safety",
            "digest": "Parents as active monitors for shade and water.",
        }
        target = ShareTarget("nesrine", "Nesrine", "222", 1002)
        label = share_label(draft)
        self.assertEqual(label, "birthday party safety")
        embed = build_preview_embed(draft, target)
        body = embed.description
        if not isinstance(body, str):
            body = f'Share **"{label}"** with **{target.address}**?\n\n{draft["digest"]}'
        self.assertIn("birthday party safety", body)
        self.assertIn("Parents as active monitors", body)


class ShareEddyEnrichTests(unittest.IsolatedAsyncioTestCase):
    async def test_enrich_export_bundle_uses_llm_digest(self) -> None:
        from share_eddy import build_export_bundle, enrich_export_bundle

        bundle = build_export_bundle(
            title="hello to turtle please update your status",
            history=[
                {"role": "user", "content": "Birthday party shade and sprinkler plan"},
                {"role": "assistant", "content": "Active monitoring makes sense."},
            ],
            sharer_id="1",
            sharer_key="k",
            sharer_address="Kermit",
            source_thread_id=9,
        )
        with patch(
            "share_eddy.synthesize_share_metadata",
            new=AsyncMock(
                return_value=(
                    "birthday party safety",
                    "Kids' party in heat — parents as active monitors for shade and water.",
                )
            ),
        ):
            enriched = await enrich_export_bundle(bundle)
        self.assertEqual(enriched["display_title"], "birthday party safety")
        self.assertIn("party", enriched["digest"].lower())


class ShareEddyClientTests(unittest.TestCase):
    def test_get_share_bot_client_uses_guild_not_message_client(self) -> None:
        from share_eddy import get_share_bot_client

        mock_client = object()
        message = MagicMock()
        message.channel.guild._state._get_client.return_value = mock_client
        del message.client  # discord.Message has no .client in our runtime

        with patch("mage.river_bot_enabled", return_value=False):
            self.assertIs(get_share_bot_client(message), mock_client)


class ShareActiveActsTests(unittest.IsolatedAsyncioTestCase):
    async def test_supersede_keeps_older_different_shares(self) -> None:
        from share_eddy import _save_active_share_acts, supersede_stale_share_acts

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

            from share_eddy import _load_active_share_acts

            acts = _load_active_share_acts(tmp)
            share_ids = {act["share_id"] for act in acts}
            self.assertEqual(share_ids, {"share_a", "share_b", "share_c"})

    async def test_supersede_strips_duplicate_share_only(self) -> None:
        from share_eddy import _save_active_share_acts, supersede_stale_share_acts

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

            from share_eddy import _load_active_share_acts

            acts = _load_active_share_acts(tmp)
            self.assertEqual(
                acts,
                [
                    {"share_id": "share_a", "message_id": "100"},
                    {"share_id": "dup", "message_id": "999"},
                ],
            )


class ShareReceivedThreadConfigTests(unittest.TestCase):
    def test_received_thread_config_roundtrip(self) -> None:
        from share_eddy import (
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


class ShareNotifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_maybe_notify_loads_config_from_disk(self) -> None:
        from share_eddy import maybe_notify_sharer_on_first_peer_reply, save_received_thread_config

        class FakeThread:
            id = 777
            parent_id = 1002
            name = "testing eddy sharing"
            jump_url = "https://discord.com/channels/x/y/z"

        message = MagicMock()
        message.author.bot = False
        message.author.id = 222
        message.author.display_name = "Nesrine"
        message.channel = FakeThread()

        cfg = {
            "origin": "received",
            "share_id": "abc",
            "share_creator": "111",
            "sharer_key": "kermit",
            "share_recipient_id": "222",
            "share_notify_pending": True,
            "topic": "testing eddy sharing",
        }

        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(tmp, 777, cfg)
            with patch("eddy_lifecycle_bar.is_practitioner_input", return_value=True), patch(
                "commands.thread_configs",
                {},
            ), patch("share_eddy.set_practice_context_for_channel"), patch(
                "share_eddy.discord.Thread",
                FakeThread,
            ), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ), patch(
                "share_eddy.notify_sharer_first_peer_reply",
                new=AsyncMock(),
            ) as notify:
                await maybe_notify_sharer_on_first_peer_reply(message)
                notify.assert_awaited_once()

            from share_eddy import load_received_thread_config

            loaded = load_received_thread_config(tmp, 777)
            assert loaded is not None
            self.assertFalse(loaded["share_notify_pending"])


if __name__ == "__main__":
    unittest.main()
