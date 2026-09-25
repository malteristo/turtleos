"""Tests for dialogue_message — message surface (discord_bot decomposition Slice 2)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import dialogue_message


class VisibleMessageContentTests(unittest.TestCase):
    def test_plain_content(self) -> None:
        message = MagicMock(content="hello", message_snapshots=[])

        visible, forwarded = dialogue_message.visible_message_content(message)

        self.assertEqual(visible, "hello")
        self.assertEqual(forwarded, "")

    def test_forwarded_snapshot_only(self) -> None:
        snapshot = MagicMock(
            content="forwarded smoke",
            created_at=None,
            type=None,
            embeds=[],
            attachments=[],
        )
        message = MagicMock(content="", message_snapshots=[snapshot], reference=None)

        visible, forwarded = dialogue_message.visible_message_content(message)

        self.assertIn("forwarded smoke", visible)
        self.assertIn("forwarded smoke", forwarded)
        self.assertIn("[Forwarded message 1]", visible)

    def test_content_plus_forward(self) -> None:
        snapshot = MagicMock(
            content="inner",
            created_at=None,
            type=None,
            embeds=[],
            attachments=[],
        )
        message = MagicMock(content="outer", message_snapshots=[snapshot], reference=None)

        visible, forwarded = dialogue_message.visible_message_content(message)

        self.assertTrue(visible.startswith("outer"))
        self.assertIn("inner", visible)
        self.assertIn("inner", forwarded)


class ForwardSourceRefTests(unittest.TestCase):
    def test_no_snapshots_returns_none(self) -> None:
        message = MagicMock(message_snapshots=[])

        self.assertIsNone(dialogue_message.forward_source_ref(message))

    def test_reference_tuple(self) -> None:
        ref = MagicMock(channel_id=100, message_id=200, guild_id=1)
        message = MagicMock(message_snapshots=[MagicMock()], reference=ref)

        self.assertEqual(dialogue_message.forward_source_ref(message), (1, 100, 200))


class FetchingClientIsProcessCorrectTests(unittest.TestCase):
    """Craft intake dereference runs in River; it must not reach for Turtle's client.

    Live 2026-09-16 → 09-21: every forwarded-source dereference in River died on
    `_MissingSentinel.is_set` and wrote the traceback into the intake file.
    """

    def test_river_process_uses_the_river_client(self) -> None:
        import river_state
        import state

        sentinel = object()
        with (
            patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}),
            patch.object(river_state, "_river_client", sentinel),
            patch.object(state, "_ensure_client", side_effect=AssertionError("built Turtle's client in River")),
        ):
            self.assertIs(dialogue_message.fetching_client(), sentinel)

    def test_turtle_process_uses_turtles_client(self) -> None:
        import state

        sentinel = object()
        with (
            patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "turtle"}),
            patch.object(state, "_client", sentinel),
        ):
            self.assertIs(dialogue_message.fetching_client(), sentinel)

    def test_the_fetch_hands_that_client_to_the_reader(self) -> None:
        import asyncio

        seen = {}

        async def fake_fetch(client, refs, *, label, limit):
            seen["client"] = client
            seen["refs"] = refs
            return "", 0

        marker = object()
        with (
            patch.object(dialogue_message, "fetching_client", return_value=marker),
            patch("discord_ref_read.fetch_discord_message_context", new=fake_fetch),
        ):
            asyncio.run(
                dialogue_message.fetch_discord_message_context([(None, 5, 6)], label="x")
            )
        self.assertIs(seen["client"], marker)
        self.assertEqual(seen["refs"], [(0, 5, 6)])


class ForwardedSnapshotPartialTests(unittest.TestCase):
    def test_empty_snapshots_not_partial(self) -> None:
        message = MagicMock(message_snapshots=[])

        self.assertFalse(dialogue_message.forwarded_snapshot_is_partial(message))

    def test_unreadable_snapshot_is_partial(self) -> None:
        snapshot = MagicMock(content="", embeds=[], attachments=[])
        message = MagicMock(message_snapshots=[snapshot])

        self.assertTrue(dialogue_message.forwarded_snapshot_is_partial(message))
