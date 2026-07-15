import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import story_notes
from helpers import local_now
from sessions import CheckpointResult, checkpoint_session, close_session


HISTORY_4 = [
    {"role": "user", "content": "I slept terribly again last night."},
    {"role": "assistant", "content": "Rough. Any idea what kept you up?"},
    {"role": "user", "content": "Maybe the late walks. And we should plan the weekend trip."},
    {"role": "assistant", "content": "Earlier walks could help. For the trip: pack light."},
]

HISTORY_6 = HISTORY_4 + [
    {"role": "user", "content": "Actually, the trip is what I care about right now."},
    {"role": "assistant", "content": "Then let's nail the itinerary."},
]

VALID_LLM_RESPONSE = (
    "---HELD---\n"
    "Kermit talked through a rough night of sleep and traced it to late walks. "
    "A plan emerged to move the walks earlier.\n"
    "---RELATION---\nnone\n"
    "---RELATED-TOPICS---\nnone\n"
    "---END---"
)


def _msg(i: int, prefix: str = "M") -> dict:
    role = "user" if i % 2 == 0 else "assistant"
    return {"role": role, "content": f"{prefix}{i} distinct message body {prefix}{i} end"}


def _fingerprints(history: list[dict]) -> list[tuple[str, str]]:
    return [(m["role"], m["content"]) for m in history]


def _fake_note(tmp: str, entry_body: str = "A note body.") -> story_notes.EddyNoteResult:
    entry_text = (
        "---\n"
        "thread: '42'\n"
        "title: Test eddy\n"
        "trigger: idle\n"
        "timestamp: 2026-07-15T07:00:00\n"
        "related-topics: []\n"
        "---\n\n"
        f"{entry_body}\n"
    )
    return story_notes.EddyNoteResult(
        note_path=Path(tmp) / "story" / "eddies" / "42-test-eddy.md",
        entry_text=entry_text,
        preview_text=entry_body,
    )


class CheckpointResultTests(unittest.TestCase):
    def test_captured_anything(self) -> None:
        self.assertFalse(CheckpointResult().captured_anything)
        self.assertTrue(
            CheckpointResult(flow_writes=["state/notes/shelter-last.md"]).captured_anything
        )
        self.assertTrue(CheckpointResult(session_note="2026-06-18.md").captured_anything)
        self.assertTrue(
            CheckpointResult(eddy_note=_fake_note("/tmp/x")).captured_anything
        )


class _CheckpointHarness(unittest.IsolatedAsyncioTestCase):
    """CRITICAL test hygiene (issue 037): practice-root resolution is patched
    to a temp dir in every test — nothing may resolve or write ~/workshops/."""

    CHANNEL_ID = 42

    def setUp(self) -> None:
        self._clear_state()

    def tearDown(self) -> None:
        self._clear_state()

    def _clear_state(self) -> None:
        from state import active_sessions, last_checkpoint_anchor, last_reflection_time

        active_sessions.pop(self.CHANNEL_ID, None)
        last_reflection_time.pop(self.CHANNEL_ID, None)
        last_checkpoint_anchor.pop(self.CHANNEL_ID, None)

    def _patched(
        self,
        practice_dir: str,
        history: list[dict],
        flow_writes: list[str] | None = None,
    ) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("sessions.set_practice_context_for_channel"))
        stack.enter_context(patch("sessions.get_pd", return_value=practice_dir))
        stack.enter_context(patch("sessions.reload_history", return_value=history))
        stack.enter_context(patch("sessions.get_mage_name", return_value="Kermit"))
        stack.enter_context(patch("sessions.get_mage_type", return_value="mage"))
        stack.enter_context(
            patch(
                "sessions._write_flow_checkpoint_if_needed",
                new_callable=AsyncMock,
                return_value=flow_writes or [],
            )
        )
        stack.enter_context(
            patch("sessions.assess_readiness", return_value={"dimensions": []})
        )
        stack.enter_context(patch("sessions.save_readiness_trail"))
        stack.enter_context(patch("sessions.log_activity", new_callable=AsyncMock))
        stack.enter_context(patch("sessions.client", MagicMock()))
        return stack


