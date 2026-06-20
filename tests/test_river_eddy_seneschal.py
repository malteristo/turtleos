"""Tests for River-side seneschal helpers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import river_eddy_seneschal as res


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


class TestMaybeOfferEddySaveOnTurtleReply(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    async def test_posts_save_row_when_turtle_replies(self) -> None:
        channel = MagicMock()
        channel.id = 99
        channel.name = "test-eddy"
        channel.parent_id = 12345
        practitioner = MagicMock()
        practitioner.author = MagicMock(bot=False)
        practitioner.content = "what do you think https://example.com/article"
        turtle_message = MagicMock()
        turtle_message.channel = channel
        turtle_message.reference = MagicMock(message_id=555, resolved=practitioner)
        turtle_message.created_at = MagicMock()

        with patch("mage.river_bot_enabled", return_value=True), patch(
            "prompts.uses_native_turtle_prompt", return_value=True
        ), patch("eddy_spawn.is_awaiting_flow_intake", return_value=False), patch(
            "eddy_spawn.is_awaiting_title", return_value=False
        ), patch("commands._get_cached_resonance", return_value=None), patch(
            "eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock
        ) as post_mock, patch(
            "bar_anchor.ensure_channel_bars", new_callable=AsyncMock
        ):
            post_mock.return_value = MagicMock()
            await res.maybe_offer_eddy_save_on_turtle_reply(turtle_message)

        post_mock.assert_awaited_once()
        args = post_mock.await_args[0]
        self.assertEqual(args[1], "-# Save to library")
        self.assertEqual(args[2][0][0], "Save to library")

    async def test_no_op_when_river_disabled(self) -> None:
        turtle_message = MagicMock()
        turtle_message.channel = MagicMock(id=1, parent_id=2)
        with patch("mage.river_bot_enabled", return_value=False), patch(
            "eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock
        ) as post_mock:
            await res.maybe_offer_eddy_save_on_turtle_reply(turtle_message)
        post_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
