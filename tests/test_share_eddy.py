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


class ShareEddyClientTests(unittest.TestCase):
    def test_get_share_bot_client_uses_guild_not_message_client(self) -> None:
        from share_eddy import get_share_bot_client

        mock_client = object()
        message = MagicMock()
        message.channel.guild._state._get_client.return_value = mock_client
        del message.client  # discord.Message has no .client in our runtime

        with patch("mage.river_bot_enabled", return_value=False):
            self.assertIs(get_share_bot_client(message), mock_client)


class ShareReceivedContextTests(unittest.TestCase):
    def test_received_eddy_context_lines_name_recipient_not_sharer(self) -> None:
        from share_eddy import received_eddy_context_lines

        with patch("mage.get_mage_name", return_value="Nesrine"):
            lines = received_eddy_context_lines({"from_sharer": "Kermit"})
        joined = "\n".join(lines)
        self.assertIn("Kermit is not in this thread", joined)
        self.assertIn("Nesrine", joined)
        self.assertIn("joining", joined.lower())


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
            with patch("share_eddy.set_practice_context_for_channel"), patch(
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
                "share_eddy.save_received_thread_config"
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
            with patch("share_eddy.set_practice_context_for_channel"), patch(
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
            "share_eddy.materialize_received_eddy",
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
            "share_eddy.materialize_received_eddy",
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
            with patch("share_eddy.get_registry", return_value=registry), patch(
                "share_targets.get_registry",
                return_value=registry,
            ), patch(
                "eddy_lifecycle_bar.is_practitioner_input",
                return_value=True,
            ), patch("commands.thread_configs", {}), patch(
                "share_eddy.set_practice_context_for_channel"
            ), patch("share_eddy.discord.Thread", FakeThread), patch(
                "mage.get_runtime_dir",
                return_value=tmp,
            ), patch(
                "share_eddy.notify_sharer_first_peer_reply",
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
            ), patch("share_eddy.set_practice_context_for_channel"), patch(
                "share_eddy.discord.Thread",
                FakeThread,
            ), patch("mage.get_runtime_dir", return_value=tmp), patch(
                "share_eddy.notify_sharer_first_peer_reply",
                new=AsyncMock(),
            ) as notify:
                await maybe_notify_sharer_on_first_peer_reply(message)
                notify.assert_not_awaited()


class ShareSharedEddyContextTests(unittest.TestCase):
    def test_sharer_is_space_member(self) -> None:
        from share_eddy import sharer_is_space_member

        registry = {
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        with patch("share_eddy.get_registry", return_value=registry):
            self.assertTrue(
                sharer_is_space_member(
                    {"space_key": "family", "sharer_key": "kermit"},
                )
            )
            self.assertFalse(
                sharer_is_space_member(
                    {"space_key": "family", "sharer_key": "lukas"},
                )
            )

    def test_shared_context_member_sharer_visibility(self) -> None:
        from share_eddy import shared_eddy_context_lines

        registry = {
            "mages": {
                "kermit": {"address": "Kermit"},
                "nesrine": {"address": "Nesrine"},
            },
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        cfg = {
            "from_sharer": "Kermit",
            "sharer_key": "kermit",
            "space_key": "family",
        }
        with patch("share_eddy.get_registry", return_value=registry):
            lines = shared_eddy_context_lines(
                cfg,
                speaker_display="Nesrine",
                speaker_mage_key="nesrine",
            )
        joined = "\n".join(lines)
        self.assertIn("You are Turtle", joined)
        self.assertIn("you did not initiate the share", joined)
        self.assertIn("Kermit", joined)
        self.assertIn("is a **Family** member", joined)
        self.assertIn("Speaking now:** **Nesrine**", joined)
        self.assertIn("thanks for sharing", joined.lower())
        self.assertIn("do **not** reply", joined.lower())

    def test_shared_context_guest_sharer_visibility(self) -> None:
        from share_eddy import shared_eddy_context_lines

        registry = {
            "mages": {
                "lukas": {"address": "Lukas"},
                "nesrine": {"address": "Nesrine"},
            },
            "spaces": {"family": {"members": ["nesrine"]}},
        }
        cfg = {
            "from_sharer": "Lukas",
            "sharer_key": "lukas",
            "space_key": "family",
        }
        with patch("share_eddy.get_registry", return_value=registry):
            lines = shared_eddy_context_lines(cfg, speaker_display="Nesrine")
        joined = "\n".join(lines)
        self.assertIn("is **not** a **Family** member", joined)
        self.assertIn("their own river", joined)


class ShareEddyMentionGateTests(unittest.TestCase):
    TURTLE_ID = 999888777

    def _message(
        self,
        content: str,
        *,
        mentions=None,
        reply_author_id: int | None = None,
    ):
        message = MagicMock()
        message.content = content
        message.mentions = mentions or []
        message.channel = MagicMock()
        message.channel.parent = MagicMock()
        message.channel.parent.guild = MagicMock()
        message.author.display_name = "Nesrine"
        if reply_author_id is not None:
            ref_msg = MagicMock()
            ref_msg.author.id = reply_author_id
            ref_msg.author.bot = True
            message.reference = MagicMock(resolved=ref_msg, cached_message=None)
        else:
            message.reference = None
        return message

    def test_respond_on_turtle_mention(self) -> None:
        from share_eddy import shared_eddy_response_decision

        turtle = MagicMock(id=self.TURTLE_ID, bot=True)
        msg = self._message("what do you think?", mentions=[turtle])
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "mention_turtle")

    def test_pass_on_peer_mention(self) -> None:
        from share_eddy import shared_eddy_response_decision

        kermit = MagicMock(id=111, bot=False)
        msg = self._message("@kermit thanks for sharing!", mentions=[kermit])
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "mention_peer")

    def test_pass_on_thanks_for_sharing(self) -> None:
        from share_eddy import shared_eddy_response_decision

        msg = self._message("thanks for sharing!")
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "peer_thanks")

    def test_respond_on_explicit_hey_turtle(self) -> None:
        from share_eddy import shared_eddy_response_decision

        msg = self._message("hey Turtle, what do you think about the heat plan?")
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "explicit_invoke")

    def test_pass_on_ambiguous_question(self) -> None:
        from share_eddy import shared_eddy_response_decision

        msg = self._message("what do you think about the heat plan?")
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "mention_gated_default")

    def test_respond_on_reply_to_turtle(self) -> None:
        from share_eddy import shared_eddy_response_decision

        msg = self._message("sounds good", reply_author_id=self.TURTLE_ID)
        with patch("share_eddy._turtle_user_id_for_message", return_value=self.TURTLE_ID), patch(
            "eddy_spawn.is_turtle_bot_message",
            return_value=True,
        ):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "reply_to_turtle")


