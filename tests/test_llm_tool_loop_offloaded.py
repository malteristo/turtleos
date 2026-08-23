"""Both tool loops run their tools off the event loop — measured through `llm.py`.

`tests/test_offload.py` proves the helper works and that no module calls a blocking
tool entrypoint from async code. This file closes the gap between those two facts and
the thing that actually matters: that the *real* tool loops, driven end to end, leave
the loop free.

It exists because the Ollama loop had no test of any kind. The Anthropic loop is
driven by `tests/test_llm_tool_empty_reply.py` — nine tests that pass an
`execute_tool` and would have caught a broken await — but the family rivers run on
the Ollama path, and that half was covered by nothing at all. A change made to two
call sites where only one is exercised is a change half-verified.

The measurement is the same in both: while a deliberately slow tool runs, count how
many times the event loop gets control. A blocked loop counts zero.
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import llm  # noqa: E402

TOOL_SECONDS = 0.30
TICK_INTERVAL = 0.01
MIN_TICKS = 10


def _slow_tool(name, args):
    time.sleep(TOOL_SECONDS)
    return f"{name} finished"


async def _ticks_during(coro) -> tuple[int, object]:
    ticks = 0
    stop = False

    async def ticker():
        nonlocal ticks
        while not stop:
            await asyncio.sleep(TICK_INTERVAL)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await coro
    finally:
        stop = True
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return ticks, result


class _Block:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class AnthropicToolLoopTests(unittest.IsolatedAsyncioTestCase):
    """One tool round, then prose — the ordinary shape of a turn."""

    def _scripted_client(self):
        responses = [
            MagicMock(content=[_Block("tool_use", name="read_practice_file", input={"filename": "x"}, id="t1")]),
            MagicMock(content=[_Block("text", text="Here is what it says.")]),
        ]

        client = MagicMock()

        async def create(**kwargs):
            return responses.pop(0)

        client.messages.create = create
        return client

    async def test_the_loop_stays_free_while_a_tool_runs(self) -> None:
        with patch.object(llm, "ANTHROPIC_API_KEY", "test-key"), patch(
            "anthropic.AsyncAnthropic", return_value=self._scripted_client()
        ):
            ticks, (text, executed) = await _ticks_during(
                llm.chat_anthropic_with_model(
                    "system",
                    [{"role": "user", "content": "hi"}],
                    "claude-test",
                    use_tools=True,
                    tos_tools=[
                        {
                            "function": {
                                "name": "read_practice_file",
                                "description": "d",
                                "parameters": {},
                            }
                        }
                    ],
                    execute_tool=_slow_tool,
                )
            )
        self.assertEqual(text, "Here is what it says.")
        self.assertEqual(executed[0]["result"], "read_practice_file finished")
        self.assertGreaterEqual(
            ticks,
            MIN_TICKS,
            f"the loop got control only {ticks} times while a {TOOL_SECONDS}s tool "
            "ran — the Anthropic tool loop is still blocking every other channel",
        )


class OllamaToolLoopTests(unittest.IsolatedAsyncioTestCase):
    """The path the family rivers run on, which had no test before 2026-08-14."""

    def _scripted_http(self):
        payloads = [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "list_practice_files", "arguments": {}}}
                    ],
                }
            },
            {"message": {"content": "Two files.", "tool_calls": []}},
        ]

        class Response:
            def __init__(self, data):
                self._data = data

            def raise_for_status(self):
                return None

            def json(self):
                return self._data

        class Client:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, json=None):
                return Response(payloads.pop(0))

        return Client

    async def test_the_loop_stays_free_while_a_tool_runs(self) -> None:
        with patch.object(llm.httpx, "AsyncClient", self._scripted_http()):
            ticks, (text, executed) = await _ticks_during(
                llm.chat_ollama_with_tools(
                    "system",
                    [{"role": "user", "content": "hi"}],
                    model_override="qwen-test",
                    tos_tools=[],
                    execute_tool=_slow_tool,
                )
            )
        self.assertEqual(text, "Two files.")
        self.assertEqual(executed[0]["result"], "list_practice_files finished")
        self.assertGreaterEqual(
            ticks,
            MIN_TICKS,
            f"the loop got control only {ticks} times while a {TOOL_SECONDS}s tool "
            "ran — the Ollama tool loop is still blocking every other channel",
        )

    async def test_a_tool_that_raises_still_reaches_the_model(self) -> None:
        """Offloading must not change how a failing tool is reported.

        The tool layer classifies exceptions into typed failures upstream of here;
        if `run_blocking` swallowed or re-wrapped them, a tool failure would become
        a silent empty result instead of something the model can respond to.
        """

        def angry_tool(name, args):
            raise ConnectionError("ollama down")

        with patch.object(llm.httpx, "AsyncClient", self._scripted_http()):
            with self.assertRaises(ConnectionError):
                await llm.chat_ollama_with_tools(
                    "system",
                    [{"role": "user", "content": "hi"}],
                    model_override="qwen-test",
                    tos_tools=[],
                    execute_tool=angry_tool,
                )


if __name__ == "__main__":
    unittest.main()
