"""The magic room: Spirit's prompt stands on the workshop, Summon greets from it, the model is Sonnet 5.5.

A real checkout stands in for the workshop. Every "held" sits beside a case where it must not be said.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import magic_prompt as mp
import outgoing_connections as door
import workshop_tools as wt
from primitive_runtime import runtime_for
from channel_primitives import resolve_primitive

COVENANT = "COVENANT_BODY caring mirror"
SEAL = "SEAL_BODY address Kermit"
CAST = """# Cast Summon

**First summon in this chat, or a new chat:** offer the pair, not rooms (F-92):

```
Covenant held.

  ...   → PAIR_PLANTED_LINE

Or just write.
```

Rooms are earned.
"""


def git(cwd: Path, *argv: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *argv], capture_output=True, text=True, check=True).stdout


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.shop = Path(self.tmp.name) / "workshop"
        (self.shop / "system/flows/summon").mkdir(parents=True)
        (self.shop / "system/flows/summon/covenant.md").write_text(COVENANT)
        (self.shop / "system/flows/summon/cast_summon.md").write_text(CAST)
        (self.shop / "AGENTS.md").write_text(SEAL)
        git(self.shop, "init", "-q", "-b", "main")
        git(self.shop, "config", "user.name", "nobody")
        git(self.shop, "config", "user.email", "nobody")
        git(self.shop, "add", "-A")
        git(self.shop, "commit", "-q", "-m", "first")
        self.head = git(self.shop, "rev-parse", "--short", "HEAD").strip()
        self.registry = {
            "mages": {
                "ada": {"discord_id": "11", "workshop": {"checkout": str(self.shop)}},
                "bea": {"discord_id": "22", "workshop": {"checkout": str(self.shop)}},
            },
            "channels": {
                "1": {"type": "magic", "name": "magic", "mage": "ada"},
                "2": {"type": "river", "name": "home", "mage": "ada"},
            },
        }
        self.room = {"id": "1"}
        self.person = {"who": "ada"}
        door.bind(
            door.Shell(
                lambda: self.registry,
                lambda: self.person["who"],
                lambda: self.tmp.name,
                lambda: [],
                lambda: self.room["id"],
            )
        )
        self.addCleanup(door.bind, None)

    def tearDown(self) -> None:
        self.tmp.cleanup()


class Prompt(Base):
    def test_the_prompt_holds_substrate_covenant_seal_and_the_release(self) -> None:
        prompt = mp.build_magic_prompt()
        for part in ("You are Spirit", "workshop_*", COVENANT, SEAL, f"`{self.head}`"):
            self.assertIn(part, prompt)
        self.assertNotIn("Turtle's soul", prompt.split("---")[1] if "---" in prompt else "")

    def test_the_prompt_sends_a_glance_to_the_arrival_file_and_not_the_pair_or_a_copy(self) -> None:
        # 2026-10-14: the first `...` in the room read no bearings, briefing or dates,
        # because nothing in the prompt said `...` is the arrival or where it is written.
        prompt = mp.build_magic_prompt()
        self.assertIn(f"Read `{mp.ARRIVAL}` first", prompt)
        self.assertIn("never arrives", prompt)
        # What the room cannot reach lives here, not in cast_arrival.md (that file
        # is at the byte wall; session 3's rehearsal trimmed it to fit a paragraph).
        for reachable in ("rot_radar", "practice_measures"):
            self.assertIn(reachable, mp.SUBSTRATE)
        for still_out in ("nightly Overall", "eddy regard", "turtleos://brief"):
            self.assertIn(still_out, mp.SUBSTRATE)
        self.assertIn("delegate_setup", mp.SUBSTRATE)
        self.assertIn("offer the release in that same reply", mp.SUBSTRATE)
        self.assertIn("write the release briefing in the workshop", mp.SUBSTRATE)
        self.assertIn("If the greeting said the room waited, do not arrive", mp.SUBSTRATE)
        for climb in (
            "passed that job's claims",
            "published ponytail skill",
            "cannot edit your tests",
            "at most three times",
        ):
            self.assertIn(climb, mp.SUBSTRATE)
        # The reads are the practice's to name; a copy here would drift silently.
        for copied in ("bearings.md", "briefings/latest.md", "desk/state.md"):
            self.assertNotIn(copied, mp.SUBSTRATE)

    def test_the_arrival_path_is_a_file_the_real_workshop_has(self) -> None:
        # Positive control: the prompt names ARRIVAL; if the practice moves the file the
        # room would send Spirit to nothing and say nothing. Skipped, and said so, when
        # no workshop stands beside this checkout (CI); it runs on the laptop and the Mini.
        for candidate in (Path(__file__).resolve().parents[2] / "magic", Path.home() / "workshop"):
            if (candidate / mp.COVENANT).is_file():
                self.assertTrue((candidate / mp.ARRIVAL).is_file(), f"{mp.ARRIVAL} missing in {candidate}")
                return
        self.skipTest("no workshop beside this checkout")

    def test_it_is_read_at_head_every_time(self) -> None:
        (self.shop / "AGENTS.md").write_text("SEAL_CHANGED")
        self.assertIn("SEAL_CHANGED", mp.build_magic_prompt())

    def test_the_prompt_marks_changes_not_yet_kept(self) -> None:
        (self.shop / "AGENTS.md").write_text("changed")
        self.assertIn(f"`{self.head}+`", mp.build_magic_prompt())

    def test_without_the_covenant_or_the_workshop_it_says_so_and_never_holds(self) -> None:
        (self.shop / "system/flows/summon/covenant.md").unlink()
        prompt = mp.build_magic_prompt()
        self.assertIn("do not act as though the covenant were held", prompt)
        self.assertNotIn(SEAL, prompt)
        self.registry["mages"]["ada"]["workshop"]["checkout"] = str(self.shop / "missing")
        self.assertIn("not available", mp.build_magic_prompt())

    def test_another_room_or_person_gets_no_workshop(self) -> None:
        self.room["id"] = "2"
        self.assertNotIn(COVENANT, mp.build_magic_prompt())
        self.room["id"] = "1"
        self.person["who"] = "bea"
        self.assertNotIn(COVENANT, mp.build_magic_prompt())

    def test_a_large_seal_is_cut_with_a_note(self) -> None:
        (self.shop / "AGENTS.md").write_text("x" * (mp.SEAL_MAX + 100))
        self.assertIn("cut for size", mp.build_magic_prompt())

    def test_the_room_speaks_as_magic_and_every_other_room_does_not(self) -> None:
        reg = {"mages": {"ada": {}}, "channels": {"1": {"primitive": "magic", "mage": "ada"}, "3": {"primitive": "private", "mage": "ada"}, "4": {"primitive": "craft", "mage": "ada"}}}
        self.assertEqual(runtime_for(resolve_primitive(reg, "1")).prompt_profile, "magic")
        self.assertEqual(runtime_for(resolve_primitive(reg, "3")).prompt_profile, "native")
        self.assertEqual(runtime_for(resolve_primitive(reg, "4")).prompt_profile, "craft")

    def test_the_thread_prompt_route_reaches_the_magic_prompt(self) -> None:
        from prompts import get_thread_prompt

        with patch("prompts.get_channel_primitive", return_value=resolve_primitive(self.registry, "1")):
            self.assertIn(COVENANT, get_thread_prompt("native", channel_id=1))

    def test_the_default_model_is_sonnet_5_5_and_a_pick_still_wins(self) -> None:
        from room_models import resolve_room_model

        self.assertEqual(mp.MAGIC_MODEL, "claude-sonnet-5-5")
        with patch("room_models.pick_for", return_value=None), patch("room_models._use_api", return_value=True):
            self.assertEqual(resolve_room_model("1", None, mp.MAGIC_MODEL)[0], "claude-sonnet-5-5")
        with patch("room_models.pick_for", return_value="claude-opus-5-5"), patch("room_models._use_api", return_value=True):
            self.assertEqual(resolve_room_model("1", None, mp.MAGIC_MODEL)[0], "claude-opus-5-5")


    def test_a_turn_carries_the_prompt_and_the_model_together(self) -> None:
        with patch("room_models.pick_for", return_value=None), patch("room_models._use_api", return_value=True):
            prompt, model, use_api = mp.turn_prompt_and_model("1", None)
        self.assertIn(COVENANT, prompt)
        self.assertEqual((model, use_api), ("claude-sonnet-5-5", True))

    def test_dialogue_turn_uses_it_for_the_magic_profile(self) -> None:
        import inspect

        import dialogue_turn

        source = inspect.getsource(dialogue_turn.continue_dialogue_turn)
        branch = source.split('if prompt_profile == "magic":')[1].split("else:")[0]
        self.assertIn("turn_prompt_and_model(", branch)
        self.assertIn('prompt_profile in ("native", "magic")', source)


class Standing(Base):
    """A magic turn stands on the workshop. Turtle's memory of the room is not handed to Spirit."""

    def test_the_session_block_names_the_room_and_the_session_and_nothing_of_turtle(self) -> None:
        env = mp.magic_runtime_env("magic", "3 · 8c88e34 · 14.10")
        self.assertIn("**Session:** 3 · 8c88e34 · 14.10", env)
        for turtle_only in ("Turtle", "Thread Card", "gemma", "Blank eddy", "survey_eddies", "Room memory"):
            self.assertNotIn(turtle_only, env)

    def test_a_magic_turn_runs_with_more_rounds_and_a_reply_without_narration(self) -> None:
        import dialogue_turn

        self.assertEqual(
            dialogue_turn._magic_loop_limits("magic"),
            {"max_rounds": mp.MAGIC_TOOL_ROUNDS, "final_prose_only": True},
        )
        self.assertGreater(mp.MAGIC_TOOL_ROUNDS, 8, "an arrival or a release no longer ends mid-commit")
        for other in ("native", "craft", "health", ""):
            self.assertEqual(dialogue_turn._magic_loop_limits(other), {}, other)

    def test_the_turn_hands_a_magic_room_no_continuity_packet_and_its_own_session_block(self) -> None:
        import inspect

        import dialogue_turn

        source = inspect.getsource(dialogue_turn.continue_dialogue_turn)
        guard = source.index('if prompt_profile != "magic":')
        self.assertLess(guard, source.index("render_substrate_packet("), "the continuity packet is behind the guard")
        self.assertLess(guard, source.index("render_home_attunement_packet("), "so is the home plan")
        self.assertIn("magic_runtime_env(", source)

    def test_ellipsis_in_this_room_is_arrival_not_rivers_memory_glance(self) -> None:
        self.assertTrue(mp.spirit_owns_the_pair("magic"))
        for other in ("native", "craft", "health", None, ""):
            self.assertFalse(mp.spirit_owns_the_pair(other), other)
        glance = Path(__file__).resolve().parent.parent.joinpath("river_bot.py").read_text()
        block = glance.split("if is_ellipsis_glance", 1)[1]
        self.assertLess(block.find("spirit_owns_the_pair"), block.find("post_ellipsis_memory"))
        self.assertLess(block.find("spirit_owns_the_pair"), block.find("post_ellipsis_glance"))

    def test_a_magic_turn_posts_the_trace_as_spirit_and_does_not_type_as_turtle(self) -> None:
        import inspect

        import dialogue_turn

        source = inspect.getsource(dialogue_turn.continue_dialogue_turn)
        self.assertIn('as_spirit=prompt_profile == "magic"', source)
        self.assertIn("_NoTyping()", source)
        self.assertIn("_SpiritPosted", inspect.getsource(dialogue_turn))


