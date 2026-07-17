"""Tests for !pin working-plan product path vs river legacy pin."""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())


class _FakeThread:
    """Stand-in so isinstance(..., discord.Thread) can be forced."""


class TestCmdPinHome(unittest.IsolatedAsyncioTestCase):
    async def test_eddy_bind_path(self) -> None:
        import commands as cmds
        import discord as d

        d.Thread = _FakeThread
        d.NotFound = type("NotFound", (Exception,), {})
        d.Forbidden = type("Forbidden", (Exception,), {})
        d.HTTPException = type("HTTPException", (Exception,), {})

        thread = _FakeThread()
        thread.id = 1527001
        thread.parent_id = 1479001
        thread.name = "workout plan"
        thread.fetch_message = AsyncMock()

        message = MagicMock()
        message.channel = thread
        message.reference = None
        message.reply = AsyncMock()

        fake_plan = {
            "id": "p1",
            "title": "workout plan",
            "artifact_path": "state/notes/workout-plan.md",
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_pd", return_value=tmp), patch(
                "home_plans.get_by_eddy", return_value=None
            ), patch(
                "home_plan_ui.bind_and_post_pin",
                new_callable=AsyncMock,
                return_value=fake_plan,
            ) as bind:
                await cmds.cmd_pin(message, [])

        bind.assert_awaited_once()
        kwargs = bind.await_args.kwargs
        self.assertEqual(kwargs["home_eddy_id"], 1527001)
        self.assertEqual(kwargs["river_channel_id"], 1479001)
        self.assertIn("Pinned", message.reply.await_args.args[0])

    async def test_eddy_refresh_existing(self) -> None:
        import commands as cmds
        import discord as d

        d.Thread = _FakeThread
        thread = _FakeThread()
        thread.id = 10
        thread.parent_id = 20
        thread.name = "home"
        message = MagicMock()
        message.channel = thread
        message.reference = None
        message.reply = AsyncMock()

        existing = {"id": "x", "title": "Existing", "artifact_path": "state/notes/e.md"}

        with patch("mage.get_pd", return_value="/tmp"), patch(
            "home_plans.get_by_eddy", return_value=existing
        ), patch(
            "home_plan_ui.bind_and_post_pin",
            new_callable=AsyncMock,
            return_value=existing,
        ) as bind:
            await cmds.cmd_pin(message, [])

        self.assertTrue(bind.await_args.kwargs.get("refresh_plan"))
        self.assertIn("Refreshed", message.reply.await_args.args[0])

    async def test_river_legacy_pin_still_works(self) -> None:
        import commands as cmds
        import discord as d

        d.Thread = _FakeThread
        d.NotFound = type("NotFound", (Exception,), {})
        d.Forbidden = type("Forbidden", (Exception,), {})
        d.HTTPException = type("HTTPException", (Exception,), {})

        channel = MagicMock()  # not a _FakeThread
        target = MagicMock()
        target.pin = AsyncMock()
        channel.fetch_message = AsyncMock(return_value=target)

        message = MagicMock()
        message.channel = channel
        message.reference = MagicMock()
        message.reference.message_id = 555
        message.reply = AsyncMock()
        message.add_reaction = AsyncMock()

        with patch("commands.is_practice_channel", return_value=True), patch(
            "commands.get_mage_name", return_value="kermit"
        ):
            await cmds.cmd_pin(message, [])

        target.pin.assert_awaited_once()
        message.add_reaction.assert_awaited_once_with("📌")


class TestResolvePinClient(unittest.TestCase):
    def test_prefers_ready_river_client(self) -> None:
        from home_plan_ui import resolve_pin_client

        river = MagicMock()
        river.is_ready = MagicMock(return_value=True)
        river.user = MagicMock()
        with patch("mage.river_bot_enabled", return_value=True), patch(
            "river_state.river_client", river
        ):
            self.assertIs(resolve_pin_client(message=MagicMock()), river)

    def test_explicit_client_wins(self) -> None:
        from home_plan_ui import resolve_pin_client

        explicit = MagicMock(name="explicit")
        self.assertIs(resolve_pin_client(discord_client=explicit), explicit)


class TestStickyCool(unittest.IsolatedAsyncioTestCase):
    async def test_sticky_skips_mark_cooled(self) -> None:
        import sessions as sess
        import discord as d

        d.Thread = _FakeThread
        d.NotFound = type("NotFound", (Exception,), {})
        d.HTTPException = type("HTTPException", (Exception,), {})
        d.Forbidden = type("Forbidden", (Exception,), {})

        thread = _FakeThread()
        thread.name = "sticky-home"
        thread.archived = True
        thread.parent_id = 1
        thread.jump_url = "https://discord.com/channels/1/2"
        thread.edit = AsyncMock()

        dc = MagicMock()
        dc.get_channel = MagicMock(return_value=thread)

        with patch("sessions.client", dc), patch(
            "mage.get_pd", return_value="/tmp/p"
        ), patch(
            "home_plans.is_sticky_eddy", return_value=True
        ), patch(
            "thread_registry.mark_cooled"
        ) as mark, patch(
            "sessions.post_eddy_lifecycle_feedback", new_callable=AsyncMock
        ) as feedback:
            await sess.cool_eddy_from_auto_archive(
                42,
                discord_client=dc,
                thread_name="sticky-home",
                parent_channel_id=1,
            )

        mark.assert_not_called()
        feedback.assert_not_awaited()
        thread.edit.assert_awaited()


if __name__ == "__main__":
    unittest.main()
