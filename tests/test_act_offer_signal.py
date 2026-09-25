"""Turtle → River structured act-offer IPC."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import act_offer_signal as aos
import river_eddy_seneschal as res


class TestActOfferSignal(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self._rt_patch = patch("mage.get_runtime_dir", return_value=str(self.runtime))
        self._rt_patch.start()
        self.addCleanup(self._rt_patch.stop)
        aos.clear_act_offer_signal()

    def test_propose_and_consume_checkpoint(self):
        aos.propose_act_offer(42, 1001, "checkpoint", reason="wrap up")
        intent = aos.consume_act_offer(42, 1001)
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.action, "checkpoint")
        self.assertIsNone(aos.consume_act_offer(42, 1001))

    def test_wrong_message_id_left_pending(self):
        aos.propose_act_offer(42, 1001, "checkpoint")
        self.assertIsNone(aos.consume_act_offer(42, 9999))
        intent = aos.consume_act_offer(42, 1001)
        self.assertIsNotNone(intent)

    def test_save_requires_url(self):
        with self.assertRaises(ValueError):
            aos.propose_act_offer(42, 1001, "save")
        aos.propose_act_offer(42, 1001, "save", url="https://example.com/a")
        intent = aos.consume_act_offer(42, 1001)
        assert intent is not None
        self.assertEqual(intent.action, "save")
        self.assertEqual(intent.url, "https://example.com/a")

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            aos.propose_act_offer(42, 1001, "dissolve")

    def test_tool_needs_context(self):
        msg = aos.propose_act_offer_from_tool("checkpoint")
        self.assertIn("outside an active", msg)

    def test_tool_with_context(self):
        with aos.act_offer_turn_context(7, 55):
            msg = aos.propose_act_offer_from_tool("checkpoint", reason="done")
        self.assertIn("Queued", msg)
        intent = aos.consume_act_offer(7, 55)
        self.assertIsNotNone(intent)

    def test_trailer_strip_and_propose(self):
        reply = "We can pause here.\n\n[[act-offer:checkpoint]]\n"
        cleaned, intent = aos.extract_and_propose_from_reply(reply, 9, 88)
        self.assertNotIn("[[act-offer", cleaned)
        self.assertIn("pause", cleaned)
        assert intent is not None
        self.assertEqual(intent.action, "checkpoint")

    def test_trailer_save_url(self):
        reply = "Worth keeping.\n[[act-offer:save https://example.com/x]]"
        cleaned, intent = aos.extract_and_propose_from_reply(reply, 9, 88)
        self.assertNotIn("[[act-offer", cleaned)
        assert intent is not None
        self.assertEqual(intent.action, "save")
        self.assertEqual(intent.url, "https://example.com/x")

    def test_invalid_trailer_stripped_no_signal(self):
        reply = "Hi\n[[act-offer:dissolve]]"
        cleaned, intent = aos.extract_and_propose_from_reply(reply, 9, 88)
        self.assertEqual(cleaned.strip(), "Hi")
        self.assertIsNone(intent)
        self.assertIsNone(aos.consume_act_offer(9, 88))


class TestMaybeOfferTurtleIntent(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.runtime = Path(self._tmpdir.name) / "runtime"
        self.runtime.mkdir()
        self._rt_patch = patch("mage.get_runtime_dir", return_value=str(self.runtime))
        self._rt_patch.start()
        self.addCleanup(self._rt_patch.stop)
        aos.clear_act_offer_signal()
        res.clear_save_offer_state()

    async def test_posts_turtle_checkpoint_offer(self):
        aos.propose_act_offer(99, 1001, "checkpoint")
        channel = MagicMock()
        channel.id = 99
        channel.name = "eddy"
        channel.parent_id = 12345

        with patch("mage.river_bot_enabled", return_value=True), patch(
            "prompts.river_posts_turtle_offers", return_value=True
        ), patch("eddy_spawn.is_awaiting_flow_intake", return_value=False), patch(
            "eddy_spawn.is_awaiting_title", return_value=False
        ), patch(
            "eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock
        ) as post_mock:
            post_mock.return_value = MagicMock()
            offered = await res.maybe_offer_turtle_intent_after_turn(
                channel, practitioner_message_id=1001
            )

        self.assertTrue(offered)
        post_mock.assert_awaited_once()
        kwargs = post_mock.await_args.kwargs
        self.assertIn("checkpoint", kwargs.get("description", "").lower())

    async def _run_intent(self, channel, *, native, craft, post_mock):
        with patch("mage.river_bot_enabled", return_value=True), patch(
            "prompts.uses_native_turtle_prompt", return_value=native
        ), patch("prompts.uses_craft_surface", return_value=craft), patch(
            "eddy_spawn.is_awaiting_flow_intake", return_value=False
        ), patch("eddy_spawn.is_awaiting_title", return_value=False), patch(
            "eddy_lifecycle_bar.post_act_suggestion_row", new=post_mock
        ):
            return await res.maybe_offer_turtle_intent_after_turn(
                channel, practitioner_message_id=1001
            )

    async def test_craft_parent_posts_even_when_not_native(self):
        """The 2026-08-14 / 09-03 defect: craft Turtle queued; River never posted."""
        aos.propose_act_offer(99, 1001, "checkpoint")
        channel = MagicMock()
        channel.id = 99
        channel.name = "eddy"
        channel.parent_id = 12345
        post_mock = AsyncMock(return_value=MagicMock())

        offered = await self._run_intent(channel, native=False, craft=True, post_mock=post_mock)

        self.assertTrue(offered)
        post_mock.assert_awaited_once()

    async def test_health_parent_does_not_post(self):
        aos.propose_act_offer(99, 1001, "checkpoint")
        channel = MagicMock()
        channel.id = 99
        channel.name = "eddy"
        channel.parent_id = 12345
        recorded: list[tuple] = []
        post_mock = AsyncMock(return_value=MagicMock())

        with patch.object(
            res, "_log_contextual_skip", lambda ch, kind, why: recorded.append((kind, why))
        ):
            offered = await self._run_intent(
                channel, native=False, craft=False, post_mock=post_mock
            )

        self.assertFalse(offered)
        post_mock.assert_not_awaited()
        self.assertIn(("turtle_intent", "parent_not_offer_surface"), recorded)

    async def test_old_native_only_gate_would_skip_craft(self):
        """Positive control: the pre-lift gate fails the case we just shipped."""
        from prompts import uses_native_turtle_prompt, river_posts_turtle_offers

        with patch("prompts.uses_native_eddy", return_value=False), patch(
            "prompts.uses_craft_surface", return_value=True
        ):
            self.assertFalse(uses_native_turtle_prompt(12345))
            self.assertTrue(river_posts_turtle_offers(12345))


if __name__ == "__main__":
    unittest.main()
