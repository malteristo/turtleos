"""Tests for the daily note writer (issue 039, TURTLE_SPEC §6.5)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import story_daily


TARGET = date(2026, 7, 15)


def _write_entry(
    eddies_dir: Path,
    filename: str,
    *,
    timestamp: str,
    title: str,
    body: str,
    topics: list[str] | None = None,
) -> None:
    fields = {
        "thread": "111",
        "title": title,
        "trigger": "manual",
        "timestamp": timestamp,
        "related-topics": topics or [],
    }
    dumped = yaml.safe_dump(fields, sort_keys=False, allow_unicode=True).strip()
    eddies_dir.mkdir(parents=True, exist_ok=True)
    (eddies_dir / filename).write_text(
        f"---\n{dumped}\n---\n\n{body}\n", encoding="utf-8"
    )


def _write_prior_daily(daily_dir: Path, day: date, body: str) -> None:
    daily_dir.mkdir(parents=True, exist_ok=True)
    fields = {"date": day.isoformat(), "eddy_count": 1, "related-topics": []}
    dumped = yaml.safe_dump(fields, sort_keys=False).strip()
    (daily_dir / f"{day.isoformat()}.md").write_text(
        f"---\n{dumped}\n---\n\n{body}\n", encoding="utf-8"
    )


SYNTH_BODY = (
    "You moved between sleep worries and weekend planning today. The thread "
    "about health kept surfacing without forcing a single conclusion — a day "
    "of tending rather than deciding."
)


class DailyNoteWriterTests(unittest.IsolatedAsyncioTestCase):
    def _practice(self, tmp: str) -> Path:
        root = Path(tmp)
        _write_entry(
            root / "story" / "eddies",
            "111-morning.md",
            timestamp="2026-07-15T09:00:00+02:00",
            title="Sleep check-in",
            body="You talked through another rough night.",
            topics=["health"],
        )
        _write_entry(
            root / "story" / "eddies",
            "222-trip.md",
            timestamp="2026-07-15T14:00:00+02:00",
            title="Weekend trip",
            body="You sketched a packing list for the weekend.",
        )
        return root

    async def test_two_eddy_entries_write_coherent_note(self) -> None:
        llm = AsyncMock(return_value=SYNTH_BODY)
        with tempfile.TemporaryDirectory() as tmp:
            root = self._practice(tmp)
            with patch("story_daily.chat_ollama", llm):
                result = await story_daily.write_daily_note(
                    TARGET, practice_dir=root
                )

            path = root / "story" / "daily" / "2026-07-15.md"
            self.assertTrue(result.created)
            self.assertEqual(result.note_path, path)
            self.assertTrue(path.is_file())
            self.assertIn(SYNTH_BODY, path.read_text(encoding="utf-8"))
            self.assertEqual(result.preview_text, SYNTH_BODY)

            front = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])
            self.assertEqual(front["date"], "2026-07-15")
            self.assertEqual(front["eddy_count"], 2)
            self.assertEqual(front["related-topics"], ["health"])

    async def test_zero_eddy_entries_skip_without_llm(self) -> None:
        llm = AsyncMock(return_value=SYNTH_BODY)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("story_daily.chat_ollama", llm):
                result = await story_daily.write_daily_note(
                    TARGET, practice_dir=root
                )

            self.assertFalse(result.created)
            self.assertIsNone(result.note_path)
            llm.assert_not_called()
            self.assertFalse((root / "story" / "daily").exists())

    async def test_prior_daily_notes_included_in_prompt(self) -> None:
        llm = AsyncMock(return_value=SYNTH_BODY)
        with tempfile.TemporaryDirectory() as tmp:
            root = self._practice(tmp)
            _write_prior_daily(
                root / "story" / "daily",
                date(2026, 7, 14),
                "Yesterday you rested more than you expected.",
            )
            with patch("story_daily.chat_ollama", llm):
                await story_daily.write_daily_note(TARGET, practice_dir=root)

            prompt = llm.await_args.args[1][0]["content"]
            self.assertIn("RECENT DAYS", prompt)
            self.assertIn("2026-07-14", prompt)
            self.assertIn("rested more than you expected", prompt)

    async def test_idempotent_skip_then_force_overwrite(self) -> None:
        llm = AsyncMock(
            side_effect=[SYNTH_BODY, "You refreshed the day with new emphasis."]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._practice(tmp)
            path = root / "story" / "daily" / "2026-07-15.md"

            with patch("story_daily.chat_ollama", llm):
                first = await story_daily.write_daily_note(
                    TARGET, practice_dir=root
                )
                second = await story_daily.write_daily_note(
                    TARGET, practice_dir=root
                )
                third = await story_daily.write_daily_note(
                    TARGET, practice_dir=root, force=True
                )

            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(second.note_path, path)
            self.assertTrue(third.created)
            self.assertIn(
                "You refreshed the day with new emphasis.",
                path.read_text(encoding="utf-8"),
            )
            self.assertEqual(llm.await_count, 2)

    async def test_degenerate_llm_output_raises_before_write(self) -> None:
        llm = AsyncMock(return_value="(no response generated)")
        with tempfile.TemporaryDirectory() as tmp:
            root = self._practice(tmp)
            with patch("story_daily.chat_ollama", llm):
                with self.assertRaises(story_daily.DailyNoteError):
                    await story_daily.write_daily_note(
                        TARGET, practice_dir=root
                    )

            self.assertFalse(
                (root / "story" / "daily" / "2026-07-15.md").exists()
            )


if __name__ == "__main__":
    unittest.main()
