"""Tests for daily note triggers (issue 040)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import yaml

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import state
import story_daily


TZ = ZoneInfo("Europe/Berlin")


def _write_entry(eddies_dir: Path, *, timestamp: str, body: str = "Held.") -> None:
    fields = {
        "thread": "111",
        "title": "Thread",
        "trigger": "manual",
        "timestamp": timestamp,
        "related-topics": [],
    }
    dumped = yaml.safe_dump(fields, sort_keys=False).strip()
    eddies_dir.mkdir(parents=True, exist_ok=True)
    (eddies_dir / "111-thread.md").write_text(
        f"---\n{dumped}\n---\n\n{body}\n", encoding="utf-8"
    )


class DailyNoteTriggerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        state.daily_note_catchup_done = None
        state.daily_note_scheduled_done = None

    async def test_scheduled_fires_once_when_hour_gate_and_material(self) -> None:
        write = AsyncMock(
            return_value=story_daily.DailyNoteResult(
                Path("story/daily/2026-07-15.md"), "preview", True
            )
        )
        now = datetime(2026, 7, 15, 22, 30, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_entry(
                root / "story" / "eddies",
                timestamp="2026-07-15T10:00:00+02:00",
            )
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.get_pd", return_value=str(root)),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                first = await story_daily.run_scheduled_daily_note()
                second = await story_daily.run_scheduled_daily_note()

            write.assert_awaited_once()
            self.assertIsNotNone(first)

    async def test_scheduled_skips_when_daily_file_exists(self) -> None:
        write = AsyncMock()
        now = datetime(2026, 7, 15, 23, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily = root / "story" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-07-15.md").write_text("exists", encoding="utf-8")
            _write_entry(
                root / "story" / "eddies",
                timestamp="2026-07-15T10:00:00+02:00",
            )
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.get_pd", return_value=str(root)),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                result = await story_daily.run_scheduled_daily_note()

            write.assert_not_called()
            self.assertIsNone(result)

    async def test_scheduled_skips_empty_eddy_day(self) -> None:
        write = AsyncMock()
        now = datetime(2026, 7, 15, 22, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.get_pd", return_value=tmp),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                result = await story_daily.run_scheduled_daily_note()

            write.assert_not_called()
            self.assertIsNone(result)

    async def test_catchup_writes_yesterday_once_before_noon(self) -> None:
        write = AsyncMock(
            return_value=story_daily.DailyNoteResult(
                Path("story/daily/2026-07-14.md"), "preview", True
            )
        )
        now = datetime(2026, 7, 15, 9, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_entry(
                root / "story" / "eddies",
                timestamp="2026-07-14T18:00:00+02:00",
            )
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.get_pd", return_value=str(root)),
                patch("story_daily.write_daily_note", write),
            ):
                first = await story_daily.maybe_run_daily_note_catchup()
                second = await story_daily.maybe_run_daily_note_catchup()

            write.assert_awaited_once_with(date(2026, 7, 14), practice_dir=root)
            self.assertEqual(state.daily_note_catchup_done, "2026-07-14")
            self.assertIsNotNone(first)
            self.assertIsNone(second)

    async def test_catchup_skips_after_noon(self) -> None:
        write = AsyncMock()
        now = datetime(2026, 7, 15, 12, 0, tzinfo=TZ)
        with patch("story_daily.local_now", return_value=now), patch(
            "story_daily.write_daily_note", write
        ):
            result = await story_daily.maybe_run_daily_note_catchup()

        write.assert_not_called()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
