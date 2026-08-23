"""A gap is filed against the channel's root, or it is not filed at all.

2026-08-17. `sessions._record_gap` resolved its destination with `get_pd()`
and never looked at the channel. On the live host that meant every run of
the unit suite appended rows to the operator's ledger: `ManualEddyDissolveGateTests`
drives `checkpoint_session` on fixture channels 301-303 with the eddy-note
writer stubbed to raise, and each raise recorded a `declined` gap. 114 of the
115 rows in the live file were test runs, and the nightly ops report printed
them under *"Where the practice record failed to write."*

This is the third generation of one defect. `offer_ledger` was fixed for it on
2026-08-06 (a fixture channel filing into the operator's ledger); `record_gaps`
was written on 08-07 and did not take the lesson.

The 08-06 fix is also why the negative control alone is worthless. That fix was
verified by confirming the *test suite wrote nothing* — and it had cut the real
write path at the same time, so an instrument recorded nothing for eight days
while its guard stayed green. Both directions are asserted here: an unregistered
channel writes nothing, **and** a registered one writes exactly one row.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from core import record_gaps

# The fixture ids ManualEddyDissolveGateTests actually uses. If that class
# changes its channels, this test should be pointed at the new ones — the
# leak is about unregistered ids, not about these three numbers.
FIXTURE_CHANNELS = (301, 302, 303)


class RecordGapRootResolutionTests(unittest.TestCase):
    """`_record_gap` files against the channel's root, never the ambient one."""

    def test_unregistered_channel_writes_nothing_anywhere(self) -> None:
        """The leak, stated directly: a fixture channel must reach no root."""
        import sessions

        with tempfile.TemporaryDirectory() as td:
            with patch("offer_ledger.root_for_channel", return_value=None), patch(
                "sessions.get_pd", return_value=td
            ) as pd_mock:
                for cid in FIXTURE_CHANNELS:
                    sessions._record_gap(
                        cid, kind="eddy_note", reason="declined", detail="stubbed out"
                    )

            self.assertFalse(
                record_gaps.gaps_path(td).exists(),
                "an unregistered channel wrote into the ambient practice root",
            )
            pd_mock.assert_not_called()

    def test_registered_channel_writes_exactly_one_row(self) -> None:
        """The positive control the 08-06 fix never ran.

        Without this, cutting the real write path passes every other test in
        this file — which is precisely what happened one surface over.
        """
        import sessions

        with tempfile.TemporaryDirectory() as td:
            with patch("offer_ledger.root_for_channel", return_value=td):
                sessions._record_gap(
                    999, kind="eddy_note", reason="failed", detail="boom", attempts=3
                )

            counts = record_gaps.tally([td])
            self.assertEqual(counts["eddy_note"]["failed"], 1)

    def test_resolution_does_not_consult_the_ambient_root(self) -> None:
        """A wire assertion: the destination comes from the channel.

        Asserting only on the written row would pass if someone reinstated
        `get_pd()` as a fallback, which is the shape that caused this.
        """
        import sessions

        with tempfile.TemporaryDirectory() as chan_root, tempfile.TemporaryDirectory() as ambient:
            with patch("offer_ledger.root_for_channel", return_value=chan_root), patch(
                "sessions.get_pd", return_value=ambient
            ) as pd_mock:
                sessions._record_gap(42, kind="daily_note", reason="failed")

            pd_mock.assert_not_called()
            self.assertTrue(record_gaps.gaps_path(chan_root).exists())
            self.assertFalse(record_gaps.gaps_path(ambient).exists())


class CheckpointFixtureLeakTests(unittest.IsolatedAsyncioTestCase):
    """The end-to-end control: run the real checkpoint the way the suite does.

    The three unit tests above pin `_record_gap`. This one drives
    `checkpoint_session` on a fixture channel with the eddy-note writer stubbed
    to raise — the exact shape of `ManualEddyDissolveGateTests` — and asserts
    the ambient root stays empty. It is the test that would have been red
    before today's change, and it fails again if anyone reinstates the fallback
    somewhere upstream of `_record_gap`.
    """

    async def test_a_stubbed_eddy_note_leaves_the_ambient_root_untouched(self) -> None:
        import story_notes
        from sessions import active_sessions, checkpoint_session
        from state import last_checkpoint_anchor, last_reflection_time, thread_configs

        channel_id = FIXTURE_CHANNELS[0]
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "more"},
            {"role": "assistant", "content": "sure"},
        ]
        active_sessions[channel_id] = {
            "closed": False,
            "last_message": datetime.now(timezone.utc),
        }
        thread_configs[channel_id] = {"eddy_type": "manual"}

        with tempfile.TemporaryDirectory() as ambient:
            try:
                with patch("sessions._append_resonance_chronicle"), patch(
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
                    "sessions.get_pd", return_value=ambient
                ), patch(
                    "story_notes.write_eddy_note",
                    new_callable=AsyncMock,
                    side_effect=story_notes.EddyNoteError("stubbed out"),
                ):
                    await checkpoint_session(channel_id, trigger="idle", mark_paused=True)
            finally:
                active_sessions.pop(channel_id, None)
                thread_configs.pop(channel_id, None)
                last_checkpoint_anchor.pop(channel_id, None)
                last_reflection_time.pop(channel_id, None)

            self.assertFalse(
                record_gaps.gaps_path(ambient).exists(),
                "the checkpoint fixture wrote a gap into the ambient practice "
                "root — this is the live-ledger contamination, reproduced",
            )


if __name__ == "__main__":
    unittest.main()
