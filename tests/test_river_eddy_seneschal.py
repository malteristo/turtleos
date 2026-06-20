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


class TestMaybeOfferEddySave(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        res.clear_save_offer_state()

    async def test_posts_save_row_when_eligible(self) -> None:
        channel = MagicMock()
        channel.id = 99
        url = "https://example.com/new"
        with patch("mage.river_bot_enabled", return_value=True), patch(
            "commands._get_cached_resonance", return_value=None
        ), patch(
            "commands.send_with_actions", new_callable=AsyncMock
        ) as send_mock:
            await res.maybe_offer_eddy_save_after_turn(
                channel,
                practitioner_text=f"what do you think {url}",
                history=[],
            )
        send_mock.assert_awaited_once()
        args = send_mock.await_args
        self.assertEqual(args[0][1], "-# Save to library")
        self.assertEqual(args[0][2][0][0], "Save to library")

    async def test_no_op_when_river_disabled(self) -> None:
        channel = MagicMock()
        channel.id = 1
        with patch("mage.river_bot_enabled", return_value=False), patch(
            "commands.send_with_actions", new_callable=AsyncMock
        ) as send_mock:
            await res.maybe_offer_eddy_save_after_turn(
                channel,
                practitioner_text="https://example.com/x",
                history=[],
            )
        send_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
