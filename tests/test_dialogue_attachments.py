"""Tests for dialogue_attachments — attachment pipeline (discord_bot decomposition Slice 4)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import dialogue_attachments


class AttachmentDisplayNamesTests(unittest.TestCase):
    def test_formats_filename_and_content_type(self) -> None:
        att = MagicMock(filename="photo.png", content_type="image/png")
        self.assertEqual(
            dialogue_attachments.attachment_display_names([att]),
            "photo.png (image/png)",
        )

    def test_unknown_content_type(self) -> None:
        att = MagicMock(filename="data.bin", content_type=None)
        self.assertEqual(
            dialogue_attachments.attachment_display_names([att]),
            "data.bin (unknown)",
        )


class GatherDialogueAttachmentsTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_attachments_returns_empty(self) -> None:
        message = MagicMock(attachments=[], reference=None)

        extracted, names, note, raw, source = await dialogue_attachments.gather_dialogue_attachments(
            message
        )

        self.assertEqual(extracted, [])
        self.assertEqual(names, [])
        self.assertEqual(note, "")
        self.assertEqual(raw, [])
        self.assertEqual(source, "")

    async def test_direct_attachments_extracted(self) -> None:
        att = MagicMock(filename="doc.pdf", content_type="application/pdf")
        message = MagicMock(attachments=[att], reference=None)

        with patch(
            "dialogue_attachments.extract_attachments",
            new_callable=AsyncMock,
            return_value=[(b"data", "application/pdf", "doc.pdf")],
        ) as extract:
            extracted, names, note, raw, source = await dialogue_attachments.gather_dialogue_attachments(
                message
            )

        extract.assert_awaited_once()
        self.assertEqual(names, ["doc.pdf"])
        self.assertIn("[attached: doc.pdf]", note)
        self.assertEqual(raw, [att])
        self.assertEqual(source, "")


class AttachmentsFromForwardChainTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_failure_returns_empty(self) -> None:
        with patch("dialogue_attachments.client") as mock_client:
            mock_client.fetch_channel = AsyncMock(side_effect=Exception("network"))
            result = await dialogue_attachments.attachments_from_forward_chain((1, 100, 200))

        self.assertEqual(result, ([], [], ""))
