"""Eddy-open continuity record — dimensions + first pair, no catch-up verdict."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import continuity_open as co

CEST = timezone(timedelta(hours=2))
AFTER = datetime(2026, 9, 14, 9, 0, tzinfo=CEST)
BEFORE = datetime(2026, 9, 12, 9, 0, tzinfo=CEST)


def _note(path: Path, eddy_id: str, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nthread: '{eddy_id}'\ntimestamp: '{when.isoformat()}'\n---\n\nnote\n",
        encoding="utf-8",
    )


class DimensionLoadTests(unittest.TestCase):
    def test_absent_context_is_named_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loads = co.dimension_loads(tmp, thread_loaded=True)
        self.assertEqual(loads["context"], "not loaded — file absent")
        self.assertEqual(loads["thread"], "loaded")
        self.assertEqual(loads["character"], "not loaded")
        self.assertEqual(loads["relation"], "not loaded")

    def test_present_files_count_as_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mirror.md").write_text("who", encoding="utf-8")
            (root / "resonance.md").write_text("trust", encoding="utf-8")
            (root / "state").mkdir()
            (root / "state" / "context.md").write_text("now", encoding="utf-8")
            loads = co.dimension_loads(root, thread_loaded=False)
        self.assertEqual(loads["character"], "loaded")
        self.assertEqual(loads["relation"], "loaded")
        self.assertEqual(loads["context"], "loaded")
        self.assertEqual(loads["thread"], "not loaded")


class PersistOnceTests(unittest.TestCase):
    def test_first_write_keeps_the_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = co.persist_first_exchange(
                tmp,
                42,
                practitioner_text="where were we",
                turtle_text="here",
                thread_loaded=True,
                recorded_at=AFTER,
            )
            self.assertIsNotNone(path)
            first = path.read_text(encoding="utf-8")
            co.persist_first_exchange(
                tmp,
                42,
                practitioner_text="later",
                turtle_text="changed",
                thread_loaded=False,
            )
            later = path.read_text(encoding="utf-8")
        self.assertEqual(first, later)
        self.assertIn("where were we", first)
        self.assertIn("here", first)
        self.assertNotIn("later", later)
        self.assertNotIn("reoriented", first.lower())
        self.assertNotIn("caught up", first.lower())

    def test_missing_root_is_a_noop(self) -> None:
        self.assertIsNone(
            co.persist_first_exchange(
                "/nonexistent-practice-dir",
                1,
                practitioner_text="x",
                turtle_text="y",
                thread_loaded=True,
            )
        )


class CompletedMissingTests(unittest.TestCase):
    def test_a_new_note_without_a_record_fails(self) -> None:
        """Positive control: empty output is not evidence the writer ran."""
        with tempfile.TemporaryDirectory() as tmp:
            _note(Path(tmp) / "story" / "eddies" / "99-gap.md", "99", AFTER)
            missing = co.completed_eddies_missing_record(tmp)
        self.assertEqual(missing, ["99"])

    def test_a_new_note_with_a_record_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _note(Path(tmp) / "story" / "eddies" / "7-ok.md", "7", AFTER)
            co.persist_first_exchange(
                tmp,
                7,
                practitioner_text="hi",
                turtle_text="hello",
                thread_loaded=True,
            )
            self.assertEqual(co.completed_eddies_missing_record(tmp), [])

    def test_notes_from_before_the_writer_are_not_owed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _note(Path(tmp) / "story" / "eddies" / "1-old.md", "1", BEFORE)
            self.assertEqual(co.completed_eddies_missing_record(tmp), [])


if __name__ == "__main__":
    unittest.main()
