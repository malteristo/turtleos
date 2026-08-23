"""A dropped record is visible to nobody — so count it where a human reads.

Pins the 2026-08-07 repair to the eddy-note write path. The read-error chapter
found two failures stacked: the note write timed out like the dialogue did,
*and* the checkpoint anchor advanced anyway — closing the window behind a
write that never happened, which is why two 08-06 river eddies have no note
and never would have got one.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from core import record_gaps


class RecordGapLedgerTests(unittest.TestCase):
    def test_records_and_tallies_by_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            record_gaps.record(td, kind="eddy_note", reason="failed", channel_id=1)
            record_gaps.record(td, kind="eddy_note", reason="failed", channel_id=1)
            record_gaps.record(td, kind="eddy_note", reason="exhausted", channel_id=1)
            record_gaps.record(td, kind="eddy_note", reason="declined", channel_id=2)

            counts = record_gaps.tally([td])
            self.assertEqual(counts["eddy_note"]["failed"], 2)
            self.assertEqual(counts["eddy_note"]["exhausted"], 1)
            self.assertEqual(counts["eddy_note"]["declined"], 1)

    def test_unknown_reason_is_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            record_gaps.record(td, kind="eddy_note", reason="vibes")
            self.assertFalse(record_gaps.gaps_path(td).exists())

    def test_recording_never_raises(self) -> None:
        """A failure to record a failure must not take down the checkpoint."""
        record_gaps.record("/nonexistent/\0/path", kind="eddy_note", reason="failed")

    def test_a_path_that_never_failed_still_renders(self) -> None:
        """The lesson offer_ledger paid for: a missing row and a zero row mean
        opposite things."""
        section = record_gaps.render_record_gaps_section({}, window_days=30)
        for kind in record_gaps.KINDS:
            self.assertIn(kind, section)
        self.assertIn("No gaps", section)

    def test_lost_records_are_the_headline(self) -> None:
        counts = {"eddy_note": {"failed": 3, "exhausted": 2, "declined": 0}}
        section = record_gaps.render_record_gaps_section(counts, window_days=30)
        self.assertIn("2 record(s) lost", section)
        self.assertIn("holes, not delays", section)

    def test_recovered_failures_are_not_reported_as_holes(self) -> None:
        counts = {"eddy_note": {"failed": 4, "exhausted": 0, "declined": 0}}
        section = record_gaps.render_record_gaps_section(counts, window_days=30)
        self.assertIn("recovered on retry", section)
        self.assertIn("No holes", section)


class CheckpointRetryTests(unittest.IsolatedAsyncioTestCase):
    """The note is retried on an outage and not on a decline."""

    async def test_timeout_is_retried_and_can_recover(self) -> None:
        import sessions

        calls = {"n": 0}

        async def flaky(*a, **kw):
            calls["n"] += 1
            if calls["n"] < 2:
                raise TimeoutError("ReadTimeout")
            return MagicMock(note_path=Path("/tmp/n.md"), preview_text="ok")

        with patch.object(sessions.story_notes, "write_eddy_note", flaky), \
             patch.object(sessions, "_record_gap"), \
             patch.object(sessions.asyncio, "sleep", AsyncMock()):
            note, failed = await _run_note_loop(sessions)

        self.assertEqual(calls["n"], 2)
        self.assertIsNotNone(note)
        self.assertFalse(failed)

    async def test_a_declined_note_is_never_retried(self) -> None:
        import sessions

        calls = {"n": 0}

        async def declines(*a, **kw):
            calls["n"] += 1
            raise sessions.story_notes.EddyNoteError("nothing worth writing")

        with patch.object(sessions.story_notes, "write_eddy_note", declines), \
             patch.object(sessions, "_record_gap"), \
             patch.object(sessions.asyncio, "sleep", AsyncMock()):
            note, failed = await _run_note_loop(sessions)

        self.assertEqual(calls["n"], 1, "a decline is an answer, not an outage")
        self.assertIsNone(note)
        self.assertFalse(failed, "a decline must not hold the anchor open")

    async def test_exhausting_every_attempt_marks_the_window_unrecorded(self) -> None:
        import sessions

        calls = {"n": 0}

        async def always_fails(*a, **kw):
            calls["n"] += 1
            raise TimeoutError("ReadTimeout")

        with patch.object(sessions.story_notes, "write_eddy_note", always_fails), \
             patch.object(sessions, "_record_gap") as gap, \
             patch.object(sessions.asyncio, "sleep", AsyncMock()):
            note, failed = await _run_note_loop(sessions)

        self.assertEqual(calls["n"], sessions.EDDY_NOTE_ATTEMPTS)
        self.assertIsNone(note)
        self.assertTrue(failed, "the anchor must stay open when nothing was written")
        reasons = [c.kwargs.get("reason") for c in gap.call_args_list]
        self.assertIn("exhausted", reasons)


async def _run_note_loop(sessions):
    """Exercise the retry loop's contract without a live Discord checkpoint."""
    note = None
    note_failed = False
    for attempt in range(1, sessions.EDDY_NOTE_ATTEMPTS + 1):
        try:
            note = await sessions.story_notes.write_eddy_note(1, [])
            note_failed = False
            break
        except sessions.story_notes.EddyNoteError as e:
            sessions._record_gap(1, reason="declined", detail=str(e))
            break
        except Exception as e:
            note_failed = True
            sessions._record_gap(1, reason="failed", detail=str(e), attempts=attempt)
            if attempt < sessions.EDDY_NOTE_ATTEMPTS:
                await sessions.asyncio.sleep(0)
            else:
                sessions._record_gap(1, reason="exhausted", detail=str(e), attempts=attempt)
    return note, note_failed


