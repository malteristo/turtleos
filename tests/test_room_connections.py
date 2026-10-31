"""Which service answers in which room: the ceiling, the switch, and X as the first row.

Every case here has a planted control: a room that must say yes beside the one
that must say no, so an empty answer cannot pass for a refusal.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import outgoing_connections as door
import room_connections as rc
import tos_tools

REGISTRY = {
    "channels": {
        "1": {"type": "river", "name": "home", "mage": "ada"},
        "2": {"type": "craft", "name": "craft", "attunement": "craft", "mage": "ada"},
        "3": {"type": "health", "name": "my-health", "mage": "ada"},
        "4": {"type": "shared-river", "name": "family", "mage": "ada"},
        "5": {"type": "hosted-river", "name": "home-other", "mage": "bea"},
        "6": {"type": "mystery", "name": "unknown kind", "mage": "ada"},
        "7": {"type": "river", "name": "no owner"},
        "8": {"type": "river", "name": "bea home", "mage": "bea"},
    }
}
PLANTED = rc.Service(id="planted", label="Planted", ceiling={"river": "act", "craft": "look"}, default={"river": "look"})


def _names(tools) -> set[str]:
    return {(t.get("function") or {}).get("name") or t.get("name") or "" for t in tools}


class CeilingTests(unittest.TestCase):
    def test_no_service_ever_names_a_health_or_shared_room(self) -> None:
        for service in rc.SERVICES.values():
            for room in rc.NEVER_ANSWER_IN:
                self.assertNotIn(room, service.ceiling, f"{service.id} names {room}")
                self.assertNotIn(room, service.default, f"{service.id} defaults in {room}")

    def test_a_ceiling_names_only_room_types_that_exist(self) -> None:
        for service in rc.SERVICES.values():
            for room in (*service.ceiling, *service.default):
                self.assertIn(room, rc.ROOM_TYPES, f"{service.id}: {room}")
            for room, wanted in {**service.default}.items():
                self.assertLessEqual(rc._rank(wanted), rc._rank(service.ceiling.get(room, "off")), f"{service.id} defaults above its ceiling in {room}")

    def test_every_room_type_against_the_planted_service(self) -> None:
        with patch.dict(rc.SERVICES, {"planted": PLANTED}):
            got = {
                cid: rc.level("planted", registry=REGISTRY, channel_id=cid, person="ada", root=None)
                for cid in REGISTRY["channels"]
            }
        self.assertEqual(got["1"], "look", "positive control: the room the ceiling allows answers")
        self.assertEqual(got["2"], "off", "inside the ceiling but not on by default: the person switches it on")
        for cid in ("3", "4", "5", "6"):
            self.assertEqual(got[cid], "off", REGISTRY["channels"][cid]["type"])

    def test_a_sign_in_is_not_used_in_a_room_that_belongs_to_someone_else(self) -> None:
        with patch.dict(rc.SERVICES, {"planted": PLANTED}):
            own = rc.level("planted", registry=REGISTRY, channel_id="1", person="ada", root=None)
            theirs = rc.level("planted", registry=REGISTRY, channel_id="1", person="bea", root=None)
            ownerless = rc.level("planted", registry=REGISTRY, channel_id="7", person="ada", root=None)
        self.assertEqual(own, "look", "positive control: her own room")
        self.assertEqual(theirs, "off", "bea asking in ada's room does not use bea's sign-in there")
        self.assertEqual(ownerless, "off", "a room nobody owns answers for nobody")

    def test_an_unregistered_room_is_off(self) -> None:
        with patch.dict(rc.SERVICES, {"planted": PLANTED}):
            self.assertEqual(rc.level("planted", registry=REGISTRY, channel_id="999", person="ada", root=None), "off")
            self.assertEqual(rc.level("planted", registry=REGISTRY, channel_id=None, person="ada", root=None), "off")
            self.assertEqual(rc.level("planted", registry=None, channel_id="1", person="ada", root=None), "off")
        self.assertEqual(rc.level("nothing", registry=REGISTRY, channel_id="1", person="ada", root=None), "off")

    def test_x_names_the_one_room_the_door_enforces(self) -> None:
        self.assertEqual(set(rc.SERVICES["x"].ceiling), {door.ANSWERS_IN})


class SwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        patcher = patch.dict(rc.SERVICES, {"planted": PLANTED})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _level(self, cid, person="ada") -> str:
        return rc.level("planted", registry=REGISTRY, channel_id=cid, person=person, root=self.root)

    def test_a_choice_is_kept_and_read_back(self) -> None:
        self.assertEqual(self._level("1"), "look")
        rc.choose(self.root, "ada", "planted", "1", "act", registry=REGISTRY)
        self.assertEqual(self._level("1"), "act")
        rc.choose(self.root, "ada", "planted", "1", "off", registry=REGISTRY)
        self.assertEqual(self._level("1"), "off")

    def test_the_choice_is_the_persons_own(self) -> None:
        rc.choose(self.root, "ada", "planted", "1", "off", registry=REGISTRY)
        self.assertEqual(self._level("1", "ada"), "off")
        self.assertEqual(self._level("8", "bea"), "look", "another person's own room keeps its default")
        with self.assertRaises(rc.Forbidden):
            rc.choose(self.root, "ada", "planted", "8", "off", registry=REGISTRY)  # not ada's room

    def test_a_choice_wider_than_the_ceiling_is_refused(self) -> None:
        with self.assertRaises(rc.Forbidden):
            rc.choose(self.root, "ada", "planted", "2", "act", registry=REGISTRY)  # craft tops out at look
        rc.choose(self.root, "ada", "planted", "2", "look", registry=REGISTRY)  # positive control
        for cid in ("3", "4", "5"):
            with self.assertRaises(rc.Forbidden):
                rc.choose(self.root, "ada", "planted", cid, "look", registry=REGISTRY)
        self.assertEqual(self._level("3"), "off")
        with self.assertRaises(rc.Forbidden):
            rc.choose(self.root, "ada", "no-such-service", "1", "look", registry=REGISTRY)

    def test_a_file_edited_past_the_ceiling_does_not_widen_a_room(self) -> None:
        path = rc.choices_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ada": {"planted": {"2": "act", "3": "act", "4": "look"}}}), encoding="utf-8")
        self.assertEqual(self._level("2"), "look", "clamped to the ceiling")
        self.assertEqual(self._level("3"), "off")
        self.assertEqual(self._level("4"), "off")

    def test_an_unreadable_or_odd_file_falls_back_to_the_default(self) -> None:
        path = rc.choices_path(self.root)
        path.parent.mkdir(parents=True)
        for body in ("not json", "[]", json.dumps({"ada": "x"}), json.dumps({"ada": {"planted": {"1": "banana"}}})):
            path.write_text(body, encoding="utf-8")
            self.assertEqual(self._level("1"), "look", body)

    def test_the_file_holds_no_secret_field(self) -> None:
        rc.choose(self.root, "ada", "planted", "1", "look", registry=REGISTRY)
        data = json.loads(rc.choices_path(self.root).read_text(encoding="utf-8"))
        self.assertEqual(data, {"ada": {"planted": {"1": "look"}}})
        self.assertEqual(rc.choices_path(self.root).stat().st_mode & 0o777, 0o600)


class XIsTheFirstRowTests(unittest.TestCase):
    """X still answers in craft, and the person can now switch it off there."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.room = {"id": "2"}
        door.install_catalog({"instructions": "M", "tools": [{"name": "get_posts", "inputSchema": {}}]})

        def bind(channel):
            door.bind(
                door.Shell(
                    lambda: REGISTRY,
                    lambda: "ada",
                    lambda: str(self.root),
                    lambda: [],
                    (lambda: self.room["id"]) if channel else None,
                )
            )

        self.bind = bind
        self.addCleanup(door.bind, None)
        self.addCleanup(door.install_catalog, None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_craft_answers_by_default(self) -> None:
        self.bind(True)
        self.assertIn("get_posts", _names(tos_tools.tools_for_attunement("craft")))

    def test_switched_off_in_craft_it_is_gone_and_the_manual_goes_with_it(self) -> None:
        self.bind(True)
        self.assertEqual(door.connection_preamble("craft"), "M", "positive control")
        rc.choose(self.root, "ada", "x", "2", "off", registry=REGISTRY)
        self.assertNotIn("get_posts", _names(tos_tools.tools_for_attunement("craft")))
        self.assertEqual(door.connection_preamble("craft"), "")

    def test_a_health_room_refuses_even_if_the_attunement_said_craft(self) -> None:
        self.bind(True)
        self.room["id"] = "3"
        self.assertNotIn("get_posts", _names(tos_tools.tools_for_attunement("craft")))
        self.room["id"] = "4"
        self.assertNotIn("get_posts", _names(tos_tools.tools_for_attunement("craft")))
        self.room["id"] = "2"
        self.assertIn("get_posts", _names(tos_tools.tools_for_attunement("craft")), "positive control")

    def test_another_persons_choice_is_not_hers(self) -> None:
        self.bind(True)
        path = rc.choices_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"bea": {"x": {"2": "off"}}}), encoding="utf-8")  # written by hand
        self.assertIn("get_posts", _names(tos_tools.tools_for_attunement("craft")), "ada asks; bea's line is not hers")

    def test_a_shell_that_cannot_name_its_room_keeps_the_attunement_rule(self) -> None:
        self.bind(False)
        self.assertIn("get_posts", _names(tos_tools.tools_for_attunement("craft")))
        self.assertNotIn("get_posts", _names(tos_tools.tools_for_attunement("native")))

    def test_the_real_shells_are_given_a_room(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("discord_bot.py", "river_bot.py"):
            text = (root / name).read_text(encoding="utf-8")
            self.assertIn("list_registered_runtime_dirs, get_current_channel_id)", text, name)


if __name__ == "__main__":
    unittest.main()
