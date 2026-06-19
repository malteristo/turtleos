import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from content_fetch import (
    _guess_attachment_mime,
    _is_transient_gemini_error,
    preprocess_attachments,
)


class GuessAttachmentMimeTests(unittest.TestCase):
    def test_mp_jpg_extension(self) -> None:
        self.assertEqual(_guess_attachment_mime("PXL_20260521_165718629.MP.jpg"), "image/jpeg")

    def test_regular_jpeg(self) -> None:
        self.assertEqual(_guess_attachment_mime("photo.jpeg"), "image/jpeg")


class TransientGeminiErrorTests(unittest.TestCase):
    def test_detects_unavailable_message(self) -> None:
        exc = Exception("503 UNAVAILABLE. high demand")
        self.assertTrue(_is_transient_gemini_error(exc))


class PreprocessAttachmentsRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_transient_error_then_succeeds(self) -> None:
        genai = MagicMock()
        client = MagicMock()
        genai.Client.return_value = client
        response_ok = MagicMock()
        response_ok.text = "A photo of a turtle shell."
        client.aio.models.generate_content = AsyncMock(
            side_effect=[Exception("503 UNAVAILABLE"), response_ok]
        )

        with patch("content_fetch.asyncio.sleep", new=AsyncMock()):
            result = await preprocess_attachments(
                [("image/jpeg", b"fake", "photo.jpg")],
                genai_module=genai,
                api_key="test-key",
            )

        self.assertEqual(result, "A photo of a turtle shell.")
        self.assertEqual(client.aio.models.generate_content.await_count, 2)

    async def test_failure_message_is_actionable(self) -> None:
        genai = MagicMock()
        client = MagicMock()
        genai.Client.return_value = client
        client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("503 UNAVAILABLE")
        )

        with patch("content_fetch.asyncio.sleep", new=AsyncMock()):
            result = await preprocess_attachments(
                [("image/jpeg", b"fake", "photo.jpg")],
                genai_module=genai,
                api_key="test-key",
            )

        self.assertIn("Attachment processing failed", result)
        self.assertIn("photo.jpg", result)
        self.assertIn("retry", result.lower())


class ExtractAttachmentsMimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_guesses_mime_when_content_type_missing(self) -> None:
        from content_fetch import extract_attachments

        att = MagicMock()
        att.content_type = None
        att.filename = "PXL_20260521_165718629.MP.jpg"
        att.size = 1000
        att.read = AsyncMock(return_value=b"img-bytes")

        message = MagicMock()
        message.attachments = [att]

        extracted = await extract_attachments(message)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0][0], "image/jpeg")


if __name__ == "__main__":
    unittest.main()