class AnchorHoldTests(unittest.TestCase):
    """The deeper half: a failed write used to close the window behind itself."""

    def test_checkpoint_holds_the_anchor_when_the_note_was_lost(self) -> None:
        src = Path(__file__).resolve().parent.parent / "sessions.py"
        body = src.read_text()
        self.assertIn("elif note_failed:", body)
        # And the advance is still reachable on the success path.
        self.assertIn("last_checkpoint_anchor[channel_id] = _history_fingerprints", body)

    def test_the_report_reads_the_gaps(self) -> None:
        """A ledger nothing renders is the defect this repo has shipped twice."""
        runner = (
            Path(__file__).resolve().parent.parent / "scripts" / "ops_runner.py"
        ).read_text()
        report = (
            Path(__file__).resolve().parent.parent / "scripts" / "write_ops_report.py"
        ).read_text()
        self.assertIn("_collect_record_gaps", runner)
        self.assertIn('"record_gaps":', runner)
        self.assertIn('bundle.get("record_gaps")', report)


class GapKindCoverageTests(unittest.TestCase):
    """The same guard offer_ledger earned on 2026-08-06, applied here first.

    A kind that reaches this ledger but is absent from ``KINDS`` renders as no
    row at all — and a write path that can silently fail is exactly the thing
    that must not be invisible in the instrument built to see it.
    """

    def _emitted_kinds(self) -> dict[str, set[str]]:
        import ast

        repo = Path(__file__).resolve().parent.parent
        emitted: dict[str, set[str]] = {}
        for path in sorted(repo.glob("*.py")):
            found: set[str] = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                # Direct emission, plus the thin per-module wrappers that forward
                # to it. A wrapper that took `kind` as a variable would make its
                # module invisible here and the scan would pass by finding
                # nothing — which is why every call site names its kind as a
                # literal and this scan follows both shapes.
                direct = (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "record"
                    and getattr(node.func.value, "id", "") == "record_gaps"
                )
                wrapped = isinstance(node.func, ast.Name) and node.func.id == "_record_gap"
                if not (direct or wrapped):
                    continue
                for kw in node.keywords:
                    if (
                        kw.arg == "kind"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        found.add(kw.value.value)
            if found:
                emitted[path.name] = found
        return emitted

    def test_every_emitted_gap_kind_is_watched(self) -> None:
        emitted = self._emitted_kinds()
        self.assertIn("sessions.py", emitted, "gap sites moved — retarget this scan")
        unwatched = {
            module: sorted(kinds - set(record_gaps.KINDS))
            for module, kinds in emitted.items()
            if kinds - set(record_gaps.KINDS)
        }
        self.assertEqual(unwatched, {}, f"unwatched record-gap kinds: {unwatched}")

    def test_scan_sees_kinds_routed_through_the_wrapper(self) -> None:
        """Control for the wrapper-following branch — not just that it runs."""
        emitted = self._emitted_kinds()
        self.assertIn("workspace_refresh", emitted.get("sessions.py", set()))
        self.assertIn("eddy_note", emitted.get("sessions.py", set()))

    def test_scan_catches_an_unwatched_kind(self) -> None:
        """Positive control — the guard above must be able to fail."""
        import ast

        tree = ast.parse('record_gaps.record(pd, kind="invented", reason="failed")')
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "record" and node.func.value.id == "record_gaps":
                    for kw in node.keywords:
                        if kw.arg == "kind":
                            found.add(kw.value.value)
        self.assertEqual(found - set(record_gaps.KINDS), {"invented"})


if __name__ == "__main__":
    unittest.main()
