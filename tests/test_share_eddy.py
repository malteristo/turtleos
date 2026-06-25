"""Tests for Share eddy Slice 1 (practitioner target)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class ShareEddyClientTests(unittest.TestCase):
    def test_get_share_bot_client_uses_guild_not_message_client(self) -> None:
        from share_eddy import get_share_bot_client

        mock_client = object()
        message = MagicMock()
        message.channel.guild._state._get_client.return_value = mock_client
        del message.client  # discord.Message has no .client in our runtime

        with patch("mage.river_bot_enabled", return_value=False):
            self.assertIs(get_share_bot_client(message), mock_client)


if __name__ == "__main__":
    unittest.main()
