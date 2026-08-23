import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from content_fetch import (
    _guess_attachment_mime,
    _is_transient_gemini_error,
    decode_text_attachment,
    extract_attachments,
    format_text_attachments_for_dialogue,
    is_text_attachment,
    preprocess_attachments,
    split_text_and_vision_attachments,
)


class GuessAttachmentMimeTests(unittest.TestCase):
    def test_mp_jpg_extension(self) -> None:
        self.assertEqual(_guess_attachment_mime("PXL_20260521_165718629.MP.jpg"), "image/jpeg")

    def test_regular_jpeg(self) -> None:
        self.assertEqual(_guess_attachment_mime("photo.jpeg"), "image/jpeg")

    def test_message_txt(self) -> None:
        self.assertEqual(_guess_attachment_mime("message.txt"), "text/plain")

    def test_markdown(self) -> None:
        self.assertEqual(_guess_attachment_mime("notes.md"), "text/markdown")


class TextAttachmentClassifyTests(unittest.TestCase):
    def test_message_txt_even_with_octet_stream(self) -> None:
        self.assertTrue(is_text_attachment("application/octet-stream", "message.txt"))

    def test_images_are_not_text(self) -> None:
        self.assertFalse(is_text_attachment("image/jpeg", "photo.jpg"))


class DecodeTextAttachmentTests(unittest.TestCase):
    def test_utf8(self) -> None:
        self.assertEqual(decode_text_attachment("hello café".encode("utf-8")), "hello café")

    def test_truncates_huge_pastes(self) -> None:
        from content_fetch import MAX_TEXT_INLINE_CHARS

        huge = ("x" * (MAX_TEXT_INLINE_CHARS + 50)).encode("utf-8")
        out = decode_text_attachment(huge, "message.txt")
        self.assertIn("truncated", out)
        self.assertLess(len(out), MAX_TEXT_INLINE_CHARS + 200)


class FormatTextAttachmentsTests(unittest.TestCase):
    def test_message_txt_is_primary_body(self) -> None:
        primary, extras = format_text_attachments_for_dialogue(
            [("text/plain", b"Long article body here.", "message.txt")]
        )
        self.assertEqual(primary, "Long article body here.")
        self.assertEqual(extras, "")

    def test_named_txt_stays_labeled_when_alongside_message_txt(self) -> None:
        primary, extras = format_text_attachments_for_dialogue(
            [
                ("text/plain", b"pasted body", "message.txt"),
                ("text/plain", b"notes", "notes.txt"),
            ]
        )
        self.assertEqual(primary, "pasted body")
        self.assertIn("notes.txt", extras)
        self.assertIn("notes", extras)


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

    async def test_message_txt_inlines_without_gemini(self) -> None:
        genai = MagicMock()
        result = await preprocess_attachments(
            [("text/plain", b"Article text from X.", "message.txt")],
            genai_module=genai,
            api_key="test-key",
        )
        self.assertIn("Article text from X.", result)
        self.assertIn("message.txt", result)
        genai.Client.assert_not_called()

    async def test_text_plus_image_inlines_text_and_calls_gemini(self) -> None:
        genai = MagicMock()
        client = MagicMock()
        genai.Client.return_value = client
        response_ok = MagicMock()
        response_ok.text = "screenshot of a chart"
        client.aio.models.generate_content = AsyncMock(return_value=response_ok)

        result = await preprocess_attachments(
            [
                ("text/plain", b"caption", "message.txt"),
                ("image/png", b"img", "shot.png"),
            ],
            genai_module=genai,
            api_key="test-key",
        )
        self.assertIn("caption", result)
        self.assertIn("screenshot of a chart", result)
        client.aio.models.generate_content.assert_awaited_once()


class ExtractAttachmentsMimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_guesses_mime_when_content_type_missing(self) -> None:
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

    async def test_message_txt_with_octet_stream_is_extracted(self) -> None:
        att = MagicMock()
        att.content_type = "application/octet-stream"
        att.filename = "message.txt"
        att.size = 20
        att.read = AsyncMock(return_value=b"long paste body")

        message = MagicMock()
        message.attachments = [att]

        extracted = await extract_attachments(message)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0][0], "text/plain")
        self.assertEqual(extracted[0][2], "message.txt")


class SplitAttachmentsTests(unittest.TestCase):
    def test_split(self) -> None:
        text, vision = split_text_and_vision_attachments(
            [
                ("text/plain", b"a", "message.txt"),
                ("image/png", b"b", "x.png"),
            ]
        )
        self.assertEqual(len(text), 1)
        self.assertEqual(len(vision), 1)


if __name__ == "__main__":
    unittest.main()
