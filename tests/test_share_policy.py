"""Tests for share_policy — context, mention gate, dissolve (share_eddy decomposition Slice 4)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])


class ReceivedContextTests(unittest.TestCase):
    def test_received_eddy_context_lines_name_recipient_not_sharer(self) -> None:
        from share_policy import received_eddy_context_lines

        with patch("mage.get_mage_name", return_value="Nesrine"):
            lines = received_eddy_context_lines({"from_sharer": "Kermit"})
        joined = "\n".join(lines)
        self.assertIn("Kermit is not in this thread", joined)
        self.assertIn("Nesrine", joined)
        self.assertIn("joining", joined.lower())

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import check_share_dissolve_authority, resolve_eddy_thread_cfg

        cfg = {"origin": "received", "share_creator": "111", "from_sharer": "Kermit"}
        decision = check_share_dissolve_authority(777, 1002, "111", cfg)
        self.assertTrue(decision.allowed)
        merged = resolve_eddy_thread_cfg(1, 2, cfg)
        self.assertEqual(merged, cfg)


class SharedEddyContextTests(unittest.TestCase):
    def test_sharer_is_space_member(self) -> None:
        from share_policy import sharer_is_space_member

        registry = {
            "spaces": {"family": {"members": ["kermit", "nesrine"]}},
        }
        with patch("share_policy.get_registry", return_value=registry):
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
        from share_policy import shared_eddy_context_lines

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
        with patch("share_policy.get_registry", return_value=registry):
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
        from share_policy import shared_eddy_context_lines

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
        with patch("share_policy.get_registry", return_value=registry):
            lines = shared_eddy_context_lines(cfg, speaker_display="Nesrine")
        joined = "\n".join(lines)
        self.assertIn("is **not** a **Family** member", joined)
        self.assertIn("their own river", joined)


class MentionGateTests(unittest.TestCase):
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
        from share_policy import shared_eddy_response_decision

        turtle = MagicMock(id=self.TURTLE_ID, bot=True)
        msg = self._message("what do you think?", mentions=[turtle])
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "mention_turtle")

    def test_pass_on_peer_mention(self) -> None:
        from share_policy import shared_eddy_response_decision

        kermit = MagicMock(id=111, bot=False)
        msg = self._message("@kermit thanks for sharing!", mentions=[kermit])
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "mention_peer")

    def test_pass_on_thanks_for_sharing(self) -> None:
        from share_policy import shared_eddy_response_decision

        msg = self._message("thanks for sharing!")
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "peer_thanks")

    def test_respond_on_explicit_hey_turtle(self) -> None:
        from share_policy import shared_eddy_response_decision

        msg = self._message("hey Turtle, what do you think about the heat plan?")
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "explicit_invoke")

    def test_pass_on_ambiguous_question(self) -> None:
        from share_policy import shared_eddy_response_decision

        msg = self._message("what do you think about the heat plan?")
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertFalse(decision.respond)
        self.assertEqual(decision.reason, "mention_gated_default")

    def test_respond_on_reply_to_turtle(self) -> None:
        from share_policy import shared_eddy_response_decision

        msg = self._message("sounds good", reply_author_id=self.TURTLE_ID)
        with patch("share_policy._turtle_user_id_for_message", return_value=self.TURTLE_ID), patch(
            "eddy_spawn.is_turtle_bot_message",
            return_value=True,
        ):
            decision = shared_eddy_response_decision(msg, msg.content)
        self.assertTrue(decision.respond)
        self.assertEqual(decision.reason, "reply_to_turtle")


class DissolveAuthorityTests(unittest.TestCase):
    FAMILY_REGISTRY = {
        "mages": {
            "kermit": {"discord_id": "111", "address": "Kermit"},
            "nesrine": {"discord_id": "222", "address": "Nesrine"},
            "lukas": {"discord_id": "333", "address": "Lukas"},
        },
        "spaces": {"family": {"members": ["kermit", "nesrine"]}},
    }

    def test_non_creator_cannot_dissolve_member_sharer_shared_eddy(self) -> None:
        from share_policy import check_share_dissolve_authority

        cfg = {
            "origin": "shared",
            "share_creator": "111",
            "sharer_key": "kermit",
            "from_sharer": "Kermit",
            "space_key": "family",
        }
        with patch("share_policy.get_registry", return_value=self.FAMILY_REGISTRY), patch(
            "share_targets.get_registry",
            return_value=self.FAMILY_REGISTRY,
        ):
            decision = check_share_dissolve_authority(888, 9001, "222", cfg)
        self.assertFalse(decision.allowed)
        self.assertIn("Kermit", decision.reason or "")

    def test_space_member_can_dissolve_guest_sharer_shared_eddy(self) -> None:
        from share_policy import check_share_dissolve_authority

        cfg = {
            "origin": "shared",
            "share_creator": "333",
            "sharer_key": "lukas",
            "from_sharer": "Lukas",
            "space_key": "family",
        }
        with patch("share_policy.get_registry", return_value=self.FAMILY_REGISTRY), patch(
            "share_targets.get_registry",
            return_value=self.FAMILY_REGISTRY,
        ):
            decision = check_share_dissolve_authority(888, 9001, "222", cfg)
        self.assertTrue(decision.allowed)

    def test_creator_can_dissolve_shared_eddy(self) -> None:
        from share_policy import check_share_dissolve_authority

        cfg = {"origin": "shared", "share_creator": "111", "sharer_key": "kermit", "space_key": "family"}
        decision = check_share_dissolve_authority(888, 9001, "111", cfg)
        self.assertTrue(decision.allowed)

    def test_non_creator_cannot_dissolve_received_eddy(self) -> None:
        from share_policy import check_share_dissolve_authority

        cfg = {"origin": "received", "share_creator": "111", "from_sharer": "Kermit"}
        decision = check_share_dissolve_authority(777, 1002, "222", cfg)
        self.assertFalse(decision.allowed)
        self.assertIn("Kermit", decision.reason or "")

    def test_regular_eddy_allows_anyone_with_practice_access(self) -> None:
        from share_policy import check_share_dissolve_authority

        decision = check_share_dissolve_authority(555, 1001, "222", {"origin": None})
        self.assertTrue(decision.allowed)
