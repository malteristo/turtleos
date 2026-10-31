"""A magic session can be read back, and a reasoning field cannot be stored."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import session_record as sr

PLANTED = "PLANTED_REASONING_TRACE_9f3c"
REPLY_ONLY = "REPLY_ONLY_PHRASE_7ab2"


class SessionRecord(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.when = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_two_turns_round_trip_into_a_readable_session(self) -> None:
        sr.append_turn(
            self.root, "1559",
            practitioner="...",
            reply="Here is what is there.",
            tools=[{"name": "workshop_read", "args": {"path": "desk/state.md"}, "result": "x" * 50}],
            model="claude-sonnet-5-5",
            usage={"input_tokens": 10, "output_tokens": 4, "calls": 1, "ignored": "no"},
            recorded_at=self.when,
        )
        sr.append_turn(
            self.root, "1559",
            practitioner=".",
            reply="Going on.",
            model="claude-sonnet-5-5",
            recorded_at=self.when,
        )
        text = sr.render_session(self.root, "1559")
        self.assertIn("**Practitioner:** ...", text)
        self.assertIn("**Practitioner:** .", text)
        self.assertIn("`workshop_read`", text)
        self.assertIn("desk/state.md", text)
        self.assertEqual(len(sr.read_turns(self.root, "1559")), 2)

    def test_a_reasoning_field_is_dropped_and_the_visible_reply_is_kept(self) -> None:
        sr.append_turn(
            self.root, "1559",
            practitioner="what happened",
            reply=f"the reply mentions thinking and {REPLY_ONLY}",
            tools=[{"name": "workshop_git", "args": {"verb": "status"}, "result": "clean"}],
            thinking=PLANTED,
            reasoning=PLANTED,
            chain_of_thought=PLANTED,
            recorded_at=self.when,
        )
        raw = sr.session_path(self.root, "1559").read_text(encoding="utf-8")
        self.assertNotIn(PLANTED, raw)
        self.assertNotIn('"thinking"', raw)
        self.assertIn(REPLY_ONLY, raw)
        ground = sr.render_key_ground(self.root, "1559")
        self.assertIn("what happened", ground)
        self.assertIn("workshop_git", ground)
        self.assertNotIn(REPLY_ONLY, ground)
        self.assertNotIn(PLANTED, ground)

    def test_a_long_tool_result_is_cut(self) -> None:
        sr.append_turn(
            self.root, "1",
            practitioner="read",
            reply="done",
            tools=[{"name": "workshop_read", "args": {"path": "a.md"}, "result": "y" * (sr.SUMMARY_MAX + 500)}],
            recorded_at=self.when,
        )
        turn = sr.read_turns(self.root, "1")[0]
        self.assertEqual(len(turn["tools"][0]["summary"]), sr.SUMMARY_MAX + 1)
        self.assertTrue(turn["tools"][0]["summary"].endswith("…"))

    def test_oversized_arguments_do_not_land_whole(self) -> None:
        sr.append_turn(
            self.root, "1",
            practitioner="write",
            reply="done",
            tools=[{"name": "workshop_write", "args": {"content": "z" * (sr.ARGS_MAX + 500)}, "result": "ok"}],
            recorded_at=self.when,
        )
        args = sr.read_turns(self.root, "1")[0]["tools"][0]["arguments"]
        self.assertTrue(args.get("_truncated"))
        self.assertLess(len(json.dumps(args)), sr.ARGS_MAX + 80)

    def test_the_chat_is_in_the_transcript_and_the_key_ground_stays_his_words(self) -> None:
        sr.append_event(
            self.root, "1559", kind="greeting", actor="river",
            text="Covenant held.", briefing="abc", recorded_at=self.when,
        )
        sr.append_event(
            self.root, "1559", kind="join", actor="river",
            text="River added Spirit", recorded_at=self.when,
        )
        sr.append_event(
            self.root, "1559", kind="trace", actor="spirit",
            text="read desk/state.md", recorded_at=self.when,
        )
        sr.append_turn(
            self.root, "1559", practitioner="...", reply="Here.",
            tools=[{"name": "workshop_read", "args": {"path": "desk/state.md"}, "result": "ok"}],
            recorded_at=self.when,
        )
        text = sr.render_session(self.root, "1559")
        self.assertLess(text.index("**greeting**"), text.index("**join**"))
        self.assertLess(text.index("**trace**"), text.index("**Practitioner:** ..."))
        self.assertIn("River added Spirit", text)
        ground = sr.render_key_ground(self.root, "1559")
        self.assertIn("...", ground)
        self.assertIn("workshop_read", ground)
        self.assertNotIn("Covenant held.", ground)
        self.assertNotIn("River added Spirit", ground)
        self.assertTrue(sr.is_greeted(self.root, "1559"))
        self.assertFalse(sr.is_released(self.root, "1559"))
        sr.append_event(
            self.root, "1559", kind="release", actor="spirit",
            text="Released.", recorded_at=self.when,
        )
        self.assertTrue(sr.is_released(self.root, "1559"))

    def test_a_turn_only_file_and_a_missing_file_were_not_greeted(self) -> None:
        sr.append_turn(
            self.root, "old", practitioner="hi", reply="there", recorded_at=self.when,
        )
        self.assertFalse(sr.is_greeted(self.root, "old"))
        self.assertFalse(sr.is_released(self.root, "old"))
        self.assertFalse(sr.is_greeted(self.root, "absent"))
        self.assertFalse(sr.is_released(self.root, "absent"))

    def test_a_missing_practice_root_writes_nothing(self) -> None:
        missing = self.root / "nope"
        self.assertIsNone(sr.append_turn(missing, "1", practitioner="hi", reply="there"))
        self.assertFalse(sr.session_path(missing, "1").exists())
