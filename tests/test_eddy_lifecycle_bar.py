"""Tests for in-thread lifecycle bar eligibility and state."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import eddy_lifecycle_bar as bar


class TestLifecycleBarEligibility(unittest.TestCase):
    def test_bootstrap_allows_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertTrue(bar.bootstrap_bar_eligible(11, 22))

    def test_live_blocks_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))

    def test_blocks_awaiting_intake(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=False):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=True):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))
                    self.assertFalse(bar.bootstrap_bar_eligible(11, 22))

    def test_allows_live_eddy(self) -> None:
        with patch.object(bar, "standing_lifecycle_bar_enabled", return_value=True):
            with patch("eddy_spawn.is_awaiting_title", return_value=False):
                with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                    with patch("prompts.uses_native_turtle_prompt", return_value=True):
                        self.assertTrue(bar.lifecycle_bar_eligible(11, 22))

    def test_native_enables_standing_bar(self) -> None:
        self.assertTrue(bar.standing_lifecycle_bar_enabled())


class TestLifecycleBarState(unittest.TestCase):
    def test_mark_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lifecycle_bar.json"
            with patch.object(bar, "_state_path", return_value=str(path)):
                self.assertFalse(bar.is_lifecycle_bar_active(99))
                bar._mark_bar_message(99, 12345)
                self.assertTrue(bar.is_lifecycle_bar_active(99))
                self.assertEqual(bar._load_state()["99"], 12345)
                bar.clear_lifecycle_bar_state(99)
                self.assertFalse(bar.is_lifecycle_bar_active(99))


class TestLifecycleBarArtifactsButton(unittest.TestCase):
    def test_eddy_bar_phased_flow_pick_and_live_actions(self) -> None:
        src = (Path(__file__).resolve().parents[1] / "eddy_lifecycle_bar.py").read_text(
            encoding="utf-8"
        )
        block = src.split("class EddyLifecycleBarView")[1].split("class EddyDissolveConfirmView")[0]
        self.assertIn("eddy:lifecycle:flowpick:", block)
        self.assertIn('label="checkpoint"', block)
        self.assertIn('label="share"', block)
        self.assertIn('phase == "live"', block)


class TestBarPhaseState(unittest.TestCase):
    def test_phase_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            phase_path = Path(tmp) / "bar_phase.json"
            with patch.object(bar, "_phase_state_path", return_value=str(phase_path)):
                self.assertIsNone(bar.get_bar_phase(42))
                bar.set_bar_phase(42, "bootstrap")
                self.assertEqual(bar.get_bar_phase(42), "bootstrap")
                bar.set_bar_phase(42, "live")
                self.assertEqual(bar.get_bar_phase(42), "live")
                bar.clear_bar_phase(42)
                self.assertIsNone(bar.get_bar_phase(42))


class TestPractitionerAuthor(unittest.TestCase):
    def test_spirit_counts_as_practitioner(self) -> None:
        class Author:
            bot = True
            id = 1487405701440733294  # SPIRIT_BOT_ID

        class Msg:
            author = Author()

        self.assertTrue(bar._is_practitioner_author(Msg()))


class TestRiverActCustomIds(unittest.TestCase):
    def test_roundtrip_simple_command(self) -> None:
        cid = bar._encode_act_custom_id(1234567890, "!checkpoint")
        self.assertIsNotNone(cid)
        channel_id, command = bar._decode_act_custom_id(cid)
        self.assertEqual(channel_id, 1234567890)
        self.assertEqual(command, "checkpoint")

    def test_roundtrip_thread_command(self) -> None:
        cmd = '!thread "my topic" --model local'
        cid = bar._encode_act_custom_id(99, cmd)
        self.assertIsNotNone(cid)
        _, decoded = bar._decode_act_custom_id(cid)
        self.assertEqual(decoded, cmd.lstrip("!"))

    def test_long_fetch_uses_hash_fallback(self) -> None:
        cmd = "!fetch https://example.com/" + ("a" * 120)
        cid = bar._encode_act_custom_id(42, cmd)
        self.assertIsNotNone(cid)
        self.assertIn(":h:", cid)
        _, decoded = bar._decode_act_custom_id(cid)
        self.assertEqual(decoded, cmd.lstrip("!"))


if __name__ == "__main__":
    unittest.main()
