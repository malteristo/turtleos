"""Take this up opens a session in the owner's home, and points at one that is still open."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import boom_takeup
import river_handler  # binds the press into the button


class PacketTests(unittest.TestCase):
    def test_an_open_session_is_one_that_is_there_and_not_finished(self) -> None:
        self.assertTrue(boom_takeup.still_open(found=True, archived=False, released=False))
        self.assertFalse(boom_takeup.still_open(found=False, archived=False, released=False))
        self.assertFalse(boom_takeup.still_open(found=True, archived=True, released=False))
        self.assertFalse(boom_takeup.still_open(found=True, archived=False, released=True))

    def test_the_session_opens_on_the_line_spirit_is_told_to_hear(self) -> None:
        text = boom_takeup.carry_text(words="make it a card", reply="this touches the card", note="held")
        self.assertTrue(text.startswith(boom_takeup.OPENED_FROM))
        self.assertIn("His words:\nmake it a card", text)
        self.assertIn("Boom Turtle:\nthis touches the card", text)
        self.assertIn("Note:\nheld", text)
        bare = boom_takeup.carry_text(words="", reply="", note="")
        self.assertIn("(none)", bare)
        self.assertNotIn("Boom Turtle:", bare)
        self.assertNotIn("Note:", bare)

    def test_the_eddy_line_is_the_link(self) -> None:
        self.assertEqual(boom_takeup.eddy_line("https://discord.com/channels/1/2", already=False), "Taken up. https://discord.com/channels/1/2")
        self.assertEqual(boom_takeup.eddy_line("https://discord.com/channels/1/2", already=True), "Already open. https://discord.com/channels/1/2")

    def test_the_record_remembers_the_session_and_a_broken_file_does_not(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(boom_takeup.load_session(tmp, 9))
            boom_takeup.save_session(tmp, 9, 44)
            self.assertEqual(boom_takeup.load_session(tmp, 9), 44)
            path = Path(tmp) / "thread-state" / "boom-takeup" / "9.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(boom_takeup.load_session(tmp, 9))

    def test_the_note_is_the_eddy_file_and_nothing_when_it_is_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(boom_takeup.read_note(root, 9), "")
            folder = root / "story" / "eddies"
            folder.mkdir(parents=True)
            (folder / "9-a-card.md").write_text("the card", encoding="utf-8")
            self.assertEqual(boom_takeup.read_note(root, 9), "the card")


class HomeTests(unittest.TestCase):
    def test_home_is_the_one_private_channel(self) -> None:
        registry = {
            "channels": {
                "8": {"primitive": "magic", "mage": "kermit"},
                "7": {"primitive": "craft", "type": "river", "mage": "kermit"},
                "9": {"primitive": "private", "type": "river", "mage": "kermit"},
                "4": {"primitive": "private", "mage": "ada"},
            }
        }
        self.assertEqual(boom_takeup.home_channel_id(registry, "kermit"), "9")
        self.assertEqual(boom_takeup.home_channel_id(registry, "ada"), "4")
        self.assertIsNone(boom_takeup.home_channel_id(registry, "no-one"))

    def test_two_homes_is_not_a_home(self) -> None:
        registry = {
            "channels": {
                "9": {"primitive": "private", "mage": "kermit"},
                "10": {"type": "hosted-river", "mage": "kermit"},
            }
        }
        self.assertIsNone(boom_takeup.home_channel_id(registry, "kermit"))

    def test_an_unmarked_thread_does_not_open_the_platform(self) -> None:
        import workshop_tools

        with TemporaryDirectory() as tmp:
            self.assertIsNone(boom_takeup.begin_platform_turn(True, tmp, 5))
            self.assertFalse(workshop_tools.platform_turn())
            boom_takeup.mark_platform_session(tmp, 5)
            token = boom_takeup.begin_platform_turn(True, tmp, 5)
            self.assertIsNotNone(token)
            self.assertTrue(workshop_tools.platform_turn())
            self.assertIsNone(boom_takeup.begin_platform_turn(False, tmp, 5))
            workshop_tools.reset_platform_turn(token)
            self.assertFalse(workshop_tools.platform_turn())

    def test_the_turn_asks_whether_this_thread_is_one(self) -> None:
        import inspect

        from dialogue_turn import continue_dialogue_turn

        source = inspect.getsource(continue_dialogue_turn)
        self.assertIn("begin_platform_turn", source)
        self.assertIn("reset_platform_turn", source)


class ButtonTests(unittest.TestCase):
    def test_the_button_is_persistent_and_named(self) -> None:
        view = boom_takeup.TakeUpView()
        self.assertIsNone(view.timeout)
        self.assertTrue(view.is_persistent())
        button = view.children[0]
        self.assertEqual(button.label, "Take this up")
        self.assertEqual(button.custom_id, boom_takeup.BUTTON_ID)

    def test_arming_registers_that_view(self) -> None:
        client = MagicMock()
        boom_takeup.arm_takeup(client)
        view = client.add_view.call_args.args[0]
        self.assertIsInstance(view, boom_takeup.TakeUpView)
        self.assertTrue(view.is_persistent())


def _history(*messages):
    async def walk(*_args, **_kwargs):
        for message in messages:
            yield message

    return walk


class TakeUpTests(unittest.IsolatedAsyncioTestCase):
    def _interaction(self, thread):
        interaction = MagicMock()
        interaction.channel = thread
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.user.id = 5
        interaction.client.get_channel.return_value = None
        interaction.user.id = 3
        return interaction

    def _thread(self):
        thread = MagicMock()
        thread.id = 99
        thread.parent.id = 7
        thread.send = AsyncMock()
        thread.history = _history()
        thread.parent.fetch_message = AsyncMock(return_value=MagicMock(content="make it a card"))
        thread.guild.id = 1
        return thread

    async def test_an_open_session_is_pointed_at(self) -> None:
        thread = self._thread()
        session = MagicMock()
        session.id = 44
        session.archived = False
        session.jump_url = "https://discord.com/channels/1/44"
        interaction = self._interaction(thread)
        interaction.client.fetch_channel = AsyncMock(return_value=session)
        primitive = MagicMock()
        primitive.name = "craft"
        registry = {"channels": {"8": {"primitive": "magic", "mage": "kermit"}, "7": {"primitive": "craft", "mage": "kermit"}}}
        with patch("boom_takeup.load_session", return_value=44), patch(
            "channel_primitives.resolve_primitive", return_value=primitive
        ), patch("mage.get_registry", return_value=registry), patch(
            "mage.get_runtime_dir", return_value="/tmp/runtime"
        ), patch("mage.set_practice_context_for_channel"), patch(
            "mage.get_pd", return_value="/tmp/practice"
        ), patch("session_record.is_released", return_value=False), patch(
            "eddy_spawn.spawn_river_eddy", new=AsyncMock()
        ) as spawn:
            await boom_takeup.on_takeup(interaction)
        spawn.assert_not_awaited()
        thread.send.assert_awaited_once_with("Already open. https://discord.com/channels/1/44")

    async def test_a_released_session_opens_another(self) -> None:
        thread = self._thread()
        turtle = MagicMock()
        turtle.author.bot = True
        turtle.author.id = 8
        turtle.content = "this touches the card"
        turtle.components = []
        button = MagicMock()
        button.author.bot = True
        button.author.id = 5
        button.content = "\u200b"
        child = MagicMock()
        child.custom_id = boom_takeup.BUTTON_ID
        row = MagicMock()
        row.children = [child]
        button.components = [row]
        status = MagicMock()
        status.author.bot = True
        status.author.id = 5
        status.content = "Taken up. https://discord.com/channels/1/44"
        status.components = []
        thread.history = _history(button, status, turtle)
        old = MagicMock()
        old.archived = False
        home = MagicMock()
        home.id = 9
        home.send = AsyncMock(return_value=MagicMock(id=70))
        magic = MagicMock()
        magic.id = 8
        magic.send = AsyncMock()
        opened = MagicMock()
        opened.id = 70
        opened.edit = AsyncMock()
        opened.jump_url = "https://discord.com/channels/1/70"
        interaction = self._interaction(thread)

        async def fetch(channel_id):
            if int(channel_id) == 44:
                return old
            if int(channel_id) == 9:
                return home
            if int(channel_id) == 8:
                return magic
            return None

        interaction.client.fetch_channel = AsyncMock(side_effect=fetch)
        primitive = MagicMock()
        primitive.name = "craft"
        with TemporaryDirectory() as tmp:
            shop = Path(tmp) / "workshop"
            shop.mkdir()
            (shop / ".git").mkdir()
            registry = {
                "mages": {"kermit": {"discord_id": "3", "workshop": {"checkout": str(shop)}}},
                "channels": {
                    "8": {"primitive": "magic", "mage": "kermit"},
                    "7": {"primitive": "craft", "mage": "kermit"},
                    "9": {"primitive": "private", "type": "river", "mage": "kermit"},
                },
            }
            with patch("boom_takeup.load_session", return_value=44), patch(
                "boom_takeup.save_session"
            ) as save, patch(
                "channel_primitives.resolve_primitive", return_value=primitive
            ), patch("mage.get_registry", return_value=registry), patch(
                "mage.get_runtime_dir", return_value=tmp
            ), patch("mage.set_practice_context_for_channel"), patch(
                "mage.get_pd", return_value=tmp
            ), patch("session_record.is_released", return_value=True), patch(
                "eddy_spawn.spawn_river_eddy", new=AsyncMock(return_value=opened)
            ) as spawn, patch(
                "eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()
            ), patch("eddy_spawn.river_add_spirit_to_eddy", new=AsyncMock()) as spirit, patch(
                "river_handler._name_session", new=AsyncMock()
            ) as name, patch(
                "workshop_tools.room_checkout",
                side_effect=AssertionError("the workshop opened from the room"),
            ), patch("first_eddy_handoff.write_first_eddy_handoff") as handoff:
                await boom_takeup.on_takeup(interaction)
            self.assertTrue(boom_takeup.is_platform_session(tmp, 70))
        spawn.assert_awaited_once()
        magic.send.assert_not_awaited()
        sent = home.send.await_args.args[0]
        self.assertIn(boom_takeup.OPENED_FROM, sent)
        self.assertIn("make it a card", sent)
        self.assertIn("this touches the card", sent)
        self.assertNotIn("https://discord.com/channels/1/44", sent)
        spirit.assert_awaited_once()
        name.assert_awaited_once()
        handoff.assert_called_once()
        self.assertEqual(handoff.call_args.args[:3], (70, 9, 70))
        save.assert_called_once_with(tmp, 99, 70)
        thread.send.assert_awaited_once_with("Taken up. https://discord.com/channels/1/70")

    async def test_no_home_channel_says_so_in_the_eddy(self) -> None:
        thread = self._thread()
        interaction = self._interaction(thread)
        primitive = MagicMock()
        primitive.name = "craft"
        registry = {
            "channels": {
                "8": {"primitive": "magic", "mage": "kermit"},
                "7": {"primitive": "craft", "mage": "kermit"},
            }
        }
        interaction.client.fetch_channel = AsyncMock(side_effect=AssertionError("fetched a channel"))
        with TemporaryDirectory() as tmp, patch(
            "channel_primitives.resolve_primitive", return_value=primitive
        ), patch("mage.get_registry", return_value=registry), patch(
            "mage.get_runtime_dir", return_value=tmp
        ), patch("mage.set_practice_context_for_channel"), patch(
            "mage.get_pd", return_value=tmp
        ), patch("eddy_spawn.spawn_river_eddy", new=AsyncMock()) as spawn:
            await boom_takeup.on_takeup(interaction)
        spawn.assert_not_awaited()
        thread.send.assert_awaited_once_with(boom_takeup.COULD_NOT)

    async def test_another_members_home_is_not_a_platform_session(self) -> None:
        thread = self._thread()
        interaction = self._interaction(thread)
        home = MagicMock()
        home.id = 9
        home.send = AsyncMock(return_value=MagicMock(id=70))
        opened = MagicMock()
        opened.id = 70
        opened.edit = AsyncMock()
        opened.jump_url = "https://discord.com/channels/1/70"
        async def fetch(channel_id):
            if int(channel_id) == 9:
                return home
            raise AssertionError(f"fetched {channel_id}")

        interaction.client.fetch_channel = AsyncMock(side_effect=fetch)
        primitive = MagicMock()
        primitive.name = "craft"
        registry = {
            "mages": {"ada": {}},
            "channels": {
                "8": {"primitive": "magic", "mage": "ada"},
                "7": {"primitive": "craft", "mage": "ada"},
                "9": {"primitive": "private", "mage": "ada"},
            },
        }
        with TemporaryDirectory() as tmp, patch(
            "channel_primitives.resolve_primitive", return_value=primitive
        ), patch("mage.get_registry", return_value=registry), patch(
            "mage.get_runtime_dir", return_value=tmp
        ), patch("mage.set_practice_context_for_channel"), patch(
            "mage.get_pd", return_value=tmp
        ), patch("eddy_spawn.spawn_river_eddy", new=AsyncMock(return_value=opened)), patch(
            "eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()
        ), patch("eddy_spawn.river_add_spirit_to_eddy", new=AsyncMock()), patch(
            "river_handler._name_session", new=AsyncMock()
        ) as name, patch("thread_registry.update_thread_name"), patch(
            "eddy_spawn.pop_awaiting_title"
        ), patch("first_eddy_handoff.write_first_eddy_handoff") as handoff:
            await boom_takeup.on_takeup(interaction)
        name.assert_not_awaited()
        opened.edit.assert_awaited_once_with(name="session")
        handoff.assert_called_once()
        self.assertEqual(handoff.call_args.args[:3], (70, 9, 70))
        self.assertFalse(boom_takeup.is_platform_session(tmp, 70))

    async def test_a_button_outside_boom_does_not_open_a_session(self) -> None:
        thread = self._thread()
        interaction = self._interaction(thread)
        with patch("channel_primitives.resolve_primitive", return_value=None), patch(
            "mage.get_registry", return_value={}
        ), patch("eddy_spawn.spawn_river_eddy", new=AsyncMock()) as spawn:
            await boom_takeup.on_takeup(interaction)
        spawn.assert_not_awaited()
        thread.send.assert_not_awaited()
        interaction.followup.send.assert_awaited_once()