class CheckpointConvergenceTests(_CheckpointHarness):
    """Issue 035 / TURTLE_SPEC §8.4 (2026-07-14b): the eddy note is THE
    reflection artifact at checkpoint; cooldown gates idle triggers only."""

    async def test_manual_checkpoint_bypasses_cooldown_after_idle_checkpoint(self) -> None:
        """A manual !checkpoint immediately after an idle checkpoint (well
        within SESSION_REFLECTION_COOLDOWN) must still write an eddy note,
        weighted via since_index = exchange count at the previous checkpoint."""
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ):
                idle_result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="idle", mark_paused=True
                )
            self.assertIsNotNone(idle_result.eddy_note)

            with self._patched(tmp, HISTORY_6), patch(
                "story_notes.write_eddy_note", writer
            ):
                manual_result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

        self.assertIsNotNone(manual_result.eddy_note)
        self.assertEqual(writer.await_count, 2)
        # since_index = the per-channel exchange count recorded at the idle checkpoint.
        self.assertEqual(writer.await_args.args, (self.CHANNEL_ID, HISTORY_6))
        self.assertEqual(writer.await_args.kwargs["trigger"], "manual")
        self.assertEqual(writer.await_args.kwargs["since_index"], len(HISTORY_4))

    async def test_first_checkpoint_passes_no_since_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ):
                await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )
        self.assertIsNone(writer.await_args.kwargs["since_index"])

    async def test_idle_checkpoint_within_cooldown_skips_reflection_keeps_capture(self) -> None:
        """Existing behavior preserved for idle: within the cooldown window the
        reflection is skipped, but flow captures and the chronicle still run."""
        from state import last_reflection_time

        last_reflection_time[self.CHANNEL_ID] = datetime.now(timezone.utc).timestamp()
        flow = ["state/notes/shelter-last.md"]
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, HISTORY_4, flow_writes=flow), patch(
                "story_notes.write_eddy_note", writer
            ), patch("sessions._append_resonance_chronicle") as chronicle:
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="idle", mark_paused=True
                )

        writer.assert_not_awaited()
        self.assertIsNone(result.eddy_note)
        self.assertIsNone(result.session_note)
        self.assertEqual(result.flow_writes, flow)
        chronicle.assert_called_once_with(self.CHANNEL_ID, result)

    async def test_release_checkpoint_bypasses_cooldown_and_clears_anchor(self) -> None:
        from state import last_checkpoint_anchor, last_reflection_time

        last_reflection_time[self.CHANNEL_ID] = datetime.now(timezone.utc).timestamp()
        last_checkpoint_anchor[self.CHANNEL_ID] = _fingerprints(HISTORY_4[:2])
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ):
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="release", mark_paused=True
                )

        writer.assert_awaited_once()
        self.assertIsNotNone(result.eddy_note)
        # Release clears history afterwards — a stale anchor must not survive.
        self.assertNotIn(self.CHANNEL_ID, last_checkpoint_anchor)

    async def test_exactly_one_reflection_llm_call_per_checkpoint(self) -> None:
        """Cost flat (destination criterion 5): the eddy note absorbs the
        session-note reflection — one reflection-class LLM call, no legacy
        session-note call, no second call for the day-file assembly."""
        story_llm = AsyncMock(return_value=VALID_LLM_RESPONSE)
        sessions_llm = AsyncMock()
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.chat_ollama", story_llm
            ), patch("sessions.chat_ollama", sessions_llm), patch(
                "story_notes.set_practice_context_for_channel"
            ), patch("story_notes.get_pd", return_value=tmp), patch(
                "story_notes.get_mage_name", return_value="Kermit"
            ), patch(
                "story_notes._resolve_thread_title", return_value="Sleep check-in"
            ):
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            self.assertEqual(story_llm.await_count, 1)
            sessions_llm.assert_not_awaited()
            self.assertIsNotNone(result.eddy_note)
            self.assertTrue(result.eddy_note.note_path.exists())
            self.assertIn("rough night of sleep", result.eddy_note.entry_text)

    async def test_session_day_file_assembles_days_eddy_note_entries(self) -> None:
        """sessions/YYYY-MM-DD.md is a mechanical assembly of the day's
        eddy-note entries — one file per day, appended, no LLM call."""
        with tempfile.TemporaryDirectory() as tmp:
            first_note = _fake_note(tmp, "First conversation body.")
            second_note = _fake_note(tmp, "Second conversation body.")
            writer = AsyncMock(side_effect=[first_note, second_note])
            sessions_llm = AsyncMock()
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ), patch("sessions.chat_ollama", sessions_llm):
                first = await checkpoint_session(
                    self.CHANNEL_ID, trigger="idle", mark_paused=True
                )
            with self._patched(tmp, HISTORY_6), patch(
                "story_notes.write_eddy_note", writer
            ), patch("sessions.chat_ollama", sessions_llm):
                second = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            today = local_now().strftime("%Y-%m-%d")
            day_files = sorted((Path(tmp) / "sessions").glob("*.md"))
            self.assertEqual(day_files, [Path(tmp) / "sessions" / f"{today}.md"])
            content = day_files[0].read_text(encoding="utf-8")
            self.assertIn("First conversation body.", content)
            self.assertIn("Second conversation body.", content)
            # Arrival-reader compatibility (destination criterion 8 / Flag A):
            # markdown file with the session-day heading.
            self.assertTrue(content.startswith(f"# Session — {today}"))
            self.assertEqual(first.session_note, f"{today}.md")
            self.assertEqual(second.session_note, f"{today}.md")
            sessions_llm.assert_not_awaited()

    async def test_eddy_note_error_degrades_gracefully(self) -> None:
        """A failed reflection must never break the checkpoint — flow captures
        and the chronicle still land; the result reflects no note written."""
        flow = ["state/notes/shelter-last.md"]
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(side_effect=story_notes.EddyNoteError("degenerate reply"))
            with self._patched(tmp, HISTORY_4, flow_writes=flow), patch(
                "story_notes.write_eddy_note", writer
            ), patch("sessions._append_resonance_chronicle") as chronicle:
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            writer.assert_awaited_once()
            self.assertIsNone(result.eddy_note)
            self.assertIsNone(result.session_note)
            self.assertEqual(result.flow_writes, flow)
            chronicle.assert_called_once_with(self.CHANNEL_ID, result)
            self.assertEqual(list((Path(tmp) / "sessions").glob("*")) if (
                Path(tmp) / "sessions"
            ).exists() else [], [])

    async def test_unexpected_writer_exception_degrades_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(side_effect=RuntimeError("ollama unreachable"))
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ), patch("sessions._append_resonance_chronicle") as chronicle:
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="idle", mark_paused=True
                )

            self.assertIsNone(result.eddy_note)
            chronicle.assert_called_once_with(self.CHANNEL_ID, result)

    async def test_short_history_records_checkpoint_anchor_without_reflection(self) -> None:
        from state import last_checkpoint_anchor

        short = HISTORY_4[:2]
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, short), patch(
                "story_notes.write_eddy_note", writer
            ):
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="idle", mark_paused=True
                )
        writer.assert_not_awaited()
        self.assertIsNone(result.eddy_note)
        self.assertEqual(last_checkpoint_anchor[self.CHANNEL_ID], _fingerprints(short))

    async def test_chronicle_names_eddy_note_when_day_assembly_fails(self) -> None:
        """The chronicle must never go blind on a written note: when the
        day-file assembly fails after a successful eddy note, the chronicle
        label still names the note (practice-relative) and is never empty."""
        with tempfile.TemporaryDirectory() as tmp:
            writer = AsyncMock(return_value=_fake_note(tmp))
            chronicle = MagicMock()
            with self._patched(tmp, HISTORY_4), patch(
                "story_notes.write_eddy_note", writer
            ), patch(
                "sessions._append_session_day_entry",
                side_effect=RuntimeError("disk full"),
            ), patch("river_handler._append_chronicle", chronicle):
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            self.assertIsNotNone(result.eddy_note)
            self.assertIsNone(result.session_note)
            chronicle.assert_called_once()
            label = chronicle.call_args.args[1]
            deep = chronicle.call_args.args[2]
            self.assertIn("story/eddies/42-test-eddy.md", label)
            self.assertNotEqual(label.rstrip(), "💾 checkpoint (manual):")
            self.assertEqual(deep["eddy_note"], "story/eddies/42-test-eddy.md")