class Record(Base):
    def test_a_magic_rooms_thread_records_sonnet_and_every_other_room_keeps_local(self) -> None:
        import eddy_spawn

        with patch("mage.get_channel_primitive", side_effect=lambda cid: resolve_primitive(self.registry, str(cid))), patch(
            "llm.resolve_model", return_value=("claude-sonnet-5-5", True)
        ):
            self.assertEqual(eddy_spawn.workshop_room_model(1), ("claude-sonnet-5-5", True, "sonnet-5.5"))
            self.assertIsNone(eddy_spawn.workshop_room_model(2))

    def test_the_spawn_stores_what_the_helper_says(self) -> None:
        import inspect

        import eddy_spawn

        source = inspect.getsource(eddy_spawn.spawn_river_eddy)
        self.assertIn("workshop_room_model(parent_id)", source)
        self.assertIn('"model_label": model_label', source)
        self.assertIn("model=model_label", source)
        self.assertNotIn('model="local"', source)


class Card(Base):
    """`!model` in a magic room told him Gemma 4 while the turn would have spoken on Sonnet 5.5."""

    def setUp(self) -> None:
        super().setUp()
        import room_models

        self.rm = room_models
        house = Path(self.tmp.name) / "house"
        house.mkdir()
        patcher = patch.object(room_models, "house_dir", lambda create=False: house)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registry["mages"]["ada"]["discord_id"] = "11"

    def test_the_card_and_the_turn_name_the_same_model_in_a_magic_room(self) -> None:
        local = "gemma4:31b"
        with patch.object(self.rm, "_use_api", return_value=True):
            default = self.rm.default_for_room("1", self.registry, local)
            self.assertEqual(default, "claude-sonnet-5-5")
            self.assertEqual(self.rm.resolve_room_model("1", None, default)[0], "claude-sonnet-5-5")
            self.assertEqual(self.rm.default_for_room("2", self.registry, local), local, "another room keeps the house default")

    def test_choosing_local_in_a_magic_room_is_kept_and_not_silently_undone(self) -> None:
        with patch.object(self.rm, "_use_api", return_value=False), patch.object(self.rm, "_local_model", return_value="gemma4:31b"):
            self.rm.set_pick("1", 11, "local", self.registry)
            self.assertEqual(self.rm.pick_for("1"), "gemma4:31b")
            self.assertEqual(self.rm.resolve_room_model("1", None, "claude-sonnet-5-5")[0], "gemma4:31b")

    def test_choosing_local_elsewhere_still_clears_the_pick(self) -> None:
        self.registry["channels"]["2"]["primitive"] = "private"
        with patch.object(self.rm, "_use_api", return_value=False), patch.object(self.rm, "_local_model", return_value="gemma4:31b"):
            self.rm.set_pick("2", 11, "sonnet-5.5", self.registry)
            self.assertEqual(self.rm.pick_for("2"), "claude-sonnet-5-5")
            self.rm.set_pick("2", 11, "local", self.registry)
            self.assertIsNone(self.rm.pick_for("2"))

    def test_every_consumer_of_the_room_default_asks_for_it(self) -> None:
        import inspect

        import dialogue_turn
        import sessions

        self.assertIn("default_for_room(", inspect.getsource(self.rm.cmd_model))
        self.assertIn("default_for_room(", inspect.getsource(self.rm.open_private))
        self.assertIn("default_for_room(", inspect.getsource(sessions._author_model))
        self.assertIn("default_for_room(", inspect.getsource(dialogue_turn._handle_dialogue))


