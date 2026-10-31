"""The workshop tools: offered by room and asker, refused again at the call, confined to the checkout.

A real git checkout and a real bare remote stand in for the house. Every refusal sits beside the
act it must not stop.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import outgoing_connections as door
import tos_tools
import workshop_tools as wt
from channel_primitives import resolve_primitive

ALL = set(wt.NAMES)


def _names(tools) -> set[str]:
    return {(t.get("function") or {}).get("name") or t.get("name") or "" for t in tools}


def git(cwd: Path, *argv: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "nobody", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "nobody"}
    return subprocess.run(["git", "-C", str(cwd), *argv], capture_output=True, text=True, env=env, check=True).stdout


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.remote = base / "house.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        self.shop = base / "workshop"
        self.shop.mkdir()
        git(self.shop, "init", "-q", "-b", "main")
        git(self.shop, "config", "user.name", "t")
        git(self.shop, "config", "user.email", "nobody")
        (self.shop / "desk").mkdir()
        (self.shop / "desk" / "note.md").write_text("alpha\nbeta\ngamma\n")
        (self.shop / "scripts").mkdir()
        (self.shop / "scripts" / "size_budget.py").write_text("print('ok budget')\n")
        git(self.shop, "add", "-A")
        git(self.shop, "commit", "-q", "-m", "first")
        git(self.shop, "remote", "add", wt.REMOTE, str(self.remote))
        git(self.shop, "push", "-q", wt.REMOTE, "main")
        # A nested repository and a folder that holds someone else's record.
        (self.shop / "circles" / "other").mkdir(parents=True)
        git(self.shop / "circles" / "other", "init", "-q")
        (self.shop / "circles" / "other" / "page.md").write_text("their words\n")
        (self.shop / "circles" / "plain.md").write_text("tracked beside\n")
        self.outside = base / "outside.txt"
        self.outside.write_text("SECRET_OUTSIDE\n")
        (self.shop / "link.md").symlink_to(self.outside)

        self.runtime = base / "runtime"
        self.runtime.mkdir()
        self.registry = {
            "mages": {
                "ada": {"workshop": {"repo": str(self.remote), "checkout": str(self.shop)}},
                "bea": {"workshop": {"repo": str(self.remote), "checkout": str(self.shop)}},
            },
            "channels": {
                "1": {"type": "magic", "name": "magic", "mage": "ada"},
                "2": {"type": "river", "name": "home", "mage": "ada"},
                "3": {"type": "craft", "name": "craft", "attunement": "craft", "mage": "ada"},
                "4": {"type": "magic", "name": "magic", "mage": "bea"},
            },
        }
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
        self.addCleanup(door.bind, None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def audit(self) -> list[dict]:
        path = self.runtime / "state" / wt.AUDIT_NAME
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class Offer(Base):
    def test_offered_in_the_owners_magic_room(self) -> None:
        self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, ALL)

    def test_the_primitive_carries_the_capability_and_no_other_room_does(self) -> None:
        self.assertTrue(resolve_primitive(self.registry, "1").has("workshop"))
        for room in ("2", "3"):
            self.assertFalse(resolve_primitive(self.registry, room).has("workshop"), room)

    def test_a_platform_turn_in_the_owners_home_offers_the_workshop(self) -> None:
        self.room["id"] = "2"
        self.assertFalse(wt.offered())
        token = wt.set_platform_turn(True)
        try:
            self.assertTrue(wt.offered())
            self.assertEqual(wt.current_checkout(), self.shop)
            self.assertIn("beta", wt.call("workshop_read", {"path": "desk/note.md"}))
            self.person["who"] = "bea"
            self.assertFalse(wt.offered())
            self.assertIsNone(wt.current_checkout())
            self.assertEqual(wt.call("workshop_read", {"path": "desk/note.md"}), "Not in this room.")
        finally:
            wt.reset_platform_turn(token)
            self.person["who"] = "ada"
        self.assertFalse(wt.offered())

    def test_a_platform_turn_without_a_checkout_offers_nothing(self) -> None:
        self.room["id"] = "2"
        self.registry["mages"]["ada"]["workshop"]["checkout"] = str(Path(self.tmp.name) / "missing")
        token = wt.set_platform_turn(True)
        try:
            self.assertFalse(wt.offered())
        finally:
            wt.reset_platform_turn(token)

    def test_not_in_any_other_room(self) -> None:
        for room in ("2", "3"):
            self.room["id"] = room
            self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, set(), room)

    def test_not_for_someone_else_in_the_room(self) -> None:
        self.person["who"] = "bea"
        self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, set())

    def test_not_in_a_room_that_does_not_belong_to_the_asker_even_if_the_type_is_magic(self) -> None:
        self.room["id"] = "4"
        self.person["who"] = "ada"
        self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, set())

    def test_not_without_a_checkout(self) -> None:
        self.registry["mages"]["ada"]["workshop"]["checkout"] = str(Path(self.tmp.name) / "missing")
        self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, set())

    def test_not_when_the_shell_cannot_name_its_room(self) -> None:
        door.bind(door.Shell(lambda: self.registry, lambda: "ada", lambda: str(self.runtime), lambda: []))
        self.assertEqual(_names(tos_tools.tools_for_attunement("native")) & ALL, set())

    def test_a_call_from_a_room_without_the_tools_is_refused_and_audited(self) -> None:
        self.room["id"] = "2"
        self.assertEqual(wt.call("workshop_read", {"path": "desk/note.md"}), "Not in this room.")
        self.assertEqual(self.audit()[-1]["decision"], "refused")

    def test_dispatch_goes_through_the_door(self) -> None:
        out = tos_tools._execute_tos_tool_raw("workshop_read", {"path": "desk/note.md"})
        self.assertIn("beta", out)


class Reading(Base):
    def test_list_read_and_search_work(self) -> None:
        self.assertIn("desk/", wt.call("workshop_list", {}))
        self.assertNotIn(".git", wt.call("workshop_list", {}))
        self.assertEqual(wt.call("workshop_read", {"path": "desk/note.md", "start_line": 2, "max_lines": 1}), "beta")
        self.assertIn("desk/note.md:3: gamma", wt.call("workshop_search", {"query": "GAMMA"}))

    def test_search_never_reads_inside_dot_git(self) -> None:
        git(self.shop, "tag", "gamma_tag_marker")
        self.assertNotIn(".git", wt.call("workshop_search", {"query": "gamma_tag_marker"}))

    def test_nested_records_may_be_read(self) -> None:
        self.assertIn("their words", wt.call("workshop_read", {"path": "circles/other/page.md"}))

    def test_outside_and_dot_git_are_refused(self) -> None:
        for path in ("../outside.txt", "/etc/hosts", "~/x", ".git/config", "desk/../.git/HEAD", "link.md"):
            out = wt.call("workshop_read", {"path": path})
            self.assertNotIn("SECRET_OUTSIDE", out, path)
            self.assertNotIn("[core]", out, path)
        self.assertEqual(wt.call("workshop_read", {"path": "link.md"}), "That is outside the workshop.")

    def test_a_long_file_is_cut(self) -> None:
        (self.shop / "big.md").write_text("x" * (wt.READ_MAX * 2))
        self.assertLess(len(wt.call("workshop_read", {"path": "big.md"})), wt.READ_MAX + 200)


class Writing(Base):
    def test_write_and_edit_work(self) -> None:
        self.assertIn("Created", wt.call("workshop_write", {"path": "desk/new/page.md", "content": "hello"}))
        self.assertEqual((self.shop / "desk/new/page.md").read_text(), "hello")
        self.assertEqual(wt.call("workshop_edit", {"path": "desk/note.md", "old": "beta", "new": "BETA"}), "Edited desk/note.md.")
        self.assertIn("BETA", (self.shop / "desk/note.md").read_text())

    def test_edit_needs_exactly_one_match(self) -> None:
        (self.shop / "twice.md").write_text("a a")
        self.assertIn("2 times", wt.call("workshop_edit", {"path": "twice.md", "old": "a", "new": "b"}))
        self.assertIn("nowhere", wt.call("workshop_edit", {"path": "twice.md", "old": "zzz", "new": "b"}))
        self.assertEqual((self.shop / "twice.md").read_text(), "a a")

    def test_writes_outside_dot_git_and_nested_repos_are_refused(self) -> None:
        for path in ("../escape.md", "/tmp/escape.md", ".git/hooks/pre-commit", "link.md", "circles/other/page.md", "circles/new.md", "portals/x/y.md"):
            wt.call("workshop_write", {"path": path, "content": "X"})
        self.assertFalse((self.shop.parent / "escape.md").exists())
        self.assertFalse((self.shop / ".git/hooks/pre-commit").exists())
        self.assertEqual(self.outside.read_text(), "SECRET_OUTSIDE\n")
        self.assertEqual((self.shop / "circles/other/page.md").read_text(), "their words\n")
        self.assertFalse((self.shop / "circles/new.md").exists())
        self.assertFalse((self.shop / "portals").exists())

    def test_a_write_in_a_nested_repo_names_why(self) -> None:
        self.assertIn("other people's records", wt.call("workshop_write", {"path": "circles/other/page.md", "content": "X"}))

    def test_too_large_a_write_is_refused(self) -> None:
        self.assertIn("too large", wt.call("workshop_write", {"path": "big.md", "content": "x" * (wt.WRITE_MAX + 1)}))

    def test_a_forge_turn_can_look_and_cannot_change_the_workshop(self) -> None:
        token = wt.set_forge_turn(True)
        try:
            held = wt.call("workshop_write", {"path": "desk/from-forge.md", "content": "no"})
            self.assertEqual(held, wt.FORGE_HELD)
            self.assertFalse((self.shop / "desk/from-forge.md").exists())
            for name in ("workshop_edit", "workshop_git", "workshop_run"):
                self.assertEqual(wt.call(name, {}), wt.FORGE_HELD, name)
        finally:
            wt.reset_forge_turn(token)
        self.assertIn("Created", wt.call("workshop_write", {"path": "desk/from-forge.md", "content": "yes"}))
        self.assertEqual((self.shop / "desk/from-forge.md").read_text(), "yes")


class Keeping(Base):
    def keep(self, **kw):
        return wt.call("workshop_git", kw)

    def test_the_whole_way_on_a_branch(self) -> None:
        self.assertIn("On branch house/port", self.keep(verb="branch", name="house/port"))
        wt.call("workshop_write", {"path": "desk/made.md", "content": "made"})
        self.assertIn("made.md", self.keep(verb="status"))
        self.assertIn("Staged 1", self.keep(verb="add", paths=["desk/made.md"]))
        self.assertIn("a thing", self.keep(verb="commit", message="a thing"))
        self.assertEqual(self.keep(verb="push"), "Pushed house/port to the house.")
        self.assertIn("house/port", git(self.remote, "branch", "--list"))
        self.assertEqual(git(self.remote, "log", "--oneline", "main").count("\n"), 1)  # main untouched

    def test_nothing_is_added_wholesale(self) -> None:
        wt.call("workshop_write", {"path": "desk/stray.md", "content": "s"})
        for args in ({"paths": []}, {"paths": ["."]}, {"paths": ["desk/*"]}, {"paths": ["-A"]}, {"paths": ["circles/other/page.md"]}, {"paths": [".git/config"]}):
            self.keep(verb="add", **args)
        self.assertEqual(git(self.shop, "diff", "--cached", "--name-only").strip(), "")

    def test_a_commit_needs_a_message_and_something_staged(self) -> None:
        self.assertIn("Nothing is staged", self.keep(verb="commit", message="m"))
        wt.call("workshop_write", {"path": "desk/a.md", "content": "a"})
        self.keep(verb="add", paths=["desk/a.md"])
        self.assertIn("needs a message", self.keep(verb="commit", message="  "))

    def test_main_is_not_pushed_until_the_house_is_its_only_writer(self) -> None:
        wt.call("workshop_write", {"path": "desk/a.md", "content": "a"})
        self.keep(verb="add", paths=["desk/a.md"])
        self.keep(verb="commit", message="m")
        before = git(self.remote, "rev-parse", "main").strip()
        self.assertIn("only writer", self.keep(verb="push"))
        self.assertEqual(git(self.remote, "rev-parse", "main").strip(), before)
        self.registry["mages"]["ada"]["workshop"]["main_writable"] = True
        self.assertEqual(self.keep(verb="push"), "Pushed main to the house.")
        self.assertNotEqual(git(self.remote, "rev-parse", "main").strip(), before)

    def test_only_the_houses_remote_is_ever_named(self) -> None:
        self.assertEqual(wt.REMOTE, "turtle")
        git(self.shop, "remote", "add", "elsewhere", str(self.shop.parent / "nowhere.git"))
        self.keep(verb="branch", name="b1")
        wt.call("workshop_write", {"path": "desk/a.md", "content": "a"})
        self.keep(verb="add", paths=["desk/a.md"])
        self.keep(verb="commit", message="m")
        self.keep(verb="push", name="elsewhere", paths=["--force"])
        self.assertIn("b1", git(self.remote, "branch", "--list"))

    def test_branch_names_are_plain_and_not_main(self) -> None:
        for name in ("main", "-d", "a b", "x;y", "", "../x"):
            self.assertNotIn("On branch", self.keep(verb="branch", name=name), name)

    def test_unknown_verbs_do_nothing(self) -> None:
        for verb in ("reset", "rebase", "checkout", "clean", "config", "remote"):
            self.assertIn("not something Spirit does", self.keep(verb=verb))


class Running(Base):
    def test_a_listed_check_runs(self) -> None:
        self.assertIn("ok budget", wt.call("workshop_run", {"name": "size_budget"}))
        self.assertRegex(wt.call("workshop_run", {"name": "date"}), r"20\d\d")

    def test_the_arrivals_two_readers_run_the_scripts_they_name(self) -> None:
        (self.shop / "scripts" / "rot_radar.py").write_text("import sys\nprint('radar', sys.argv[1:])\n")
        (self.shop / "scripts" / "practice_ledger.py").write_text("import sys\nprint('ledger', sys.argv[1:])\n")
        self.assertIn("radar ['--quiet']", wt.call("workshop_run", {"name": "rot_radar"}))
        self.assertIn("ledger ['measures']", wt.call("workshop_run", {"name": "practice_measures"}))

    def test_anything_else_does_not(self) -> None:
        for name in ("rm", "bash -c 'touch /tmp/x'", "size_budget; touch /tmp/x", ""):
            self.assertIn("not one of the workshop's checks", wt.call("workshop_run", {"name": name}))

    def test_the_list_is_short_and_fixed(self) -> None:
        self.assertEqual(
            set(wt.RUNNABLE),
            {"size_budget", "public_surface_check", "publish_dry_run", "date", "rot_radar", "practice_measures"},
        )
        for argv in wt.RUNNABLE.values():
            self.assertFalse(any(ch in " ".join(argv) for ch in "|;&$`"), argv)


class Audit(Base):
    def test_the_audit_holds_acts_and_no_content(self) -> None:
        wt.call("workshop_write", {"path": "desk/x.md", "content": "PLANTED_CONTENT"})
        wt.call("workshop_read", {"path": "desk/x.md"})
        wt.call("workshop_read", {"path": "../outside.txt"})
        rows = self.audit()
        self.assertEqual([r["decision"] for r in rows], ["called", "called", "refused"])
        text = (self.runtime / "state" / wt.AUDIT_NAME).read_text()
        for planted in ("PLANTED_CONTENT", "desk/x.md", "outside.txt"):
            self.assertNotIn(planted, text)

    def test_the_channel_names_the_file_and_never_the_content(self) -> None:
        import turn_trace

        step = turn_trace.describe_tool(
            "workshop_write",
            {"path": "desk/secret-name.md", "content": "PLANTED_CONTENT"},
            "Created desk/secret-name.md",
        )
        self.assertEqual(step.text, "wrote `desk/secret-name.md`")
        self.assertNotIn("PLANTED_CONTENT", step.text)
        read = turn_trace.describe_tool("workshop_read", {"path": "desk/bearings.md"}, "# Bearings\nPLANTED_BODY")
        self.assertEqual(read.text, "read `desk/bearings.md`")
        self.assertNotIn("PLANTED_BODY", read.text)
        found = turn_trace.describe_tool("workshop_search", {"query": "stale dates"}, "desk/x.md:1: hit")
        self.assertEqual(found.text, 'searched for "stale dates"')
        ran = turn_trace.describe_tool("workshop_run", {"name": "rot_radar"}, "ok")
        self.assertEqual(ran.text, "ran `rot_radar`")


class ReadingCheckout(unittest.TestCase):
    def test_a_room_without_the_workshop_capability_can_still_read_the_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            registry = {"mages": {"kermit": {"workshop": {"checkout": str(root)}}}}
            craft = type("Prim", (), {"has": lambda self, name: False})()
            with unittest.mock.patch.object(wt, "_context", return_value=(registry, "1504", "kermit")), \
                    unittest.mock.patch("channel_primitives.resolve_primitive", return_value=craft), \
                    unittest.mock.patch("room_connections.owner_of", return_value="kermit"):
                self.assertIsNone(wt.current_checkout())
                self.assertEqual(wt.reading_checkout(), root)


class ForgeStandsInTheRoom(unittest.TestCase):
    """A forge message is posted by Spirit's account. The workshop is the owner's."""

    def test_the_owner_has_the_workshop_and_a_stranger_does_not(self) -> None:
        import mage
        from outgoing_connections import Shell

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        shop = Path(tmp.name) / "workshop"
        shop.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(shop)], check=True)
        (shop / "readme.md").write_text("the covenant stands here\n")
        registry = {
            "mages": {
                "ada": {
                    "discord_id": "11",
                    "address": "Ada",
                    "practice_dir": str(shop),
                    "workshop": {"checkout": str(shop)},
                }
            },
            "channels": {"1": {"type": "magic", "name": "magic", "mage": "ada"}},
        }
        saved = (
            mage._actor_key_ctx.get(),
            mage._channel_id_ctx.get(),
            mage._mage_key_ctx.get(),
            mage._mage_name_ctx.get(),
            mage._practice_dir_ctx.get(),
            mage._runtime_dir_ctx.get(),
        )
        previous = dict(mage._MAGE_REGISTRY)

        def restore() -> None:
            mage._MAGE_REGISTRY.clear()
            mage._MAGE_REGISTRY.update(previous)
            (
                mage._actor_key_ctx.set(saved[0])
            )
            mage._channel_id_ctx.set(saved[1])
            mage._mage_key_ctx.set(saved[2])
            mage._mage_name_ctx.set(saved[3])
            mage._practice_dir_ctx.set(saved[4])
            mage._runtime_dir_ctx.set(saved[5])

        self.addCleanup(restore)
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(registry)
        door.bind(
            Shell(
                lambda: registry,
                mage.get_actor_key,
                mage.get_runtime_dir,
                lambda: [],
                mage.get_current_channel_id,
            )
        )
        self.addCleanup(door.bind, None)

        def message(content: str, author_id: int = 999):
            author = type("Author", (), {"id": author_id})()
            channel = type("Channel", (), {"id": 50, "parent_id": 1})()
            return type("Message", (), {"author": author, "channel": channel, "content": content})()

        mage.set_practice_context(message("Forge:\nhello from outside"))
        self.assertEqual(mage.get_actor_key(), "ada")
        self.assertEqual(wt.current_checkout(), shop)
        self.assertIn("covenant", wt.call("workshop_read", {"path": "readme.md"}))
        token = wt.set_forge_turn(True)
        try:
            held = wt.call("workshop_write", {"path": "desk/from-forge.md", "content": "no"})
            self.assertEqual(held, wt.FORGE_HELD)
            self.assertFalse((shop / "desk" / "from-forge.md").exists())
        finally:
            wt.reset_forge_turn(token)

        mage.set_practice_context(message("hello"))
        self.assertIsNone(mage.get_actor_key())
        self.assertIsNone(wt.current_checkout())


if __name__ == "__main__":
    unittest.main()
