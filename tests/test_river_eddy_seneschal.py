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

    async def test_posts_save_row(self) -> None:
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
        kwargs = post_mock.await_args.kwargs
        self.assertEqual(
            kwargs.get("description"),
            "Optional — **save this link** to your practice library.",
        )


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


class TestHomePlanOfferHelpers(unittest.TestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    def test_latest_assistant_after_turn(self) -> None:
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
            {"role": "user", "content": "give me a workout plan"},
            {"role": "assistant", "content": "### Plan\n- a\n- b"},
        ]
        text = res._latest_assistant_after_turn(history, "give me a workout plan")
        self.assertIn("### Plan", text)

    def test_home_plan_skip_not_shaped(self) -> None:
        reason = res.home_plan_offer_skip_reason("short reply", channel_id=1)
        self.assertEqual(reason, "not_plan_shaped")

    def test_home_plan_skip_already_offered(self) -> None:
        plan = """
### 1. Strength
* pull-ups
* push-ups
* squats
### 2. Mobility
* hang
* stretch
* wall slides
### 3. Rotation
* quick refresh circuit with several named moves and enough prose to clear the length bar for a durable working document someone would pin.
"""
        res._home_plan_offer_seen.add(9)
        with patch("mage.get_pd", return_value="/tmp"), patch(
            "home_plans.get_by_eddy", return_value=None
        ):
            reason = res.home_plan_offer_skip_reason(plan, channel_id=9)
        self.assertEqual(reason, "already_offered_this_session")


class TestMaybeOfferHomePlan(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    async def test_offers_when_plan_shaped(self) -> None:
        channel = MagicMock()
        channel.id = 55
        channel.name = "workouts"
        channel.parent_id = 99
        plan = """
Here is a break-time plan you can rotate through between development sessions.

### 1. The Strength Core
*   **Upper Pull:** Pull-ups or chin-ups on the bar you already have.
*   **Upper Push:** Push-ups — standard or diamond when you want more challenge.
*   **Lower Body:** Bulgarian split squats or air squats to wake the legs.
### 2. The Mobility Reset
*   Hang from the bar for thirty seconds and let the shoulders drop.
*   World's Greatest Stretch — lunge plus torso twist for hips and mid-back.
### Break Rotation
*   Quick refresh with pull-ups and push-ups between development commits on turtleOS.
*   Deep reset: hang, stretch, then a short squat set before returning to code.
"""
        history = [
            {"role": "user", "content": "suggest a break workout"},
            {"role": "assistant", "content": plan},
        ]
        with patch("mage.river_bot_enabled", return_value=True), patch(
            "prompts.uses_native_turtle_prompt", return_value=True
        ), patch("mage.get_pd", return_value="/tmp"), patch(
            "home_plans.get_by_eddy", return_value=None
        ), patch.object(
            res, "_dialogue_history_snapshot", return_value=history
        ), patch.object(
            res, "_turtle_plan_reference_message", new_callable=AsyncMock, return_value=None
        ), patch(
            "home_plan_ui.offer_home_plan", new_callable=AsyncMock, return_value=True
        ) as offer_mock:
            offered = await res.maybe_offer_home_plan_after_turtle_reply(
                channel, practitioner_text="suggest a break workout"
            )
        self.assertTrue(offered)
        offer_mock.assert_awaited_once()
        self.assertIn(55, res._home_plan_offer_seen)


if __name__ == "__main__":
    import asyncio

    unittest.main()
