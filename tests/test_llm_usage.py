"""The cloud loop reports what it spent, round by round, and caches its system prompt."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest import mock


def _block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


def _resp(content, usage):
    return SimpleNamespace(content=content, usage=SimpleNamespace(**usage))


class UsageTests(unittest.TestCase):
    def _run(self, responses, fail_after=None):
        import llm

        seen: list[dict] = []
        calls = iter(responses)

        class _Messages:
            async def create(self, **kwargs):
                seen.append(kwargs)
                if fail_after is not None and len(seen) > fail_after:
                    raise RuntimeError("credit balance is too low")
                return next(calls)

        class _Client:
            messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.AsyncAnthropic = lambda **kw: _Client()
        usage: dict = {}
        tools = [{"function": {"name": "read_practice_file", "description": "d", "parameters": {}}}]
        with mock.patch.dict(sys.modules, {"anthropic": fake}):
            try:
                asyncio.run(llm.chat_anthropic_with_model(
                    "SYSTEM", [{"role": "user", "content": "hi"}], "claude-opus-5-5",
                    use_tools=True, tos_tools=tools,
                    execute_tool=lambda n, a: "text", usage=usage))
            except RuntimeError:
                pass
        return usage, seen

    ROUND = {"input_tokens": 100, "output_tokens": 10,
             "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0}

    def test_usage_sums_over_tool_rounds(self) -> None:
        tool_round = _resp([_block("tool_use", id="t1", name="read_practice_file", input={})], self.ROUND)
        final = _resp([_block("text", text="done")], dict(self.ROUND, cache_creation_input_tokens=0,
                                                          cache_read_input_tokens=1000))
        usage, seen = self._run([tool_round, final])
        self.assertEqual(usage["calls"], 2)
        self.assertEqual(usage["input_tokens"], 200)
        self.assertEqual(usage["cache_read_input_tokens"], 1000)

    def test_a_turn_that_fails_mid_loop_still_reports_what_it_spent(self) -> None:
        tool_round = _resp([_block("tool_use", id="t1", name="read_practice_file", input={})], self.ROUND)
        usage, _ = self._run([tool_round], fail_after=1)
        self.assertEqual(usage["calls"], 1)
        self.assertEqual(usage["output_tokens"], 10)

    def test_system_prompt_carries_a_cache_breakpoint(self) -> None:
        final = _resp([_block("text", text="done")], self.ROUND)
        _, seen = self._run([final])
        system = seen[0]["system"]
        self.assertEqual(system[0]["text"], "SYSTEM")
        self.assertEqual(system[0]["cache_control"], {"type": "ephemeral"})

    def test_ledger_row_carries_cost_and_room(self) -> None:
        import cloud_fallback

        with tempfile.TemporaryDirectory() as house:
            with mock.patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": house}):
                cost = cloud_fallback.record_usage(
                    channel_id=1, room="craft", model="claude-opus-5-5",
                    usage={"input_tokens": 1_000_000, "output_tokens": 0, "calls": 1})
                self.assertIsNone(cloud_fallback.record_usage(
                    channel_id=1, room="craft", model="claude-opus-5-5", usage={}))
                rows = [json.loads(l) for l in open(os.path.join(house, "usage.jsonl"))]
        self.assertEqual(cost, 4.0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["room"], "craft")
        self.assertEqual(rows[0]["usd"], 4.0)


class ReportTests(unittest.TestCase):
    def test_report_totals_by_room_and_keeps_unpriced_visible(self) -> None:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from usage_report import summarise

        rows = [
            {"ts": "2026-10-01T10:00:00+00:00", "room": "craft", "model": "claude-opus-5-5", "usd": 0.5},
            {"ts": "2026-10-02T10:00:00+00:00", "room": "craft", "model": "claude-opus-5-5", "usd": 0.25},
            {"ts": "2026-10-02T11:00:00+00:00", "room": "atrium", "model": "claude-new", "usd": None},
        ]
        text = "\n".join(summarise(rows))
        self.assertIn("2026-10: $0.75", text)
        self.assertIn("#craft · claude-opus-5-5 · 2 turns · $0.75", text)
        self.assertIn("1 unpriced", text)
        self.assertIn("No cloud usage", "\n".join(summarise(rows, "2026-11")))


class ClassifyTests(unittest.TestCase):
    def test_kinds(self) -> None:
        import cloud_fallback as cf

        self.assertEqual(cf.classify(RuntimeError(
            "BadRequestError: Your credit balance is too low to access the Anthropic API")), cf.FUNDS)
        err = RuntimeError("nope")
        err.status_code = 401
        self.assertEqual(cf.classify(err), cf.ACCESS)
        self.assertEqual(cf.classify(RuntimeError("overloaded_error 529")), cf.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
