"""The read-error repair, 2026-08-07 — a conversation waits, it never fails.

Three claims, each pinned against the evidence that produced it:

1. Calls to the local runner form one line. Per-channel serialization already
   existed; the family river's four concurrent eddies all hit a single Ollama
   slot (``-np 1``) and raced there.
2. Waiting in line is not a deadline. The old 300s ``read`` timeout measured
   the gap between bytes, and a queued request emits none — so it killed turns
   that had not started. Only silence *after* the first token is a fault.
3. Messages arriving mid-reply are absorbed in order and answered once, by the
   newest. Nothing is dropped; the replies collapse, not the record.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import llm


class InferenceGateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        llm.reset_gate_for_tests()

    async def test_local_calls_do_not_overlap(self) -> None:
        """Four eddies, one slot — the bot forms the line instead of racing."""
        overlap = []
        active = {"n": 0}

        async def call():
            async with llm._InferenceGate():
                active["n"] += 1
                overlap.append(active["n"])
                await asyncio.sleep(0.01)
                active["n"] -= 1

        await asyncio.gather(*[call() for _ in range(4)])
        self.assertEqual(overlap, [1, 1, 1, 1], "concurrent calls reached the runner")

    async def test_gate_releases_when_a_call_raises(self) -> None:
        async def boom():
            async with llm._InferenceGate():
                raise RuntimeError("runner died")

        with self.assertRaises(RuntimeError):
            await boom()

        ran = []

        async def after():
            async with llm._InferenceGate():
                ran.append("ok")

        await asyncio.wait_for(after(), timeout=1)
        self.assertEqual(ran, ["ok"])

    async def test_default_inflight_matches_the_servers_single_slot(self) -> None:
        self.assertEqual(llm.OLLAMA_MAX_INFLIGHT, 1)


class StreamDeadlineTests(unittest.IsolatedAsyncioTestCase):
    """No byte-gap deadline before the first token; a stall guard after it."""

    def setUp(self) -> None:
        llm.reset_gate_for_tests()

    def test_streaming_client_has_no_read_deadline(self) -> None:
        """The regression that produced `[dialogue error: ReadTimeout: ]`.

        A queued request emits no bytes, so any finite `read` timeout is a
        deadline on *waiting*, which is exactly what must not fail.
        """
        import inspect

        src = inspect.getsource(llm.chat_ollama)
        self.assertIn("read=None", src)
        self.assertNotIn("read=300.0", src)

    def test_stall_guard_applies_only_after_the_first_token(self) -> None:
        import inspect

        src = inspect.getsource(llm.chat_ollama)
        # The wait_for wraps __anext__ only on the branch where tokens exist.
        self.assertIn("if reply_chunks:", src)
        self.assertIn("OLLAMA_STALL_SECONDS", src)

    def test_a_wedged_call_is_still_bounded(self) -> None:
        """Never failing on load must not mean hanging forever on a fault."""
        self.assertGreater(llm.OLLAMA_TURN_CEILING_SECONDS, 0)


class FallbackTests(unittest.TestCase):
    """The old fallback amplified the outage it was meant to soften."""

    def test_failure_path_does_not_reach_for_a_different_model(self) -> None:
        """Retrying with REFLECTION_MODEL bought an eviction and a 17GB reload
        queued behind the already-congested slot, then posted the second
        exception into the conversation."""
        import pathlib

        src = pathlib.Path(__file__).resolve().parent.parent / "dialogue_turn.py"
        body = src.read_text()
        failure_block = body.split("Dialogue error (")[1].split("# Detect and remove")[0]
        self.assertNotIn("REFLECTION_MODEL", failure_block)
        self.assertIn("model=thread_model", failure_block)

    def test_practitioner_never_sees_a_traceback(self) -> None:
        import dialogue_turn

        self.assertNotIn("error", dialogue_turn.TURN_UNAVAILABLE_REPLY.lower())
        self.assertNotIn("{", dialogue_turn.TURN_UNAVAILABLE_REPLY)


class CoalescingTests(unittest.IsolatedAsyncioTestCase):
    """'Keep the latest state of the conversation in mind while working off
    the queue' — absorb every message in order, answer once at the newest."""

    def setUp(self) -> None:
        import dialogue_queue

        dialogue_queue._queues.clear()
        dialogue_queue._draining.clear()

    async def test_messages_sent_during_a_reply_are_absorbed_then_answered_once(
        self,
    ) -> None:
        import dialogue_queue

        absorbed: list[int] = []
        answered: list[int] = []

        async def handler(message, *, reply: bool = True):
            absorbed.append(message.id)
            if reply:
                answered.append(message.id)
                await asyncio.sleep(0.01)

        msgs = []
        for i in (1, 2, 3, 4):
            m = MagicMock()
            m.channel.id = 55
            m.channel.name = "family"
            m.id = i
            msgs.append(m)

        for m in msgs:
            await dialogue_queue.enqueue_dialogue(m, handler)
        await asyncio.sleep(0.2)

        self.assertEqual(absorbed, [1, 2, 3, 4], "a message was dropped, not deferred")
        self.assertEqual(answered, [4], "the room got more than one answer")

    async def test_a_lone_message_is_answered_normally(self) -> None:
        import dialogue_queue

        answered = []

        async def handler(message, *, reply: bool = True):
            if reply:
                answered.append(message.id)

        m = MagicMock()
        m.channel.id = 56
        m.id = 1
        await dialogue_queue.enqueue_dialogue(m, handler)
        await asyncio.sleep(0.05)
        self.assertEqual(answered, [1])

    async def test_handler_without_reply_support_is_never_told_to_defer(self) -> None:
        """Legacy/injected handlers keep the old behaviour rather than raising."""
        import dialogue_queue

        seen = []

        async def bare_handler(message):
            seen.append(message.id)

        for i in (1, 2):
            m = MagicMock()
            m.channel.id = 57
            m.id = i
            await dialogue_queue.enqueue_dialogue(m, bare_handler)
        await asyncio.sleep(0.05)
        self.assertEqual(seen, [1, 2])

    async def test_after_turn_fires_only_for_the_answering_message(self) -> None:
        import dialogue_queue

        after = []

        async def handler(message, *, reply: bool = True):
            return None

        async def after_turn(message):
            after.append(message.id)

        for i in (1, 2, 3):
            m = MagicMock()
            m.channel.id = 58
            m.id = i
            await dialogue_queue.enqueue_dialogue(m, handler, after_turn=after_turn)
        await asyncio.sleep(0.05)
        self.assertEqual(after, [3])


if __name__ == "__main__":
    unittest.main()
