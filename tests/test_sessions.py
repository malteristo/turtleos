import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

from sessions import CheckpointResult, checkpoint_session, close_session


class CheckpointResultTests(unittest.TestCase):
    def test_captured_anything(self) -> None:
        self.assertFalse(CheckpointResult().captured_anything)
        self.assertTrue(
            CheckpointResult(flow_writes=["state/notes/shelter-last.md"]).captured_anything
        )
        self.assertTrue(CheckpointResult(session_note="2026-06-18.md").captured_anything)


class CheckpointSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_checkpoint_pauses_session(self) -> None:
        from sessions import active_sessions

        active_sessions[42] = {"closed": False, "last_message": datetime.now(timezone.utc)}
        with patch("sessions._append_resonance_chronicle"), patch(
            "sessions._write_flow_checkpoint_if_needed",
            new_callable=AsyncMock,
            return_value=[],
        ), patch("sessions.get_history", return_value=[]), patch(
            "sessions.get_mage_name", return_value="Kermit"
        ), patch("sessions.set_practice_context_for_channel"):
            result = await checkpoint_session(42, trigger="idle", mark_paused=True)
        self.assertTrue(result.paused)
        self.assertEqual(result.trigger, "idle")
        self.assertTrue(active_sessions[42]["closed"])

    async def test_manual_checkpoint_does_not_pause(self) -> None:
        from sessions import active_sessions

        active_sessions[99] = {"closed": False, "last_message": datetime.now(timezone.utc)}
        with patch("sessions._append_resonance_chronicle"), patch(
            "sessions._write_flow_checkpoint_if_needed",
            new_callable=AsyncMock,
            return_value=["state/notes/shelter-last.md"],
        ), patch(
            "sessions.get_history",
            return_value=[{"role": "user", "content": "hi"}],
        ), patch("sessions.get_mage_name", return_value="Kermit"), patch(
            "sessions.set_practice_context_for_channel"
        ):
            result = await checkpoint_session(99, trigger="manual", mark_paused=False)
        self.assertFalse(result.paused)
        self.assertFalse(active_sessions[99]["closed"])
        self.assertEqual(result.flow_writes, ["state/notes/shelter-last.md"])

    async def test_close_session_alias(self) -> None:
        with patch("sessions.checkpoint_session", new_callable=AsyncMock) as mock_cp:
            mock_cp.return_value = CheckpointResult(trigger="idle")
            await close_session(1)
            mock_cp.assert_awaited_once_with(1, trigger="idle", mark_paused=True)


class ManualEddyDissolveGateTests(unittest.IsolatedAsyncioTestCase):
    """TURTLE_SPEC §8.4: idle checkpoint pauses with history retained.
    Only an explicit release may dissolve a manual eddy (issue 001)."""

    def _checkpoint_patches(self, channel_id: int):
        import sessions as sess
        from sessions import active_sessions
        from state import thread_configs

        active_sessions[channel_id] = {
            "closed": False,
            "last_message": datetime.now(timezone.utc),
        }
        thread_configs[channel_id] = {"eddy_type": "manual"}
        # Enough history to pass MIN_EXCHANGES_FOR_REFLECTION and reach the
        # dissolve branch; reflection itself is skipped via the cooldown.
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "more"},
            {"role": "assistant", "content": "sure"},
        ]
        sess.last_reflection_time[channel_id] = datetime.now(timezone.utc).timestamp()
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
        ), patch("sessions.save_readiness_trail")

    def _cleanup(self, channel_id: int) -> None:
        import sessions as sess
        from sessions import active_sessions
        from state import thread_configs

        active_sessions.pop(channel_id, None)
        thread_configs.pop(channel_id, None)
        sess.last_reflection_time.pop(channel_id, None)

    async def test_idle_checkpoint_does_not_dissolve_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9 = self._checkpoint_patches(301)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9:
                await checkpoint_session(301, trigger="idle", mark_paused=True)
            dissolve_mock.assert_not_awaited()
        finally:
            self._cleanup(301)

    async def test_manual_checkpoint_does_not_dissolve_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9 = self._checkpoint_patches(302)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9:
                await checkpoint_session(302, trigger="manual", mark_paused=False)
            dissolve_mock.assert_not_awaited()
        finally:
            self._cleanup(302)

    async def test_release_dissolves_manual_eddy(self) -> None:
        p1, p2, p3, p4, p5, p6, p7, p8, p9 = self._checkpoint_patches(303)
        try:
            with p1, p2, p3, p4, p5, p6 as dissolve_mock, p7, p8, p9:
                await checkpoint_session(303, trigger="release", mark_paused=True)
            dissolve_mock.assert_awaited_once()
        finally:
            self._cleanup(303)


if __name__ == "__main__":
    unittest.main()
