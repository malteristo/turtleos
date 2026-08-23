"""Pins for Anthropic tool-loop prose recovery."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from unittest import mock

from llm import _text_after_tools_only, _tool_result_failed


class _Block:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _Response:
    def __init__(self, content):
        self.content = content


def _run_loop(responses, executed=None):
    """Drive chat_anthropic_with_model against a scripted Anthropic client."""
    import llm

    calls = iter(responses)

    class _Messages:
        async def create(self, **kwargs):
            return next(calls)

    class _Client:
        messages = _Messages()

    fake = types.ModuleType("anthropic")
    fake.AsyncAnthropic = lambda **kw: _Client()

    tools = [{"function": {"name": "offer_river_act", "description": "d", "parameters": {}}}]
    with mock.patch.dict(sys.modules, {"anthropic": fake}):
        return asyncio.run(
            llm.chat_anthropic_with_model(
                "sys",
                [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6",
                use_tools=True,
                tos_tools=tools,
                execute_tool=lambda name, args: (executed or {}).get(name, "Queued"),
            )
        )


class ProseAlongsideToolCallTests(unittest.TestCase):
    """The reply and the tool call arrive in the same content block."""

    def test_prose_emitted_with_a_tool_call_survives_the_round(self) -> None:
        reply, tools = _run_loop([
            _Response([
                _Block("text", text="Here is the answer you asked for."),
                _Block("tool_use", id="t1", name="offer_river_act",
                       input={"action": "checkpoint"}),
            ]),
            _Response([]),  # model has nothing left to add
        ])
        self.assertEqual(reply, "Here is the answer you asked for.")
        self.assertEqual([t["name"] for t in tools], ["offer_river_act"])
        self.assertNotIn("without prose", reply)

    def test_prose_across_rounds_is_joined(self) -> None:
        reply, _ = _run_loop([
            _Response([
                _Block("text", text="Let me look."),
                _Block("tool_use", id="t1", name="offer_river_act",
                       input={"action": "checkpoint"}),
            ]),
            _Response([_Block("text", text="Found it.")]),
        ])
        self.assertEqual(reply, "Let me look.\n\nFound it.")

    def test_recovery_line_only_when_no_prose_at_all(self) -> None:
        reply, _ = _run_loop([
            _Response([
                _Block("tool_use", id="t1", name="offer_river_act",
                       input={"action": "checkpoint"}),
            ]),
            _Response([]),
        ])
        self.assertIn("checkpoint", reply)
        self.assertIn("fault on my side", reply)


class ToolFailureDetectionTests(unittest.TestCase):
    def test_typed_failures_are_failures(self) -> None:
        self.assertTrue(_tool_result_failed(
            "ToolResult[blocked] run_turtleos_shell: command not allowed: sed"))
        self.assertTrue(_tool_result_failed("Cannot patch x.md — not a writable practice file"))
        self.assertTrue(_tool_result_failed("Unknown tool: nope"))

    def test_successful_read_of_error_handling_code_is_not_a_failure(self) -> None:
        """The old substring test failed here: any source file mentioning errors."""
        self.assertFalse(_tool_result_failed(
            "# llm.py\nexcept Exception as e:\n    print(f'Gemini chat error: {e}')"))
        self.assertFalse(_tool_result_failed("Done. Patched craft/surface-nimble-boom.md."))


class TextAfterToolsOnlyTests(unittest.TestCase):
    def test_offer_river_act_names_the_queued_action(self) -> None:
        text = _text_after_tools_only(
            [
                {
                    "name": "offer_river_act",
                    "args": {
                        "action": "save",
                        "url": "https://www.aihero.dev/skills-improve-codebase-architecture",
                    },
                    "result": "Queued",
                }
            ]
        )
        self.assertIn("save", text)
        self.assertIn("aihero.dev", text)
        self.assertNotIn("no response generated", text)

    def test_no_button_is_promised(self) -> None:
        """River posts buttons on native surfaces only — craft-turtle gets none."""
        text = _text_after_tools_only(
            [{"name": "offer_river_act", "args": {"action": "checkpoint"}, "result": "Queued"}]
        )
        self.assertNotIn("button", text.lower())

    def test_other_tools_get_generic_recovery(self) -> None:
        text = _text_after_tools_only(
            [{"name": "read_practice_file", "args": {"filename": "x.md"}, "result": "ok"}]
        )
        self.assertIn("read_practice_file", text)


if __name__ == "__main__":
    unittest.main()
