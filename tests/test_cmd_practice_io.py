"""Tests for practice-root browse commands."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import cmd_practice_io as cpio


class TestCmdRead(unittest.IsolatedAsyncioTestCase):
    async def test_usage_without_args(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        await cpio.cmd_read(message, [])
        self.assertIn("which note", message.reply.await_args[0][0])

    async def test_reads_small_file_inline_without_web_base(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.PRACTICE_WEB_BASE", ""), patch(
            "cmd_practice_io.is_readable", return_value=True
        ), patch("cmd_practice_io.get_pd", return_value="/practice"), patch(
            "cmd_practice_io.read_safe", return_value="# Hello\n"
        ), patch("cmd_practice_io.obsidian_link", return_value="[[sessions/2026-07-09.md]]"):
            await cpio.cmd_read(message, ["sessions/2026-07-09.md"])
        body = message.reply.await_args[0][0]
        self.assertIn("Hello", body)

    async def test_reads_via_browser_embed_when_web_base_set(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        captured: dict = {}

        class FakeEmbed:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def add_field(self, **kwargs):
                captured.setdefault("fields", []).append(kwargs)

            def set_footer(self, **kwargs):
                captured["footer"] = kwargs

        with patch("cmd_practice_io.discord.Embed", FakeEmbed), patch(
            "cmd_practice_io.PRACTICE_WEB_BASE", "http://127.0.0.1:8080"
        ), patch("cmd_practice_io.is_readable", return_value=True), patch(
            "cmd_practice_io.resolve_artifact_path", return_value="/practice/sessions/2026-07-09.md"
        ), patch("cmd_practice_io.read_safe", return_value="# Hello\nworld"), patch(
            "cmd_practice_io.obsidian_link",
            return_value="http://127.0.0.1:8080/kermit/sessions/2026-07-09.md",
        ):
            await cpio.cmd_read(message, ["sessions/2026-07-09.md"])
        self.assertEqual(captured.get("url"), "http://127.0.0.1:8080/kermit/sessions/2026-07-09.md")
        self.assertIn("browser", (captured.get("description") or "").lower())
        message.reply.assert_awaited_once()
        self.assertIn("embed", message.reply.await_args.kwargs)


class TestCmdExport(unittest.IsolatedAsyncioTestCase):
    async def test_export_replies_with_compact_handoff_and_attachment(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()

        with patch("cmd_practice_io.is_readable", return_value=True), patch(
            "cmd_practice_io.resolve_artifact_path", return_value="/practice/sessions/a.md"
        ), patch("cmd_practice_io.os.path.isfile", return_value=True), patch(
            "cmd_practice_io.read_safe", return_value="# Hello\n" * 20
        ):
            await cpio.cmd_export(message, ["sessions/a.md"])

        args, kwargs = message.reply.await_args
        self.assertIn("Download", args[0])
        self.assertIn("⋯", args[0])
        self.assertIn("file", kwargs)
        self.assertNotIn("embed", kwargs)
        self.assertNotIn("view", kwargs)


if __name__ == "__main__":
    unittest.main()
