"""Thread-history backfill must not re-store the message being processed.

INT-043: on an eddy's first turn the in-memory history is empty, so
``load_thread_history`` backfills from Discord — which already contains the
triggering message. ``dialogue_turn`` then appends that same turn itself,
storing it twice and duplicating it in every downstream synthesis prompt.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import helpers
import state


def _msg(msg_id: int, name: str, content: str, *, bot: bool = False):
    m = MagicMock()
    m.id = msg_id
    m.author.bot = bot
    m.author.display_name = name
    m.content = content
    m.attachments = []
    return m


def _thread(messages):
    thread = MagicMock()

    async def _history(limit=50, oldest_first=True):
        for m in messages:
            yield m

    thread.history = _history
    thread.name = "eddy"
    return thread


class ThreadBackfillTests(unittest.IsolatedAsyncioTestCase):
    async def test_excluded_message_is_omitted(self) -> None:
        messages = [
            _msg(1, "riverhand", "first thing"),
            _msg(2, "riverhand", "the triggering message"),
        ]
        with patch.object(state, "client", MagicMock()):
            loaded = await helpers.load_thread_history(
                _thread(messages), exclude_message_id=2
            )
        contents = [m["content"] for m in loaded]
        self.assertEqual(contents, ["[riverhand]: first thing"])

    async def test_first_turn_backfill_yields_empty_history(self) -> None:
        """The INT-043 case: only the triggering message exists."""
        messages = [_msg(2, "riverhand", "the triggering message")]
        with patch.object(state, "client", MagicMock()):
            loaded = await helpers.load_thread_history(
                _thread(messages), exclude_message_id=2
            )
        self.assertEqual(loaded, [])

    async def test_without_exclusion_behaviour_is_unchanged(self) -> None:
        """Resume paths (lifecycle, !resume) still want the full history."""
        messages = [
            _msg(1, "riverhand", "first thing"),
            _msg(2, "riverhand", "second thing"),
        ]
        with patch.object(state, "client", MagicMock()):
            loaded = await helpers.load_thread_history(_thread(messages))
        self.assertEqual(len(loaded), 2)


if __name__ == "__main__":
    unittest.main()
