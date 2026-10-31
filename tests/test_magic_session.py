"""A magic summon stands on the release, continues one open session, and a release that did not write the briefing does not close."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import magic_session as ms
from session_record import append_event


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)


def _init(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True, text=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")


def _commit(path: Path, name: str) -> None:
    file = path / name
    file.write_text(name + "\n", encoding="utf-8")
    _git(path, "add", name)
    _git(path, "commit", "-m", name)


class Decisions(unittest.TestCase):
    def test_only_a_clean_checkout_that_is_behind_moves(self) -> None:
        behind = dict(dirty=False, head="a", main="b", head_contained=True, main_contained=False)
        self.assertEqual(ms.stand_decision(**behind), "move")
        self.assertEqual(ms.stand_decision(**{**behind, "dirty": True}), "wait")
        self.assertEqual(
            ms.stand_decision(dirty=False, head="b", main="b", head_contained=True, main_contained=True),
            "stay",
        )
        self.assertEqual(
            ms.stand_decision(dirty=False, head="c", main="b", head_contained=False, main_contained=True),
            "stay",
            "a clean checkout that already contains main stands",
        )
        self.assertEqual(
            ms.stand_decision(dirty=True, head="c", main="b", head_contained=False, main_contained=True),
            "wait",
            "a dirty checkout waits even when it contains main",
        )
        self.assertEqual(
            ms.stand_decision(dirty=False, head="c", main="b", head_contained=False, main_contained=False),
            "wait",
            "diverged waits",
        )

    def test_the_words_that_are_a_release(self) -> None:
        for words in ("release", "Release.", "let's release here. I will recap.", "@/release now"):
            self.assertTrue(ms.is_release_ask(words), words)
        for words in ("the release is on main", "please send the release notes tomorrow", ""):
            self.assertFalse(ms.is_release_ask(words), words)

    def test_summon_always_opens_and_names_unreleased_spirits(self) -> None:
        """Five open sittings used to refuse the summon. They are company now."""
        five = [
            {"id": i, "name": f"{i} · old", "released": False}
            for i in range(1, 6)
        ]
        choice = ms.pick_session(five)
        self.assertEqual(choice["act"], "open")
        self.assertNotIn("Release one", choice["text"])
        self.assertIn("1 · old", choice["text"])
        self.assertIn("5 · old", choice["text"])
        one = ms.pick_session([
            {"id": 1, "name": "3 · done", "released": True},
            {"id": 2, "name": "5 · still", "greeted": True, "released": False},
        ])
        self.assertEqual(one["act"], "open")
        self.assertIn("5 · still", one["text"])
        self.assertNotIn("3 · done", one["text"])
        archived = ms.pick_session([
            {"id": 1, "name": "3", "released": False, "archived": True},
        ])
        self.assertEqual(archived["act"], "open")
        self.assertEqual(archived["text"], "")

    def test_a_briefing_that_did_not_change_cannot_close(self) -> None:
        events = [{"kind": "greeting", "briefing": "abc"}]
        self.assertFalse(ms.release_can_close(events, "abc"))
        self.assertFalse(ms.release_can_close(events, "missing"))
        self.assertFalse(ms.release_can_close([], "def"))
        self.assertTrue(ms.release_can_close(events, "def"))


class Checkout(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bare = self.root / "bare.git"
        self.shop = self.root / "shop"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.bare)], check=True, capture_output=True)
        _init(self.shop)
        _commit(self.shop, "one")
        _git(self.shop, "remote", "add", "turtle", str(self.bare))
        _git(self.shop, "push", "-u", "turtle", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _ahead(self) -> None:
        other = self.root / "other"
        subprocess.run(["git", "clone", str(self.bare), str(other)], check=True, capture_output=True)
        _git(other, "config", "user.email", "t@example.com")
        _git(other, "config", "user.name", "t")
        _commit(other, "two")
        _git(other, "push", "origin", "main")

    def test_a_clean_room_that_is_behind_moves_to_house_main(self) -> None:
        self._ahead()
        note = ms.apply_stand(self.shop)
        self.assertEqual(note, "")
        head = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        main = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "turtle/main"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(head, main)
        self.assertTrue((self.shop / "two").is_file())

    def test_a_dirty_room_waits_and_stays_where_it_is(self) -> None:
        self._ahead()
        (self.shop / "scratch").write_text("x", encoding="utf-8")
        before = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        note = ms.apply_stand(self.shop)
        self.assertIn("The room waited.", note)
        after = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(before, after)
        self.assertFalse((self.shop / "two").is_file())

    def test_a_branch_with_its_own_commit_is_not_moved(self) -> None:
        self._ahead()
        _git(self.shop, "checkout", "-b", "magic-port-writepath")
        _commit(self.shop, "checklist")
        note = ms.apply_stand(self.shop)
        self.assertIn("The room waited.", note)
        branch = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(branch, "magic-port-writepath")
        self.assertTrue((self.shop / "checklist").is_file())
        self.assertFalse((self.shop / "two").is_file())

    def test_a_branch_that_contains_main_stands_and_is_not_moved(self) -> None:
        _git(self.shop, "checkout", "-b", "magic-port-writepath")
        _commit(self.shop, "checklist")
        note = ms.apply_stand(self.shop)
        self.assertEqual(note, "")
        branch = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(branch, "magic-port-writepath")
        self.assertTrue((self.shop / "checklist").is_file())

    def test_a_dirty_branch_that_contains_main_still_waits(self) -> None:
        _git(self.shop, "checkout", "-b", "magic-port-writepath")
        _commit(self.shop, "checklist")
        (self.shop / "scratch").write_text("x", encoding="utf-8")
        note = ms.apply_stand(self.shop)
        self.assertIn("The room waited.", note)
        branch = subprocess.run(
            ["git", "-C", str(self.shop), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(branch, "magic-port-writepath")


class Close(unittest.IsolatedAsyncioTestCase):
    async def test_an_unchanged_briefing_does_not_archive_and_a_changed_one_does(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        practice = root / "practice"
        practice.mkdir()
        shop = root / "shop"
        briefing = shop / ms.BRIEFING
        briefing.parent.mkdir(parents=True)
        briefing.write_text("old\n", encoding="utf-8")
        opened = ms.briefing_digest(briefing)
        append_event(practice, 9, kind="greeting", actor="river", text="hello", briefing=opened)
        channel = MagicMock()
        channel.id = 9
        channel.edit = AsyncMock()
        with patch("spirit_voice.say", new=AsyncMock()) as say:
            held = await ms.finish_release(channel, practice, shop)
        self.assertEqual(held, "hold")
        channel.edit.assert_not_awaited()
        say.assert_awaited()
        self.assertIn(ms.HELD, say.await_args.args)

        briefing.write_text("new\n", encoding="utf-8")
        channel.edit = AsyncMock()
        closed = await ms.finish_release(channel, practice, shop)
        self.assertEqual(closed, "close")
        channel.edit.assert_awaited_once()
        tmp.cleanup()


class Wired(unittest.TestCase):
    def test_summon_resume_stand_trace_and_spirit_are_called(self) -> None:
        root = Path(__file__).resolve().parents[1]
        handler = (root / "river_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("_resume_open_session", handler)
        self.assertNotIn("Release one before a new summon", handler)
        self.assertIn("_workshop_company", handler)
        self.assertIn("apply_stand(root)", handler)
        self.assertIn("river_add_spirit_to_eddy", handler)
        turn = (root / "dialogue_turn.py").read_text(encoding="utf-8")
        self.assertIn("def _record_magic_trace(", turn)
        self.assertIn("_record_magic_trace(", turn)
        self.assertIn("finish_release(", turn)
        bot = (root / "river_bot.py").read_text(encoding="utf-8")
        self.assertIn("river_add_spirit_to_eddy", bot)


if __name__ == "__main__":
    unittest.main()
