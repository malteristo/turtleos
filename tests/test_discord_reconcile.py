"""Tests for Discord native UI reconciliation (policy C)."""

from __future__ import annotations

import sys
import unittest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord
except ImportError:
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())
    import discord


class _FakeThread:
    """Duck-typed thread for reconcile handler tests (no isinstance gate)."""

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
        light.assert_awaited_once_with(
            9001,
            discord_client=light.await_args.kwargs["discord_client"],
            via_discord_ui=True,
            thread_name="test-eddy",
            parent_channel_id=100,
        )

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


class TestHandleThreadDelete(unittest.IsolatedAsyncioTestCase):
    async def test_skips_unregistered_parent(self) -> None:
        from discord_reconcile import handle_thread_delete

        thread = _thread()
        with patch("discord_reconcile.is_registered_parent_channel", return_value=False):
            result = await handle_thread_delete(thread, discord_client=MagicMock())
        self.assertEqual(result["skipped"], "unregistered_parent")

    async def test_cleans_registry_and_memory(self) -> None:
        from discord_reconcile import handle_thread_delete

        thread = _thread()
        parent = MagicMock()
        client = MagicMock()
        client.get_channel.return_value = parent

        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "discord_reconcile._registry_entry",
            return_value={"harvest_status": "pending", "message_count": 3},
        ), patch("discord_reconcile._cleanup_eddy_memory") as cleanup, patch(
            "helpers.reload_history",
            return_value=[{"role": "user", "content": "x"}],
        ), patch("thread_registry.remove_thread") as remove, patch(
            "helpers.log_activity",
            new_callable=AsyncMock,
        ) as log:
            result = await handle_thread_delete(thread, discord_client=client)

        cleanup.assert_called_once_with(9001)
        remove.assert_called_once_with(9001)
        self.assertTrue(result["thread_deleted"])
        log.assert_awaited_once()


class TestHandleThreadOpen(unittest.IsolatedAsyncioTestCase):
    async def test_skips_unregistered_parent(self) -> None:
        from discord_reconcile import handle_thread_open

        thread = _thread(parent_id=999)
        with patch("discord_reconcile.is_registered_parent_channel", return_value=False):
            result = await handle_thread_open(thread, discord_client=MagicMock())
        self.assertIsNone(result)

    async def test_skips_system_eddy(self) -> None:
        from discord_reconcile import handle_thread_open

        thread = _thread(name="vortex")
        with patch("discord_reconcile.is_registered_parent_channel", return_value=True):
            result = await handle_thread_open(thread, discord_client=MagicMock())
        self.assertEqual(result, {"skipped": "system_eddy", "thread_id": 9001})

    async def test_native_open_via_discord_ui(self) -> None:
        from discord_reconcile import handle_thread_open

        thread = _thread(name="jokes")
        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "sessions.post_eddy_opened_feedback",
            new_callable=AsyncMock,
        ) as opened:
            result = await handle_thread_open(thread, discord_client=MagicMock(), pending=None)

        opened.assert_awaited_once_with(
            100,
            thread_name="jokes",
            via_discord_ui=True,
            jump_url=thread.jump_url,
            detail=None,
        )
        self.assertEqual(result, {"opened_act": True, "thread_id": 9001, "via_discord_ui": True})

    async def test_river_spawn_not_via_discord_ui(self) -> None:
        from discord_reconcile import handle_thread_open

        thread = _thread(name="flow-eddy")
        pending = {"context_type": "quest"}
        with patch("discord_reconcile.is_registered_parent_channel", return_value=True), patch(
            "sessions.post_eddy_opened_feedback",
            new_callable=AsyncMock,
        ) as opened:
            result = await handle_thread_open(thread, discord_client=MagicMock(), pending=pending)

        opened.assert_awaited_once_with(
            100,
            thread_name="flow-eddy",
            via_discord_ui=False,
            jump_url=thread.jump_url,
            detail="flow `quest`",
        )
        self.assertFalse(result["via_discord_ui"])


class TestHandleGuildChannelDelete(unittest.IsolatedAsyncioTestCase):
    async def test_skips_unregistered_channel(self) -> None:
        from discord_reconcile import handle_guild_channel_delete

        channel = MagicMock()
        channel.id = 555
        with patch("mage.get_registry", return_value={"channels": {}}):
            result = await handle_guild_channel_delete(channel, discord_client=MagicMock())
        self.assertEqual(result["skipped"], "unregistered_channel")

    async def test_marks_orphan_and_logs(self) -> None:
        from discord_reconcile import handle_guild_channel_delete

        channel = MagicMock()
        channel.id = 555
        channel.name = "lukas-play"
        registry = {
            "channels": {
                "555": {"type": "shared-river", "mage": "lukas_play"},
            }
        }

        with patch("mage.get_registry", return_value=registry), patch(
            "space_provisioning.mark_channel_orphaned",
            return_value=True,
        ) as mark, patch("mage.reload_mage_registry"), patch(
            "helpers.log_activity",
            new_callable=AsyncMock,
        ) as log:
            result = await handle_guild_channel_delete(channel, discord_client=MagicMock())

        mark.assert_called_once()
        self.assertTrue(result["channel_orphaned"])
        log.assert_awaited_once()


class TestPostEddyLifecycleFeedback(unittest.IsolatedAsyncioTestCase):
    async def test_close_delegates_action_first(self) -> None:
        from sessions import post_eddy_lifecycle_feedback

        with patch("sessions.post_lifecycle_act", new_callable=AsyncMock) as act:
            await post_eddy_lifecycle_feedback(
                1479428854513664030,
                thread_name="what makes jokes work",
                mode="dissolve",
                via_discord_ui=True,
                entry_count=1,
            )
        act.assert_awaited_once()
        kwargs = act.await_args.kwargs
        self.assertEqual(kwargs["action"], "Closed eddy")
        self.assertEqual(kwargs["thread_name"], "what makes jokes work")
        self.assertIn("1 entries", kwargs["detail"])

    async def test_open_delegates_action_first(self) -> None:
        from sessions import post_eddy_opened_feedback

        with patch("sessions.post_lifecycle_act", new_callable=AsyncMock) as act:
            await post_eddy_opened_feedback(
                1479428854513664030,
                thread_name="new eddy",
                via_discord_ui=False,
                jump_url="https://discord.com/channels/1/2/3",
            )
        act.assert_awaited_once()
        kwargs = act.await_args.kwargs
        self.assertEqual(kwargs["action"], "Opened eddy")
        self.assertEqual(kwargs["emoji"], "🌀")
        self.assertEqual(kwargs["thread_name"], "new eddy")

    async def test_lifecycle_act_delivers(self) -> None:
        from sessions import post_lifecycle_act

        with patch("helpers.deliver_channel_embed", new_callable=AsyncMock) as deliver:
            await post_lifecycle_act(
                1479428854513664030,
                action="Opened eddy",
                thread_name="new eddy",
                emoji="🌀",
            )
        deliver.assert_awaited_once_with(1479428854513664030, unittest.mock.ANY, silent=False)


if __name__ == "__main__":
    unittest.main()