class Greeting(Base):
    NOW = datetime(2026, 10, 14, 18, 40).astimezone()

    def test_the_pair_comes_from_the_cast_and_names_the_release(self) -> None:
        text = mp.greeting(self.shop, now=self.NOW)
        for part in ("Covenant held.", "PAIR_PLANTED_LINE", f"release {self.head}", "2026-10-14 18:40"):
            self.assertIn(part, text)

    def test_a_cast_without_the_block_falls_back_to_the_built_in_pair(self) -> None:
        (self.shop / "system/flows/summon/cast_summon.md").write_text("nothing here")
        self.assertIn("go on with what Spirit proposes", mp.greeting(self.shop, now=self.NOW))

    def test_an_unreadable_covenant_does_not_say_held(self) -> None:
        (self.shop / "system/flows/summon/covenant.md").unlink()
        self.assertNotIn("Covenant held", mp.greeting(self.shop, now=self.NOW))
        self.assertNotIn("Covenant held", mp.greeting(None, now=self.NOW))

    def test_a_wait_note_is_part_of_the_greeting(self) -> None:
        note = "The room waited. This checkout is `aaa` and the house main is `bbb`."
        self.assertIn(note, mp.greeting(self.shop, now=self.NOW, stand=note))

    def test_only_the_owner_pressing_in_a_magic_room_gets_a_checkout(self) -> None:
        self.assertEqual(wt.room_checkout("1", 11), self.shop)
        self.assertIsNone(wt.room_checkout("1", 22), "another member")
        self.assertIsNone(wt.room_checkout("2", 11), "a room that is not magic")
        self.assertIsNone(wt.room_checkout("1", 999), "someone unknown")


