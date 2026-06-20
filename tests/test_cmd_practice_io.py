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

    async def test_reads_small_file(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.is_readable", return_value=True), patch(
            "cmd_practice_io.get_pd", return_value="/practice"
        ), patch("cmd_practice_io.read_safe", return_value="# Hello\n"), patch(
            "cmd_practice_io.obsidian_link", return_value="[[bright.md]]"
        ):
            await cpio.cmd_read(message, ["bright.md"])
        body = message.reply.await_args[0][0]
        self.assertIn("Hello", body)


class TestCmdLs(unittest.IsolatedAsyncioTestCase):
    async def test_lists_markdown_files(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "notes.md"), "w").close()
            with patch("cmd_practice_io.get_pd", return_value=tmp), patch(
                "cmd_practice_io.obsidian_link", side_effect=lambda p: f"[[{p}]]"
            ):
                await cpio.cmd_ls(message, [])
        body = message.reply.await_args[0][0]
        self.assertIn("notes.md", body)

    async def test_missing_directory(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.get_pd", return_value="/practice"):
            await cpio.cmd_ls(message, ["missing"])
        self.assertIn("not found", message.reply.await_args[0][0])


class TestCmdSearch(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_to_tool(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.execute_tos_tool", return_value="match: turtle.md"):
            await cpio.cmd_search(message, ["turtle"])
        message.reply.assert_awaited_once_with("match: turtle.md", mention_author=False)


if __name__ == "__main__":
    unittest.main()