class SlidingWindowSinceIndexTests(_CheckpointHarness):
    """F1 (review 2026-07-15): the since-checkpoint boundary must survive the
    MAX_DIALOGUE_HISTORY sliding window (pops past 20) and mid-reflection
    appends to the live history list. The anchor is a fingerprint snapshot of
    the transcript at the previous checkpoint; the boundary is the longest
    anchor suffix that prefixes the current transcript."""

    async def _idle_checkpoint(self, tmp: str, history: list[dict]) -> None:
        writer = AsyncMock(return_value=_fake_note(tmp))
        with self._patched(tmp, history), patch("story_notes.write_eddy_note", writer):
            await checkpoint_session(self.CHANNEL_ID, trigger="idle", mark_paused=True)

    def _story_patches(self, stack: ExitStack, tmp: str) -> AsyncMock:
        """Run the REAL write_eddy_note with a fake LLM so the prompt split
        is observable."""
        llm = AsyncMock(return_value=VALID_LLM_RESPONSE)
        stack.enter_context(patch("story_notes.chat_ollama", llm))
        stack.enter_context(patch("story_notes.set_practice_context_for_channel"))
        stack.enter_context(patch("story_notes.get_pd", return_value=tmp))
        stack.enter_context(patch("story_notes.get_mage_name", return_value="Kermit"))
        stack.enter_context(
            patch("story_notes._resolve_thread_title", return_value="Window eddy")
        )
        return llm

    async def test_manual_weighting_survives_window_saturation(self) -> None:
        """(a) Idle checkpoint at a FULL 20-entry window, then 4 new exchanges
        arrive (4 oldest popped). The manual checkpoint must still weight —
        the 4 new exchanges land in the SINCE section, survivors in background."""
        old = [_msg(i) for i in range(20)]
        fresh = [_msg(i, prefix="N") for i in range(4)]
        after_window = old[4:] + fresh  # len stays 20 — saturation
        with tempfile.TemporaryDirectory() as tmp:
            await self._idle_checkpoint(tmp, old)

            with self._patched(tmp, after_window) as stack:
                llm = self._story_patches(stack, tmp)
                result = await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            self.assertIsNotNone(result.eddy_note)
            prompt = llm.await_args.args[1][0]["content"]
            self.assertIn("SINCE THE LAST CHECKPOINT", prompt)
            background, focus = prompt.split("SINCE THE LAST CHECKPOINT", 1)
            for m in fresh:
                self.assertIn(m["content"], focus)
                self.assertNotIn(m["content"], background)
            for m in old[4:]:
                self.assertIn(m["content"], background)
                self.assertNotIn(m["content"], focus)

    async def test_manual_weighting_splits_correctly_after_window_pops(self) -> None:
        """(b) Checkpoint at 16 entries; 8 more arrive and the window pops the
        4 oldest. The true boundary is 12 (survivors), not the recorded 16 —
        all 8 new exchanges must land in the SINCE section."""
        old = [_msg(i) for i in range(16)]
        fresh = [_msg(i, prefix="N") for i in range(8)]
        after_window = old[4:] + fresh  # 12 survivors + 8 new = 20
        with tempfile.TemporaryDirectory() as tmp:
            await self._idle_checkpoint(tmp, old)

            with self._patched(tmp, after_window) as stack:
                llm = self._story_patches(stack, tmp)
                await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            prompt = llm.await_args.args[1][0]["content"]
            self.assertIn("SINCE THE LAST CHECKPOINT", prompt)
            background, focus = prompt.split("SINCE THE LAST CHECKPOINT", 1)
            for m in fresh:
                self.assertIn(m["content"], focus)
                self.assertNotIn(m["content"], background)
            for m in old[4:]:
                self.assertIn(m["content"], background)
                self.assertNotIn(m["content"], focus)

    async def test_fully_rotated_window_degrades_to_unweighted(self) -> None:
        """When nothing from the previous checkpoint survived the window,
        everything is new — the whole transcript goes unweighted."""
        old = [_msg(i) for i in range(20)]
        rotated = [_msg(i, prefix="N") for i in range(20)]
        with tempfile.TemporaryDirectory() as tmp:
            await self._idle_checkpoint(tmp, old)

            with self._patched(tmp, rotated) as stack:
                llm = self._story_patches(stack, tmp)
                await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )

            prompt = llm.await_args.args[1][0]["content"]
            self.assertNotIn("SINCE THE LAST CHECKPOINT", prompt)
            self.assertIn(rotated[0]["content"], prompt)
            self.assertIn(rotated[-1]["content"], prompt)

    async def test_mid_reflection_appends_not_counted_as_covered(self) -> None:
        """(c) Race closure: the checkpoint snapshots the history at start.
        An exchange appended to the LIVE list during the reflection await is
        neither shown to the note nor claimed by the anchor — the next manual
        checkpoint weights it as new."""
        live = list(HISTORY_4)
        mid_reflection_msg = {"role": "user", "content": "arrived mid-reflection"}

        with tempfile.TemporaryDirectory() as tmp:
            first_writer = AsyncMock()

            async def append_during_await(*args, **kwargs):
                live.append(mid_reflection_msg)
                return _fake_note(tmp)

            first_writer.side_effect = append_during_await
            with self._patched(tmp, HISTORY_4) as stack:
                stack.enter_context(patch("sessions.reload_history", lambda cid: live))
                stack.enter_context(patch("story_notes.write_eddy_note", first_writer))
                await checkpoint_session(self.CHANNEL_ID, trigger="idle", mark_paused=True)

            # The note saw the consistent pre-await snapshot, not the append.
            seen = first_writer.await_args.args[1]
            self.assertEqual(seen, HISTORY_4)
            self.assertNotIn(mid_reflection_msg, seen)

            # The next manual checkpoint treats the appended exchange as new.
            second_writer = AsyncMock(return_value=_fake_note(tmp))
            with self._patched(tmp, live), patch(
                "story_notes.write_eddy_note", second_writer
            ):
                await checkpoint_session(
                    self.CHANNEL_ID, trigger="manual", mark_paused=False
                )
            self.assertEqual(second_writer.await_args.kwargs["since_index"], len(HISTORY_4))


