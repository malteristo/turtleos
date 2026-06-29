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
        self.assertIn("Usage", message.reply.await_args[0][0])

    async def test_reads_small_file_inline_without_web_base(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.PRACTICE_WEB_BASE", ""), patch(
            "cmd_practice_io.is_readable", return_value=True
        ), patch("cmd_practice_io.get_pd", return_value="/practice"), patch(
            "cmd_practice_io.read_safe", return_value="# Hello\n"
        ), patch("cmd_practice_io.obsidian_link", return_value="[[bright.md]]"):
            await cpio.cmd_read(message, ["bright.md"])
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
            "cmd_practice_io.resolve_artifact_path", return_value="/practice/bright.md"
        ), patch("cmd_practice_io.read_safe", return_value="# Hello\nworld"), patch(
            "cmd_practice_io.obsidian_link",
            return_value="http://127.0.0.1:8080/kermit/bright.md",
        ):
            await cpio.cmd_read(message, ["bright.md"])
        self.assertEqual(captured.get("url"), "http://127.0.0.1:8080/kermit/bright.md")
        self.assertIn("browser", (captured.get("description") or "").lower())
        message.reply.assert_awaited_once()
        self.assertIn("embed", message.reply.await_args.kwargs)


class TestCmdLs(unittest.IsolatedAsyncioTestCase):
    async def test_lists_markdown_files(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "bright.md"), "w").close()
            with patch("cmd_practice_io.get_pd", return_value=tmp), patch(
                "cmd_practice_io.get_mage_type", return_value="practitioner"
            ), patch(
                "cmd_practice_io.is_artifact_directory", return_value=True
            ), patch(
                "cmd_practice_io.is_artifact_readable", return_value=True
            ), patch(
                "cmd_practice_io.obsidian_link", side_effect=lambda p: f"[[{p}]]"
            ):
                await cpio.cmd_ls(message, [])
        body = message.reply.await_args[0][0]
        self.assertIn("bright.md", body)

    async def test_denied_directory(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.get_pd", return_value="/practice"), patch(
            "cmd_practice_io.get_mage_type", return_value="practitioner"
        ), patch("cmd_practice_io.is_artifact_directory", return_value=False):
            await cpio.cmd_ls(message, ["proposals"])
        self.assertIn("!artifacts", message.reply.await_args[0][0])


class TestCmdSearch(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_to_tool(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.execute_tos_tool", return_value="match: turtle.md"):
            await cpio.cmd_search(message, ["turtle"])
        message.reply.assert_awaited_once_with("match: turtle.md", mention_author=False)


if __name__ == "__main__":
    unittest.main()
