"""state/context.md is a reader, not a file that exists.

The same helper feeds the native prompt, the craft prompt, and the
eddy-open dimension row. A planted file must appear; whitespace must
not. Removing the call is the positive control.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import continuity_open as co
import practitioner_context as pc
from prompts import (
    build_craft_channel_prompt,
    build_health_channel_prompt,
    build_native_eddy_prompt,
)


PLANTED = "PLANTED-CONTEXT-9c2e-must-reach-the-prompt"


def _write_context(root: str, body: str) -> None:
    path = Path(root) / "state"
    path.mkdir(parents=True, exist_ok=True)
    (path / "context.md").write_text(body, encoding="utf-8")


class LoaderTests(unittest.TestCase):
    def test_missing_and_blank_are_the_same(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pc.load_practitioner_context(tmp), "")
            self.assertFalse(pc.practitioner_context_loaded(tmp))
            _write_context(tmp, "   \n")
            self.assertEqual(pc.load_practitioner_context(tmp), "")
            self.assertFalse(pc.practitioner_context_loaded(tmp))

    def test_nonempty_file_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, PLANTED)
            self.assertEqual(pc.load_practitioner_context(tmp), PLANTED)
            self.assertTrue(pc.practitioner_context_loaded(tmp))
            block = pc.practitioner_context_block(tmp)
            self.assertIn(pc.CONTEXT_HEADER, block)
            self.assertIn(PLANTED, block)


class PromptWireTests(unittest.TestCase):
    def test_native_prompt_carries_planted_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, PLANTED)
            with patch("prompts.get_pd", return_value=tmp):
                with patch("prompts.load_character_file", return_value="You are Turtle"):
                    with patch("prompts.get_mage_type", return_value="mage"):
                        prompt = build_native_eddy_prompt()
        self.assertIn(PLANTED, prompt)
        self.assertIn(pc.CONTEXT_HEADER, prompt)

    def test_craft_prompt_carries_planted_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, PLANTED)
            with patch("prompts.build_discord_prompt", return_value="practice"):
                with patch("prompts._build_context_resonance", return_value=""):
                    with patch("prompts.load_character_file", return_value="You are Turtle"):
                        with patch("prompts.get_pd", return_value=tmp):
                            prompt = build_craft_channel_prompt("craft")
        self.assertIn(PLANTED, prompt)

    def test_native_prompt_omits_blank_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, "\n")
            with patch("prompts.get_pd", return_value=tmp):
                with patch("prompts.load_character_file", return_value="You are Turtle"):
                    with patch("prompts.get_mage_type", return_value="mage"):
                        prompt = build_native_eddy_prompt()
        self.assertNotIn(pc.CONTEXT_HEADER, prompt)

    def test_health_prompt_carries_planted_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, PLANTED)
            with patch("prompts.load_character_file", return_value="You are Turtle"):
                with patch("prompts._build_context_resonance", return_value=""):
                    with patch("mage.get_pd", return_value=tmp):
                        prompt = build_health_channel_prompt("health")
        self.assertIn(PLANTED, prompt)
        self.assertIn(pc.CONTEXT_HEADER, prompt)

    def test_reader_call_is_in_the_native_builder(self) -> None:
        source = inspect.getsource(build_native_eddy_prompt)
        self.assertIn("practitioner_context_block", source)
        self.assertIn("get_pd()", source)

    def test_reader_call_is_in_the_health_builder(self) -> None:
        source = inspect.getsource(build_health_channel_prompt)
        self.assertIn("practitioner_context_block", source)
        self.assertIn("get_pd()", source)


class DimensionShareTests(unittest.TestCase):
    def test_whitespace_is_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, "  \n")
            loads = co.dimension_loads(tmp, thread_loaded=True)
        self.assertEqual(loads["context"], "not loaded — file absent")

    def test_same_helper_as_the_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_context(tmp, PLANTED)
            loads = co.dimension_loads(tmp, thread_loaded=False)
            self.assertEqual(loads["context"], "loaded")
            self.assertTrue(pc.practitioner_context_loaded(tmp))


if __name__ == "__main__":
    unittest.main()