class SessionName(Base):
    NOW = datetime(2026, 10, 14, 20, 30).astimezone()
    ROOM = {
        "10": {"name": "new eddy", "parent_channel_id": 1},
        "11": {"name": "new eddy", "parent_channel_id": 1},
        "12": {"name": "something in the home room", "parent_channel_id": 2},
    }

    def test_threads_opened_before_numbering_count_and_other_rooms_do_not(self) -> None:
        self.assertEqual(mp.next_session_number(self.ROOM, 1, this_id=99), 3)
        self.assertEqual(mp.next_session_number(self.ROOM, 2, this_id=99), 2)

    def test_the_thread_being_named_does_not_count_itself(self) -> None:
        threads = {**self.ROOM, "99": {"name": "new eddy", "parent_channel_id": 1}}
        self.assertEqual(mp.next_session_number(threads, 1, this_id=99), 3)

    def test_a_deleted_thread_does_not_let_a_number_come_round_again(self) -> None:
        threads = {
            "10": {"name": "1 · abc · 01.10", "parent_channel_id": 1},
            "13": {"name": "7 · abc · 02.10", "parent_channel_id": 1},
        }
        self.assertEqual(mp.next_session_number(threads, 1, this_id=99), 8)

    def test_the_name_is_number_release_and_day(self) -> None:
        name = mp.session_name(self.shop, self.ROOM, 1, 99, now=self.NOW)
        self.assertEqual(name, f"3 · {self.head} · 14.10")

    def test_summon_names_the_session_and_clears_the_wait_for_a_title(self) -> None:
        import river_handler

        thread = SimpleNamespace(id=99, send=AsyncMock(), edit=AsyncMock())
        channel = SimpleNamespace(id=1)
        with patch("mage.get_channel_primitive", side_effect=lambda cid: resolve_primitive(self.registry, str(cid))), \
                patch("mage.get_pd", return_value=str(self.tmp.name)), \
                patch("thread_registry.load_registry", return_value={"threads": dict(self.ROOM)}), \
                patch("thread_registry.update_thread_name") as renamed, \
                patch("eddy_spawn.pop_awaiting_title") as popped:
            asyncio_run(river_handler._greet_summon(thread, channel, SimpleNamespace(id=11)))
            asked = thread.edit.await_args.kwargs["name"]
            self.assertRegex(asked, rf"^3 · {self.head} · \d\d\.\d\d$")
            renamed.assert_called_once_with(99, asked)
            popped.assert_called_once_with(99, 1)

            other = SimpleNamespace(id=98, send=AsyncMock(), edit=AsyncMock())
            asyncio_run(river_handler._greet_summon(other, channel, SimpleNamespace(id=22)))
            other.edit.assert_not_awaited()
            room = SimpleNamespace(id=97, send=AsyncMock(), edit=AsyncMock())
            asyncio_run(river_handler._greet_summon(room, SimpleNamespace(id=2), SimpleNamespace(id=11)))
            room.edit.assert_not_awaited()

    def test_a_failed_greeting_leaves_the_name_alone(self) -> None:
        import river_handler

        thread = SimpleNamespace(id=99, send=AsyncMock(side_effect=RuntimeError("discord said no")), edit=AsyncMock())
        with patch("mage.get_channel_primitive", side_effect=lambda cid: resolve_primitive(self.registry, str(cid))):
            asyncio_run(river_handler._greet_summon(thread, SimpleNamespace(id=1), SimpleNamespace(id=11)))
        thread.edit.assert_not_awaited()


