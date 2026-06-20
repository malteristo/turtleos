"""Tests for seneschal act extraction (native vs legacy allowlists)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import discord_bot as bot
from commands import LIFECYCLE_BAR_COMMANDS, SENESCHAL_ACTION_COMMANDS


class TestSeneschalExtraction(unittest.TestCase):
    def test_native_excludes_lifecycle_trio(self) -> None:
        reply = "Save progress with `!checkpoint` or fetch with `!fetch https://example.com`."
        actions = bot._extract_contextual_actions(
            reply, allowed_commands=SENESCHAL_ACTION_COMMANDS
        )
        self.assertEqual(len(actions), 1)
        self.assertIn("fetch", actions[0][1])

    def test_legacy_includes_lifecycle(self) -> None:
        reply = "Try `!checkpoint` when you are ready."
        actions = bot._extract_contextual_actions(reply)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][1], "!checkpoint")

    def test_lifecycle_commands_disjoint_from_seneschal(self) -> None:
        overlap = LIFECYCLE_BAR_COMMANDS & SENESCHAL_ACTION_COMMANDS
        self.assertEqual(overlap, frozenset())

    def test_thread_command_on_native(self) -> None:
        reply = 'Want me to run `!thread "planning" --model local`?'
        actions = bot._extract_contextual_actions(
            reply, allowed_commands=SENESCHAL_ACTION_COMMANDS
        )
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0][1].startswith("!thread"))


if __name__ == "__main__":
    unittest.main()
