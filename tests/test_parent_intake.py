"""A parent drop opens an eddy. Boom does not post a registration. Magic opens a session."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import parent_intake


class DropKindTests(unittest.TestCase):
    def test_boom_and_magic_and_a_display(self) -> None:
        self.assertEqual(parent_intake.drop_kind("craft", display=False), "boom")
        self.assertEqual(parent_intake.drop_kind("magic", display=False), "session")
        self.assertIsNone(parent_intake.drop_kind("magic", display=True))
        self.assertIsNone(parent_intake.drop_kind("private", display=False))
        self.assertIsNone(parent_intake.drop_kind(None, display=False))

    def test_title_is_his_first_line(self) -> None:
        self.assertEqual(parent_intake.eddy_title("  \nI want this to be a card"), "I want this to be a card")
        self.assertEqual(parent_intake.eddy_title(""), "boom")
        self.assertEqual(parent_intake.eddy_title("   "), "boom")

    def test_preface_is_only_the_forward_beside_a_comment(self) -> None:
        self.assertEqual(parent_intake.preface_for("make it a card", "the forward"), "the forward")
        self.assertEqual(parent_intake.preface_for("", "the forward"), "")
        self.assertEqual(parent_intake.preface_for("the forward", "the forward"), "")


class OpenDropTests(unittest.IsolatedAsyncioTestCase):
    def _anchor(self):
        anchor = MagicMock()
        anchor.id = 42
        anchor.channel.id = 7
        anchor.author.id = 3
        return anchor

    def _patches(self, thread):
        return (
            patch("eddy_spawn.spawn_river_eddy", new=AsyncMock(return_value=thread)),
            patch("eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()),
            patch("eddy_spawn.river_add_spirit_to_eddy", new=AsyncMock()),
            patch("eddy_spawn.pop_awaiting_title"),
            patch("eddy_spawn.patch_pending_native_eddy"),
            patch("thread_registry.update_thread_name"),
            patch("first_eddy_handoff.write_first_eddy_handoff"),
            patch("mage.get_runtime_dir", return_value="/tmp/runtime"),
        )

    async def test_boom_names_the_eddy_and_asks_turtle_not_spirit(self) -> None:
        thread = MagicMock()
        thread.id = 99
        thread.edit = AsyncMock()
        thread.send = AsyncMock()
        anchor = self._anchor()
        patches = self._patches(thread)
        with patches[0] as spawn, patches[1] as turtle, patches[2] as spirit, patches[3] as pop, patches[4], patches[5] as rename, patches[6] as handoff, patches[7], patch(
            "boom_takeup.post_takeup_button", new=AsyncMock()
        ) as button:
            from river_handler import open_drop_thread

            opened = await open_drop_thread(
                anchor, title="a card", kind="boom", preface="forwarded words"
            )
        self.assertTrue(opened)
        spawn.assert_awaited_once_with(anchor)
        thread.edit.assert_awaited_once_with(name="a card")
        rename.assert_called_once_with(99, "a card")
        pop.assert_called_once_with(99, 7)
        thread.send.assert_awaited_once_with("forwarded words")
        turtle.assert_awaited_once()
        spirit.assert_not_awaited()
        handoff.assert_called_once()
        self.assertEqual(handoff.call_args.args[:3], (99, 7, 42))
        button.assert_awaited_once_with(thread)

    async def test_a_closed_thread_does_not_ask_anyone(self) -> None:
        anchor = self._anchor()
        with patch("eddy_spawn.spawn_river_eddy", new=AsyncMock(return_value=None)), patch(
            "first_eddy_handoff.write_first_eddy_handoff"
        ) as handoff:
            from river_handler import open_drop_thread

            opened = await open_drop_thread(anchor, title="a card", kind="boom")
        self.assertFalse(opened)
        handoff.assert_not_called()

    async def test_a_session_adds_spirit_and_uses_the_session_name(self) -> None:
        thread = MagicMock()
        thread.id = 99
        thread.edit = AsyncMock()
        thread.send = AsyncMock()
        anchor = self._anchor()
        patches = self._patches(thread)
        with patches[0], patches[1], patches[2] as spirit, patches[3] as pop, patches[4], patches[5] as rename, patches[6], patches[7], patch(
            "workshop_tools.room_checkout", return_value="/tmp/workshop"
        ), patch("river_handler._name_session", new=AsyncMock()) as name, patch(
            "boom_takeup.post_takeup_button", new=AsyncMock()
        ) as button:
            from river_handler import open_drop_thread

            opened = await open_drop_thread(anchor, title="ship it", kind="session")
        self.assertTrue(opened)
        name.assert_awaited_once()
        spirit.assert_awaited_once()
        thread.send.assert_awaited_once_with(parent_intake.SESSION_OPENED)
        button.assert_not_awaited()
        thread.edit.assert_not_awaited()
        rename.assert_not_called()
        pop.assert_not_called()


class BoomDropTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_drop_opens_an_eddy_and_does_not_write_the_backlog(self) -> None:
        import craft_intake

        anchor = MagicMock()
        anchor.content = "I want this to be a card"
        anchor.author.display_name = "kermit"
        anchor.channel.name = "craft-room"
        evidence = {
            "merged_user": "I want this to be a card",
            "merged_forward": "the receipt",
        }
        with patch(
            "craft_intake.gather_craft_evidence", new=AsyncMock(return_value=evidence)
        ), patch(
            "river_handler.open_drop_thread", new=AsyncMock(return_value=True)
        ) as open_thread, patch(
            "craft_intake.write_craft_intake"
        ) as write:
            await craft_intake.open_boom_drop([anchor], MagicMock())
        write.assert_not_called()
        anchor.channel.send.assert_not_called()
        open_thread.assert_awaited_once()
        self.assertEqual(open_thread.await_args.kwargs["kind"], "boom")
        self.assertEqual(open_thread.await_args.kwargs["title"], "I want this to be a card")
        self.assertEqual(open_thread.await_args.kwargs["preface"], "the receipt")

    async def test_the_boom_channel_says_a_thought_opens_at_home(self) -> None:
        import craft_intake
        from parent_intake import MOVED_HOME

        for name in ("boom", "craft-turtle", "Boom"):
            anchor = MagicMock()
            anchor.channel.name = name
            anchor.channel.send = AsyncMock()
            with patch("craft_intake.gather_craft_evidence", new=AsyncMock()) as gather, patch(
                "river_handler.open_drop_thread", new=AsyncMock()
            ) as open_thread:
                await craft_intake.open_boom_drop([anchor], MagicMock())
            gather.assert_not_awaited()
            open_thread.assert_not_awaited()
            anchor.channel.send.assert_awaited_once_with(MOVED_HOME)


class MagicChannelDropTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_message_in_magic_opens_a_session(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "Ship the git card"
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel.id = 8
        message.channel.send = AsyncMock()
        primitive = MagicMock()
        primitive.name = "magic"
        with patch("craft_intake.is_craft_intake_channel", return_value=False), patch(
            "mage.get_channel_primitive", return_value=primitive
        ), patch(
            "river_handler.open_drop_thread", new=AsyncMock(return_value=True)
        ) as open_thread, patch(
            "river_handler.classify_river_acts", new=AsyncMock()
        ) as classify, patch(
            "river_handler._river_client_for_channel", return_value=None
        ):
            await handle_river_message(message)
        classify.assert_not_awaited()
        message.channel.send.assert_not_awaited()
        open_thread.assert_awaited_once()
        self.assertEqual(open_thread.await_args.kwargs["kind"], "session")
        self.assertEqual(open_thread.await_args.kwargs["title"], "Ship the git card")

    async def test_a_display_in_magic_stays_a_display(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "show threads"
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel.id = 8
        with patch("craft_intake.is_craft_intake_channel", return_value=False), patch(
            "river_handler.open_drop_thread", new=AsyncMock()
        ) as open_thread, patch(
            "river_handler.render_acts",
            new=AsyncMock(return_value={"acts": ["show_threads"], "views": 1}),
        ) as render, patch(
            "river_handler._river_client_for_channel", return_value=None
        ):
            await handle_river_message(message)
        open_thread.assert_not_awaited()
        self.assertEqual(render.await_args.args[1][0]["type"], "show_threads")


class PromptTests(unittest.TestCase):
    def test_the_channel_drop_is_a_check_then_the_work(self) -> None:
        from magic_prompt import SUBSTRATE

        self.assertIn("When River says the session opened on his message", SUBSTRATE)
        self.assertIn("When River says the session opened from a Boom eddy", SUBSTRATE)
        self.assertIn("Summon is the other door", SUBSTRATE)
