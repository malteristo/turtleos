"""Tests for daily note river visibility (issue 041)."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import story_daily


class DailyNoteVisibilityTests(unittest.IsolatedAsyncioTestCase):
    def test_build_surface_includes_preview_and_open_note(self) -> None:
        result = story_daily.DailyNoteResult(
            note_path=Path("/tmp/practice/story/daily/2026-07-15.md"),
            preview_text="You held the build thread open today.",
            created=True,
        )
        # The relative path derives from the note's own root, not ambient context.
        surface = story_daily.build_daily_note_surface(date(2026, 7, 15), result)

        self.assertIsNotNone(surface)
        assert surface is not None
        self.assertEqual(surface.template_id, "post_daily_note")
        self.assertIn("```md", surface.content or "")
        self.assertIn(
            ("Open note", "!read story/daily/2026-07-15.md"),
            surface.open_actions,
        )

    async def test_river_post_only_on_fresh_write(self) -> None:
        send = AsyncMock()
        created = story_daily.DailyNoteResult(
            Path("story/daily/2026-07-15.md"), "preview", True
        )
        skipped = story_daily.DailyNoteResult(
            Path("story/daily/2026-07-15.md"), "preview", False
        )

        # Routing is covered in test_daily_note_routing; pin it here so this
        # test asserts only the fresh-write gate, independent of any registry
        # present in the environment.
        with (
            patch("mage.river_channel_id_for_practice_dir", return_value=42),
            patch("artifact_presenter.send_artifact_surface", send),
        ):
            await story_daily.post_daily_note_river_visibility(
                date(2026, 7, 15), created
            )
            await story_daily.post_daily_note_river_visibility(
                date(2026, 7, 15), skipped
            )

        send.assert_awaited_once()
        kwargs = send.await_args.kwargs
        self.assertFalse(kwargs.get("silent", True))
        surface = send.await_args.args[1]
        self.assertEqual(surface.template_id, "post_daily_note")


if __name__ == "__main__":
    unittest.main()
