"""The state check-in can be answered by a tap, and the tap stores the draft."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from health_checkin import (
    StateCapture,
    already_logged,
    mark_posted,
    open_checkin_for_message,
)
from health_checkin_ui import NO_ID, SKIP_ID, STATE_ID, YES_ID, state_checkin_buttons
from health_record_ui import apply_state_capture


class StateCheckinButtonTests(unittest.TestCase):
    def test_draft_post_offers_yes_no_and_skip(self) -> None:
        self.assertEqual(
            state_checkin_buttons(locale="de", has_draft=True),
            [("Ja", YES_ID), ("Nein, eher …", NO_ID), ("Skip", SKIP_ID)],
        )

    def test_open_question_does_not_offer_yes(self) -> None:
        ids = [custom_id for _, custom_id in state_checkin_buttons(locale="en", has_draft=False)]
        self.assertEqual(ids, [STATE_ID, SKIP_ID])
        self.assertNotIn(YES_ID, ids)

    def test_registered_view_can_answer_every_button(self) -> None:
        ids = {
            custom_id
            for _, custom_id in state_checkin_buttons(
                locale="de", has_draft=True, register_all=True
            )
        }
        self.assertEqual(ids, {YES_ID, NO_ID, SKIP_ID, STATE_ID})

    def test_the_view_is_built_from_that_list(self) -> None:
        src = (Path(__file__).resolve().parents[1] / "health_checkin_ui.py").read_text(encoding="utf-8")
        view = src.split("class StateCheckinView", 1)[1].split("def _button", 1)[0]
        self.assertIn("state_checkin_buttons", view)

    def test_unanswered_message_is_findable_and_a_logged_one_is_not(self) -> None:
        day = date(2026, 9, 23)
        with tempfile.TemporaryDirectory() as tmp:
            mark_posted(tmp, day, "99", draft="a picture")
            self.assertEqual(open_checkin_for_message(tmp, "99"), day)
            self.assertIsNone(open_checkin_for_message(tmp, "100"))
            from health_checkin import mark_logged

            mark_logged(tmp, day)
            self.assertIsNone(open_checkin_for_message(tmp, "99"))

    def test_confirm_stores_the_draft_not_the_word_ja(self) -> None:
        day = date(2026, 9, 23)
        primitive = SimpleNamespace(name="health", subject="kermit")
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "health_record.save_observation",
                return_value={"decision": "applied"},
            ) as save:
                ack = apply_state_capture(
                    root=tmp,
                    primitive=primitive,
                    actor="kermit",
                    today=day,
                    locale="de",
                    capture=StateCapture("confirm"),
                    draft="Heute ist der Stand benennbar.",
                )
            self.assertIn("bestätigt", ack or "")
            self.assertTrue(already_logged(tmp, day))
            self.assertEqual(save.call_args.kwargs["text"], "Heute ist der Stand benennbar.")
            self.assertEqual(save.call_args.kwargs["verdict"], "confirmed")
            self.assertNotIn("ja", save.call_args.kwargs["text"].lower())

    def test_confirm_without_a_draft_stores_nothing(self) -> None:
        day = date(2026, 9, 23)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("health_record.save_observation") as save:
                ack = apply_state_capture(
                    root=tmp,
                    primitive=SimpleNamespace(),
                    actor="kermit",
                    today=day,
                    locale="de",
                    capture=StateCapture("confirm"),
                    draft=None,
                )
            self.assertIsNone(ack)
            save.assert_not_called()
            self.assertFalse(already_logged(tmp, day))

    def test_skip_writes_no_observation(self) -> None:
        day = date(2026, 9, 23)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("health_record.save_observation") as save:
                ack = apply_state_capture(
                    root=tmp,
                    primitive=SimpleNamespace(),
                    actor="kermit",
                    today=day,
                    locale="de",
                    capture=StateCapture("skip"),
                    draft="a picture",
                )
            self.assertEqual(ack, "Heute ausgesetzt.")
            save.assert_not_called()
            self.assertTrue(already_logged(tmp, day))

    def test_only_state_mode_attaches_buttons_and_river_registers_them(self) -> None:
        import story_daily

        src = inspect.getsource(story_daily._run_scheduled_health_checkins)
        self.assertIn("if config.mode == MODE_STATE", src)
        self.assertIn("state_checkin_view", src)
        river = (Path(__file__).resolve().parents[1] / "river_bot.py").read_text(encoding="utf-8")
        self.assertIn("register_state_checkin_view(river_client, get_registry)", river)
        ui = (Path(__file__).resolve().parents[1] / "health_checkin_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("import mage", ui)
        self.assertNotIn("from mage", ui)


if __name__ == "__main__":
    unittest.main()