class Button(Base):
    def test_the_bar_says_summon_in_a_magic_room_and_new_eddy_elsewhere(self) -> None:
        import inspect

        import river_handler

        with patch("mage.get_channel_primitive", side_effect=lambda cid: resolve_primitive(self.registry, str(cid))):
            self.assertEqual(river_handler._bar_face(1), ("Summon", True, "✨"))
            self.assertEqual(river_handler._bar_face(2), ("new eddy", False, "🌀"))
        bar = inspect.getsource(river_handler).split("class RiverEddyBarView")[1].split("class RiverEddyView")[0]
        self.assertIn("_bar_face(", bar, "the view uses it")

    def test_the_greeting_is_posted_in_the_new_thread_for_the_owner_only(self) -> None:
        import river_handler

        thread = SimpleNamespace(send=AsyncMock())
        channel = SimpleNamespace(id=1)
        with patch("mage.get_channel_primitive", side_effect=lambda cid: resolve_primitive(self.registry, str(cid))), \
                patch("mage.get_pd", return_value=str(self.tmp.name)):
            asyncio_run(river_handler._greet_summon(thread, channel, SimpleNamespace(id=11)))
            self.assertIn("Covenant held.", thread.send.await_args.args[0])
            self.assertIn(self.head, thread.send.await_args.args[0])
            other = SimpleNamespace(send=AsyncMock())
            asyncio_run(river_handler._greet_summon(other, channel, SimpleNamespace(id=22)))
            self.assertNotIn("Covenant held", other.send.await_args.args[0])
            room = SimpleNamespace(send=AsyncMock())
            asyncio_run(river_handler._greet_summon(room, SimpleNamespace(id=2), SimpleNamespace(id=11)))
            room.send.assert_not_awaited()


