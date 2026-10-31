"""The press shows the command that is in the record, and not a file body."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import session_record as sr
import trace_calls  # loads before any test stubs discord, so the button class is real
from trace_reveal import calls_for_message, reveal_calls

PLANTED_BODY = "PLANTED_FILE_BODY_should_not_leave_the_record"
PLANTED_SECRET = "PLANTED_SECRET_should_not_be_shown"


class RevealTests(unittest.TestCase):
    def test_a_read_is_named_the_way_the_card_names_it(self) -> None:
        text = reveal_calls([
            {
                "name": "workshop_read",
                "arguments": {"path": "desk/boom.md"},
                "summary": PLANTED_BODY,
            }
        ])
        self.assertIn("read `desk/boom.md`", text)
        self.assertIn("Submit closes this. Nothing is posted.", text)
        self.assertNotIn("workshop_read", text)
        self.assertNotIn("### What this turn opened", text)
        self.assertNotIn(PLANTED_BODY, text)
        self.assertNotIn("http", text)

    def test_a_file_the_house_can_open_is_a_link_and_a_workshop_file_is_not(self) -> None:
        opened = "https://notes.example/sessions/a.md"
        text = reveal_calls(
            [
                {"name": "read_practice_file", "arguments": {"filename": "sessions/a.md"}, "summary": "ok"},
                {"name": "workshop_read", "arguments": {"path": "desk/boom.md"}, "summary": PLANTED_BODY},
            ],
            link_for=lambda path: opened if path.startswith("sessions/") else None,
        )
        self.assertIn(f"[sessions/a.md]({opened})", text)
        self.assertNotIn("desk/boom.md](http", text)
        self.assertNotIn(PLANTED_BODY, text)
        from dialogue_turn import _file_link
        self.assertIsNone(_file_link("desk/boom.md"))

    def test_the_window_keeps_the_grammar(self) -> None:
        from ui_kit import read_window, violations

        text = reveal_calls([
            {"name": "workshop_read", "arguments": {"path": "desk/state.md"}, "summary": "a short note"},
        ])
        self.assertEqual(violations(read_window("What this turn opened", text)), [])

    def test_the_command_is_shown_and_the_file_body_is_not(self) -> None:
        text = reveal_calls([
            {
                "name": "run_turtleos_shell",
                "arguments": {"command": "git log --oneline -14"},
                "summary": PLANTED_BODY,
            }
        ])
        self.assertIn("looked · git log", text)
        self.assertIn("git log --oneline -14", text)
        self.assertNotIn("run_turtleos_shell", text)
        self.assertNotIn(PLANTED_BODY, text)

    def test_a_refusal_is_shown_and_a_secret_argument_is_not(self) -> None:
        text = reveal_calls([
            {
                "name": "house_terminal",
                "arguments": {
                    "command": "git branch -vv",
                    "token": PLANTED_SECRET,
                },
                "summary": "ToolResult[blocked]: only git branch --show-current is allowed",
            }
        ])
        self.assertIn("git branch -vv", text)
        self.assertIn("show-current", text)
        self.assertNotIn(PLANTED_SECRET, text)
        self.assertNotIn("token=", text)

    def test_an_edit_names_the_path_and_the_count_and_not_the_paragraphs(self) -> None:
        old = "PLANTED_OLD_PARAGRAPH"
        new = "PLANTED_NEW_PARAGRAPH"
        text = reveal_calls([
            {
                "name": "workshop_edit",
                "arguments": {"path": "desk/state.md", "old": old, "new": new},
                "summary": PLANTED_BODY,
            }
            for _ in range(5)
        ])
        self.assertIn("edited `desk/state.md` × 5", text)
        self.assertEqual(text.count("desk/state.md"), 1)
        self.assertNotIn("workshop_edit", text)
        self.assertNotIn(old, text)
        self.assertNotIn(new, text)
        self.assertNotIn(PLANTED_BODY, text)

    def test_different_commands_stay_and_the_same_command_collapses(self) -> None:
        different = reveal_calls([
            {"name": "house_terminal", "arguments": {"command": "git log --oneline -6"}, "summary": ""},
            {"name": "house_terminal", "arguments": {"command": "git log --oneline -30"}, "summary": ""},
        ])
        self.assertIn("git log --oneline -6", different)
        self.assertIn("git log --oneline -30", different)
        self.assertNotIn("×", different)
        self.assertNotIn("house_terminal", different)

        same = reveal_calls([
            {"name": "house_terminal", "arguments": {"command": "git log --oneline -6"}, "summary": ""},
            {"name": "house_terminal", "arguments": {"command": "git log --oneline -6"}, "summary": ""},
        ])
        self.assertIn("× 2", same)
        self.assertEqual(same.count("git log --oneline -6"), 1)

    def test_a_slice_of_a_file_names_the_lines_and_not_the_tool(self) -> None:
        text = reveal_calls([{
            "name": "workshop_read",
            "arguments": {
                "path": "desk/intentions/active/hai_facilitation.md",
                "start_line": 33,
                "max_lines": 3,
            },
            "summary": PLANTED_BODY,
        }])
        self.assertIn("read `desk/intentions/active/hai_facilitation.md`", text)
        self.assertIn("lines 33-35", text)
        self.assertNotIn("workshop_read", text)
        self.assertNotIn("start_line", text)
        self.assertNotIn(PLANTED_BODY, text)

    def test_a_search_does_not_repeat_the_tool(self) -> None:
        text = reveal_calls([{
            "name": "workshop_search",
            "arguments": {"query": "Take this up", "path": "desk/boom.md"},
            "summary": PLANTED_BODY,
        }])
        self.assertIn('searched for "Take this up" in `desk/boom.md`', text)
        self.assertNotIn("workshop_search", text)
        self.assertNotIn(PLANTED_BODY, text)

    def test_a_window_that_cannot_hold_the_middle_keeps_the_ends(self) -> None:
        tools = []
        for i in range(30):
            tools.append({
                "name": "house_terminal",
                "arguments": {"command": f"git log --oneline marker-{i:02d} " + ("word " * 12)},
                "summary": "",
            })
        tools[0]["arguments"]["command"] = "git log --oneline FIRST_ACT_TOKEN"
        tools[-1]["arguments"]["command"] = "git log --oneline LAST_ACT_TOKEN"
        text = reveal_calls(tools)
        self.assertIn("FIRST_ACT_TOKEN", text)
        self.assertIn("LAST_ACT_TOKEN", text)
        self.assertLessEqual(len(text), 1900)
        self.assertIn("more, in the record", text)
        self.assertNotIn("FIRST_ACT_TOKE\n", text)
        self.assertNotIn("LAST_ACT_TOKE\n", text)
        self.assertTrue(text.rstrip().endswith("LAST_ACT_TOKEN") or "LAST_ACT_TOKEN" in text.split("\n\n")[-1])

    def test_the_button_picks_the_turn_that_followed_it(self) -> None:
        events = [
            {"kind": "trace", "message": "1", "text": "earlier"},
            {"kind": "turn", "tools": [{"name": "a", "arguments": {"command": "first"}}]},
            {"kind": "trace", "message": "2", "text": "later"},
            {"kind": "turn", "tools": [{"name": "b", "arguments": {"command": "second"}}]},
        ]
        self.assertEqual(calls_for_message(events, "2")[0]["arguments"]["command"], "second")
        self.assertEqual(calls_for_message(events, "1")[0]["arguments"]["command"], "first")
        self.assertIsNone(calls_for_message(events, "9"))

    def test_a_dressed_card_inspects_the_one_call_above_the_answer(self) -> None:
        events = [
            {"kind": "turn", "tools": [
                {"name": "workshop_read", "arguments": {"path": "desk/state.md"}},
                {"name": "workshop_read", "arguments": {"path": "desk/boom.md"}},
            ]},
            {"kind": "trace", "message": "10", "tool": 0, "text": "read state"},
            {"kind": "trace", "message": "11", "tool": 1, "text": "read boom"},
        ]
        self.assertEqual(calls_for_message(events, "11")[0]["arguments"]["path"], "desk/boom.md")
        self.assertEqual(len(calls_for_message(events, "10")), 1)
        self.assertIsNone(calls_for_message([{"kind": "trace", "message": "10", "tool": 0}], "10"))

    def test_a_button_whose_turn_is_not_written_yet_has_no_calls(self) -> None:
        events = [{"kind": "trace", "message": "1", "text": "card"}]
        self.assertIsNone(calls_for_message(events, "1"))

    def test_the_button_id_is_what_the_press_reads(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sr.append_event(
                root, "9", kind="trace", actor="spirit", text="card", message="button-44",
            )
            sr.append_turn(
                root, "9", practitioner=".", reply="done",
                tools=[{"name": "run_turtleos_shell", "args": {"command": "git status"}, "result": PLANTED_BODY}],
            )
            events = sr.read_turns(root, "9")
            text = reveal_calls(calls_for_message(events, "button-44"))
            self.assertIn("git status", text)
            self.assertNotIn(PLANTED_BODY, text)
            self.assertNotIn("button-44", sr.render_session(root, "9"))

    def test_the_button_is_not_edited_onto_the_call(self) -> None:
        """The button still exists. It is not on the call until the visual layer is.

        Editing it on was what marked every line as edited, and it replaced
        the call with a paraphrase to do it.
        """
        from trace_reveal import calls_components

        row = calls_components()[0]["components"][0]
        self.assertEqual(row["label"], "What was opened")
        self.assertEqual(row["custom_id"], trace_calls.CALLS_ID)
        dialogue = Path(__file__).resolve().parents[1].joinpath("dialogue_turn.py").read_text()
        self.assertIn("def call_as_sent", dialogue)
        self.assertNotIn("calls_components", dialogue)
        self.assertNotIn("post_button", dialogue)

    def test_the_reveal_is_a_window_and_spirit_does_not_take_messages(self) -> None:
        root = Path(__file__).resolve().parents[1]
        calls = (root / "trace_calls.py").read_text()
        self.assertIn("send_modal", (root / "dialogue_turn.py").read_text())
        self.assertNotIn("interaction.channel.send", calls)
        ears = (root / "spirit_ears.py").read_text()
        self.assertIn("Intents.none()", ears)
        self.assertNotIn("on_message", ears)
        self.assertIn("arm_stocked", ears)
        self.assertNotIn("on_message", (root / "cloud_stocked.py").read_text())
        self.assertNotIn("spirit_ears", (root / "river_bot.py").read_text())


class PressTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_press_answers_only_the_person_who_pressed(self) -> None:
        from dialogue_turn import open_trace_calls

        interaction = MagicMock()
        interaction.channel_id = 9
        interaction.message.id = "button-44"
        interaction.response.is_done.return_value = False
        interaction.response.send_modal = AsyncMock()
        events = [
            {"kind": "trace", "message": "button-44", "text": "card"},
            {
                "kind": "turn",
                "tools": [{
                    "name": "run_turtleos_shell",
                    "arguments": {"command": "git status"},
                    "summary": PLANTED_BODY,
                }],
            },
        ]
        with (
            patch("mage.set_practice_context_for_channel"),
            patch("mage.get_pd", return_value="/tmp"),
            patch("session_record.read_turns", return_value=events),
        ):
            await open_trace_calls(interaction)
        interaction.response.send_modal.assert_awaited()
        modal = interaction.response.send_modal.await_args.args[0]
        shown = modal.to_components()[0]["content"]
        self.assertIn("git status", shown)
        self.assertNotIn(PLANTED_BODY, shown)
        interaction.channel.send.assert_not_called()
        interaction.response.send_message.assert_not_called()
