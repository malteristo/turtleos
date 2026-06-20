"""Tests for legacy seneschal prose extraction (not on native runtime path)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

import legacy_seneschal as ls
from cmd_dispatch import LIFECYCLE_BAR_COMMANDS, SENESCHAL_ACTION_COMMANDS


class TestSeneschalExtraction(unittest.TestCase):
    def test_native_allowlist_excludes_lifecycle_trio(self) -> None:
        reply = "Save progress with `!checkpoint` or fetch with `!fetch https://example.com`."
        actions = ls.extract_contextual_actions(reply, allowed_commands=SENESCHAL_ACTION_COMMANDS)
        self.assertEqual(len(actions), 1)
        self.assertIn("fetch", actions[0][1])

    def test_legacy_allowlist_includes_lifecycle(self) -> None:
        reply = "Try `!checkpoint` when you are ready."
        actions = ls.extract_contextual_actions(reply)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][1], "!checkpoint")

    def test_lifecycle_commands_disjoint_from_seneschal(self) -> None:
        overlap = LIFECYCLE_BAR_COMMANDS & SENESCHAL_ACTION_COMMANDS
        self.assertEqual(overlap, frozenset())

    def test_thread_command_on_native_allowlist(self) -> None:
        reply = 'Want me to run `!thread "planning" --model local`?'
        actions = ls.extract_contextual_actions(reply, allowed_commands=SENESCHAL_ACTION_COMMANDS)
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0][1].startswith("!thread"))


class TestSeneschalFilter(unittest.TestCase):
    def test_drops_fetch_after_act(self) -> None:
        history = [{"role": "user", "content": "[Act: !fetch] Fetched article excerpt here"}]
        actions = [("Fetch link", "!fetch https://example.com")]
        filtered = ls.filter_seneschal_actions(actions, history)
        self.assertEqual(filtered, [])


if __name__ == "__main__":
    unittest.main()
