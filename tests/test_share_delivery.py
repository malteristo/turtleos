"""Tests for share_delivery — async delivery paths (share_eddy decomposition Slice 5)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])

class ShareMaterializeTests(unittest.IsolatedAsyncioTestCase):
    async def test_materialize_uses_sibling_thread_and_reposts_digest(self) -> None:
        from share_eddy import materialize_received_eddy

        bundle = {
            "share_id": "abc123",
            "recipient_discord_id": "222",
            "sharer_address": "Kermit",
            "display_title": "chicken joke",
            "digest": "Why did the chicken cross the road?",
            "history": [{"role": "user", "content": "tell me a joke"}],
        }

        interaction = MagicMock()
        interaction.user.id = 222
        interaction.client = MagicMock()
        interaction.client.get_channel.return_value = None
        interaction.channel = AsyncMock()
        interaction.channel.name = "nesrine-dialogue"
        interaction.channel.create_thread = AsyncMock()

        fake_thread = AsyncMock()
        fake_thread.id = 555
        fake_thread.send = AsyncMock()
        interaction.channel.create_thread.return_value = fake_thread

        with tempfile.TemporaryDirectory() as tmp:
            from share_eddy import write_inbox_bundle

            write_inbox_bundle(tmp, bundle)
            with patch("mage.set_practice_context_for_channel"), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ), patch("eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()), patch(
                "commands.thread_configs",
                {},
            ), patch("state.dialogue_histories", {}), patch(
                "helpers.sync_history"
            ), patch(
                "thread_registry.register_thread"
            ), patch(
                "share_storage.save_received_thread_config"
            ):
                thread = await materialize_received_eddy(interaction, "abc123", 1002)

        self.assertIs(thread, fake_thread)
        interaction.channel.create_thread.assert_awaited_once()
        self.assertEqual(fake_thread.send.await_count, 2)
        first_call = fake_thread.send.await_args_list[0]
        self.assertIn("embed", first_call.kwargs)

    async def test_materialize_reuses_existing_thread_for_share(self) -> None:
        from share_eddy import materialize_received_eddy, save_received_thread_config

        interaction = MagicMock()
        interaction.user.id = 222
        existing = MagicMock()
        existing.add_user = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.get_channel.return_value = existing
        interaction.channel = MagicMock()

        cfg = {
            "origin": "received",
            "share_id": "abc123",
            "share_creator": "111",
            "sharer_key": "kermit",
            "share_recipient_id": "222",
            "share_notify_pending": False,
            "topic": "chicken joke",
            "from_sharer": "Kermit",
        }

        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(tmp, 777, cfg)
            from share_eddy import write_inbox_bundle

            write_inbox_bundle(
                tmp,
                {
                    "share_id": "abc123",
                    "recipient_discord_id": "222",
                    "sharer_address": "Kermit",
                    "digest": "x",
                    "history": [],
                },
            )
            with patch("mage.set_practice_context_for_channel"), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ):
                thread = await materialize_received_eddy(interaction, "abc123", 1002)

        self.assertIs(thread, existing)
        interaction.channel.create_thread.assert_not_called()



class ShareContinueContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_continue_success_is_silent(self) -> None:
        """Success = thread chip on digest only; no second river/ephemeral message."""
        from share_eddy import continue_received_share

        interaction = MagicMock()
        interaction.channel = MagicMock()
        interaction.channel.id = 1002
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.delete_original_response = AsyncMock()

        fake_thread = MagicMock()
        fake_thread.name = "testing eddy sharing"

        with patch(
            "share_delivery.materialize_received_eddy",
            new=AsyncMock(return_value=fake_thread),
        ):
            thread = await continue_received_share(interaction, "share-abc", 1002)

        self.assertIs(thread, fake_thread)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.delete_original_response.assert_awaited_once()
        interaction.followup.send.assert_not_awaited()

    async def test_continue_failure_sends_ephemeral_error(self) -> None:
        from share_eddy import continue_received_share

        interaction = MagicMock()
        interaction.channel = MagicMock()
        interaction.channel.id = 1002
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.delete_original_response = AsyncMock()

        with patch(
            "share_delivery.materialize_received_eddy",
            new=AsyncMock(side_effect=PermissionError("Only the recipient can continue.")),
        ):
            thread = await continue_received_share(interaction, "share-abc", 1002)

        self.assertIsNone(thread)
        interaction.followup.send.assert_awaited_once_with(
            "Only the recipient can continue.",
            ephemeral=True,
        )
        interaction.delete_original_response.assert_not_awaited()



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
            ), patch("mage.set_practice_context_for_channel"), patch(
                "share_delivery.discord.Thread",
                FakeThread,
            ), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ), patch(
                "share_delivery.notify_sharer_first_peer_reply",
                new=AsyncMock(),
            ) as notify:
                await maybe_notify_sharer_on_first_peer_reply(message)
                notify.assert_awaited_once()

            from share_eddy import load_received_thread_config

            loaded = load_received_thread_config(tmp, 777)
            assert loaded is not None
            self.assertFalse(loaded["share_notify_pending"])

    async def test_maybe_notify_shared_eddy_on_member_first_reply(self) -> None:
        from share_eddy import maybe_notify_sharer_on_first_peer_reply, save_received_thread_config

        class FakeThread:
            id = 888
            parent_id = 1491163697278881836
            name = "birthday party safety"
            jump_url = "https://discord.com/channels/x/y/z"

        message = MagicMock()
        message.author.bot = False
        message.author.id = 222
        message.author.display_name = "Nesrine"
        message.channel = FakeThread()

        cfg = {
            "origin": "shared",
            "share_id": "abc",
            "share_creator": "111",
            "sharer_key": "kermit",
            "space_key": "family",
            "share_notify_pending": True,
            "topic": "birthday party safety",
            "from_sharer": "Kermit",
        }

        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
            },
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }

        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(tmp, 888, cfg)
            with patch(
                "share_targets.get_registry",
                return_value=registry,
            ), patch(
                "eddy_lifecycle_bar.is_practitioner_input",
                return_value=True,
            ), patch("commands.thread_configs", {}), patch(
                "mage.set_practice_context_for_channel"
            ), patch("share_delivery.discord.Thread", FakeThread), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ), patch(
                "share_delivery.notify_sharer_first_peer_reply",
                new=AsyncMock(),
            ) as notify:
                await maybe_notify_sharer_on_first_peer_reply(message)
                notify.assert_awaited_once()

            from share_eddy import load_received_thread_config

            loaded = load_received_thread_config(tmp, 888)
            assert loaded is not None
            self.assertFalse(loaded["share_notify_pending"])

    async def test_maybe_notify_shared_eddy_skips_sharer_own_message(self) -> None:
        from share_eddy import maybe_notify_sharer_on_first_peer_reply, save_received_thread_config

        class FakeThread:
            id = 888
            parent_id = 1491163697278881836
            name = "birthday party safety"

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111
        message.author.display_name = "Kermit"
        message.channel = FakeThread()

        cfg = {
            "origin": "shared",
            "share_creator": "111",
            "sharer_key": "kermit",
            "space_key": "family",
            "share_notify_pending": True,
            "topic": "birthday party safety",
        }

        with tempfile.TemporaryDirectory() as tmp:
            save_received_thread_config(tmp, 888, cfg)
            with patch("eddy_lifecycle_bar.is_practitioner_input", return_value=True), patch(
                "commands.thread_configs",
                {},
            ), patch("mage.set_practice_context_for_channel"), patch(
                "share_delivery.discord.Thread",
                FakeThread,
            ), patch("mage.get_runtime_dir", return_value=tmp), patch(
                "share_delivery.notify_sharer_first_peer_reply",
                new=AsyncMock(),
            ) as notify:
                await maybe_notify_sharer_on_first_peer_reply(message)
                notify.assert_not_awaited()



class ShareNotifyPolicyTests(unittest.TestCase):
    def test_should_notify_received_only_recipient(self) -> None:
        from share_eddy import should_notify_sharer_on_first_peer_reply

        cfg = {
            "origin": "received",
            "share_notify_pending": True,
            "share_recipient_id": "222",
        }
        self.assertTrue(should_notify_sharer_on_first_peer_reply(cfg, "222"))
        self.assertFalse(should_notify_sharer_on_first_peer_reply(cfg, "111"))

    def test_should_notify_shared_space_member_not_sharer(self) -> None:
        from share_eddy import should_notify_sharer_on_first_peer_reply

        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
            },
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        cfg = {
            "origin": "shared",
            "share_notify_pending": True,
            "share_creator": "111",
            "space_key": "family",
        }
        with patch("share_targets.get_registry", return_value=registry):
            self.assertTrue(should_notify_sharer_on_first_peer_reply(cfg, "222"))
            self.assertFalse(should_notify_sharer_on_first_peer_reply(cfg, "111"))
            self.assertFalse(should_notify_sharer_on_first_peer_reply(cfg, "999"))


class DeliveryReexportTests(unittest.TestCase):
    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import continue_received_share, deliver_practitioner_share

        self.assertTrue(callable(continue_received_share))
        self.assertTrue(callable(deliver_practitioner_share))


if __name__ == "__main__":
    unittest.main()

