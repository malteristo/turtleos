"""River house picture — supply for action selection, not chatter."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from river_house import (
    attach_house_to_prompt,
    gather_house_facts,
    house_prompt_block,
    render_house_facts,
    should_withhold,
)


class RenderTests(unittest.TestCase):
    def test_drops_unknown_and_keeps_order(self) -> None:
        self.assertEqual(
            render_house_facts({"canary": "green", "last_turn": "unknown"}),
            {"canary": "green"},
        )

    def test_block_names_withhold_and_forbids_narration(self) -> None:
        block = house_prompt_block({"canary": "red", "last_turn": "in flight"})
        self.assertIn("canary: red", block)
        self.assertIn("last_turn: in flight", block)
        self.assertIn("withhold", block.lower())
        self.assertIn("Never put these facts in an act", block)

    def test_empty_facts_make_no_block(self) -> None:
        self.assertEqual(house_prompt_block({}), "")

    def test_red_or_in_flight_withholds(self) -> None:
        self.assertTrue(should_withhold({"canary": "red"}))
        self.assertTrue(should_withhold({"last_turn": "in flight"}))
        self.assertFalse(should_withhold({"canary": "green", "last_turn": "5.8h ago"}))


class GatherTests(unittest.TestCase):
    def test_planted_canary_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            history = root / "canary-history.jsonl"
            history.write_text(
                json.dumps({"overall": "red", "checks": []}) + "\n",
                encoding="utf-8",
            )
            workshop = root / "kermit"
            locks = workshop / "story" / "eddies"
            locks.mkdir(parents=True)
            (locks / "1.lock").write_text("", encoding="utf-8")
            facts = gather_house_facts(workshops=root, canary_history=history)
            self.assertEqual(facts["canary"], "red")
            self.assertEqual(facts["last_turn"], "in flight")

    def test_missing_instruments_are_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            facts = gather_house_facts(
                workshops=root / "none",
                canary_history=root / "nope.jsonl",
            )
            self.assertEqual(facts, {})


class AttachTests(unittest.TestCase):
    def test_classify_prompt_receives_the_block(self) -> None:
        import asyncio
        from river_handler import classify_river_acts

        captured: dict[str, str] = {}

        async def _fake_chat(prompt, messages, **kwargs):
            captured["prompt"] = prompt
            return '{"acts": [{"type": "offer_flow", "flow": "Navigator"}]}'

        async def _run() -> None:
            with (
                patch("river_handler.load_river_prompt", return_value="classify into JSON acts"),
                patch("river_handler.chat_ollama", new_callable=AsyncMock, side_effect=_fake_chat),
                patch(
                    "river_house.gather_house_facts",
                    return_value={"canary": "red", "last_turn": "in flight"},
                ),
            ):
                acts = await classify_river_acts("hello")
            captured["acts"] = acts

        asyncio.run(_run())
        self.assertIn("canary: red", captured["prompt"])
        self.assertIn("Never put these facts in an act", captured["prompt"])
        self.assertEqual(captured["acts"], [])
