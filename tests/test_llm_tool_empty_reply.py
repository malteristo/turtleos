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


class ThinkingBlockProseTests(unittest.TestCase):
    def test_between_tool_words_in_a_thinking_block_reach_the_reply(self) -> None:
        # Before this reader, a round whose only prose sat in a thinking block
        # contributed nothing: the loop kept text and tool_use only.
        reply, _ = _run_loop([
            _Response([
                _Block("thinking", thinking="The words between the tool calls."),
                _Block("tool_use", id="t1", name="offer_river_act",
                       input={"action": "checkpoint"}),
            ]),
            _Response([_Block("text", text="Done.")]),
        ])
        self.assertIn("The words between the tool calls.", reply)
        self.assertIn("Done.", reply)

    def test_a_text_block_wins_over_a_thinking_block(self) -> None:
        from llm import visible_round_text

        self.assertEqual(
            visible_round_text([
                _Block("thinking", thinking="aside"),
                _Block("text", text="shown"),
            ]),
            "shown",
        )
        self.assertEqual(visible_round_text([_Block("thinking", thinking="")]), "")

    def test_sonnet_5_5_request_sends_between_tools_and_no_temperature(self) -> None:
        import llm

        seen: dict = {}

        class _Messages:
            async def create(self, **kwargs):
                seen.update(kwargs)
                return _Response([_Block("text", text="ok")])

        class _Client:
            messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.AsyncAnthropic = lambda **kw: _Client()
        with mock.patch.dict(sys.modules, {"anthropic": fake}):
            asyncio.run(llm.chat_anthropic_with_model(
                "sys", [{"role": "user", "content": "hi"}], "claude-sonnet-5-5"))
        self.assertEqual(seen["thinking"], {"type": "between_tools"})
        self.assertNotIn("temperature", seen)

        seen.clear()
        with mock.patch.dict(sys.modules, {"anthropic": fake}):
            asyncio.run(llm.chat_anthropic_with_model(
                "sys", [{"role": "user", "content": "hi"}], "claude-sonnet-5"))
        self.assertNotIn("thinking", seen)


class StreamNamesTheCallTests(unittest.TestCase):
    def test_a_named_call_reaches_the_line_before_the_tool_runs(self) -> None:
        import llm

        order: list[str] = []

        class _Handle:
            def __init__(self, events, final):
                self._events = list(events)
                self._final = final

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._events:
                    raise StopAsyncIteration
                return self._events.pop(0)

            async def get_final_message(self):
                return self._final

        rounds = [
            (
                [
                    types.SimpleNamespace(
                        type="content_block_start", index=0,
                        content_block=types.SimpleNamespace(type="text"),
                    ),
                    types.SimpleNamespace(
                        type="content_block_delta", index=0,
                        delta=types.SimpleNamespace(type="text_delta", text="Let me look."),
                    ),
                    types.SimpleNamespace(
                        type="content_block_start", index=1,
                        content_block=types.SimpleNamespace(type="tool_use", name="read_practice_file"),
                    ),
                    types.SimpleNamespace(
                        type="content_block_delta", index=1,
                        delta=types.SimpleNamespace(type="input_json_delta", partial_json='{"filename": "x"}'),
                    ),
                ],
                _Response([
                    _Block("text", text="Let me look."),
                    _Block("tool_use", id="t1", name="read_practice_file", input={"filename": "x"}),
                ]),
            ),
            (
                [],
                _Response([_Block("text", text="Done.")]),
            ),
        ]

        class _Messages:
            def stream(self, **kwargs):
                events, final = rounds.pop(0)
                return _Handle(events, final)

            async def create(self, **kwargs):
                raise AssertionError("a streaming client should not fall back to the plain call")

        async def on_event(kind, payload):
            if kind == "status" and payload.get("name"):
                order.append("named")
            if kind == "status" and payload.get("text") == "writing":
                order.append("writing")
            if kind == "prose":
                order.append(payload.get("text") or "")

        def execute(name, args):
            order.append("ran")
            return "ok"

        fake = types.ModuleType("anthropic")
        fake.AsyncAnthropic = lambda **kw: types.SimpleNamespace(messages=_Messages())
        tools = [{"function": {"name": "read_practice_file", "description": "d", "parameters": {}}}]
        with mock.patch.dict(sys.modules, {"anthropic": fake}):
            reply, executed = asyncio.run(llm.chat_anthropic_with_model(
                "sys", [{"role": "user", "content": "hi"}], "claude-test",
                use_tools=True, tos_tools=tools, execute_tool=execute, on_event=on_event,
            ))
        self.assertEqual(reply, "Let me look.\n\nDone.")
        self.assertEqual(executed[0]["result"], "ok")
        self.assertEqual(order[:2], ["writing", "named"])
        self.assertLess(order.index("named"), order.index("ran"))
        self.assertEqual(order.count("Let me look."), 1)
        self.assertLess(order.index("Let me look."), order.index("ran"))


def _loop_with(responses, **extra):
    import llm

    calls = iter(responses)
    seen = {"calls": 0}

    class _Messages:
        async def create(self, **kwargs):
            seen["calls"] += 1
            return next(calls)

    class _Client:
        messages = _Messages()

    fake = types.ModuleType("anthropic")
    fake.AsyncAnthropic = lambda **kw: _Client()
    tools = [{"function": {"name": "workshop_read", "description": "d", "parameters": {}}}]
    with mock.patch.dict(sys.modules, {"anthropic": fake}):
        reply, executed = asyncio.run(llm.chat_anthropic_with_model(
            "sys", [{"role": "user", "content": "..."}], "claude-sonnet-5-5",
            use_tools=True, tos_tools=tools, execute_tool=lambda name, args: "ok", **extra))
    return reply, executed, seen["calls"]


def _lookup(text):
    return _Response([
        _Block("text", text=text),
        _Block("tool_use", id="t", name="workshop_read", input={"path": "a.md"}),
    ])


class FinalProseOnlyTests(unittest.TestCase):
    """A room that narrates between lookups opens every reply with the narration, unless asked not to."""

    def test_the_default_still_joins_every_round(self) -> None:
        reply, _, _ = _loop_with([_lookup("Reading the flow."), _Response([_Block("text", text="The answer.")])])
        self.assertIn("Reading the flow.", reply)
        self.assertIn("The answer.", reply)

    def test_final_prose_only_keeps_the_last_round_and_drops_the_narration(self) -> None:
        reply, executed, _ = _loop_with(
            [_lookup("Reading the flow."), _lookup("Now the core reads."), _Response([_Block("text", text="The answer.")])],
            final_prose_only=True,
        )
        self.assertEqual(reply, "The answer.")
        self.assertEqual(len(executed), 2, "the lookups still ran")

    def test_an_empty_last_round_falls_back_to_the_joined_prose(self) -> None:
        reply, _, _ = _loop_with(
            [_lookup("Everything I found."), _Response([_Block("text", text="")])],
            final_prose_only=True,
        )
        self.assertIn("Everything I found.", reply)

    def test_the_round_cap_is_the_turns_own(self) -> None:
        endless = [_lookup(f"step {i}") for i in range(30)]
        _, _, calls = _loop_with(endless, max_rounds=5)
        self.assertEqual(calls, 5)
        endless = [_lookup(f"step {i}") for i in range(30)]
        _, _, calls = _loop_with(endless, max_rounds=20)
        self.assertEqual(calls, 20, "positive control: a larger cap lets the loop run longer")


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