class CheckpointSessionTests(_CheckpointHarness):
    async def test_idle_checkpoint_pauses_session(self) -> None:
        from sessions import active_sessions

        active_sessions[42] = {"closed": False, "last_message": datetime.now(timezone.utc)}
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, []), patch("sessions._append_resonance_chronicle"):
                result = await checkpoint_session(42, trigger="idle", mark_paused=True)
        self.assertTrue(result.paused)
        self.assertEqual(result.trigger, "idle")
        self.assertTrue(active_sessions[42]["closed"])

    async def test_manual_checkpoint_does_not_pause(self) -> None:
        from sessions import active_sessions

        active_sessions[42] = {"closed": False, "last_message": datetime.now(timezone.utc)}
        history = [{"role": "user", "content": "hi"}]
        flow = ["state/notes/shelter-last.md"]
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, history, flow_writes=flow), patch(
                "sessions._append_resonance_chronicle"
            ):
                result = await checkpoint_session(42, trigger="manual", mark_paused=False)
        self.assertFalse(result.paused)
        self.assertFalse(active_sessions[42]["closed"])
        self.assertEqual(result.flow_writes, flow)

    async def test_close_session_alias(self) -> None:
        with patch("sessions.checkpoint_session", new_callable=AsyncMock) as mock_cp:
            mock_cp.return_value = CheckpointResult(trigger="idle")
            await close_session(1)
            mock_cp.assert_awaited_once_with(1, trigger="idle", mark_paused=True)