class ShareDissolveAuthorityTests(unittest.TestCase):
    FAMILY_REGISTRY = {
        "mages": {
            "kermit": {"discord_id": "111", "address": "Kermit"},
            "nesrine": {"discord_id": "222", "address": "Nesrine"},
            "lukas": {"discord_id": "333", "address": "Lukas"},
        },
        "spaces": {"family": {"members": ["kermit", "nesrine"]}},
    }

    def test_non_creator_cannot_dissolve_member_sharer_shared_eddy(self) -> None:
        from share_eddy import check_share_dissolve_authority

        cfg = {
            "origin": "shared",
            "share_creator": "111",
            "sharer_key": "kermit",
            "from_sharer": "Kermit",
            "space_key": "family",
        }
        with patch("share_eddy.get_registry", return_value=self.FAMILY_REGISTRY), patch(
            "share_targets.get_registry",
            return_value=self.FAMILY_REGISTRY,
        ):
            decision = check_share_dissolve_authority(888, 9001, "222", cfg)
        self.assertFalse(decision.allowed)
        self.assertIn("Kermit", decision.reason or "")

    def test_space_member_can_dissolve_guest_sharer_shared_eddy(self) -> None:
        from share_eddy import check_share_dissolve_authority

        cfg = {
            "origin": "shared",
            "share_creator": "333",
            "sharer_key": "lukas",
            "from_sharer": "Lukas",
            "space_key": "family",
        }
        with patch("share_eddy.get_registry", return_value=self.FAMILY_REGISTRY), patch(
            "share_targets.get_registry",
            return_value=self.FAMILY_REGISTRY,
        ):
            decision = check_share_dissolve_authority(888, 9001, "222", cfg)
        self.assertTrue(decision.allowed)

    def test_creator_can_dissolve_shared_eddy(self) -> None:
        from share_eddy import check_share_dissolve_authority

        cfg = {"origin": "shared", "share_creator": "111", "sharer_key": "kermit", "space_key": "family"}
        decision = check_share_dissolve_authority(888, 9001, "111", cfg)
        self.assertTrue(decision.allowed)

    def test_non_creator_cannot_dissolve_received_eddy(self) -> None:
        from share_eddy import check_share_dissolve_authority

        cfg = {"origin": "received", "share_creator": "111", "from_sharer": "Kermit"}
        decision = check_share_dissolve_authority(777, 1002, "222", cfg)
        self.assertFalse(decision.allowed)
        self.assertIn("Kermit", decision.reason or "")

    def test_regular_eddy_allows_anyone_with_practice_access(self) -> None:
        from share_eddy import check_share_dissolve_authority

        decision = check_share_dissolve_authority(555, 1001, "222", {"origin": None})
        self.assertTrue(decision.allowed)


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


if __name__ == "__main__":
    unittest.main()
