"""Tests for River-side eddy fetch offers and dedupe helpers."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import river_eddy_seneschal as res


class TestDedupeFetchActions(unittest.TestCase):
    def test_collapses_duplicate_fetch_commands(self) -> None:
        actions = [
            ("Fetch link", "!fetch https://example.com/a"),
            ("Fetch link", "!fetch https://example.com/a"),
        ]
        deduped = res.dedupe_fetch_actions(actions)
        self.assertEqual(len(deduped), 1)


class TestRecentFetchAct(unittest.TestCase):
    def test_detects_act_line(self) -> None:
        history = [{"role": "user", "content": "[Act: !fetch] excerpt here"}]
        self.assertTrue(res._recent_fetch_act(history))

    def test_absent_when_no_act(self) -> None:
        self.assertFalse(res._recent_fetch_act([]))


class TestMaybeOfferEddyFetch(unittest.IsolatedAsyncioTestCase):
    async def test_posts_fetch_for_external_url(self) -> None:
        message = MagicMock()
        message.content = "see https://example.com/article"
        message.channel.id = 42

        with patch("river_eddy_seneschal.extract_urls", new_callable=AsyncMock, return_value=["https://example.com/article"]), patch(
            "river_eddy_seneschal.get_history", return_value=[]
        ), patch("eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock) as post:
            await res.maybe_offer_eddy_fetch(message, MagicMock())
            post.assert_awaited_once()
            args = post.await_args[0]
            self.assertEqual(args[2][0][1], "!fetch https://example.com/article")

    async def test_skips_after_recent_fetch_act(self) -> None:
        message = MagicMock()
        message.content = "https://example.com/x"
        message.channel.id = 43

        with patch("river_eddy_seneschal.extract_urls", new_callable=AsyncMock, return_value=["https://example.com/x"]), patch(
            "river_eddy_seneschal.get_history",
            return_value=[{"role": "user", "content": "[Act: !fetch] done"}],
        ), patch("eddy_lifecycle_bar.post_act_suggestion_row", new_callable=AsyncMock) as post:
            await res.maybe_offer_eddy_fetch(message, MagicMock())
            post.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
