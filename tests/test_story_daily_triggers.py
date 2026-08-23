"""Tests for daily note triggers (issue 040; INT-046 root-explicit)."""

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


def _write_entry(
    eddies_dir: Path, *, timestamp: str, body: str = "Held.", thread: str = "111"
) -> None:
    fields = {
        "thread": thread,
        "title": "Thread",
        "trigger": "manual",
        "timestamp": timestamp,
        "related-topics": [],
    }
    dumped = yaml.safe_dump(fields, sort_keys=False).strip()
    eddies_dir.mkdir(parents=True, exist_ok=True)
    (eddies_dir / f"{thread}-thread.md").write_text(
        f"---\n{dumped}\n---\n\n{body}\n", encoding="utf-8"
    )


class DailyNoteTriggerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        state.daily_note_catchup_done = {}
        state.daily_note_scheduled_done = {}

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
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                first = await story_daily.run_scheduled_daily_note(
                    practice_dirs=[root]
                )
                second = await story_daily.run_scheduled_daily_note(
                    practice_dirs=[root]
                )

            write.assert_awaited_once()
            self.assertIsNotNone(first)
            self.assertIsNone(second)

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
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                result = await story_daily.run_scheduled_daily_note(
                    practice_dirs=[root]
                )

            write.assert_not_called()
            self.assertIsNone(result)

    async def test_scheduled_skips_empty_eddy_day(self) -> None:
        write = AsyncMock()
        now = datetime(2026, 7, 15, 22, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                result = await story_daily.run_scheduled_daily_note(
                    practice_dirs=[tmp]
                )

            write.assert_not_called()
            self.assertIsNone(result)

    async def test_scheduled_writes_non_primary_root_while_primary_also_has_material(
        self,
    ) -> None:
        """INT-046 regression: a non-primary root must win its own scheduled day."""
        write = AsyncMock(
            side_effect=lambda day, practice_dir: story_daily.DailyNoteResult(
                Path(practice_dir) / "story" / "daily" / f"{day.isoformat()}.md",
                "preview",
                True,
            )
        )
        now = datetime(2026, 7, 15, 22, 30, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "kermit"
            hosted = Path(tmp) / "partner"
            for root, thread in ((primary, "111"), (hosted, "222")):
                _write_entry(
                    root / "story" / "eddies",
                    timestamp="2026-07-15T10:00:00+02:00",
                    thread=thread,
                )
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                await story_daily.run_scheduled_daily_note(
                    practice_dirs=[primary, hosted]
                )

            self.assertEqual(write.await_count, 2)
            written_roots = {
                call.kwargs["practice_dir"] for call in write.await_args_list
            }
            self.assertEqual(written_roots, {primary, hosted})
            self.assertEqual(
                state.daily_note_scheduled_done[story_daily._done_key(primary)],
                "2026-07-15",
            )
            self.assertEqual(
                state.daily_note_scheduled_done[story_daily._done_key(hosted)],
                "2026-07-15",
            )

    async def test_scheduled_primary_done_does_not_suppress_other_root(self) -> None:
        """INT-046: per-root done-keys — first root must not silence the second."""
        write = AsyncMock(
            return_value=story_daily.DailyNoteResult(
                Path("story/daily/2026-07-15.md"), "preview", True
            )
        )
        now = datetime(2026, 7, 15, 22, 30, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "kermit"
            hosted = Path(tmp) / "family"
            _write_entry(
                primary / "story" / "eddies",
                timestamp="2026-07-15T10:00:00+02:00",
                thread="111",
            )
            _write_entry(
                hosted / "story" / "eddies",
                timestamp="2026-07-15T11:00:00+02:00",
                thread="222",
            )
            state.daily_note_scheduled_done[story_daily._done_key(primary)] = (
                "2026-07-15"
            )
            with (
                patch("story_daily.local_now", return_value=now),
                patch("story_daily.write_daily_note", write),
                patch.object(state, "DAILY_NOTE_HOUR", 22),
            ):
                await story_daily.run_scheduled_daily_note(
                    practice_dirs=[primary, hosted]
                )

            write.assert_awaited_once_with(
                date(2026, 7, 15), practice_dir=hosted
            )

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
                patch("story_daily.write_daily_note", write),
            ):
                first = await story_daily.maybe_run_daily_note_catchup(
                    practice_dir=root
                )
                second = await story_daily.maybe_run_daily_note_catchup(
                    practice_dir=root
                )

            write.assert_awaited_once_with(date(2026, 7, 14), practice_dir=root)
            self.assertEqual(
                state.daily_note_catchup_done[story_daily._done_key(root)],
                "2026-07-14",
            )
            self.assertIsNotNone(first)
            self.assertIsNone(second)

    async def test_catchup_skips_after_noon(self) -> None:
        write = AsyncMock()
        now = datetime(2026, 7, 15, 12, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("story_daily.local_now", return_value=now), patch(
                "story_daily.write_daily_note", write
            ):
                result = await story_daily.maybe_run_daily_note_catchup(
                    practice_dir=tmp
                )

        write.assert_not_called()
        self.assertIsNone(result)

    async def test_catchup_without_context_does_not_fall_back_to_primary(self) -> None:
        """INT-046: no ambient primary — unresolvable context is a no-op."""
        write = AsyncMock()
        now = datetime(2026, 7, 15, 9, 0, tzinfo=TZ)
        with (
            patch("story_daily.local_now", return_value=now),
            patch("story_daily.current_practice_dir", return_value=None),
            patch("story_daily.write_daily_note", write),
            patch("story_daily.get_pd") as get_pd,
        ):
            result = await story_daily.maybe_run_daily_note_catchup()

        write.assert_not_called()
        get_pd.assert_not_called()
        self.assertIsNone(result)

    async def test_catchup_uses_active_context_not_get_pd(self) -> None:
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
                patch("story_daily.current_practice_dir", return_value=str(root)),
                patch("story_daily.write_daily_note", write),
                patch("story_daily.get_pd") as get_pd,
            ):
                await story_daily.maybe_run_daily_note_catchup()

            write.assert_awaited_once_with(date(2026, 7, 14), practice_dir=root)
            get_pd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
