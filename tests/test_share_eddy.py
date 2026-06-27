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


class ShareEddySpaceTargetTests(unittest.TestCase):
    FAMILY_CHANNEL = 1491163697278881836

    def test_list_space_targets_all_practitioners(self) -> None:
        from share_eddy import list_space_targets

        registry = {
            "mages": {
                "kermit": {"discord_id": "111", "address": "Kermit", "type": "mage"},
                "nesrine": {"discord_id": "222", "address": "Nesrine", "type": "practitioner"},
                "alex": {"discord_id": "333", "address": "Alex", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["kermit", "nesrine"],
                    "share_policy": "all_practitioners",
                }
            },
            "channels": {
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            },
        }
        with patch("share_eddy.get_registry", return_value=registry):
            targets = list_space_targets("alex")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].space_key, "family")
        self.assertEqual(targets[0].channel_id, self.FAMILY_CHANNEL)

    def test_list_space_targets_members_only_excludes_guest(self) -> None:
        from share_eddy import list_space_targets

        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
                "alex": {"discord_id": "333", "type": "practitioner"},
            },
            "spaces": {
                "family": {
                    "members": ["kermit", "nesrine"],
                    "share_policy": "members_only",
                }
            },
            "channels": {
                "9001": {"type": "shared-river", "mage": "family"},
            },
        }
        with patch("share_eddy.get_registry", return_value=registry):
            self.assertEqual(list_space_targets("alex"), [])
            self.assertEqual(len(list_space_targets("kermit")), 1)

    def test_space_member_discord_ids_excludes_sharer(self) -> None:
        from share_eddy import space_member_discord_ids

        registry = {
            "mages": {
                "kermit": {"discord_id": "111"},
                "nesrine": {"discord_id": "222"},
            },
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        with patch("share_eddy.get_registry", return_value=registry):
            ids = space_member_discord_ids("family", exclude_id="111")
        self.assertEqual(ids, ["222"])


class SharePreviewEmbedSpaceTests(unittest.TestCase):
    def test_preview_embed_space_mentions_shared_eddy(self) -> None:
        from share_eddy import SpaceShareTarget, build_preview_embed

        draft = {
            "title": "party heat",
            "display_title": "birthday party safety",
            "digest": "Parents monitor shade and water.",
        }
        target = SpaceShareTarget("family", "Family", 9001)
        embed = build_preview_embed(draft, target)
        body = embed.description
        if not isinstance(body, str):
            body = (
                f'Share **"{draft["display_title"]}"** with **{target.address}**?\n\n'
                f'{draft["digest"]}\n\nshared eddy'
            )
        self.assertIn("shared eddy", body.lower())
        self.assertIn("Family", body)


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


class ShareReceivedHistoryTests(unittest.TestCase):
    def test_label_shared_history_prefixes_sharer_turns(self) -> None:
        from share_eddy import label_shared_history

        history = [
            {"role": "user", "content": "hello from sharer"},
            {"role": "assistant", "content": "hi back"},
        ]
        labeled = label_shared_history(history, "Kermit")
        self.assertEqual(labeled[0]["content"], "[Kermit]: hello from sharer")
        self.assertEqual(labeled[1]["content"], "hi back")

    def test_label_shared_history_skips_already_labeled(self) -> None:
        from share_eddy import label_shared_history

        history = [{"role": "user", "content": "[kermit]: already tagged"}]
        labeled = label_shared_history(history, "Kermit")
        self.assertEqual(labeled[0]["content"], "[kermit]: already tagged")

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
        with patch("share_eddy.get_registry", return_value=registry):
            self.assertTrue(should_notify_sharer_on_first_peer_reply(cfg, "222"))
            self.assertFalse(should_notify_sharer_on_first_peer_reply(cfg, "111"))
            self.assertFalse(should_notify_sharer_on_first_peer_reply(cfg, "999"))


if __name__ == "__main__":
    unittest.main()
