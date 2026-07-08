"""Tests for thread/eddy command handlers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import cmd_threads as ct


class _FakeThread:
    pass


class TestBuildConfigLine(unittest.TestCase):
    def test_includes_eddy_type(self) -> None:
        from state import thread_configs

        thread_configs[42] = {
            "model_label": "local",
            "model": "gemma",
            "use_api": False,
            "attunement": "native",
            "eddy_type": "standard",
        }
        line = ct.build_config_line(42)
        self.assertIn("standard", line.lower() or "Standard" in line)
        self.assertIn("gemma", line)


class TestCmdEddyCheck(unittest.IsolatedAsyncioTestCase):
    async def test_retired_message(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        await ct.cmd_eddy_check(message, [])
        self.assertIn("retired", message.reply.await_args[0][0].lower())


class TestCmdRename(unittest.IsolatedAsyncioTestCase):
    async def test_requires_thread(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.reply = AsyncMock()
        with patch.object(ct.discord, "Thread", _FakeThread):
            await ct.cmd_rename(message, [])
        self.assertIn("inside an eddy thread", message.reply.await_args[0][0])


class TestCmdNew(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_in_thread(self) -> None:
        message = MagicMock()
        message.channel = _FakeThread()
        message.reply = AsyncMock()
        with patch.object(ct.discord, "Thread", _FakeThread):
            await ct.cmd_new(message, [])
        self.assertIn("main channel", message.reply.await_args[0][0])


if __name__ == "__main__":
    unittest.main()
