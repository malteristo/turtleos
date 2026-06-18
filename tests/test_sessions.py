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


if __name__ == "__main__":
    unittest.main()