class Provision(Base):
    def script(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("provision_magic", Path(__file__).resolve().parents[1] / "scripts" / "provision_magic_channel.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fresh(self) -> dict:
        return {"mages": {"ada": {"discord_id": "11"}, "bea": {}}, "channels": {"5": {"type": "river", "mage": "ada", "name": "home"}}}

    def test_the_row_resolves_to_the_magic_primitive_and_touches_nothing_else(self) -> None:
        mod = self.script()
        reg = self.fresh()
        before = {k: dict(v) for k, v in reg["channels"].items()}
        mod.write_registry(reg, channel_id=77, owner="ada", checkout=str(self.shop))
        self.assertTrue(mod.resolves_to_magic(reg, 77))
        self.assertEqual(reg["channels"]["5"], before["5"])
        self.assertEqual(reg["mages"]["ada"]["workshop"]["checkout"], str(self.shop))
        self.assertEqual(reg["mages"]["bea"], {}, "another member is untouched")

    def test_a_row_that_does_not_resolve_is_seen_as_not_magic(self) -> None:
        mod = self.script()
        reg = self.fresh()
        mod.write_registry(reg, channel_id=77, owner="ada", checkout=str(self.shop))
        reg["channels"]["77"]["primitive"] = "private"
        self.assertFalse(mod.resolves_to_magic(reg, 77), "positive control: the check can fail")

    def test_the_room_belongs_to_the_magic_category_in_the_registry_and_on_discord(self) -> None:
        mod = self.script()
        reg = self.fresh()
        mod.write_registry(reg, channel_id=77, owner="ada", checkout=str(self.shop))
        self.assertEqual(reg["channels"]["77"]["discord_category"], "Magic")

        class Cat:
            def __init__(self, id, name):
                self.id, self.name = id, name

        payload = [{"id": "1", "type": 0, "deny": "1024", "allow": "0"}]
        http = SimpleNamespace(create_channel=AsyncMock(return_value={"id": "555"}))
        client, guild = SimpleNamespace(http=http), SimpleNamespace(id=9)
        with patch.object(sys.modules["discord"], "CategoryChannel", Cat):
            found = asyncio_run(mod.ensure_category(client, guild, [Cat(41, "magic"), Cat(42, "Craft")], payload))
            self.assertEqual(found, 41, "an existing category is found by name, any case")
            http.create_channel.assert_not_awaited()
            made = asyncio_run(mod.ensure_category(client, guild, [Cat(42, "Craft")], payload))
            self.assertEqual(made, 555, "positive control: with no Magic category one is made, never skipped")
            kwargs = http.create_channel.await_args.kwargs
            self.assertEqual(http.create_channel.await_args.args, (9, 4))
            self.assertEqual((kwargs["name"], kwargs["permission_overwrites"]), ("Magic", payload), "as private as the room")

    def test_it_aborts_for_a_stranger_a_missing_checkout_or_a_second_room(self) -> None:
        mod = self.script()
        reg = self.fresh()
        with self.assertRaises(mod.Abort):
            mod.check_ready(reg, "bea", str(self.shop))
        with self.assertRaises(mod.Abort):
            mod.check_ready(reg, "ada", str(self.shop / "missing"))
        with patch.object(mod, "DEFAULT_CHECKOUT", str(self.shop)):
            self.assertEqual(mod.check_ready(reg, "ada", str(self.shop)), 11)
            mod.write_registry(reg, channel_id=77, owner="ada", checkout=str(self.shop))
            with self.assertRaises(mod.Abort):
                mod.check_ready(reg, "ada", str(self.shop))


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
