"""Tier 1 reliability — idle checkpoint wedge and registry persistence."""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class LogActivityReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_log_activity_does_not_reanchor_bars(self) -> None:
        import helpers

        channel = MagicMock()
        channel.id = 42
        channel.parent_id = 99
        with patch("helpers.get_channel", return_value=channel), patch(
            "mage.river_bot_enabled", return_value=True
        ), patch("river_handler._river_client_for_channel", return_value=None), patch(
            "bar_anchor.ensure_channel_bars", new_callable=AsyncMock
        ) as ensure_mock:
            channel.send = AsyncMock()
            await helpers.log_activity("test note", channel=channel)
        ensure_mock.assert_not_called()


class SessionMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_checkpoint_runs_in_background_task(self) -> None:
        import sessions as sess
        from state import active_sessions

        active_sessions.clear()
        active_sessions[7] = {
            "closed": False,
            "last_message": datetime.now(timezone.utc),
        }
        sess._idle_checkpoint_running.clear()

        with patch.object(sess, "SESSION_TIMEOUT_SECONDS", 0), patch(
            "sessions.asyncio.create_task"
        ) as create_task_mock:
            sess._scan_idle_sessions()
            create_task_mock.assert_called_once()

        active_sessions.clear()
        sess._idle_checkpoint_running.clear()


class ThreadRegistryPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        import thread_registry as tr

        tr.clear_registry_cache_for_tests()

    def tearDown(self) -> None:
        import thread_registry as tr

        tr.clear_registry_cache_for_tests()

    def test_debounced_save_and_flush(self) -> None:
        import thread_registry as tr

        with patch.object(tr, "_persist_registry") as persist:
            reg = tr.load_registry()
            tr.save_registry(reg)
            tr.save_registry(reg)
            self.assertEqual(persist.call_count, 1)
            tr.flush_registry()
            self.assertEqual(persist.call_count, 2)

    def test_new_thread_forces_immediate_save(self) -> None:
        import thread_registry as tr

        with patch.object(tr, "_persist_registry") as persist:
            tr.register_thread(123, "test-eddy", parent_channel="river")
            self.assertEqual(persist.call_count, 1)


if __name__ == "__main__":
    unittest.main()
