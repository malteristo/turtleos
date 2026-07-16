"""Tests for Continuity Engine Slice 2 theme confirm."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import continuity_confirm as cc
import continuity_engine as ce
import yaml


class TestThemeConfirmHelpers(unittest.TestCase):
    def test_compose_single_and_multi(self) -> None:
        one = cc.compose_theme_confirm_text(["earlier evening walks"])
        self.assertIn("this feels live", one)
        self.assertIn("• earlier evening walks", one)
        self.assertIn("Keep them in mind", one)
        self.assertNotIn("alive", one.lower())
        self.assertNotIn("knot", one.lower())

        multi = cc.compose_theme_confirm_text(["A", "B"])
        self.assertIn("these feel live", multi)
        self.assertIn("• A", multi)
        self.assertIn("• B", multi)

    def test_apply_keep_writes_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kept = cc.apply_keep_themes(tmp, ["earlier evening walks", "weekend trip"])
            self.assertEqual(kept, ["earlier evening walks", "weekend trip"])
            labels = [t["label"] for t in ce.list_active_threads(tmp)]
            self.assertEqual(labels, ["earlier evening walks", "weekend trip"])
            alive_path = Path(tmp) / "state" / "alive.yaml"
            self.assertTrue(alive_path.exists())
            data = yaml.safe_load(alive_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["active_threads"]), 2)

    def test_apply_keep_idempotent_on_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cc.apply_keep_themes(tmp, ["sleep rhythm"])
            cc.apply_keep_themes(tmp, ["sleep rhythm"])
            self.assertEqual(len(ce.list_active_threads(tmp)), 1)


class TestOfferThemeConfirm(unittest.IsolatedAsyncioTestCase):
    async def test_offer_posts_reply_with_view(self) -> None:
        message = MagicMock()
        message.channel.id = 99
        message.reply = AsyncMock()

        with patch("mage.get_pd", return_value="/tmp/practice"):
            sent = await cc.offer_theme_confirm(
                message, ["earlier evening walks"], practice_dir="/tmp/practice"
            )

        self.assertTrue(sent)
        message.reply.assert_awaited_once()
        kwargs = message.reply.await_args.kwargs
        self.assertIn("view", kwargs)
        self.assertIn("earlier evening walks", message.reply.await_args.args[0])

    async def test_offer_skips_empty(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        sent = await cc.offer_theme_confirm(message, [])
        self.assertFalse(sent)
        message.reply.assert_not_awaited()


class TestCmdCheckpointOffersConfirm(unittest.IsolatedAsyncioTestCase):
    async def test_checkpoint_offers_confirm_after_surface(self) -> None:
        import cmd_sessions as cs
        import story_notes
        from sessions import CheckpointResult

        message = MagicMock()
        message.channel.id = 2
        message.channel.parent_id = None
        message.reply = AsyncMock()

        note = story_notes.EddyNoteResult(
            note_path=Path("/tmp/practice/story/eddies/2-x.md"),
            entry_text="body",
            preview_text="Preview of the talk.",
            proposed_themes=["earlier evening walks"],
        )
        result = CheckpointResult(trigger="manual", eddy_note=note)

        class _FakeEmbed:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def set_footer(self, **kwargs):
                pass

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}] * 4,
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
            "cmd_sessions.get_pd", return_value="/tmp/practice"
        ), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ), patch(
            "cmd_sessions._offer_theme_confirm_if_any", new_callable=AsyncMock
        ) as offer:
            await cs.cmd_checkpoint(message)

        offer.assert_awaited_once()
        self.assertEqual(offer.await_args.args[1], result)


if __name__ == "__main__":
    unittest.main()
