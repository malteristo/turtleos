"""Backfill reads a past conversation without lying about when it happened.

The positive control is first and deliberate: a genuine Turtle reply must land
in the history as ``assistant``. Without it the whole suite is satisfiable by a
``build_history`` that returns ``[]``, which is precisely the shape of a guard
that reports success while blind (Defect Set 01: twenty of twenty-eight).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "backfill_eddy_notes", ROOT / "scripts" / "backfill_eddy_notes.py"
)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)

def snowflake_for(when: datetime) -> str:
    """Inverse of ``backfill.snowflake_time`` — build an id that decodes to a
    given moment. Computing the fixtures rather than writing out 19-digit
    literals keeps real-looking ids out of a tracked file entirely, which is
    also what the repo's own sanitation guard asks for."""
    ms = int(when.timestamp() * 1000)
    return str((ms - backfill.DISCORD_EPOCH_MS) << 22)


# Synthetic actors. A test that needs a real bot id is testing the deployment.
TURTLE = str(10**18 + 1)
RIVER = str(10**18 + 2)

EARLY = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def user_msg(name: str, content: str, **extra) -> dict:
    return {"author": {"id": "701", "username": name, "bot": False}, "content": content, **extra}


def bot_msg(bot_id: str, content: str) -> dict:
    return {"author": {"id": bot_id, "username": "bot", "bot": True}, "content": content}


class BuildHistoryTests(unittest.TestCase):
    def test_turtle_reply_becomes_an_assistant_turn(self):
        """Positive control — if this fails, nothing below means anything."""
        history = backfill.build_history(
            [user_msg("kermit", "what do you think?"), bot_msg(TURTLE, "I think this.")],
            TURTLE,
        )
        self.assertEqual(
            history,
            [
                {"role": "user", "content": "[kermit]: what do you think?"},
                {"role": "assistant", "content": "I think this."},
            ],
        )

    def test_other_bots_are_furniture(self):
        """River's embeds and the eddy bar are not conversation."""
        history = backfill.build_history(
            [bot_msg(RIVER, "**Eddy bar**"), user_msg("kermit", "hi"), bot_msg(TURTLE, "hello")],
            TURTLE,
        )
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])

    def test_thread_open_marker_is_dropped(self):
        history = backfill.build_history(
            [bot_msg(TURTLE, "🧵 opened"), bot_msg(TURTLE, "real reply")], TURTLE
        )
        self.assertEqual(history, [{"role": "assistant", "content": "real reply"}])

    def test_author_prefix_is_preserved_for_the_witness_layer(self):
        """INT-040: authorship is parsed back out of this prefix downstream, so
        dropping it here would re-create the misattribution in a new place."""
        history = backfill.build_history([user_msg("second-member", "my turn")], TURTLE)
        self.assertEqual(history[0]["content"], "[second-member]: my turn")

    def test_global_name_wins_over_username(self):
        msg = {"author": {"id": "7", "username": "raw", "global_name": "Shown", "bot": False},
               "content": "hi"}
        self.assertEqual(backfill.build_history([msg], TURTLE)[0]["content"], "[Shown]: hi")

    def test_attachment_only_message_survives_as_a_note(self):
        """Pinned against ``helpers.load_thread_history`` verbatim, including its
        double mention of the filename. Fidelity to the live shape is the point;
        a tidier backfill would produce notes subtly unlike every existing one."""
        history = backfill.build_history(
            [user_msg("kermit", "", attachments=[{"filename": "shot.png"}])], TURTLE
        )
        self.assertEqual(
            history[0]["content"], "[kermit]: (attachment: shot.png) [attached: shot.png]"
        )

    def test_empty_user_message_is_dropped(self):
        self.assertEqual(backfill.build_history([user_msg("kermit", "   ")], TURTLE), [])


class SnowflakeTimeTests(unittest.TestCase):
    def test_id_decodes_to_its_real_creation_time(self):
        """The whole age-honesty of a backfilled note rests on this: the stamp
        comes from the message id, never from the clock at write time."""
        known = backfill.snowflake_time(snowflake_for(LATE))
        self.assertEqual(known.tzinfo, timezone.utc)
        self.assertEqual(known.date().isoformat(), "2026-07-30")

    def test_ordering_is_preserved(self):
        a = backfill.snowflake_time(snowflake_for(EARLY))
        b = backfill.snowflake_time(snowflake_for(LATE))
        self.assertLess(a, b)


class ComposeEntryAgeTests(unittest.TestCase):
    """``occurred_at`` exists so a March conversation is not dated today."""

    def test_occurred_at_overrides_the_clock(self):
        from story_notes import _compose_entry

        when = datetime(2026, 3, 18, 9, 30, tzinfo=timezone.utc)
        entry = _compose_entry(
            123, "an old eddy", "backfill", "what it held", None, [], None, None,
            occurred_at=when,
        )
        self.assertIn("2026-03-18T09:30:00", entry)
        self.assertIn("trigger: backfill", entry)

    def test_default_is_still_now(self):
        """Live callers pass nothing and must be unaffected."""
        from story_notes import _compose_entry
        from helpers import local_now

        entry = _compose_entry(123, "t", "idle", "held", None, [], None, None)
        self.assertIn(f"timestamp: '{local_now().date().isoformat()}", entry)


class ArgumentTests(unittest.TestCase):
    def test_defaults_target_the_operator_and_the_story_layer_start(self):
        """--root defaults to None and is resolved from the registry, so no
        practitioner's name is hardcoded in a repo headed for publication."""
        args = backfill.parse_args([])
        self.assertIsNone(args.root)
        self.assertEqual(args.before, backfill.STORY_LAYER_START)
        self.assertFalse(args.i_have_consent)

    def test_consent_flag_is_not_set_by_default(self):
        """A script must not be able to grant itself access to someone's record."""
        self.assertFalse(backfill.parse_args(["--root", "another-practitioner"]).i_have_consent)


if __name__ == "__main__":
    unittest.main()
