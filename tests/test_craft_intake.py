import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

discord_mod = MagicMock()
discord_mod.ext = MagicMock()
discord_mod.ext.tasks = MagicMock()
sys.modules.setdefault("discord", discord_mod)
sys.modules.setdefault("discord.ext", discord_mod.ext)
sys.modules.setdefault("discord.ui", MagicMock())

import craft_intake
import mage


class CraftIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved_registry)
        craft_intake._buffers.clear()

    def test_merge_craft_messages_combines_comment_and_forward(self) -> None:
        forward = MagicMock()
        forward.id = 1
        forward.content = ""
        forward.author = MagicMock(display_name="kermit")
        forward.message_snapshots = [MagicMock(content="forwarded turtle reply", embeds=[], attachments=[])]

        comment = MagicMock()
        comment.id = 2
        comment.content = "Image upload failed in my eddy."
        comment.author = forward.author
        comment.message_snapshots = []

        with patch("discord_bot._visible_message_content") as mock_visible, patch(
            "discord_bot._extract_forwarded_context", side_effect=["forwarded turtle reply", ""]
        ):
            mock_visible.side_effect = [
                ("", "forwarded turtle reply"),
                ("Image upload failed in my eddy.", ""),
            ]
            merged = craft_intake.merge_craft_messages([forward, comment])

        self.assertIn("Image upload failed", merged["merged_user"])
        self.assertIn("forwarded turtle reply", merged["merged_forward"])
        self.assertEqual(merged["message_ids"], [1, 2])

    def test_write_craft_intake_creates_files(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            evidence = {
                "message_ids": [10, 11],
                "author": "kermit",
                "merged_user": "Image upload failed in eddy.",
                "merged_forward": "The image didn't come through.",
                "merged_text": "Image upload failed in eddy.\n\nThe image didn't come through.",
                "channel_label": "craft-turtle",
                "thread_parent_id": None,
                "visibility": ["forwarded snapshot text present"],
                "dereferenced_context": "",
                "deref_refs": [(None, 123, 456)],
                "source_attachments": [],
                "snapshot_attachment_gaps": ["forward snapshot 1: no attachments in snapshot"],
                "registered_at": datetime(2026, 6, 19, 14, 29, tzinfo=timezone.utc),
            }
            with patch("craft_intake._craft_root", return_value=Path(tmp)):
                intake_rel, intake_id = craft_intake.write_craft_intake(evidence)

            intake_path = Path(tmp) / intake_rel
            backlog_path = Path(tmp) / craft_intake.CRAFT_BACKLOG
            self.assertTrue(intake_path.exists())
            self.assertTrue(backlog_path.exists())
            body = intake_path.read_text(encoding="utf-8")
            self.assertIn("Image upload failed in eddy.", body)
            self.assertIn("forward snapshot 1: no attachments", body)
            self.assertIn(intake_id, backlog_path.read_text(encoding="utf-8"))

    def test_format_craft_ack_mentions_backlog(self) -> None:
        evidence = {
            "merged_user": "Image upload failed.",
            "merged_forward": "forward text",
            "message_ids": [1, 2],
            "visibility": ["forwarded snapshot text present"],
            "dereferenced_context": "source body",
            "source_attachments": ["photo.png (image/png)"],
        }
        ack = craft_intake.format_craft_ack(evidence, "desk/craft/intake/test.md", "2026-06-19-test")
        self.assertIn("Registered", ack)
        self.assertIn("desk/craft/backlog.md", ack)
        self.assertIn("coalesced 2 Discord messages", ack)


class CraftCoalesceTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_coalesces_messages_before_flush(self) -> None:
        craft_intake._buffers.clear()
        craft_intake.CRAFT_COALESCE_SECONDS = 0.05
        client = MagicMock()

        msg1 = MagicMock()
        msg1.channel.id = 99
        msg1.author.id = 1
        msg1.channel.send = AsyncMock()

        msg2 = MagicMock()
        msg2.channel.id = 99
        msg2.author.id = 1
        msg2.channel = msg1.channel

        with patch("craft_intake.process_craft_intake", new=AsyncMock(return_value="ack")) as mock_process:
            await craft_intake.schedule_craft_intake(msg1, client)
            await craft_intake.schedule_craft_intake(msg2, client)
            await asyncio.sleep(0.12)

        mock_process.assert_awaited_once()
        processed = mock_process.await_args.args[0]
        self.assertEqual(processed, [msg1, msg2])


if __name__ == "__main__":
    unittest.main()
