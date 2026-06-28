"""Tests for Discord native UI reconciliation (policy C)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import discord


class _FakeThread:
    def __init__(
        self,
        *,
        thread_id: int = 9001,
        parent_id: int = 100,
        archived: bool = False,
        locked: bool = False,
        name: str = "test-eddy",
    ):
        self.id = thread_id
        self.parent_id = parent_id
        self.archived = archived
        self.locked = locked
        self.name = name
        self.jump_url = f"https://discord.com/channels/1/{parent_id}/{thread_id}"
        self.parent = None
        self.edit = AsyncMock()


discord.Thread = _FakeThread  # isinstance checks in dissolve_eddy


def _thread(*, thread_id: int = 9001, parent_id: int = 100, archived: bool = False, locked: bool = False, name: str = "test-eddy"):
    return _FakeThread(
        thread_id=thread_id,
        parent_id=parent_id,
        archived=archived,
        locked=locked,
        name=name,
    )


class TestHandleThreadArchiveTransition(unittest.IsolatedAsyncioTestCase):
    async def test_skips_non_archive_transition(self) -> None:
        from discord_reconcile import handle_thread_archive_transition

        before = _thread(archived=False)
        after = _thread(archived=False)
        result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())
        self.assertIsNone(result)

    async def test_skips_unregistered_parent(self) -> None:
        from discord_reconcile import handle_thread_archive_transition

        before = _thread(archived=False)
        after = _thread(archived=True)
        with patch("discord_reconcile.is_registered_parent_channel", return_value=False):
            result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())
        self.assertIsNone(result)

    async def test_skips_already_dissolved(self) -> None:
        from discord_reconcile import handle_thread_archive_transition

        before = _thread(archived=False)
        after = _thread(archived=True)
        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile._registry_entry",
            return_value={"harvest_status": "dissolved", "message_count": 5},
        ):
            result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())
        self.assertEqual(result, {"skipped": "already_dissolved", "thread_id": 9001})

    async def test_full_dissolve_when_registered_and_substantive(self) -> None:
        from discord_reconcile import handle_thread_archive_transition
        from sessions import DissolveResult

        before = _thread(archived=False)
        after = _thread(archived=True)
        history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        mock_result = DissolveResult(thread_name="test-eddy", entry_count=1)

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile._registry_entry",
            return_value={"harvest_status": "pending", "message_count": 2},
        ), patch(
            "discord_reconcile._load_history_for_thread",
            new_callable=AsyncMock,
            return_value=history,
        ), patch(
            "sessions.dissolve_eddy",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as dissolve, patch("helpers.clear_history"), patch("state.active_sessions", {}):
            result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())

        self.assertTrue(result["full_dissolve"])
        dissolve.assert_awaited_once()
        self.assertTrue(dissolve.await_args.kwargs.get("native_close"))

    async def test_light_archive_when_unregistered(self) -> None:
        from discord_reconcile import handle_thread_archive_transition

        before = _thread(archived=False)
        after = _thread(archived=True)

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile._registry_entry",
            return_value=None,
        ), patch(
            "discord_reconcile._load_history_for_thread",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "hi"}],
        ), patch("sessions.light_archive_eddy", new_callable=AsyncMock) as light:
            result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())

        self.assertTrue(result["light_archive"])
        light.assert_awaited_once_with(9001, discord_client=light.await_args.kwargs["discord_client"])

    async def test_light_archive_when_few_messages(self) -> None:
        from discord_reconcile import handle_thread_archive_transition

        before = _thread(archived=False)
        after = _thread(archived=True)

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile._registry_entry",
            return_value={"harvest_status": "pending", "message_count": 1},
        ), patch(
            "discord_reconcile._load_history_for_thread",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "solo"}],
        ), patch("sessions.light_archive_eddy", new_callable=AsyncMock) as light:
            result = await handle_thread_archive_transition(before, after, discord_client=MagicMock())

        self.assertTrue(result["light_archive"])
        light.assert_awaited_once()


class TestHandleThreadUpdate(unittest.IsolatedAsyncioTestCase):
    async def test_rename_still_updates_registry(self) -> None:
        from discord_reconcile import handle_thread_update

        before = _thread(name="old-name", archived=False)
        after = _thread(name="new-name", archived=False)

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "thread_registry.update_thread_name"
        ) as rename:
            await handle_thread_update(before, after, discord_client=MagicMock())

        rename.assert_called_once_with(9001, "new-name")

    async def test_archive_delegates_to_transition_handler(self) -> None:
        from discord_reconcile import handle_thread_update

        before = _thread(archived=False)
        after = _thread(archived=True)

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile.handle_thread_archive_transition",
            new_callable=AsyncMock,
            return_value={"light_archive": True, "thread_id": 9001},
        ) as archive:
            await handle_thread_update(before, after, discord_client=MagicMock())

        archive.assert_awaited_once()


class TestDissolveEddyNativeClose(unittest.IsolatedAsyncioTestCase):
    async def test_native_close_continues_when_already_archived(self) -> None:
        from sessions import dissolve_eddy

        thread = _FakeThread(archived=True, name="closed-eddy")
        thread.id = 9001

        client = MagicMock()
        client.get_channel.return_value = thread

        with patch("sessions.chat_ollama", new_callable=AsyncMock, return_value="(nothing to capture)"), patch(
            "sessions.get_pd", return_value="/tmp/test-pd"
        ), patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"), patch(
            "thread_registry.mark_dissolved"
        ), patch("state.thread_configs", {}), patch("state.threads_flagged_for_release", {}):
            result = await dissolve_eddy(9001, [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}], discord_client=client, native_close=True)

        self.assertIsNotNone(result)
        self.assertFalse(result.already_archived)
        thread.edit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
