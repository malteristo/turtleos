"""The coding-delegate key is set from a modal and never shown to Spirit."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import delegate_key as dk
import delegate_setup as ds
import outgoing_connections as door

PLANTED = "PLANTED-DELEGATE-KEY-NOT-A-REAL-SECRET"


def _registry(shop: Path, runtime: Path) -> dict:
    return {
        "mages": {
            "ada": {"discord_id": "11", "workshop": {"checkout": str(shop)}},
            "bea": {"discord_id": "22", "workshop": {"checkout": str(shop)}},
        },
        "channels": {
            "1": {"type": "magic", "name": "magic", "mage": "ada"},
            "2": {"type": "river", "name": "home", "mage": "ada"},
            "4": {"type": "magic", "name": "magic", "mage": "bea"},
        },
    }


class Store(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: setattr(dk, "_pending", False))

    def test_a_key_is_private_and_the_status_file_holds_none_of_it(self) -> None:
        dk.put_key(PLANTED, self.root)
        path = dk.key_path(self.root)
        self.assertEqual(path.read_text().strip(), PLANTED)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        plain = dk.status_path(self.root).read_text()
        self.assertNotIn(PLANTED, plain)
        self.assertEqual(dk.status(self.root)["set"], True)
        self.assertNotIn(PLANTED, json.dumps(dk.status(self.root)))

    def test_a_short_or_spaced_value_writes_nothing(self) -> None:
        for bad in ("", "   ", "short", "has a space in it that is long enough"):
            with self.assertRaises(dk.Refused) as raised:
                dk.put_key(bad, self.root)
            self.assertNotIn(bad.strip() or "x", str(raised.exception))
        self.assertFalse(dk.key_is_set(self.root))
        self.assertFalse(dk.key_path(self.root).exists())

    def test_a_second_set_replaces_the_first(self) -> None:
        dk.put_key(PLANTED, self.root)
        dk.put_key("PLANTED-DELEGATE-KEY-REPLACEMENT-01", self.root)
        self.assertEqual(dk.load_key(self.root), "PLANTED-DELEGATE-KEY-REPLACEMENT-01")
        self.assertNotIn(PLANTED, dk.key_path(self.root).read_text())

    def test_load_key_is_the_positive_control_and_accept_key_never_echoes(self) -> None:
        self.assertEqual(dk.accept_key(PLANTED, self.root), dk.SET_REPLY)
        self.assertEqual(dk.load_key(self.root), PLANTED)
        self.assertNotIn(PLANTED, dk.SET_REPLY)

    def test_the_offer_is_taken_once(self) -> None:
        self.assertFalse(dk.take_offer())
        dk.mark_offer()
        self.assertTrue(dk.take_offer())
        self.assertFalse(dk.take_offer())


class Tool(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.shop = base / "workshop"
        self.shop.mkdir()
        self.runtime = base / "runtime"
        self.runtime.mkdir()
        self.house = base / "house"
        self.house.mkdir()
        import subprocess

        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.shop, check=True)
        self.registry = _registry(self.shop, self.runtime)
        self.room = {"id": "1"}
        self.person = {"who": "ada"}
        door.bind(
            door.Shell(
                lambda: self.registry,
                lambda: self.person["who"],
                lambda: str(self.runtime),
                lambda: [],
                lambda: self.room["id"],
            )
        )
        self.env = patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": str(self.house)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(door.bind, None)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: setattr(dk, "_pending", False))

    def test_offered_only_in_the_owners_magic_room(self) -> None:
        self.assertTrue(ds.offered())
        self.assertEqual([t["function"]["name"] for t in ds.tools_offered()], [ds.TOOL])
        self.room["id"] = "2"
        self.assertFalse(ds.offered())
        self.room["id"] = "4"
        self.assertFalse(ds.offered())
        self.room["id"] = "1"
        self.person["who"] = "bea"
        self.assertFalse(ds.offered())

    def test_the_result_never_carries_the_key_and_the_offer_is_marked(self) -> None:
        out = ds.call(ds.TOOL, {})
        self.assertIn("not set", out)
        self.assertTrue(dk.take_offer())
        dk.put_key(PLANTED)
        out = ds.call(ds.TOOL, {})
        self.assertIn("already set", out)
        self.assertNotIn(PLANTED, out)
        self.assertNotIn(PLANTED, ds.NOT_SET)
        self.assertNotIn(PLANTED, ds.ALREADY)

    def test_a_call_from_another_room_is_refused_and_marks_no_offer(self) -> None:
        self.room["id"] = "2"
        self.assertEqual(ds.call(ds.TOOL, {}), "Not in this room.")
        self.assertFalse(dk.take_offer())


class Press(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        import delegate_setup_ui as ui

        self.ui = ui
        self.tmp = tempfile.TemporaryDirectory()
        self.house = Path(self.tmp.name)
        self.registry = _registry(Path("/no/shop"), Path("/no/runtime"))
        ui._registry_loader = lambda: self.registry
        self.env = patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": str(self.house)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: setattr(ui, "_registry_loader", None))
        self.addCleanup(lambda: setattr(dk, "_pending", False))

    def _interaction(self, user_id: str, *, parent: str = "1", channel: str = "99"):
        return SimpleNamespace(
            user=SimpleNamespace(id=user_id),
            channel=SimpleNamespace(id=int(channel), parent_id=int(parent)),
            response=SimpleNamespace(send_modal=AsyncMock(), send_message=AsyncMock()),
        )

    def test_only_the_owner_of_the_magic_room_may_press(self) -> None:
        self.assertTrue(self.ui.presser_allowed(self._interaction("11")))
        self.assertFalse(self.ui.presser_allowed(self._interaction("22")))
        self.assertFalse(self.ui.presser_allowed(self._interaction("11", parent="2")))

    async def test_a_stranger_is_refused_and_the_modal_does_not_open(self) -> None:
        interaction = self._interaction("22")
        await self.ui.handle_press(interaction)
        interaction.response.send_message.assert_awaited_once_with(self.ui.NOT_OWNER, ephemeral=True)
        interaction.response.send_modal.assert_not_awaited()

    async def test_the_owner_gets_the_modal_and_a_submit_never_echoes_the_key(self) -> None:
        interaction = self._interaction("11")
        with patch.object(self.ui, "KeyModal", return_value="MODAL"):
            await self.ui.handle_press(interaction)
        interaction.response.send_modal.assert_awaited_once_with("MODAL")
        await self.ui.handle_submit(interaction, PLANTED)
        interaction.response.send_message.assert_awaited_with(dk.SET_REPLY, ephemeral=True)
        self.assertEqual(dk.load_key(), PLANTED)
        posted = " ".join(str(c) for c in interaction.response.send_message.await_args_list)
        self.assertNotIn(PLANTED, posted)

    async def test_the_button_is_posted_without_the_key(self) -> None:
        channel = SimpleNamespace(send=AsyncMock())
        with patch.object(self.ui, "KeyView", return_value="VIEW"):
            await self.ui.post_key_button(channel)
        args, kwargs = channel.send.await_args
        self.assertNotIn(PLANTED, args[0])
        self.assertEqual(kwargs["view"], "VIEW")


class Wired(unittest.TestCase):
    def test_both_bots_and_the_turn_ask_for_the_button(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.assertIn("register_delegate_views(", (root / "discord_bot.py").read_text())
        self.assertIn("register_delegate_views(", (root / "river_bot.py").read_text())
        ui = (root / "delegate_setup_ui.py").read_text()
        self.assertNotIn("from mage", ui)
        self.assertNotIn("import mage", ui)
        turn = (root / "dialogue_turn.py").read_text()
        self.assertIn("take_offer()", turn)
        self.assertIn("post_key_button(", turn)
        self.assertLess(turn.index("deliver("), turn.index("take_offer()"))

    def test_tos_tools_offers_and_dispatches_it(self) -> None:
        import tos_tools

        source = Path(tos_tools.__file__).read_text()
        self.assertIn("delegate_setup", source)
        self.assertIn("delegate_call", source)


if __name__ == "__main__":
    unittest.main()
