"""Split-bot deploy/health unit — River + Turtle treated as one ops surface."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import canary
from runtime.readiness import required_service_labels, river_bot_token_configured


class TestRiverTokenConfigured(unittest.TestCase):
    def test_token_set(self):
        with patch.dict(os.environ, {"RIVER_BOT_TOKEN": "fake-token"}, clear=False):
            self.assertTrue(canary.river_bot_token_configured())
            self.assertTrue(river_bot_token_configured())

    def test_token_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "RIVER_BOT_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(canary, "_ensure_repo_env"):
                with patch("runtime.readiness._ensure_repo_env"):
                    self.assertFalse(canary.river_bot_token_configured())
                    self.assertFalse(river_bot_token_configured())


class TestCheckRiverBotAlive(unittest.TestCase):
    def test_skips_when_single_bot(self):
        with patch.object(canary, "river_bot_token_configured", return_value=False):
            status, detail = canary.check_river_bot_alive()
        self.assertEqual(status, "green")
        self.assertIn("single-bot", detail)

    def test_checks_launchd_when_split_bot(self):
        with patch.object(canary, "river_bot_token_configured", return_value=True):
            with patch.object(canary, "check_launchd_label", return_value=("green", "PID 99")) as mock_check:
                status, detail = canary.check_river_bot_alive()
        self.assertEqual(status, "green")
        self.assertEqual(detail, "PID 99")
        mock_check.assert_called_once_with("com.turtle.river")


class TestRequiredServiceLabels(unittest.TestCase):
    def test_discord_only_without_river_token(self):
        with patch("runtime.readiness.river_bot_token_configured", return_value=False):
            self.assertEqual(required_service_labels(), ["com.turtle.discord"])

    def test_includes_river_when_split_bot(self):
        with patch("runtime.readiness.river_bot_token_configured", return_value=True):
            self.assertEqual(
                required_service_labels(),
                ["com.turtle.discord", "com.turtle.river"],
            )


class TestRestartScript(unittest.TestCase):
    def test_script_mentions_both_labels(self):
        script = Path(__file__).resolve().parent.parent / "restart.sh"
        text = script.read_text(encoding="utf-8")
        self.assertIn("com.turtle.discord", text)
        self.assertIn("com.turtle.river", text)
        self.assertIn("split-bot", text)


if __name__ == "__main__":
    unittest.main()
