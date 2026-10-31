"""The channel bar's menu: which commands a channel keeps in it (his ask, 2026-10-14).

"I don't want to have to memorize all these." `!` shows what exists; the checklist on it
keeps the few he uses in the menu under "new eddy". Claims, each with a control: only
commands that can run from a menu are offered; a press runs the command it names; a
choice the channel no longer keeps is answered, not run; the choice survives a restart;
the bar is redrawn when it changes; the card says what the press did.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord
except ImportError:
    raise unittest.SkipTest("needs discord.py")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import bar_menu  # noqa: E402
import cmd_dispatch  # noqa: E402
import help_card  # noqa: E402
import room_models  # noqa: E402
import ui_kit  # noqa: E402
from tests.test_mcp_list import alltext  # noqa: E402
from tests.test_own_channel_model import ALEX, REGISTRY, _RoomEnv  # noqa: E402


def custom_ids(view) -> set[str]:
    return {n["custom_id"] for n in ui_kit._walk(view.to_components()) if n.get("custom_id")}


class WhatCanBeKeptTests(unittest.TestCase):
    def test_every_keepable_command_can_run_from_a_menu(self):
        from commands import DIRECT_COMMANDS

        typed = {cmd: shown for _, rows in help_card.GROUPS for shown, cmd, _ in rows}
        for name in bar_menu.PINNABLE:
            self.assertIn(name, DIRECT_COMMANDS, f"{name}: nothing to run")
            self.assertIn(name, help_card.listed_commands(), f"{name}: not on the `!` list")
            self.assertIn(name, cmd_dispatch._PRACTITIONER_COMMANDS)
            self.assertNotIn("<", typed[name], f"{name} takes words; a menu cannot supply them")

    def test_positive_control_a_command_with_words_would_be_caught(self):
        typed = {cmd: shown for _, rows in help_card.GROUPS for shown, cmd, _ in rows}
        self.assertIn("<", typed["rename"])
        self.assertNotIn("rename", bar_menu.PINNABLE)
        self.assertNotIn("checkpoint", bar_menu.PINNABLE, "it acts on an eddy, not on a channel")

    def test_both_languages_say_the_same_things(self):
        self.assertEqual(ui_kit.parity(bar_menu._TEXT), [])

    def test_the_menu_fits_what_discord_allows_with_everything_kept(self):
        for locale in ("en", "de"):
            rows = bar_menu.menu_options(list(bar_menu.PINNABLE), locale=locale)
            self.assertLessEqual(len(rows), 25)
            for value, label, description in rows:
                self.assertLessEqual(len(description), 100, (locale, value))
                self.assertLessEqual(len(label), 100)
            self.assertEqual([r[0] for r in rows][0], "commands")
            self.assertEqual([r[0] for r in rows][-2:], ["mcp", "model"])


class KeptBetweenVisitsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_a_press_flips_one_command_and_a_second_flips_it_back(self):
        self.assertEqual(bar_menu.pins(self.base, 5), [])
        kept, on = bar_menu.toggle(self.base, 5, "live")
        self.assertEqual((kept, on), (["live"], True))
        kept, on = bar_menu.toggle(self.base, 5, "eddy")
        self.assertEqual(kept, ["eddy", "live"], "offered in a steady order, not the order pressed")
        kept, on = bar_menu.toggle(self.base, 5, "live")
        self.assertEqual((kept, on), (["eddy"], False))

    def test_a_channel_keeps_its_own(self):
        bar_menu.toggle(self.base, 5, "eddy")
        self.assertEqual(bar_menu.pins(self.base, 6), [])
        self.assertEqual(bar_menu.pins(self.base, 5), ["eddy"])

    def test_it_survives_a_restart(self):
        bar_menu.toggle(self.base, 5, "dates")
        self.assertEqual(bar_menu.pins(Path(str(self.base)), "5"), ["dates"], "a new process reads the file")

    def test_a_command_that_cannot_be_kept_is_refused_and_writes_nothing(self):
        for bad in ("rename", "checkpoint", "nonsense", ""):
            with self.assertRaises(ValueError, msg=bad):
                bar_menu.toggle(self.base, 5, bad)
        self.assertFalse((self.base / bar_menu.PINS_FILE).exists())

    def test_a_damaged_file_or_a_withdrawn_command_does_not_break_the_menu(self):
        (self.base / bar_menu.PINS_FILE).write_text("{not json", encoding="utf-8")
        self.assertEqual(bar_menu.pins(self.base, 5), [])
        (self.base / bar_menu.PINS_FILE).write_text(json.dumps({"5": ["eddy", "gone-command", 7]}), encoding="utf-8")
        self.assertEqual(bar_menu.pins(self.base, 5), ["eddy"])


class TheBarOffersWhatIsKeptTests(_RoomEnv):
    def bar(self, channel=42):
        from river_handler import RiverEddyBarView

        view = RiverEddyBarView(channel)
        return view, next(c for c in view.children if isinstance(c, discord.ui.Select))

    def press(self, value, channel=42):
        return SimpleNamespace(
            data={"values": [value]},
            user=SimpleNamespace(id=ALEX, display_name="Alex"),
            channel=SimpleNamespace(id=channel),
            message=SimpleNamespace(id=7, flags=SimpleNamespace(components_v2=False)),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock(), edit_message=AsyncMock()),
        )

    def test_the_menu_shows_what_the_channel_keeps_in_the_order_kept(self):
        bar_menu.toggle(Path(self.house.name), 42, "live")
        bar_menu.toggle(Path(self.house.name), 42, "eddy")
        _, menu = self.bar()
        self.assertEqual([o.value for o in menu.options], ["commands", "eddy", "live", "mcp", "model"])
        _, other = self.bar(43)
        self.assertEqual([o.value for o in other.options], ["commands", "mcp", "model"], "positive control")

    def test_choosing_a_kept_command_runs_it_for_the_channel(self):
        bar_menu.toggle(Path(self.house.name), 42, "eddy")
        view, _ = self.bar()
        press = self.press("eddy")
        with patch("eddy_lifecycle_bar._run_river_act_command", new_callable=AsyncMock) as run:
            asyncio.run(view._on_more(press))
        run.assert_awaited_once_with(press, "eddy", [])
        press.response.defer.assert_awaited_once()

    def test_a_command_that_was_taken_out_is_answered_not_run(self):
        """A bar posted before the choice changed may still offer it."""
        view, _ = self.bar()
        press = self.press("live")
        with patch("eddy_lifecycle_bar._run_river_act_command", new_callable=AsyncMock) as run:
            asyncio.run(view._on_more(press))
        run.assert_not_awaited()
        self.assertIn("changed", press.response.send_message.await_args.args[0])

    def test_commands_opens_the_list_for_whoever_chose_it(self):
        view, _ = self.bar()
        press = self.press("commands")
        room_models.bind_room_lookup(lambda: REGISTRY, lambda interaction: 100)
        asyncio.run(view._on_more(press))
        sent = press.response.send_message.await_args
        self.assertTrue(sent.kwargs["ephemeral"])
        text = alltext(sent.kwargs["view"])
        self.assertIn("What you can type here", text)
        self.assertIn("Choose what's in the menu", text, "the list carries the way to the checklist")


class TheListCarriesTheButtonTests(unittest.TestCase):
    def test_the_button_is_only_there_when_something_answers_it(self):
        async def listener(interaction):
            pass

        with_button = help_card.render(menu=listener)
        self.assertIn(bar_menu.MENU_OPEN_ID, custom_ids(with_button))
        self.assertNotIn(bar_menu.MENU_OPEN_ID, custom_ids(help_card.render()))
        self.assertTrue(with_button.is_persistent())

    def test_typed_bang_carries_it(self):
        import commands

        message = MagicMock()
        message.author = SimpleNamespace(id=ALEX)
        message.reply = AsyncMock()
        with patch.object(commands, "get_registry", return_value=REGISTRY):
            asyncio.run(commands.cmd_help(message))
        self.assertIn(bar_menu.MENU_OPEN_ID, custom_ids(message.reply.await_args.kwargs["view"]))

    def test_both_languages_label_the_button(self):
        async def listener(interaction):
            pass

        self.assertIn("Wählen, was im Menü ist", alltext(help_card.render(locale="de", menu=listener)))


class TheChecklistTests(_RoomEnv):
    def setUp(self):
        super().setUp()
        self.refreshed = []

        async def refresh(client, channel_id):
            self.refreshed.append(channel_id)

        saved = (room_models._get_registry, room_models._resolve_channel, room_models._refresh_bar)
        self.addCleanup(room_models.bind_room_lookup, *saved)
        room_models.bind_room_lookup(lambda: REGISTRY, lambda interaction: 100, refresh)

    def press(self, value, *, card=True):
        return SimpleNamespace(
            data={"values": [value]},
            user=SimpleNamespace(id=ALEX, display_name="Alex"),
            client=MagicMock(),
            channel=SimpleNamespace(id=100),
            message=SimpleNamespace(id=7, flags=SimpleNamespace(components_v2=card)),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock(), edit_message=AsyncMock()),
        )

    def test_the_button_opens_the_checklist_privately_and_shows_each_command_in_or_out(self):
        bar_menu.toggle(Path(self.house.name), 100, "eddy")
        press = self.press("")
        asyncio.run(room_models.open_menu_private(press))
        sent = press.response.send_message.await_args
        self.assertTrue(sent.kwargs["ephemeral"])
        text = alltext(sent.kwargs["view"])
        for name in bar_menu.PINNABLE:
            self.assertIn(f"!{name}", text)
        self.assertEqual(text.count(ui_kit.STATES["on"]), 1, "one is in")
        self.assertEqual(text.count(ui_kit.STATES["off"]), len(bar_menu.PINNABLE) - 1, "the rest are out")

    def test_a_press_keeps_the_command_says_so_in_place_and_redraws_the_bar(self):
        press = self.press("live")
        asyncio.run(room_models._on_menu_pick(press))
        self.assertEqual(bar_menu.pins(Path(self.house.name), 100), ["live"])
        edited = press.response.edit_message.await_args.kwargs["view"]
        self.assertIn("!live is in the menu now.", alltext(edited))
        self.assertEqual(self.refreshed, [100], "the bar already posted cannot change its options")
        again = self.press("live")
        asyncio.run(room_models._on_menu_pick(again))
        self.assertEqual(bar_menu.pins(Path(self.house.name), 100), [])
        self.assertIn("!live is out of the menu.", alltext(again.response.edit_message.await_args.kwargs["view"]))

    def test_a_shared_room_is_told_the_menu_is_everyones(self):
        shared = bar_menu.render([], shared=True)
        self.assertIn("everyone here sees", alltext(shared))
        self.assertNotIn("everyone here sees", alltext(bar_menu.render([])), "positive control")

    def test_a_refused_choice_changes_nothing(self):
        press = self.press("rename")
        asyncio.run(room_models._on_menu_pick(press))
        self.assertEqual(bar_menu.pins(Path(self.house.name), 100), [])
        self.assertEqual(self.refreshed, [])
        press.response.send_message.assert_awaited()

    def test_a_bar_that_cannot_be_redrawn_does_not_lose_the_choice(self):
        async def broken(client, channel_id):
            raise RuntimeError("discord said no")

        room_models._refresh_bar = broken
        press = self.press("eddy")
        asyncio.run(room_models._on_menu_pick(press))
        self.assertEqual(bar_menu.pins(Path(self.house.name), 100), ["eddy"])

    def test_the_listeners_are_armed_so_a_press_after_a_restart_lands(self):
        client = MagicMock()
        room_models.arm_model_menu(client, lambda: REGISTRY, lambda i: 100)
        armed = set()
        for call in client.add_view.call_args_list:
            armed |= custom_ids(call.args[0])
        self.assertIn(bar_menu.MENU_OPEN_ID, armed)
        self.assertIn(bar_menu.MENU_SELECT_ID, armed)


class RedrawingTheBarTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_channel_with_no_bar_gets_none_made(self):
        import river_handler

        client = MagicMock()
        with patch.object(river_handler, "_load_eddy_bar_state", return_value={}), patch.object(
            river_handler, "post_river_eddy_bar", new_callable=AsyncMock
        ) as post:
            await river_handler.refresh_river_bar(client, 42)
        post.assert_not_awaited()

    async def test_a_channel_with_a_bar_gets_a_fresh_one_at_the_bottom(self):
        import river_handler

        channel = MagicMock(id=42)
        client = MagicMock()
        client.get_channel.return_value = channel
        with (
            patch.object(river_handler, "_load_eddy_bar_state", return_value={"42": 9}),
            patch.object(river_handler, "_delete_river_bar_orphans", new_callable=AsyncMock) as delete,
            patch.object(river_handler, "post_river_eddy_bar", new_callable=AsyncMock) as post,
        ):
            await river_handler.refresh_river_bar(client, 42)
        delete.assert_awaited_once_with(channel, 42)
        post.assert_awaited_once_with(channel, client)


if __name__ == "__main__":
    unittest.main()
