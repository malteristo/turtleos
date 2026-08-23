"""The theme gate: labels reach two durable surfaces, so it fails closed.

No model is called here. What is checked is the part that must hold when the
model is wrong, slow, or absent — which, on a single-slot inference host, is
often.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Deliberately no `discord` stub here. `theme_gate` imports nothing from it,
# and installing a MagicMock into `sys.modules` at collection time leaks into
# every module imported after this file — two unrelated suites failed to load
# the first time this was written that way.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import theme_gate as tg


NAMES = ["Ana", "Ben", "Cora", "Rex"]


class StructuralLayerTests(unittest.TestCase):
    def test_a_possessive_name_is_a_verdict(self) -> None:
        for label in ("Ana's view of Cora's patterns",
                      "Ben's baseline of apathy",
                      "ben’s real motive"):
            with self.subTest(label=label):
                self.assertTrue(tg.names_in_possessive(label, NAMES))

    def test_a_name_without_a_possessive_is_left_to_the_model(self) -> None:
        for label in ("the planned visit with Oma",
                      "protecting the sick cat from Rex",
                      "who decides bedtime"):
            with self.subTest(label=label):
                self.assertFalse(tg.names_in_possessive(label, NAMES))

    def test_no_names_disables_the_layer_rather_than_matching_everything(self) -> None:
        self.assertFalse(tg.names_in_possessive("Ben's apathy", []))


class ParseTests(unittest.TestCase):
    def test_unreadable_output_is_all_verdict(self) -> None:
        labels = ["a", "b"]
        for raw in ("", "not json", "[]", '{"verdicts": "nope"}'):
            with self.subTest(raw=raw):
                self.assertEqual(tg.parse_verdicts(raw, labels),
                                 {"a": tg.VERDICT, "b": tg.VERDICT})

    def test_a_missing_entry_does_not_shift_its_neighbours(self) -> None:
        """Keyed on text, not position — a dropped entry must not promote another."""
        raw = '{"verdicts": [{"label": "b", "kind": "topic"}]}'
        self.assertEqual(tg.parse_verdicts(raw, ["a", "b"]),
                         {"a": tg.VERDICT, "b": tg.TOPIC})

    def test_only_an_explicit_topic_survives(self) -> None:
        raw = '{"verdicts": [{"label": "a", "kind": "maybe"}]}'
        self.assertEqual(tg.parse_verdicts(raw, ["a"]), {"a": tg.VERDICT})


class FailClosedTests(unittest.TestCase):
    def test_an_outage_drops_every_label(self) -> None:
        async def go():
            return await tg.keep_topics(["who decides bedtime"], timeout_s=0.001)

        kept, dropped = asyncio.run(go())
        self.assertEqual(kept, [])
        self.assertEqual(dropped, ["who decides bedtime"])

    def test_an_outage_still_reports_the_structural_drops(self) -> None:
        """The dropped list is what the ledger will count; it must be complete."""
        async def go():
            return await tg.keep_topics(
                ["Ben's baseline of apathy", "who decides bedtime"],
                timeout_s=0.001,
            )

        with mock.patch.object(tg, "_known_names", return_value=NAMES):
            kept, dropped = asyncio.run(go())
        self.assertEqual(kept, [])
        self.assertCountEqual(
            dropped, ["Ben's baseline of apathy", "who decides bedtime"]
        )

    def test_nothing_in_means_nothing_out_and_no_call(self) -> None:
        kept, dropped = asyncio.run(tg.keep_topics([]))
        self.assertEqual((kept, dropped), ([], []))


def _stub_discord_if_absent() -> None:
    """`llm` reaches `state`, which imports discord. Stub it *here*, not at
    module import: installing a MagicMock at collection time leaks into every
    module imported afterwards and broke two unrelated loaders the first time
    this file was written that way."""
    try:
        import discord  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover — environment branch
        from unittest.mock import MagicMock

        sys.modules.setdefault("discord", MagicMock())
        sys.modules.setdefault("discord.ext", MagicMock())
        sys.modules.setdefault("discord.ext.tasks", MagicMock())


class GoesThroughTheQueueTests(unittest.IsolatedAsyncioTestCase):
    """Both fail-closed gates must reach Ollama through `llm.chat_ollama_json`.

    They each had their own httpx client and their own short deadline until
    2026-08-08, so on a one-slot host they competed with the dialogue turn
    instead of queueing behind it, timed out, and failed closed — silently
    suppressing every offer and dropping every label under exactly the load
    they exist for.

    Patching `httpx` would still pass today by accident, because the gated
    helper uses httpx too. This pins the wiring itself, so removing the queue
    fails here rather than in a family's evening.
    """

    @classmethod
    def setUpClass(cls) -> None:
        _stub_discord_if_absent()

    async def test_the_theme_gate_calls_the_gated_helper(self) -> None:
        import llm

        with mock.patch.object(
            llm, "chat_ollama_json",
            mock.AsyncMock(return_value='{"verdicts": [{"label": "who decides bedtime", "kind": "topic"}]}'),
        ) as gated:
            kept, dropped = await tg.keep_topics(["who decides bedtime"])
        gated.assert_awaited_once()
        self.assertEqual((kept, dropped), (["who decides bedtime"], []))

    async def test_the_register_gate_calls_the_gated_helper(self) -> None:
        import llm
        import offer_register as reg

        with mock.patch.object(
            llm, "chat_ollama_json",
            mock.AsyncMock(return_value='{"register": "operational"}'),
        ) as gated:
            answer = await reg.classify_register("what time is the train")
        gated.assert_awaited_once()
        self.assertEqual(answer, reg.OPERATIONAL)

    async def test_the_deadline_starts_after_the_slot_is_acquired(self) -> None:
        """A call that waits in line and then answers has not failed."""
        import llm

        llm.reset_gate_for_tests()
        slow_start = asyncio.Event()

        async def hold_the_slot():
            async with llm._InferenceGate():
                await slow_start.wait()

        holder = asyncio.create_task(hold_the_slot())
        await asyncio.sleep(0.05)

        waiter = asyncio.create_task(
            llm.chat_ollama_json("x", model="m", timeout_s=0.01)
        )
        await asyncio.sleep(0.2)  # longer than timeout_s: it must still be queued
        self.assertFalse(waiter.done(), "the read deadline must not run while queued")

        slow_start.set()
        await holder
        with self.assertRaises(Exception):
            await waiter  # now it runs, and fails on the absent server
        llm.reset_gate_for_tests()


@unittest.skipUnless(
    os.environ.get("TURTLEOS_LIVE_THEME_GATE") == "1",
    "set TURTLEOS_LIVE_THEME_GATE=1 to reach live Ollama",
)
class LiveThemeGateTests(unittest.IsolatedAsyncioTestCase):
    """Explicitly slow. Allowed to reach inference; not part of the nightly unit suite.

    The story_notes unit tests mock keep_topics so a busy slot cannot turn the
    suite red. This is the path that still exercises the real gate end-to-end.
    """

    @classmethod
    def setUpClass(cls) -> None:
        _stub_discord_if_absent()

    async def test_a_plain_topic_survives_and_a_verdict_shape_does_not(self) -> None:
        with mock.patch.object(tg, "_known_names", return_value=NAMES):
            kept, dropped = await tg.keep_topics(
                [
                    "weekend trip packing",
                    "Ben's baseline of apathy",
                ],
                timeout_s=60.0,
            )
        self.assertIn("weekend trip packing", kept)
        self.assertIn("Ben's baseline of apathy", dropped)


if __name__ == "__main__":
    unittest.main()
