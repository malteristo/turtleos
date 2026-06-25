"""Tests for River-side seneschal helpers."""

from __future__ import annotations

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import river_eddy_seneschal as res


class TestSaveOfferSkipReason(unittest.TestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    def test_none_when_uncached_url(self) -> None:
        url = "https://example.com/article"
        reason = res.save_offer_skip_reason(
            f"see {url}", [], channel_id=1, is_cached=lambda _: False
        )
        self.assertIsNone(reason)

    def test_cached_in_link_resonance(self) -> None:
        url = "https://example.com/cached"
        reason = res.save_offer_skip_reason(
            f"see {url}", [], channel_id=1, is_cached=lambda u: u == url
        )
        self.assertTrue(reason and reason.startswith("cached_in_link_resonance:"))

    def test_already_offered(self) -> None:
        url = "https://example.com/offered"
        res.mark_save_offer_posted(5, url)
        reason = res.save_offer_skip_reason(
            f"see {url}", [], channel_id=5, is_cached=lambda _: False
        )
        self.assertTrue(reason and reason.startswith("already_offered:"))

    def test_recent_fetch_act(self) -> None:
        url = "https://example.com/fetched"
        history = [{"role": "user", "content": f"[Act: !fetch] Cached {url}"}]
        reason = res.save_offer_skip_reason(
            f"again {url}", history, channel_id=1, is_cached=lambda _: False
        )
        self.assertTrue(reason and reason.startswith("recent_fetch_act:"))

    def test_no_external_url(self) -> None:
        reason = res.save_offer_skip_reason(
            "just text", [], channel_id=1, is_cached=lambda _: False
        )
        self.assertEqual(reason, "no_external_url")


class TestPickSaveOfferUrl(unittest.TestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    def test_returns_uncached_practitioner_url(self) -> None:
        url = "https://example.com/article"
        text = f"thoughts on this? {url}"
        picked = res.pick_save_offer_url(text, [], channel_id=1, is_cached=lambda _: False)
        self.assertEqual(picked, url)

    def test_skips_cached_url(self) -> None:
        url = "https://example.com/article"
        text = f"check {url}"
        picked = res.pick_save_offer_url(text, [], channel_id=1, is_cached=lambda u: u == url)
        self.assertIsNone(picked)

    def test_skips_after_recent_fetch_act(self) -> None:
        url = "https://example.com/article"
        history = [{"role": "user", "content": f"[Act: !fetch] Cached {url}"}]
        text = f"again {url}"
        picked = res.pick_save_offer_url(text, history, channel_id=1, is_cached=lambda _: False)
        self.assertIsNone(picked)

    def test_skips_after_offer_posted(self) -> None:
        url = "https://example.com/article"
        res.mark_save_offer_posted(42, url)
        picked = res.pick_save_offer_url(
            f"see {url}", [], channel_id=42, is_cached=lambda _: False
        )
        self.assertIsNone(picked)

    def test_dedupe_fetch_actions(self) -> None:
        actions = [
            ("Fetch link", "!fetch https://example.com/a"),
            ("Fetch link", "!fetch https://example.com/a"),
        ]
        deduped = res.dedupe_fetch_actions(actions)
        self.assertEqual(len(deduped), 1)


class TestMaybeOfferEddySaveAfterTurn(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    async     def test_posts_save_row(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.name = "test-eddy"
        channel.parent_id = 12345
        url = "https://example.com/article"
        text = f"what do you think {url}"

        with patch("mage.river_bot_enabled", return_value=True), patch(
            "prompts.uses_native_turtle_prompt", return_value=True
        ), patch("eddy_spawn.is_awaiting_flow_intake", return_value=False), patch(
            "eddy_spawn.is_awaiting_title", return_value=False
        ), patch("cmd_link_resonance.get_cached_resonance", return_value=None), patch(
            "eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock
        ) as post_mock, patch(
            "bar_anchor.ensure_channel_bars", new_callable=AsyncMock
        ):
            post_mock.return_value = MagicMock()
            await res.maybe_offer_contextual_act_after_turn(channel, practitioner_text=text)

        post_mock.assert_awaited_once()
        args = post_mock.await_args[0]
        self.assertEqual(args[1], "-# Save to library")


class TestCheckpointOffer(unittest.TestCase):
    def test_intent_detected(self) -> None:
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
        ]
        reason = res.checkpoint_offer_skip_reason(
            "can you checkpoint this thread?", history, min_exchanges=2
        )
        self.assertIsNone(reason)

    def test_thin_history_skips(self) -> None:
        reason = res.checkpoint_offer_skip_reason(
            "checkpoint please", [], min_exchanges=2
        )
        self.assertTrue(reason and reason.startswith("thin_history:"))

    def test_pick_checkpoint_when_no_url(self) -> None:
        history = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        offer = res.pick_contextual_offer(
            "wrap this up — checkpoint?",
            history,
            channel_id=1,
            is_cached=lambda _: False,
            min_exchanges=2,
        )
        self.assertIsNotNone(offer)
        assert offer is not None
        self.assertEqual(offer.kind, "checkpoint")
        self.assertEqual(offer.actions[0][1], "!checkpoint")


class TestDialogueSnapshot(unittest.TestCase):
    def test_reads_shared_store_in_split_bot(self) -> None:
        payload = [{"role": "user", "content": "from disk"}]
        with patch("dialogue_store.shared_dialogue_enabled", return_value=True), patch(
            "dialogue_store.read_shared", return_value=payload
        ):
            snap = res._dialogue_history_snapshot(42)
        self.assertEqual(snap[0]["content"], "from disk")

    def test_assistant_after_practitioner_turn(self) -> None:
        history = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old reply"},
            {"role": "user", "content": "see https://example.com/article"},
            {"role": "assistant", "content": "interesting article"},
        ]
        self.assertTrue(
            res._assistant_replied_for_practitioner_turn(
                history,
                "see https://example.com/article",
            )
        )
        self.assertFalse(
            res._assistant_replied_for_practitioner_turn(
                history,
                "not in history",
            )
        )


class TestScheduleContextualOffer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    async def test_schedules_poll_on_practitioner_message(self) -> None:
        channel = MagicMock()
        channel.id = 77
        channel.name = "eddy"
        channel.parent_id = 1
        message = MagicMock()
        message.channel = channel
        message.content = "let's wrap this up — checkpoint?"
        message.created_at = MagicMock()

        with patch.object(res, "_run_contextual_offer_poll", new_callable=AsyncMock) as run_mock:
            res.schedule_contextual_offer_after_practitioner_turn(message)
            await asyncio.sleep(0.05)
        run_mock.assert_awaited_once_with(message)

    async def test_schedules_poll_on_practitioner_url(self) -> None:
        channel = MagicMock()
        channel.id = 78
        channel.name = "eddy"
        channel.parent_id = 1
        message = MagicMock()
        message.channel = channel
        message.content = "check https://example.com/new-article"
        message.created_at = MagicMock()

        with patch.object(res, "_run_contextual_offer_poll", new_callable=AsyncMock) as run_mock:
            res.schedule_save_offer_after_practitioner_url(message)
            await asyncio.sleep(0.05)
        run_mock.assert_awaited_once_with(message)


if __name__ == "__main__":
    import asyncio

    unittest.main()