class ManualEddyDissolveGateTests(unittest.IsolatedAsyncioTestCase):
    """TURTLE_SPEC §8.4: idle checkpoint pauses with history retained.
    Only an explicit release may dissolve a manual eddy (issue 001)."""

    def _checkpoint_patches(self, channel_id: int):
        from sessions import active_sessions
        from state import thread_configs

        active_sessions[channel_id] = {
            "closed": False,
            "last_message": datetime.now(timezone.utc),
        }
        thread_configs[channel_id] = {"eddy_type": "manual"}
        # Enough history to pass MIN_EXCHANGES_FOR_REFLECTION and reach the
        # dissolve branch; the eddy-note writer is stubbed to fail so the
        # degrade path runs and nothing touches the filesystem.
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "more"},
            {"role": "assistant", "content": "sure"},
        ]
        return patch("sessions._append_resonance_chronicle"), patch(
            "sessions._write_flow_checkpoint_if_needed",
            new_callable=AsyncMock,
            return_value=[],
        ), patch("sessions.reload_history", return_value=history), patch(
            "sessions.get_mage_name", return_value="Kermit"
        ), patch("sessions.set_practice_context_for_channel"), patch(
            "sessions._manual_release_dissolve", new_callable=AsyncMock
        ), patch("sessions.get_mage_type", return_value="mage"), patch(
            "sessions.assess_readiness", return_value={"dimensions": []}
        ), patch("sessions.save_readiness_trail"), patch(
            "story_notes.write_eddy_note",
            new_callable=AsyncMock,
            side_effect=story_notes.EddyNoteError("stubbed out"),
        )

    def _cleanup(self, channel_id: int) -> None:
        from sessions import active_sessions
        from state import last_checkpoint_anchor, last_reflection_time, thread_configs

        active_sessions.pop(channel_id, None)
        thread_configs.pop(channel_id, None)
        last_reflection_time.pop(channel_id, None)
        last_checkpoint_anchor.pop(channel_id, None)

    async def test_idle_checkpoint_does_not_dissolve_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10 = self._checkpoint_patches(301)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9, p10:
                await checkpoint_session(301, trigger="idle", mark_paused=True)
            dissolve_mock.assert_not_awaited()
        finally:
            self._cleanup(301)

    async def test_manual_checkpoint_does_not_dissolve_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10 = self._checkpoint_patches(302)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9, p10:
                await checkpoint_session(302, trigger="manual", mark_paused=False)
            dissolve_mock.assert_not_awaited()
        finally:
            self._cleanup(302)

    async def test_release_dissolves_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10 = self._checkpoint_patches(303)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9, p10:
                await checkpoint_session(303, trigger="release", mark_paused=True)
            dissolve_mock.assert_awaited_once()
        finally:
            self._cleanup(303)


if __name__ == "__main__":
    unittest.main()
