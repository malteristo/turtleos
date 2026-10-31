"""Turtle and Spirit are asked to end on the talk. The speaker already reads it.

A prompt that drops the instruction is the control: the check has to be able
to fail, or a reply can go back to speaking the whole page.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import house_speaker
from magic_prompt import build_magic_prompt
from prompts import (
    build_craft_channel_prompt,
    build_health_channel_prompt,
    build_native_eddy_prompt,
)


def _dropped(prompt: str) -> str:
    return prompt.replace(house_speaker.TALK_CLOSE, "")


class TalkCloseTests(unittest.TestCase):
    def test_the_instruction_is_a_mark_the_speaker_reads(self) -> None:
        self.assertIn("relevant context", house_speaker.TALK_CLOSE)
        self.assertIn("numbered list", house_speaker.TALK_CLOSE)
        self.assertIn("ends with a question mark", house_speaker.TALK_CLOSE)
        self.assertIn("A finished answer does not", house_speaker.TALK_CLOSE)
        self.assertNotIn("a few sentences", house_speaker.TALK_CLOSE)
        self.assertTrue(house_speaker.TALK_MARK.search("The talk"))
        page = "PAGE-SECRET the longer writing."
        talk = "The afternoon is open."
        reply = f"{page}\n\nThe talk\n{talk}"
        self.assertEqual(house_speaker.spoken(reply), talk)
        self.assertNotIn("PAGE-SECRET", house_speaker.spoken(reply) or "")

    @patch("prompts.get_pd", return_value="/nonexistent/practice")
    def test_a_home_eddy_is_asked_to_end_on_the_talk(self, _pd) -> None:
        prompt = build_native_eddy_prompt()
        self.assertIn(house_speaker.TALK_CLOSE, prompt)
        self.assertNotIn(house_speaker.TALK_CLOSE, _dropped(prompt))

    @patch("prompts.build_discord_prompt", return_value="practice block")
    @patch("prompts._build_context_resonance", return_value="")
    def test_boom_and_health_and_spirit_are_asked_too(self, _ctx, _practice) -> None:
        craft = build_craft_channel_prompt("craft")
        self.assertIn(house_speaker.TALK_CLOSE, craft)
        self.assertNotIn(house_speaker.TALK_CLOSE, _dropped(craft))

        with patch("prompts.get_pd", return_value="/nonexistent/practice"):
            health = build_health_channel_prompt()
        self.assertIn(house_speaker.TALK_CLOSE, health)
        self.assertNotIn(house_speaker.TALK_CLOSE, _dropped(health))

        spirit = build_magic_prompt(Path("/no/workshop"))
        self.assertIn(house_speaker.TALK_CLOSE, spirit)
        self.assertNotIn(house_speaker.TALK_CLOSE, _dropped(spirit))


if __name__ == "__main__":
    unittest.main()
