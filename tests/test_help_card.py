"""`!` and `!help` as one card, and the channel bar's menu that answers privately.

What a person sees (the card, in both languages, keeping the grammar) and the claims the
card makes about the command set: it lists only commands that exist, and every command a
member can run is either listed or named as deliberately unlisted. Each guard has a
positive control. Needs the real discord.py: a layout message cannot be checked on a mock.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord  # noqa: F401
except ImportError:  # system Python without discord.py: skip, never pass by omission
    raise unittest.SkipTest("needs discord.py")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import help_card  # noqa: E402
import room_models  # noqa: E402
import ui_kit  # noqa: E402
from tests.test_mcp_list import alltext  # noqa: E402
from tests.test_own_channel_model import ALEX, REGISTRY, _RoomEnv  # noqa: E402


class CardTests(unittest.TestCase):
    def test_it_says_what_can_be_typed_in_groups_and_what_each_does(self):
        text = alltext(help_card.render())
        self.assertIn("What you can type here", text)
        for typed in ("!rename <title>", "!dates", "!model", "!mcp"):
            self.assertIn(typed, text)
        # Not for members: checkpoint is a button (and automatic); status and context are the operator's.
        self.assertNotIn("!checkpoint", alltext(help_card.render(operator=True)), "shut for everyone")
        for typed in ("!status", "!context"):
            self.assertNotIn(typed, text)
            self.assertIn(typed, alltext(help_card.render(operator=True)))
        # The card's own footnote must not name a command that has since been retired.
        for locale in ("en", "de"):
            note = help_card._TEXT[locale]["older"]
            for name in help_card.RETIRED:
                self.assertNotIn(f"`!{name}`", note, (locale, name))
        self.assertIn("older commands", text)

    def test_the_operator_card_is_only_for_the_operator(self):
        self.assertNotIn("!diagnose", alltext(help_card.render(operator=False)))
        self.assertIn("!diagnose", alltext(help_card.render(operator=True)))

    def test_it_keeps_the_grammar_in_both_languages_and_both_audiences(self):
        for locale in ("en", "de"):
            for operator in (False, True):
                view = help_card.render(locale=locale, operator=operator)
                self.assertEqual(ui_kit.violations(view, forbidden=("Continuity", "sediment", "bedrock")), [], (locale, operator))
        self.assertIn("Was du hier tippen kannst", alltext(help_card.render(locale="de")))

    def test_every_string_exists_in_english_and_german(self):
        self.assertEqual(ui_kit.parity(help_card._TEXT), [])

    def test_a_card_that_is_an_inventory_cannot_be_built(self):
        too_many = tuple(ui_kit.Item(f"!c{i}", "x") for i in range(ui_kit.ROWS_MAX + 1))
        with self.assertRaises(ui_kit.LanguageError):  # positive control for the seven-line limit
            ui_kit.Card(title="x", rows=too_many)
        for _, rows in help_card.GROUPS:
            self.assertLessEqual(len(rows), ui_kit.ROWS_MAX)


class TheCardsClaimsAreChecked(unittest.TestCase):
    def setUp(self):
        import commands
        from cmd_dispatch import _PRACTITIONER_COMMANDS

        self.commands = set(commands.DIRECT_COMMANDS)
        self.members = set(_PRACTITIONER_COMMANDS)

    def test_everything_listed_exists(self):
        self.assertEqual(sorted(help_card.listed_commands() - self.commands), [])

    def test_everything_a_member_can_run_is_listed_or_named_as_unlisted(self):
        silent = self.members & self.commands - help_card.listed_commands() - help_card.LISTED_ELSEWHERE
        self.assertEqual(sorted(silent), [], "a command a member can run: list it, or add it to LISTED_ELSEWHERE with a reason")

    def test_everything_unlisted_on_purpose_still_exists_and_is_not_also_listed(self):
        self.assertEqual(sorted(help_card.LISTED_ELSEWHERE - self.commands), [], "stale: the command is gone")
        self.assertEqual(sorted(help_card.LISTED_ELSEWHERE & help_card.listed_commands()), [])

    def test_the_guard_can_fail(self):
        with patch.object(help_card, "LISTED_ELSEWHERE", frozenset()):
            silent = self.members & self.commands - help_card.listed_commands() - help_card.LISTED_ELSEWHERE
            self.assertIn("flow", silent)

    def test_what_is_typed_starts_with_the_command_it_runs(self):
        rows = [r for _, group in help_card.GROUPS for r in group] + list(help_card.OPERATOR)
        for typed, command, key in rows:
            self.assertTrue(typed.startswith("!" + command) or (typed == "!" and command == "help"), typed)
            self.assertIn(key, help_card._TEXT["en"])


class TheCommandAnswersTests(unittest.IsolatedAsyncioTestCase):
    def message(self, text="!help"):
        message = MagicMock()
        message.content = text
        message.author.id = ALEX
        message.channel.id = 5
        message.reply = AsyncMock()
        return message

    async def test_help_replies_with_the_card_and_nothing_else(self):
        import commands

        message = self.message()
        with patch.object(commands, "get_registry", return_value=REGISTRY), patch.object(
            commands, "get_mage_type", return_value="practitioner"
        ):
            digest = await commands.cmd_help(message)
        view = message.reply.await_args.kwargs["view"]
        self.assertIn("What you can type here", alltext(view))
        self.assertNotIn("!diagnose", alltext(view))
        self.assertEqual(message.reply.await_args.args, ())
        self.assertIn("card", digest)

    async def test_a_bare_bang_asks_what_can_be_typed(self):
        import cmd_dispatch
        import commands

        handler = AsyncMock(return_value="shown")
        with patch.dict(commands.DIRECT_COMMANDS, {"help": handler}), patch.object(
            cmd_dispatch, "get_mage_type", return_value="practitioner"
        ), patch.object(cmd_dispatch, "inject_act_digest") as digest:
            self.assertTrue(await cmd_dispatch.try_direct_command(self.message("!")))
        handler.assert_awaited_once()
        digest.assert_called_once()

    async def test_a_bang_and_a_word_is_not_a_bare_bang(self):
        import cmd_dispatch
        import commands

        handler = AsyncMock(return_value="shown")
        with patch.dict(commands.DIRECT_COMMANDS, {"help": handler}), patch.object(
            cmd_dispatch, "get_mage_type", return_value="practitioner"
        ):
            self.assertFalse(await cmd_dispatch.try_direct_command(self.message("!wow")))
        handler.assert_not_awaited()


class ChannelBarMenuTests(_RoomEnv):
    """The menu under "new eddy" opens `!mcp` and `!model` in one step, for the presser alone."""

    def setUp(self):
        super().setUp()
        from river_handler import RiverEddyBarView

        self.bar = RiverEddyBarView(42)
        self.saved = (room_models._get_registry, room_models._resolve_channel)
        self.addCleanup(room_models.bind_room_lookup, *self.saved)
        room_models.bind_room_lookup(lambda: REGISTRY, lambda interaction: 100)
        flags = patch.object(room_models, "provider_flags", return_value=(True, False))
        flags.start()
        self.addCleanup(flags.stop)

    def press(self, value, channel=42, user=ALEX):
        return SimpleNamespace(
            data={"values": [value]},
            user=SimpleNamespace(id=user, display_name="Alex"),
            channel=SimpleNamespace(id=channel),
            message=SimpleNamespace(id=7, flags=SimpleNamespace(components_v2=False)),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock(), edit_message=AsyncMock()),
        )

    def test_the_menu_offers_commands_mcp_and_model_and_nothing_that_was_never_used(self):
        menu = next(c for c in self.bar.children if isinstance(c, discord.ui.Select))
        self.assertEqual([o.value for o in menu.options], ["commands", "mcp", "model"])
        self.assertEqual(menu.custom_id, "river:bar:more:42", "the id a posted bar already has")

    def test_model_opens_the_rooms_card_privately(self):
        press = self.press("model")
        with patch("core.models.conversation_model", return_value="gemma4:31b"):
            asyncio.run(self.bar._on_more(press))
        sent = press.response.send_message.await_args
        self.assertTrue(sent.kwargs["ephemeral"])
        self.assertIn("Who answers here", alltext(sent.kwargs["view"]))

    def test_mcp_opens_the_list_for_whoever_pressed(self):
        press = self.press("mcp")
        with patch("outgoing_connect_ui.open_list", new_callable=AsyncMock) as opened:
            asyncio.run(self.bar._on_more(press))
        opened.assert_awaited_once_with(press)

    def test_a_choice_from_a_bar_posted_before_this_change_is_answered_not_dropped(self):
        for old in ("artifacts", "help"):
            press = self.press(old)
            asyncio.run(self.bar._on_more(press))
            sent = press.response.send_message.await_args
            self.assertTrue(sent.kwargs["ephemeral"], old)
            self.assertIn("changed", sent.args[0], old)

    def test_a_press_from_another_channel_is_refused(self):
        press = self.press("model", channel=43)
        asyncio.run(self.bar._on_more(press))
        self.assertIn("Wrong channel", press.response.send_message.await_args.args[0])

    def test_a_pick_on_the_private_card_changes_it_in_place(self):
        # The card the menu opens is an ephemeral layout message; _on_pick edits it, as on a posted card.
        room_models.bind_room_lookup(lambda: REGISTRY, lambda interaction: 300)  # the shared family room
        press = self.press("opus")
        press.message = SimpleNamespace(id=9, flags=SimpleNamespace(components_v2=True))
        press.channel = SimpleNamespace(id=42, parent_id=300, parent=MagicMock(id=300, send=AsyncMock()))
        asyncio.run(room_models._on_pick(press))
        press.response.edit_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
